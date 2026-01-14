from django.urls import path
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from .views import (
    ai_resume_contribution, contribution_new, agent_profile,
    agent_photo_upload, staff_agent_detail, agent_console_view,
    start_patrol_view, end_patrol_view, accept_microtask_view, complete_microtask_view,
    list_shared_contributions_view, share_contribution_view, dgm_renseignement_view,
    ambassade_renseignement_view, dgm_surveillance_view, propose_micro_mission,
    chef_create_micro_mission_view, cns_dashboard_view, cns_avis_list_view,
    cns_avis_create_view
)
from .views_team import team_view
from .views_decision import contribution_decide, contribution_review_view
from .views_decision import decision_list_view
from .views_audit import audit_log_view
from .views_chef import (
    chef_commandement_view, create_recoupement_ticket, take_recoupement_ticket,
    close_recoupement_ticket, view_recoupement_ticket, escalate_recoupement_to_mission
)
from .views_mission import mission_create_view, mission_detail_view
from .views_presidence import presidence_briefing_view, presidence_briefing_pdf_view, presidence_cns_avis_read_view, presidence_cns_avis_decision_view


@login_required
def agent_dossier_ui(request):
    # Page de test : affiche le nouveau template "cinéma ANR"
    return render(request, "agents/agent_dossier.html")


urlpatterns = [
    # UI TEST (agent dossier classifié)
    path("ui/agent-dossier/", agent_dossier_ui, name="agent_dossier_ui"),

    # Contributions
    path("contributions/new/", contribution_new, name="contribution_new"),
    path("contributions/<int:pk>/resume/", ai_resume_contribution, name="ai_resume_contribution"),
    path("contributions/<int:pk>/decide/", contribution_decide, name="contribution_decide"),
    path("contributions/<int:pk>/review/", contribution_review_view, name="contribution_review"),
    path("share/<int:pk>/", share_contribution_view, name="share_contribution"),
    path("shared/", list_shared_contributions_view, name="shared_contributions"),
    path("dgm/renseignement/", dgm_renseignement_view, name="dgm_renseignement"),
    path("dgm/surveillance/", dgm_surveillance_view, name="dgm_surveillance"),
    path("ambassade/renseignement/", ambassade_renseignement_view, name="ambassade_renseignement"),
    path("console/micro/propose/", propose_micro_mission, name="propose_micro_mission"),
    path("chef/micro-missions/new/", chef_create_micro_mission_view, name="chef_create_micro_mission"),
    path("cns/", cns_dashboard_view, name="cns_dashboard"),
    path("cns/avis/", cns_avis_list_view, name="cns_avis_list"),
    path("cns/avis/new/", cns_avis_create_view, name="cns_avis_create"),

    # Missions
    path('missions/new/', mission_create_view, name='mission_create'),
    path('missions/<int:pk>/', mission_detail_view, name='mission_detail'),

    # Profil agent
    path("profile/", agent_profile, name="agent_profile"),
    path("profile/photo/", agent_photo_upload, name="agent_photo_upload"),
    path("console/", agent_console_view, name="agent_console"), # Nouvelle route pour la console agent
    path("patrol/start/", start_patrol_view, name="agent_start_patrol"),
    path("patrol/end/", end_patrol_view, name="agent_end_patrol"),
    path("micro/accept/<int:pk>/", accept_microtask_view, name="agent_accept_microtask"),
    path("micro/done/<int:pk>/", complete_microtask_view, name="agent_complete_microtask"),

    # Vue chef
    path("team/", team_view, name="team_view"),

    # Journal d'audit
    path("audit/", audit_log_view, name="audit_log"),

    # Briefing Présidence
    path("presidence/briefing/", presidence_briefing_view, name="presidence_briefing"),
    path("presidence/briefing/pdf/", presidence_briefing_pdf_view, name="presidence_briefing_pdf"),
    path("presidence/avis/<int:pk>/read/", presidence_cns_avis_read_view, name="presidence_cns_avis_read"),
    path("presidence/avis/<int:pk>/decision/", presidence_cns_avis_decision_view, name="presidence_cns_avis_decision"),
    
    # Décisions formelles
    path("decisions/", decision_list_view, name="decision_list"),

    # Vue Commandement Chef
    path("chef/commandement/", chef_commandement_view, name="chef_commandement"),
    path("chef/recoupement/create/", create_recoupement_ticket, name="chef_create_recoupement"),
    path("chef/recoupement/<int:pk>/", view_recoupement_ticket, name="chef_view_recoupement"),
    path("chef/recoupement/<int:pk>/take/", take_recoupement_ticket, name="chef_take_recoupement"),
    path("chef/recoupement/<int:pk>/close/", close_recoupement_ticket, name="chef_close_recoupement"),
    path("chef/recoupement/<int:pk>/escalate/", escalate_recoupement_to_mission, name="chef_escalate_recoupement"),

    # Vue staff (hors /admin)
    path("staff/agents/<int:pk>/", staff_agent_detail, name="staff_agent_detail"),
]
