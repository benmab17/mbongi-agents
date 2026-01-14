from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Case, When, F, Value, BooleanField
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.urls import NoReverseMatch, reverse

from .models import Agent, Contribution, AuditLog, Mission, RecoupementTicket, AgentStatus, MicroTask, MicroMission, Service, ContributionShare, CNSAvis
from .ai import resume_contribution
from .forms import (
    ContributionForm,
    AgentPhotoForm,
    ContributionShareForm,
    DGMAnomalyForm,
    EmbassyDiplomaticReportForm,
    DGMWatchlistForm,
    AgentProposeMicroMissionForm,
    ChefCreateMicroMissionForm,
    CNSAvisForm,
)
from .security import is_chef_service, chef_required, is_cns
from .utils import compute_agent_score


def staff_required(view):
    return user_passes_test(lambda u: u.is_authenticated and u.is_staff)(view)


@login_required
def contribution_new(request):
    agent = get_my_agent(request)
    if not agent:
        return redirect("dashboard")

    if request.method == "POST":
        form = ContributionForm(request.POST)
        if form.is_valid():
            c = form.save(commit=False)
            c.agent = agent
            c.statut = "SUBMITTED"  # soumise par défaut (on ajustera plus tard si besoin)
            c.save()
            return redirect("dashboard")
    else:
        form = ContributionForm()

    return render(request, "agents/contribution_new.html", {"form": form})


@login_required
def ai_resume_contribution(request, pk: int):
    """
    Résumé IA d'une contribution.
    - Agent: seulement ses propres contributions
    - Chef: peut résumer celles des agents de son service
    """
    me = getattr(request.user, "agent_profile", None)
    if not me:
        return HttpResponseForbidden("Profil agent manquant.")

    contrib = get_object_or_404(Contribution, pk=pk)

    # Agent normal => uniquement ses contributions
    if not is_chef_service(request.user):
        if contrib.agent_id != me.id:
            return HttpResponseForbidden("Accès interdit.")
    else:
        # Chef => uniquement même service
        if contrib.agent.service_id != me.service_id:
            return HttpResponseForbidden("Accès interdit (service).")

    try:
        text = resume_contribution(contrib.titre, contrib.contenu)
        return JsonResponse({"ok": True, "resume": text})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)

@login_required
def agent_profile(request):
    """
    Dossier agent :
    - Agent: /agents/profile/ => voit son propre dossier
    - Chef: /agents/profile/?a=<id> => voit le dossier d'un agent de son service
    """
    me = get_my_agent(request)
    if not me:
        # si aucun profil lié, on renvoie vers dashboard avec message simple
        return redirect("dashboard")

    agent_id = request.GET.get("a") or request.GET.get("agent")

    # Chef peut demander ?a=<id>
    if agent_id and is_chef_service(request.user):
        target = get_object_or_404(Agent.objects.select_related("service"), pk=agent_id)

        # sécurité : chef voit uniquement les agents de son service
        if target.service_id != me.service_id:
            return HttpResponseForbidden("Accès interdit (service).")

        agent = target
        staff_view = True
    else:
        # Agent normal (ou chef sans paramètre) => son propre dossier
        agent = me
        staff_view = False

    qs = Contribution.objects.filter(agent=agent)
    missions = agent.missions.all()
    score = compute_agent_score(agent)

    stats = {
        "total": qs.count(),
        "validated": qs.filter(statut="VALIDATED").count(),
        "submitted": qs.filter(statut="SUBMITTED").count(),
        "draft": qs.filter(statut="DRAFT").count(),
    }
    last = qs.order_by("-date_creation")[:10]

    return render(
        request,
        "agents/agent_dossier.html",
        {
            "agent": agent,
            "stats": stats,
            "last": last,
            "missions": missions,
            "score": score,
            "staff_view": staff_view,
            "is_chef_service": is_chef_service(request.user),
        },
    )


@login_required
def list_shared_contributions_view(request):
    me = get_my_agent(request)
    if not me:
        return HttpResponseForbidden("Profil agent manquant.")

    shares = ContributionShare.objects.select_related("contribution").filter(
        service_destinataire=me.service
    )
    return render(
        request,
        "agents/shared_contributions.html",
        {"shares": shares},
    )


