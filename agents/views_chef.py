from datetime import timedelta
from django.utils import timezone
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Count, Q
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.views.decorators.http import require_POST

from django.contrib.auth import get_user_model # Importation du modèle User
from agents.models import Agent, Contribution, Mission, AuditLog, RecoupementTicket
from agents.security import chef_required
from agents.utils import compute_agent_score # Pour le calcul du score global moyen
from agents.services import get_weak_signals


@chef_required
def chef_commandement_view(request):
    """
    Vue de commandement tactique pour les chefs de service.
    Affiche un tableau de bord consolidé pour la supervision tactique.
    """
    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)
    
    chef_agent_profile = get_object_or_404(Agent.objects.select_related('service'), user=request.user)
    service_agents = Agent.objects.filter(service=chef_agent_profile.service)


    # --- 1) Tableau tactique (KPIs) ---
    kpis = {
        # Contributions
        "contrib_submitted_24h": Contribution.objects.filter(agent__in=service_agents, statut="SUBMITTED", date_creation__gte=last_24h).count(),
        "contrib_validated_24h": Contribution.objects.filter(agent__in=service_agents, statut="VALIDATED", date_creation__gte=last_24h).count(),
        "contrib_rejected_24h": Contribution.objects.filter(agent__in=service_agents, statut="REJECTED", validated_at__gte=last_24h).count(),
        "total_contrib_submitted": Contribution.objects.filter(agent__in=service_agents, statut="SUBMITTED").count(),
        
        # Missions
        "missions_total": Mission.objects.filter(agent_assigned__in=service_agents).count(),
        "missions_in_progress": Mission.objects.filter(agent_assigned__in=service_agents, status="IN_PROGRESS").count(),
        "missions_pending": Mission.objects.filter(agent_assigned__in=service_agents, status="PENDING").count(),
        "missions_failed_7d": Mission.objects.filter(agent_assigned__in=service_agents, status="FAILED", completed_at__gte=last_7d).count(),
        "missions_completed_7d": Mission.objects.filter(agent_assigned__in=service_agents, status="COMPLETED", completed_at__gte=last_7d).count(),

        # Sécurité / Audit
        "audit_critical_events_24h": AuditLog.objects.filter(
            Q(user__in=[request.user]), # Logué par le chef
            Q(action__in=['LOGIN', 'REJECT_CONTRIBUTION', 'UPDATE_MISSION']), # Actions critiques pour démo
            timestamp__gte=last_24h
        ).count(),
        "global_service_score_avg": 0, # Calculé après pour éviter double itération
    }

    # Calcul du score moyen du service
    if service_agents.exists():
        service_scores = [compute_agent_score(agent) for agent in service_agents]
        kpis["global_service_score_avg"] = round(sum(service_scores) / len(service_scores))


    # --- 2) Missions prioritaires (top 5 non complétées) ---
    priority_missions = Mission.objects.filter(
        agent_assigned__in=service_agents,
        status__in=['PENDING', 'IN_PROGRESS', 'FAILED']
    ).order_by('-priority', 'due_date')[:5]


    # --- 3) File de validation contributions (top 5 soumises) ---
    validation_queue = Contribution.objects.filter(
        agent__in=service_agents,
        statut='SUBMITTED'
    ).order_by('priorite', 'date_creation')[:5]


    # --- 4) Journal de commandement (AuditLog du service) ---
    User = get_user_model() # Assure que User est défini ici
    command_journal = AuditLog.objects.filter(
        Q(user__in=User.objects.filter(agent__in=service_agents)) | Q(user=request.user), # Logs des agents du service ou du chef
        timestamp__gte=now - timedelta(hours=48)
    ).order_by('-timestamp')[:10]


    # --- 5) File de recoupement (tickets ouverts/en cours) ---
    recoupement_queue = RecoupementTicket.objects.filter(
        created_by=request.user,
        status__in=['OPEN', 'IN_PROGRESS']
    ).order_by('status', '-created_at')
    
    overdue_count = sum(1 for ticket in recoupement_queue if ticket.is_overdue)


    # --- 6) Signaux faibles (pour création de recoupements) ---
    weak_signals = get_weak_signals(72, 5)


    context = {
        "last_update": now,
        "chef_agent_profile": chef_agent_profile,
        "kpis": kpis,
        "priority_missions": priority_missions,
        "validation_queue": validation_queue,
        "command_journal": command_journal,
        "recoupement_queue": recoupement_queue[:10], # Limiter après comptage
        "overdue_count": overdue_count,
        "weak_signals": weak_signals,
    }
    return render(request, 'agents/chef_commandement.html', context)


