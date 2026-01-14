from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import render, get_object_or_404

from .models import Agent, Contribution
from .security import chef_required, is_chef_service, is_presidence # Importation de is_presidence
from .utils import compute_agent_score


@login_required
@chef_required
def team_view(request):
    """
    Vue 'Team / Chef de service' (MVP).
    - Colonne gauche: liste agents (service du user connecté)
    - Centre: dossier agent sélectionné
    - Droite: activité récente (dernières contributions)
    """
    me = get_object_or_404(Agent, user=request.user)

    # MVP: un chef voit les agents de son service (même service)
    qs_agents = (
        Agent.objects
        .select_related("service", "user")
        .filter(service=me.service)
        .order_by("nom", "prenom")
    )

    # Agent sélectionné (via ?a=<id>) sinon le premier de la liste
    selected_id = request.GET.get("a")
    if selected_id:
        selected = get_object_or_404(qs_agents, id=selected_id)
    else:
        selected = qs_agents.first()

    # Stats contributions par agent (pour la liste)
    # total + validated + submitted + draft
    stats_map = {}
    if qs_agents.exists():
        counts = (
            Contribution.objects
            .filter(agent__in=qs_agents)
            .values("agent_id")
            .annotate(
                total=Count("id"),
                validated=Count("id", filter=Q(statut="VALIDATED")),
                submitted=Count("id", filter=Q(statut="SUBMITTED")),
                draft=Count("id", filter=Q(statut="DRAFT")),
            )
        )
        stats_map = {c["agent_id"]: c for c in counts}

    # Calcul des scores pour chaque agent
    scores_map = {agent.id: compute_agent_score(agent) for agent in qs_agents}

    # Stats + dernières contributions pour l’agent sélectionné
    selected_stats = {"total": 0, "validated": 0, "submitted": 0, "draft": 0}
    last = []
    if selected:
        selected_stats = stats_map.get(selected.id, selected_stats)
        last = (
            Contribution.objects
            .filter(agent=selected)
            .order_by("-date_creation")[:8]
        )

    context = {
        "me": me,
        "agents_list": qs_agents,
        "selected": selected,
        "stats_map": stats_map,
        "scores_map": scores_map,
        "selected_stats": selected_stats,
        "last": last,
        "is_chef": is_chef_service(request.user),
        "is_presidence": is_presidence(request.user), # Ajout de is_presidence au contexte
    }
    return render(request, "agents/team.html", context)