@login_required
def share_contribution_view(request, pk: int):
    me = get_my_agent(request)
    if not me:
        return HttpResponseForbidden("Profil agent manquant.")

    contribution = get_object_or_404(Contribution, pk=pk)
    if contribution.statut != "VALIDATED":
        return HttpResponseForbidden("Contribution non validée.")

    services = Service.objects.order_by("nom")

    if request.method == "POST":
        service_id = request.POST.get("service_destinataire")
        motif = (request.POST.get("motif") or "").strip()
        if not service_id:
            return HttpResponse("Service destinataire requis.", status=400)

        service_destinataire = get_object_or_404(Service, pk=service_id)
        ContributionShare.objects.create(
            contribution=contribution,
            service_source=me.service,
            service_destinataire=service_destinataire,
            shared_by=request.user,
            motif=motif,
        )
        AuditLog.objects.create(
            user=request.user,
            action="CONTRIBUTION_SHARED",
            target_repr=f"Contribution {contribution.id} partagée vers {service_destinataire.nom}",
        )
        return redirect("/agents/shared/")

    try:
        back_url = reverse("agent_profile")
    except NoReverseMatch:
        back_url = "/agents/ui/agent-dossier/"

    return render(
        request,
        "agents/share_contribution.html",
        {
            "contribution": contribution,
            "services": services,
            "back_url": back_url,
        },
    )


@login_required
def dgm_renseignement_view(request):
    me = get_my_agent(request)
    if not me or me.service.nom != "DGM":
        return HttpResponseForbidden("Accès interdit.")

    if request.method == "POST":
        form = DGMAnomalyForm(request.POST)
        if form.is_valid():
            anomaly_type = form.cleaned_data["anomaly_type"]
            location = form.cleaned_data["location"]
            description = form.cleaned_data["description"]
            urgency = form.cleaned_data["urgency"]
            Contribution.objects.create(
                agent=me,
                titre=f"Alerte DGM – {anomaly_type}",
                contenu=f"[DGM-ALERTE]\\nLieu: {location}\\nUrgence: {urgency}\\n\\n{description}",
                statut="VALIDATED",
            )
            return redirect("agent_dossier_ui")
    else:
        form = DGMAnomalyForm()

    return render(
        request,
        "agents/dgm_renseignement.html",
        {"form": form},
    )


@login_required
def ambassade_renseignement_view(request):
    me = get_my_agent(request)
    if not me or not me.service.nom.startswith("Ambassade"):
        return HttpResponseForbidden("Accès interdit.")

    if request.method == "POST":
        form = EmbassyDiplomaticReportForm(request.POST)
        if form.is_valid():
            report_type = form.cleaned_data["report_type"]
            country_city = form.cleaned_data["country_city"]
            description = form.cleaned_data["description"]
            urgency = form.cleaned_data["urgency"]
            Contribution.objects.create(
                agent=me,
                titre=f"Alerte DIPLO – {report_type}",
                contenu=(
                    "[DIPLO-ALERTE]\n"
                    f"Pays / Ville: {country_city}\n"
                    f"Urgence: {urgency}\n\n"
                    f"{description}"
                ),
                statut="VALIDATED",
            )
            return redirect("agent_profile")
    else:
        form = EmbassyDiplomaticReportForm()

    return render(
        request,
        "agents/ambassade_renseignement.html",
        {"form": form},
    )


@login_required
def dgm_surveillance_view(request):
    me = get_my_agent(request)
    if not me or me.service.nom != "DGM":
        return HttpResponseForbidden("Accès interdit.")

    if request.method == "POST":
        form = DGMWatchlistForm(request.POST)
        if form.is_valid():
            identity_hint = form.cleaned_data["identity_hint"].strip() or "Inconnu"
            border_post = form.cleaned_data["border_post"]
            reason = form.cleaned_data["reason"]
            risk_level = form.cleaned_data["risk_level"]
            optional_notes = form.cleaned_data["optional_notes"]
            notes_block = f"\n\nNotes: {optional_notes}" if optional_notes else ""
            Contribution.objects.create(
                agent=me,
                titre=f"Profil à surveiller – {identity_hint}",
                contenu=(
                    "[DGM-SURVEILLANCE]\n"
                    f"Poste / Lieu: {border_post}\n"
                    f"Niveau de risque: {risk_level}\n\n"
                    f"{reason}{notes_block}"
                ),
                statut="VALIDATED",
            )
            return redirect("agent_profile")
    else:
        form = DGMWatchlistForm()

    return render(
        request,
        "agents/dgm_surveillance.html",
        {"form": form},
    )


@login_required
def cns_dashboard_view(request):
    if not is_cns(request.user):
        return HttpResponseForbidden("Accès interdit.")
    return render(
        request,
        "agents/cns_dashboard.html",
        {"is_cns": True},
    )


@login_required
def cns_avis_list_view(request):
    if not is_cns(request.user):
        return HttpResponseForbidden("Accès interdit.")
    avis_list = CNSAvis.objects.all()[:20]
    return render(
        request,
        "agents/cns_avis_list.html",
        {"avis_list": avis_list},
    )