@require_POST
@chef_required
def create_recoupement_ticket(request):
    """
    Crée un ticket de recoupement, l'assigne automatiquement à 2 agents
    et définit une date limite.
    """
    try:
        level = request.POST['level']
        if level == 'GREEN':
            messages.warning(request, "Les signaux de niveau GREEN ne justifient pas un recoupement.")
            return redirect('chef_commandement')

        # Définition du délai
        now = timezone.now()
        if level in ['RED', 'ORANGE']:
            due_at = now + timedelta(hours=24)
        else: # YELLOW
            due_at = now + timedelta(hours=48)

        ticket = RecoupementTicket.objects.create(
            created_by=request.user,
            level=level,
            title=request.POST['title'],
            evidence=request.POST['evidence'],
            keywords=request.POST.get('keywords', ''),
            window_hours=request.POST.get('window_hours', 72),
            source='weak_signals',
            due_at=due_at
        )
        
        # Log de la création
        AuditLog.objects.create(user=request.user, action="CHEF_CREATE_RECOUPEMENT", target_repr=f"Ticket #{ticket.id}: {ticket.title}")

        # Logique d'assignation automatique
        try:
            chef_service = request.user.agent.service
            # Agents du même service, excluant le chef lui-même, et qui sont des utilisateurs actifs
            available_agents = User.objects.filter(
                agent__service=chef_service,
                agent__actif=True,
                is_staff=False, # Exclure les superusers/staff si nécessaire
            ).exclude(pk=request.user.pk).annotate(
                open_tickets=Count('assigned_recoupements', filter=Q(assigned_recoupements__status='OPEN'))
            ).order_by('open_tickets')[:2]

            if available_agents:
                ticket.assigned_agents.set(available_agents)
                agent_names = ", ".join([a.username for a in available_agents])
                AuditLog.objects.create(user=request.user, action="CHEF_ASSIGN_RECOUPEMENT", target_repr=f"Ticket #{ticket.id} assigné à {agent_names}")
                messages.success(request, f"Ticket #{ticket.id} créé et assigné à {agent_names}.")
            else:
                messages.warning(request, f"Ticket #{ticket.id} créé, mais aucun agent disponible pour assignation automatique.")

        except Agent.DoesNotExist:
             messages.error(request, "Votre profil agent n'est pas correctement configuré pour trouver votre service.")
        
    except Exception as e:
        messages.error(request, f"Erreur lors de la création du ticket : {e}")

    return redirect('chef_commandement')


@require_POST
@chef_required
def take_recoupement_ticket(request, pk):
    """ Passe le statut d'un ticket à 'En cours' (pris par le chef). """
    ticket = get_object_or_404(RecoupementTicket, pk=pk)
    ticket.status = 'IN_PROGRESS'
    ticket.taken_by = request.user
    ticket.save()

    AuditLog.objects.create(user=request.user, action="CHEF_TAKE_RECOUPEMENT", target_repr=f"Ticket #{ticket.id}: {ticket.title}")
    messages.info(request, f"Vous avez pris en charge le ticket #{ticket.id} pour analyse.")
    return redirect('chef_commandement')


@require_POST
@chef_required
def close_recoupement_ticket(request, pk):
    """ Passe le statut d'un ticket à 'Clôturé'. """
    ticket = get_object_or_404(RecoupementTicket, pk=pk)
    # On vérifie que le chef est bien le créateur ou celui qui l'a pris en charge
    if ticket.created_by != request.user and ticket.taken_by != request.user:
        return HttpResponseForbidden("Vous n'êtes pas autorisé à clôturer ce ticket.")

    ticket.status = 'CLOSED'
    ticket.save()
    
    AuditLog.objects.create(user=request.user, action="CHEF_CLOSE_RECOUPEMENT", target_repr=f"Ticket #{ticket.id}: {ticket.title}")
    messages.success(request, f"Le ticket #{ticket.id} a été clôturé.")
    return redirect('chef_commandement')


