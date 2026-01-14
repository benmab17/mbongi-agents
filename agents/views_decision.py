from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.http import HttpResponseForbidden

from .models import Contribution, AuditLog, Decision # Import de Decision
from .security import chef_required
from agents.views import get_my_agent # Importation de get_my_agent

@chef_required
@require_POST
def contribution_decide(request, pk: int):
    """
    Chef : Valider / Rejeter une contribution.
    - action=validate  => VALIDATED + log + création Décision
    - action=reject    => REJECTED + log + création Décision
    """
    c = get_object_or_404(Contribution, pk=pk)

    action = request.POST.get("action", "").strip().lower()
    note = (request.POST.get("note", "") or "").strip()
    
    if action == "validate":
        c.statut = "VALIDATED"
        c.validated_by = request.user
        c.validated_at = timezone.now()
        c.decision_note = note
        c.save()

        # Créer une Décision
        Decision.objects.create(
            title=f"Décision sur contribution '{c.titre}'",
            decision_type='OPERATIONNEL',
            level='CHEF',
            contribution=c,
            decision='VALIDEE',
            comment=note,
            created_by=request.user,
        )
        AuditLog.objects.create(
            user=request.user,
            action="CREATE_DECISION",
            target_repr=f"Décision VALIDÉE sur Contribution {c.id}: '{c.titre}'",
            ip_address=request.META.get("REMOTE_ADDR"),
        )

    elif action == "reject":
        c.statut = "REJECTED"
        c.validated_by = request.user
        c.validated_at = timezone.now()
        c.decision_note = note
        c.save()

        # Créer une Décision (Refusée)
        Decision.objects.create(
            title=f"Décision sur contribution '{c.titre}'",
            decision_type='OPERATIONNEL',
            level='CHEF',
            contribution=c,
            decision='REFUSEE',
            comment=note,
            created_by=request.user,
        )
        AuditLog.objects.create(
            user=request.user,
            action="CREATE_DECISION",
            target_repr=f"Décision REFUSÉE sur Contribution {c.id}: '{c.titre}'",
            ip_address=request.META.get("REMOTE_ADDR"),
        )

    # Retour sur la team en gardant l'agent sélectionné
    agent_id = c.agent_id
    return redirect(f"/agents/team/?a={agent_id}")


@chef_required
def contribution_review_view(request, pk: int):
    """
    Affiche une page de revue détaillée pour une contribution,
    avec possibilité de Valider/Refuser.
    """
    contribution = get_object_or_404(Contribution.objects.select_related('agent__service'), pk=pk)
    
    # Les superusers ont toujours accès à tout
    if request.user.is_superuser:
        pass # Accès autorisé
    else:
        chef_agent_profile = get_my_agent(request)

        # Si chef_agent_profile est manquant pour un chef (non-superuser),
        # ou si le service de la contribution ne correspond pas à celui du chef, refuser l'accès.
        if not chef_agent_profile or \
           contribution.agent.service != chef_agent_profile.service:
            return HttpResponseForbidden("Accès non autorisé à cette ressource (profil agent chef manquant ou service non correspondant).")

    # Dans ce template, le formulaire de décision sera intégré
    # et postera vers contribution_decide
    return render(
        request,
        "agents/contribution_review.html", # Template déjà existant
        {"contribution": contribution}
    )


@chef_required
def decision_list_view(request):
    """
    Affiche la liste chronologique de toutes les décisions prises.
    Accessible uniquement aux Chefs et à la Présidence.
    """
    decisions = Decision.objects.all().select_related('contribution__agent', 'created_by').order_by('-created_at')

    # Si l'utilisateur est un chef de service, il ne voit que les décisions de son service
    if not request.user.is_superuser and hasattr(request.user, 'agent_profile'):
        chef_service = request.user.agent_profile.service
        decisions = decisions.filter(contribution__agent__service=chef_service)

    return render(request, "agents/decisions/decision_list.html", {"decisions": decisions})