@login_required
def cns_avis_create_view(request):
    if not is_cns(request.user):
        return HttpResponseForbidden("Accès interdit.")
    if request.method == "POST":
        form = CNSAvisForm(request.POST)
        if form.is_valid():
            avis = form.save(commit=False)
            avis.created_by = request.user
            # Préparation du flux stratégique CNS → Présidence.
            avis.status = "SENT"
            # Timestamp de transmission CNS → Présidence.
            if avis.sent_at is None:
                avis.sent_at = timezone.now()
            avis.save()
            # Audit transmission CNS → Présidence.
            AuditLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                action="TRANSMIT",
                target_repr=f"CNSAvis #{avis.id} - {avis.title}",
                ip_address=request.META.get("REMOTE_ADDR"),
            )
            messages.success(request, "Avis CNS transmis.")
            return redirect("cns_dashboard")
    else:
        form = CNSAvisForm()

    return render(
        request,
        "agents/cns_avis_form.html",
        {"form": form},
    )


@staff_required
def staff_agent_detail(request, pk: int):
    """
    Vue staff Django (is_staff) hors /admin.
    """
    agent = get_object_or_404(Agent, pk=pk)
    qs = Contribution.objects.filter(agent=agent)

    stats = {
        "total": qs.count(),
        "validated": qs.filter(statut="VALIDATED").count(),
        "submitted": qs.filter(statut="SUBMITTED").count(),
        "draft": qs.filter(statut="DRAFT").count(),
    }
    last = qs.order_by("-date_creation")[:10]

    return render(
        request,
        "agents/agent_dossier.html",
        {
            "agent": agent,
            "stats": stats,
            "last": last,
            "staff_view": True,
            "is_chef_service": is_chef_service(request.user),
        },
    )


@login_required
def agent_photo_upload(request):
    agent = get_object_or_404(Agent, user=request.user)

    if request.method == "POST":
        form = AgentPhotoForm(request.POST, request.FILES, instance=agent)
        if form.is_valid():
            form.save()
            return redirect("agent_profile")
    else:
        form = AgentPhotoForm(instance=agent)

    return render(request, "agents/agent_photo_upload.html", {"form": form, "agent": agent})

def get_my_agent(request):
    # Ne dépend pas du related_name (agent_profile / agent / autre)
    return Agent.objects.select_related("service").filter(user=request.user).first()


@login_required
def agent_console_view(request):
    """
    Console Agent Active (A8) - Vue minimale.
    """
    # Vérifie que l'utilisateur a un profil Agent
    if not hasattr(request.user, 'agent') or not request.user.agent.actif:
        return HttpResponseForbidden("Accès refusé : Profil agent non trouvé ou inactif.")

    # Récupérer ou créer le statut de l'agent
    agent_status, created = AgentStatus.objects.get_or_create(user=request.user)

    # Micro-missions
    suggested_microtask = None
    claimed_microtasks = None
    current_agent = get_my_agent(request)
    if not current_agent:
        return HttpResponseForbidden("Accès refusé : Profil agent non trouvé.")

    micro_proposed = MicroMission.objects.filter(agent=current_agent.user, status="PROPOSED").order_by("-created_at")[:5]
    micro_todo = MicroMission.objects.filter(agent=current_agent.user, status="TODO").order_by("-created_at")
    micro_in_progress = MicroMission.objects.filter(agent=current_agent.user, status="IN_PROGRESS").order_by("-created_at")
    micro_done = MicroMission.objects.filter(agent=current_agent.user, status="DONE").order_by("-created_at")[:5]

    if agent_status.status == 'PATROL':
        # Find a suggested micro-task (OPEN and not claimed by anyone)
        suggested_microtask = MicroTask.objects.filter(status='OPEN', claimed_by__isnull=True).order_by('?').first() # order_by('?') for random

        # Find micro-tasks claimed by the current agent and in progress
        claimed_microtasks = MicroTask.objects.filter(claimed_by=request.user, status='CLAIMED')

    context = {
        "title": "Console Agent Active (A8)",
        "message": "Console Agent prête – fonctionnalités en cours d’activation",
        "agent_current_status": agent_status.get_status_display(),
        "is_patrolling": agent_status.status == 'PATROL',
        "last_status_update": agent_status.updated_at,
        "suggested_microtask": suggested_microtask,
        "claimed_microtasks": claimed_microtasks,
        "micro_proposed": micro_proposed,
        "micro_todo": micro_todo,
        "micro_in_progress": micro_in_progress,
        "micro_done": micro_done,
    }
    return render(request, 'agents/agent_console.html', context)


@login_required
def propose_micro_mission(request):
    if request.method != "POST":
        return redirect("agent_console")

    agent = get_my_agent(request)
    if not agent:
        return HttpResponseForbidden("Accès refusé : Profil agent non trouvé.")

    form = AgentProposeMicroMissionForm(request.POST)
    if form.is_valid():
        MicroMission.objects.create(
            agent=agent.user,
            title=form.cleaned_data["title"],
            description=form.cleaned_data["description"],
            status="PROPOSED",
        )
    return redirect("agent_console")