@chef_required
def view_recoupement_ticket(request, pk):
    """ Affiche les détails d'un ticket de recoupement et ses réponses. """
    try:
        # Le chef peut voir tous les tickets qu'il a créés
        ticket = RecoupementTicket.objects.prefetch_related('responses__author__agent').get(pk=pk, created_by=request.user)
    except RecoupementTicket.DoesNotExist:
        return HttpResponseForbidden("Ticket non trouvé ou accès non autorisé.")

    context = {
        'ticket': ticket,
    }
    return render(request, 'agents/chef/recoupement_detail.html', context)


@require_POST
@chef_required
def escalate_recoupement_to_mission(request, pk):
    """
    Escalade un ticket de recoupement en une mission.
    """
    ticket = get_object_or_404(RecoupementTicket, pk=pk)

    if ticket.status == 'CLOSED':
        messages.error(request, "Impossible d'escalader un ticket clôturé en mission.")
        return redirect('chef_view_recoupement', pk=pk)

    try:
        # Déterminer la priorité de la mission
        mission_priority = 2 # Moyenne par défaut
        if ticket.level == 'RED':
            mission_priority = 4 # Critique
        elif ticket.level == 'ORANGE':
            mission_priority = 3 # Haute
        # YELLOW reste 2 (Moyenne)
        
        # Synthétiser la description de la mission
        description = f"Escaladé depuis le recoupement #{ticket.id}:\n\n"
        description += f"Titre du recoupement: {ticket.title}\n"
        description += f"Évidence: {ticket.evidence}\n"
        if ticket.keywords:
            description += f"Mots-clés: {ticket.keywords}\n"
        if ticket.is_overdue:
            description += f"Le recoupement était en retard de {ticket.overdue_hours} heures ({ticket.overdue_level}).\n"
        
        # Déterminer l'agent assigné à la mission
        assigned_agent = None
        if ticket.assigned_agents.exists():
            # Tente d'assigner au premier agent du ticket s'il a un profil Agent
            first_assigned_user = ticket.assigned_agents.first()
            assigned_agent = Agent.objects.filter(user=first_assigned_user).first()
            if assigned_agent:
                description += f"\nAgents du recoupement: {', '.join([a.username for a in ticket.assigned_agents.all()])}\n"
            else:
                messages.warning(request, "Aucun profil agent valide trouvé pour l'agent assigné au recoupement. Mission créée sans agent assigné.")
        
        if not assigned_agent:
            # Si aucun agent n'a pu être assigné directement, on peut l'assigner au chef créateur de mission ou laisser à null
            # Pour l'instant, on laisse null et le chef devra assigner manuellement
            pass

        # Créer la mission
        mission = Mission.objects.create(
            titre=f"Mission - {ticket.title}",
            description=description,
            agent_assigned=assigned_agent, # Peut être None
            created_by=request.user,
            status='PENDING', # Les missions créées par escalade sont en attente par défaut
            priority=mission_priority,
            related_recoupement=ticket, # Lien vers le ticket d'origine
        )

        # Mettre à jour le statut du ticket de recoupement
        ticket.status = 'CLOSED'
        ticket.save()

        # Log de l'action
        AuditLog.objects.create(
            user=request.user,
            action="CHEF_ESCALATE_RECOUPEMENT",
            target_repr=f"Recoupement #{ticket.id} escaladé en Mission #{mission.id}"
        )
        messages.success(request, f"Le recoupement #{ticket.id} a été escaladé en Mission #{mission.id}.")

        # Rediriger vers la page de détail de la mission
        return redirect('mission_detail', pk=mission.id)

    except Exception as e:
        messages.error(request, f"Erreur lors de l'escalade du recoupement en mission: {e}")
        return redirect('chef_view_recoupement', pk=pk)