@chef_required
def chef_create_micro_mission_view(request):
    chef_agent = get_object_or_404(Agent.objects.select_related("service"), user=request.user)

    if request.method == "POST":
        form = ChefCreateMicroMissionForm(request.POST, service=chef_agent.service)
        if form.is_valid():
            selected_agent = form.cleaned_data["agent"]
            MicroMission.objects.create(
                agent=selected_agent.user,
                title=form.cleaned_data["title"],
                description=form.cleaned_data["description"],
                status="TODO",
            )
            return redirect("chef_commandement")
    else:
        form = ChefCreateMicroMissionForm(service=chef_agent.service)

    return render(
        request,
        "agents/chef_micro_mission_create.html",
        {"form": form},
    )


@require_POST
@login_required
def start_patrol_view(request):
    """
    Démarre une patrouille pour l'agent connecté.
    """
    if not hasattr(request.user, 'agent_status'):
        AgentStatus.objects.create(user=request.user) # Créer le statut si inexistant

    agent_status = request.user.agent_status
    if agent_status.status != 'PATROL':
        agent_status.status = 'PATROL'
        agent_status.last_activity_at = timezone.now()
        agent_status.save()
        AuditLog.objects.create(
            user=request.user,
            action="AGENT_STATUS_CHANGE", # Utilisation de l'action correcte
            target_repr=f"Agent {request.user.username} a démarré une patrouille."
        )
        messages.success(request, "Patrouille démarrée.")
    else:
        messages.info(request, "Vous êtes déjà en patrouille.")

    return redirect('agent_console')


@require_POST
@login_required
def end_patrol_view(request):
    """
    Termine la patrouille pour l'agent connecté.
    """
    if not hasattr(request.user, 'agent_status'):
        AgentStatus.objects.create(user=request.user) # Créer le statut si inexistant

    agent_status = request.user.agent_status
    if agent_status.status == 'PATROL':
        agent_status.status = 'AVAILABLE'
        agent_status.last_activity_at = timezone.now()
        agent_status.save()
        AuditLog.objects.create(
            user=request.user,
            action="AGENT_STATUS_CHANGE", # Utilisation de l'action correcte
            target_repr=f"Agent {request.user.username} a terminé sa patrouille."
        )
        messages.success(request, "Patrouille terminée.")
    else:
        messages.info(request, "Vous n'êtes pas en patrouille.")
        
    return redirect('agent_console')


@require_POST
@login_required
def accept_microtask_view(request, pk):
    """
    Permet à un agent de prendre en charge une micro-tâche.
    """
    if not hasattr(request.user, 'agent') or not request.user.agent.actif:
        return HttpResponseForbidden("Accès refusé : Profil agent non trouvé ou inactif.")

    agent_status, created = AgentStatus.objects.get_or_create(user=request.user)
    if agent_status.status != 'PATROL':
        messages.warning(request, "Vous devez être en patrouille pour accepter des micro-tâches.")
        return redirect('agent_console')

    microtask = get_object_or_404(MicroTask, pk=pk)

    if microtask.status == 'OPEN':
        microtask.status = 'CLAIMED'
        microtask.claimed_by = request.user
        microtask.claimed_at = timezone.now()
        microtask.save()
        AuditLog.objects.create(
            user=request.user,
            action="MICROTASK_CLAIMED",
            target_repr=f"Micro-tâche #{microtask.id}: {microtask.title} prise en charge."
        )
        messages.success(request, f"Micro-tâche '{microtask.title}' prise en charge.")
    else:
        messages.info(request, "Cette micro-tâche n'est plus disponible ou est déjà prise.")

    return redirect('agent_console')


@require_POST
@login_required
def complete_microtask_view(request, pk):
    """
    Permet à un agent de marquer une micro-tâche comme terminée.
    """
    if not hasattr(request.user, 'agent') or not request.user.agent.actif:
        return HttpResponseForbidden("Accès refusé : Profil agent non trouvé ou inactif.")

    agent_status, created = AgentStatus.objects.get_or_create(user=request.user)
    if agent_status.status != 'PATROL':
        messages.warning(request, "Vous devez être en patrouille pour terminer des micro-tâches.")
        return redirect('agent_console')

    microtask = get_object_or_404(MicroTask, pk=pk, claimed_by=request.user, status='CLAIMED')

    if microtask:
        microtask.status = 'DONE'
        microtask.completed_at = timezone.now()
        microtask.save()
        AuditLog.objects.create(
            user=request.user,
            action="MICROTASK_COMPLETED",
            target_repr=f"Micro-tâche #{microtask.id}: {microtask.title} terminée."
        )
        messages.success(request, f"Micro-tâche '{microtask.title}' terminée.")
    else:
        messages.error(request, "Micro-tâche non trouvée ou non assignée à vous, ou déjà terminée.")

    return redirect('agent_console')

