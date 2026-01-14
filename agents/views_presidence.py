from datetime import timedelta
import json
from collections import Counter
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from django.contrib.auth.models import User
from django.db.models import Count, Avg, Q, F
from django.http import HttpResponse, HttpResponseForbidden # Importation manquante

from agents.models import AuditLog, Contribution, Mission, Agent, Decision, RecoupementTicket, CNSAvis, FieldObservation # Import de Decision et RecoupementTicket
from agents.security import presidence_required, presidence_or_cns_required, is_presidence, is_cns, is_chef_service # Importations des fonctions de sécurité
from agents.utils import compute_agent_score # Importation des utilitaires
from .views import get_my_agent # Importation de get_my_agent depuis views.py
from agents.services import get_weak_signals


@presidence_or_cns_required
def presidence_briefing_view(request):
    """
    Vue du briefing de la Présidence : tableau de bord ultra impressionnant.
    """
    if request.method != "GET" and not is_presidence(request.user):
        return HttpResponseForbidden("Lecture seule pour le CNS.")
    # --- Journalisation de l'accès ---
    AuditLog.objects.create(
        user=request.user,
        action="VIEW_PRESIDENCE_BRIEFING",
        target_repr="Présidence briefing",
        ip_address=request.META.get("REMOTE_ADDR")
    )

    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    last_3d = now - timedelta(days=3)
    last_7d = now - timedelta(days=7)
    last_14d = now - timedelta(days=14)
    
    escalations = [] # Initialisation pour éviter NameError
    weak_signals = [] # Initialisation pour éviter NameError


    # --- Données pour Statut National ---
    total_validated_24h = Contribution.objects.filter(statut="VALIDATED", date_creation__gte=last_24h).count()
    total_rejected_7d = Contribution.objects.filter(statut="REJECTED", date_creation__gte=last_7d).count()
    
    missions_failed_active_7d = Mission.objects.filter(
        status="FAILED",
        created_at__gte=last_7d
    ).count() # Compter les missions FAILED créées ou terminées/échouées dans les 7 derniers jours

    contributions_submitted_pending = Contribution.objects.filter(
        statut="SUBMITTED",
        date_creation__lt=last_3d
    ).count()

    # --- Calcul du Statut National ---
    national_status = "STABLE"
    national_status_color = "green"
    national_status_summary = "La situation nationale est stable. Aucun indicateur critique n'est signalé. Une surveillance proactive est maintenue."

    if missions_failed_active_7d >= 2 or total_validated_24h >= 15: # Critical if too many validated or failed missions
        national_status = "CRITIQUE"
        national_status_color = "red"
        national_status_summary = "La situation nationale est CRITIQUE. Des signaux d'alerte élevés nécessitent une attention immédiate. Réévaluation des protocoles en cours."
    elif contributions_submitted_pending >= 5 or total_rejected_7d >= 5:
        national_status = "SOUS TENSION"
        national_status_color = "orange"
        national_status_summary = "La situation nationale est sous tension. Plusieurs indicateurs nécessitent une observation renforcée. Des actions correctives sont envisagées."

    # --- ALERTES INTELLIGENTES ---
    alert_level = "GREEN"
    alert_reasons = []

    # RED conditions
    red_failed_missions_count = Mission.objects.filter(
        status="FAILED", completed_at__gte=last_7d
    ).count()
    red_rejected_contributions_count = Contribution.objects.filter(
        statut="REJECTED", validated_at__gte=now - timedelta(hours=48)
    ).count()

    if red_failed_missions_count >= 1: # au moins 1 Mission status='FAILED' sur les 7 derniers jours
        alert_level = "RED"
        alert_reasons.append(f"{red_failed_missions_count} mission(s) échouée(s) récemment ({red_failed_missions_count} en 7j).")
    
    if red_rejected_contributions_count >= 3: # au moins 3 Contributions refusées sur les 48 dernières heures
        alert_level = "RED"
        alert_reasons.append(f"{red_rejected_contributions_count} contribution(s) refusée(s) en 48h.")

    # ORANGE conditions (si pas déjà RED)
    if alert_level != "RED":
        orange_pending_contributions_count = Contribution.objects.filter(
            statut="SUBMITTED",
            date_creation__gte=now - timedelta(hours=48),
            date_creation__lt=now - timedelta(hours=6) # Considéré "en attente" si soumis il y a plus de 6h
        ).count()

        orange_overdue_missions_count = Mission.objects.filter(
            due_date__lt=now.date(), # Comparer date avec date
            status__in=['PENDING', 'IN_PROGRESS']
        ).count()

        if orange_pending_contributions_count >= 5: # au moins 5 Contributions "en attente" sur les 48 dernières heures
            alert_level = "ORANGE"
            alert_reasons.append(f"{orange_pending_contributions_count} contribution(s) soumise(s) en attente depuis >6h.")
        
        if orange_overdue_missions_count >= 2: # au moins 2 Missions en retard
            alert_level = "ORANGE"
            alert_reasons.append(f"{orange_overdue_missions_count} mission(s) en retard.")

    # Si aucune alerte ORANGE ou RED
    if not alert_reasons:
        alert_reasons.append("Aucune alerte significative. Opérations normales.")


    # --- Données pour KPIs ---
    kpi_contributions_validated_24h = total_validated_24h
    kpi_contributions_validated_7d = Contribution.objects.filter(statut="VALIDATED", date_creation__gte=last_7d).count()

    kpi_missions_pending = Mission.objects.filter(status="PENDING").count()
    kpi_missions_in_progress = Mission.objects.filter(status="IN_PROGRESS").count()
    kpi_missions_completed_7d = Mission.objects.filter(status="COMPLETED", completed_at__gte=last_7d).count()
    kpi_missions_failed_7d = Mission.objects.filter(status="FAILED", completed_at__gte=last_7d).count()
    
    # Score global
    all_agents = Agent.objects.all()
    if all_agents.exists():
        global_scores = [compute_agent_score(agent) for agent in all_agents]
        global_score_avg = sum(global_scores) / len(global_scores)
    else:
        global_score_avg = 0

    # --- Timelines events ---
    # This list will hold processed audit logs for the timeline
    timeline_events_processed = []
    for log_item in AuditLog.objects.filter(timestamp__gte=now - timedelta(hours=72)).order_by('-timestamp')[:10]: # 10 événements max
        
        # Default values
        event_type = "SYSTÈME"
        event_level = "INFO"
        event_description = log_item.target_repr or log_item.get_action_display()

        # Determine type/source based on user groups or action
        if log_item.user and log_item.user.is_superuser:
            event_type = "SUPERUSER"
        elif log_item.user and log_item.user.groups.filter(name="CHEF_SERVICE").exists():
            event_type = "CHEF"
        elif log_item.user:
            event_type = "AGENT"
        
        # Determine level based on action
        if log_item.action in ['REJECT_CONTRIBUTION', 'FAILED_MISSION']: # Assuming FAILED_MISSION exists as an action
            event_level = "CRITICAL"
        elif log_item.action in ['SUBMIT_CONTRIBUTION', 'UPDATE_MISSION']:
            event_level = "WARNING"
        
        timeline_events_processed.append({
            'timestamp': log_item.timestamp,
            'user': log_item.user,
            'action_display': log_item.get_action_display(),
            'target_repr': log_item.target_repr,
            'ip_address': log_item.ip_address,
            'event_type': event_type,
            'event_description': event_description,
            'event_level': event_level,
        })


    # --- Données pour le nouveau bloc KPIs ---
    kpis_data = {
        "contrib_submitted_24h": Contribution.objects.filter(statut="SUBMITTED", date_creation__gte=last_24h).count(),
        "contrib_validated_24h": Contribution.objects.filter(statut="VALIDATED", date_creation__gte=last_24h).count(),
        "contrib_rejected_24h": Contribution.objects.filter(statut="REJECTED", validated_at__gte=last_24h).count(),
        "missions_in_progress": Mission.objects.filter(status="IN_PROGRESS").count(),
        "missions_critical": Mission.objects.filter(
            priority=4, # Assuming priority 4 is 'Critique'
            status__in=['PENDING', 'IN_PROGRESS']
        ).count(),
        # Événements audit sensibles (LOGIN + REJECT_CONTRIBUTION dans les dernières 24h)
        "sensitive_audit_events_24h": AuditLog.objects.filter(
            action__in=['LOGIN', 'REJECT_CONTRIBUTION'],
            timestamp__gte=last_24h
        ).count(),
        "global_score_avg": round(global_score_avg) if global_score_avg else 0,
    } # <-- Accolade fermante manquante ici    # Dernières décisions (AuditLog)
    latest_decisions = Decision.objects.all().select_related('created_by').order_by('-created_at')[:5]

    # --- Données pour Carte RDC stylée (simplifié) ---
    # Journalisation de l'accès à la carte RDC
    AuditLog.objects.create(
        user=request.user,
        action="VIEW_RDC_MAP_STATUS",
        target_repr="Carte RDC sur briefing Présidence",
        ip_address=request.META.get("REMOTE_ADDR")
    )
    zone_data = {
        "kinshasa": {"level": "green", "label": "Kinshasa", "count": 0},
        "est": {"level": "orange", "label": "Est", "count": 0},
        "ouest": {"level": "green", "label": "Ouest", "count": 0},
        "nord": {"level": "green", "label": "Nord", "count": 0},
        "sud": {"level": "red", "label": "Sud", "count": 0},
        "centre": {"level": "green", "label": "Centre", "count": 0},
    }
    # Simulation: niveau basé sur le nombre de contributions validées dans les 7j par mots-clés
    # ou une logique plus complexe. Pour l'instant, juste des exemples.
    keywords_to_zones = {
        'kinshasa': ['kinshasa', 'capitale'],
        'est': ['est', 'kivu', 'ituri', 'bunia'],
        'ouest': ['ouest', 'kongo', 'matadi'],
        'nord': ['nord', 'kisangani'],
        'sud': ['sud', 'lubumbashi', 'katanga'],
        'centre': ['centre', 'kasai'],
    }

    for zone_key, keywords in keywords_to_zones.items():
        zone_contrib_count = Contribution.objects.filter(
            statut="VALIDATED", 
            date_creation__gte=last_7d,
            contenu__icontains=keywords[0] # Simplification, devrait boucler sur tous les keywords
        ).count()
        zone_data[zone_key]['count'] = zone_contrib_count
        if zone_contrib_count > 3: # Exemple de règle
            zone_data[zone_key]['level'] = "red"
        elif zone_contrib_count > 1:
            zone_data[zone_key]['level'] = "orange"
        else:
             zone_data[zone_key]['level'] = "green"

    zone_provinces = {
        "EST": ["Nord-Kivu", "Sud-Kivu", "Ituri", "Maniema"],
        "NORD": ["Bas-Uele", "Haut-Uele", "Tshopo"],
        "CENTRE": ["Kasai", "Kasai-Central", "Kasai-Oriental", "Lomami", "Sankuru"],
        "OUEST": ["Kinshasa", "Kongo-Central", "Kwango", "Kwilu", "Mai-Ndombe", "Mongala", "Nord-Ubangi", "Sud-Ubangi", "Equateur", "Tshuapa"],
        "SUD": ["Haut-Katanga", "Lualaba", "Haut-Lomami", "Tanganyika"],
    }

    def _province_variants(name):
        lower = name.lower()
        return {
            lower,
            lower.replace("-", " "),
            lower.replace(" ", "-"),
        }

    def _province_q_for_contrib(province):
        q = Q()
        for variant in _province_variants(province):
            q |= Q(titre__icontains=variant) | Q(contenu__icontains=variant)
        return q

    def _province_q_for_obs(province):
        q = Q()
        for variant in _province_variants(province):
            q |= Q(zone__icontains=variant)
        return q

    zone_evolution = {}
    for zone_name, provinces in zone_provinces.items():
        zone_contrib_q = Q()
        zone_obs_q = Q()
        for province in provinces:
            zone_contrib_q |= _province_q_for_contrib(province)
            zone_obs_q |= _province_q_for_obs(province)

        contrib_7d = Contribution.objects.filter(date_creation__gte=last_7d).filter(zone_contrib_q)
        contrib_prev = Contribution.objects.filter(date_creation__gte=last_14d, date_creation__lt=last_7d).filter(zone_contrib_q)
        obs_7d = FieldObservation.objects.filter(created_at__gte=last_7d).filter(zone_obs_q)
        obs_prev = FieldObservation.objects.filter(created_at__gte=last_14d, created_at__lt=last_7d).filter(zone_obs_q)

        incidents_7d = contrib_7d.count() + obs_7d.count()
        incidents_prev7d = contrib_prev.count() + obs_prev.count()

        if incidents_7d > incidents_prev7d:
            trend = "hausse"
        elif incidents_7d < incidents_prev7d:
            trend = "baisse"
        else:
            trend = "stable"

        if incidents_7d >= 10:
            risk = "critique"
        elif incidents_7d >= 6:
            risk = "eleve"
        elif incidents_7d >= 3:
            risk = "modere"
        else:
            risk = "faible"

        signal_counter = Counter()
        signal_counter.update([title.strip() for title in contrib_7d.values_list("titre", flat=True) if title and title.strip()])
        signal_counter.update([subject.strip() for subject in obs_7d.values_list("subject", flat=True) if subject and subject.strip()])
        top_signals = [item for item, _ in signal_counter.most_common(3)]

        province_counts = []
        for province in provinces:
            province_count = contrib_7d.filter(_province_q_for_contrib(province)).count()
            province_count += obs_7d.filter(_province_q_for_obs(province)).count()
            province_counts.append((province, province_count))
        province_counts = sorted(province_counts, key=lambda item: item[1], reverse=True)
        hotspots = [name for name, count in province_counts if count > 0][:3]

        if trend == "hausse" and risk in ["eleve", "critique"]:
            projection_7d = "Risque d aggravation sur les 7 prochains jours."
        else:
            projection_7d = "Situation sous controle relatif."

        if risk in ["eleve", "critique"]:
            recommendation = "Renforcer la surveillance regionale."
        elif risk == "modere":
            recommendation = "Maintenir la vigilance renforcee."
        else:
            recommendation = "Maintenir la vigilance."

        insufficient = incidents_7d == 0 and incidents_prev7d == 0 and not top_signals and not hotspots

        zone_evolution[zone_name] = {
            "trend": trend,
            "risk": risk,
            "incidents_7d": incidents_7d,
            "incidents_prev7d": incidents_prev7d,
            "top_signals": top_signals,
            "hotspots": hotspots,
            "projection_7d": projection_7d,
            "recommendation": recommendation,
            "insufficient": insufficient,
        }


    # --- Synthèse IA (simulée) ---
    ai_summary = "La situation nationale est " + national_status.lower() + ". "
    if national_status == "CRITIQUE":
        ai_summary += "Des défaillances critiques et un volume anormalement élevé de validations urgentes requièrent une intervention immédiate. "
    elif national_status == "SOUS TENSION":
        ai_summary += "Des retards dans le traitement des contributions et un nombre croissant de rejets indiquent une surcharge opérationnelle ou des problèmes de qualité. "
    else:
        ai_summary += "Les opérations se déroulent selon les prévisions. Les indicateurs sont au vert."
    ai_summary += "Les signaux dominants sont "
    if kpi_contributions_validated_24h > 5: ai_summary += "une activité de validation élevée ({} validations 24h). ".format(kpi_contributions_validated_24h)
    if kpi_missions_failed_7d > 0: ai_summary += "des échecs de mission récents ({} en 7j). ".format(kpi_missions_failed_7d)
    if kpi_missions_pending > 0: ai_summary += "des missions en attente de démarrage ({} missions). ".format(kpi_missions_pending)
    if kpi_missions_in_progress > 0: ai_summary += "des opérations en cours ({} missions). ".format(kpi_missions_in_progress)

    ai_recommendation = "Recommandation : "
    if national_status == "CRITIQUE":
        ai_recommendation += "Activation du protocole d'urgence et convocation du comité de crise. Prioriser l'analyse des échecs de mission."
    elif national_status == "SOUS TENSION":
        ai_recommendation += "Réaffecter les ressources pour accélérer le traitement des contributions en attente. Analyser les motifs de rejet."
    else:
        ai_recommendation += "Maintenir la vigilance. Optimiser les processus pour réduire les contributions en brouillon."

    ai_projection = "Projection 7 jours (IA) : "
    if national_status == "CRITIQUE" or national_status == "SOUS TENSION":
        ai_projection += "Risque élevé de dégradation si aucune action corrective n'est entreprise."
    else:
        ai_projection += "Stabilité probable avec des risques modérés identifiés. Evolution à surveiller."


    # --- Signaux Faibles (V1) ---
    weak_signals = get_weak_signals(last_hours=72, limit=5)
    AuditLog.objects.create(
        user=request.user,
        action="SYSTEM_WEAK_SIGNALS",
        target_repr=f"Présidence: calcul signaux faibles (72h) - {len(weak_signals)} résultats"
    )

    # --- Executive Dashboard Calculations ---
    # Common filters for 72h window
    last_72h = now - timedelta(hours=72)
    active_recoupements = RecoupementTicket.objects.filter(status__in=['OPEN', 'IN_PROGRESS'])
    active_missions = Mission.objects.filter(status__in=['PENDING', 'IN_PROGRESS'])

    # A6.1 — KPI PRESIDENT (line of cards)
    kpi_presidence = {
        "contributions_received_72h": Contribution.objects.filter(date_creation__gte=last_72h).count(),
        "contributions_validated_72h": Contribution.objects.filter(statut="VALIDATED", date_creation__gte=last_72h).count(),
        "recoupements_open": active_recoupements.count(),
        "recoupements_overdue": sum(1 for ticket in active_recoupements if ticket.is_overdue),
        "missions_active": active_missions.count(),
    }
    
    # KPI6: Délai moyen de réaction (en heures) - Temporairement désactivé pour éviter FieldError sur 'responses'
    kpi_presidence["avg_reaction_time_h"] = "N/A"


    # A6.2 — “RÉACTION DE L’ÉTAT” (central block)
    state_reaction = {
        "overdue_count": kpi_presidence["recoupements_overdue"],
        "overdue_message": "Action requise" if kpi_presidence["recoupements_overdue"] > 0 else "Aucun recoupement en retard",
        "in_progress_recoupements": active_recoupements.filter(status='IN_PROGRESS').count(),
        "escalated_missions": Mission.objects.filter(related_recoupement__isnull=False, created_at__gte=last_72h).count(),
        "services_under_pressure": []
    }

    # Top 3 services with most overdue recoupements
    # Group by service of created_by user
    services_overdue_counts = RecoupementTicket.objects.filter(
        status__in=['OPEN', 'IN_PROGRESS'],
        created_at__gte=last_72h,
    ).annotate(
        service_id=F('created_by__agent__service')
    ).values('service_id', 'created_by__agent__service__nom').annotate(
        total_tickets=Count('id')
    ).order_by('-total_tickets')

    # Filter for actually overdue tickets within these services
    service_overdue_list = []
    for entry in services_overdue_counts:
        if entry['service_id']: # Ensure service is linked
            service_tickets = RecoupementTicket.objects.filter(
                created_by__agent__service_id=entry['service_id'],
                status__in=['OPEN', 'IN_PROGRESS']
            )
            overdue_in_service = sum(1 for ticket in service_tickets if ticket.is_overdue)
            if overdue_in_service > 0:
                service_overdue_list.append({
                    'name': entry['created_by__agent__service__nom'],
                    'overdue_count': overdue_in_service
                })
    state_reaction["services_under_pressure"] = sorted(service_overdue_list, key=lambda x: x['overdue_count'], reverse=True)[:3]


    # A6.3 — Focus 72h (top listes)
    focus_72h = {
        "top_themes": [],
        "top_zones": [],
        "top_weak_signals": weak_signals, # Réutiliser les signaux faibles déjà calculés
    }

    # Top Themes from RecoupementTicket keywords and Contribution content
    all_keywords_72h = []
    for ticket in RecoupementTicket.objects.filter(created_at__gte=last_72h):
        if ticket.keywords:
            all_keywords_72h.extend([k.strip().lower() for k in ticket.keywords.split(',') if k.strip()])
    for contrib in Contribution.objects.filter(date_creation__gte=last_72h):
        all_keywords_72h.extend([k.strip().lower() for k in contrib.titre.split() + contrib.contenu.split() if k.strip() and len(k.strip()) >= 4])

    keyword_counts = {}
    for keyword in all_keywords_72h:
        keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1
    
    sorted_keywords = sorted(keyword_counts.items(), key=lambda item: item[1], reverse=True)
    focus_72h["top_themes"] = [k for k, v in sorted_keywords if v > 1][:5] # Seulement ceux qui apparaissent plus d'une fois

    # Top Zones (from service of assigned_agents/created_by for active recoupements)
    all_zones_72h = []
    for ticket in active_recoupements.filter(created_at__gte=last_72h).prefetch_related('assigned_agents__agent__service', 'created_by__agent__service'):
        if ticket.created_by and hasattr(ticket.created_by, 'agent') and ticket.created_by.agent.service:
            all_zones_72h.append(ticket.created_by.agent.service.nom)
        for user in ticket.assigned_agents.all():
            if hasattr(user, 'agent') and user.agent.service:
                all_zones_72h.append(user.agent.service.nom)

    zone_counts = {}
    for zone in all_zones_72h:
        zone_counts[zone] = zone_counts.get(zone, 0) + 1
    
    sorted_zones = sorted(zone_counts.items(), key=lambda item: item[1], reverse=True)
    focus_72h["top_zones"] = [z for z, v in sorted_zones if v > 0][:5] # Top 5 zones avec au moins un recoupement


    # A6.4 — Table “Dernières actions institutionnelles”
    institutional_actions = []

    # Missions from recoupement (escalations)
    for mission in Mission.objects.filter(related_recoupement__isnull=False, created_at__gte=last_72h).select_related('created_by', 'agent_assigned', 'related_recoupement').order_by('-created_at')[:12]:
        institutional_actions.append({
            'date': mission.created_at,
            'type': 'MISSION',
            'objet': f"Mission #{mission.id}: {mission.titre}",
            'actor': mission.created_by.username if mission.created_by else "N/A",
            'status': mission.get_status_display(),
            'level': mission.related_recoupement.level if mission.related_recoupement else 'INFO',
        })

    # Recoupement Tickets
    for ticket in RecoupementTicket.objects.filter(created_at__gte=last_72h).select_related('created_by').order_by('-created_at')[:12]:
        institutional_actions.append({
            'date': ticket.created_at,
            'type': 'REC',
            'objet': f"Recoupement #{ticket.id}: {ticket.title}",
            'actor': ticket.created_by.username if ticket.created_by else "N/A",
            'status': ticket.get_status_display(),
            'level': ticket.level,
        })
    
    # Decisions
    for decision in Decision.objects.filter(created_at__gte=last_72h).select_related('created_by').order_by('-created_at')[:12]:
        institutional_actions.append({
            'date': decision.created_at,
            'type': 'DECISION',
            'objet': f"Décision #{decision.id}: {decision.title}",
            'actor': decision.created_by.username if decision.created_by else "N/A",
            'status': decision.get_decision_display(), # Assuming Decision model has get_decision_display
            'level': 'INFO', # Default level for decisions
        })

    # Trier toutes les actions par date
    institutional_actions = sorted(institutional_actions, key=lambda x: x['date'], reverse=True)[:12]


    # Read receipt Chef sur chargement briefing
    if is_chef_service(request.user) or is_presidence(request.user):
        unread_avis = CNSAvis.objects.filter(status__in=["SENT", "TRANSMITTED"], read_at__isnull=True)
        unread_ids = list(unread_avis.values_list("id", flat=True))
        if unread_ids:
            now = timezone.now()
            CNSAvis.objects.filter(id__in=unread_ids, read_at__isnull=True).update(read_at=now)
            for avis in CNSAvis.objects.filter(id__in=unread_ids):
                AuditLog.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    action="READ",
                    target_repr=f"CNSAvis #{avis.id} - {avis.title}",
                    ip_address=request.META.get("REMOTE_ADDR"),
                )

    # Traçabilité stratégique (7 jours) - synthèse lecture CNS
    trace_window_start = now - timedelta(days=7)
    transmit_logs = list(
        AuditLog.objects.filter(
            action="TRANSMIT",
            timestamp__gte=trace_window_start,
            target_repr__startswith="CNSAvis"
        ).order_by("timestamp")
    )
    read_logs = list(
        AuditLog.objects.filter(
            action="READ",
            timestamp__gte=trace_window_start,
            target_repr__startswith="CNSAvis"
        ).order_by("timestamp")
    )
    read_by_target = {}
    for log in read_logs:
        if log.target_repr and log.target_repr not in read_by_target:
            read_by_target[log.target_repr] = log

    matched_delays = []
    for log in transmit_logs:
        read_log = read_by_target.get(log.target_repr)
        if read_log:
            matched_delays.append(read_log.timestamp - log.timestamp)

    avg_delay_minutes = None
    if matched_delays:
        total_seconds = sum(delay.total_seconds() for delay in matched_delays)
        avg_delay_minutes = int(total_seconds // len(matched_delays) // 60)

    last_read_log = read_logs[-1] if read_logs else None
    trace_read_rate = 0
    if transmit_logs:
        trace_read_rate = int((len(read_by_target) / len(transmit_logs)) * 100)

    context = {
        "last_update": now,
        "national_status": national_status,
        "national_status_color": national_status_color,
        "national_status_summary": national_status_summary,

        "kpi_contributions_validated_24h": kpi_contributions_validated_24h,
        "kpi_contributions_validated_7d": kpi_contributions_validated_7d,
        "kpi_missions_pending": kpi_missions_pending,
        "kpi_missions_in_progress": kpi_missions_in_progress,
        "kpi_missions_completed_7d": kpi_missions_completed_7d,
        "kpi_missions_failed_7d": kpi_missions_failed_7d,
        "global_score_avg": round(global_score_avg) if global_score_avg else 0,

        "latest_decisions": latest_decisions,
        "zone_data": zone_data,
        "ai_summary": ai_summary,
        "ai_recommendation": ai_recommendation,
        "ai_projection": ai_projection,
        "kpis": kpis_data, # Passer le dictionnaire kpis au contexte
        "timeline_events": timeline_events_processed, # Ajouter les événements de la timeline
        "weak_signals": weak_signals, # --- AJOUT SIGNAUX FAIBLES ---
        "recent_decisions_escalations": escalations, # --- AJOUT DÉCISIONS & ESCALADES RÉCENTES ---
        # --- AJOUT TABLEAU EXÉCUTIF ---
        "kpi_presidence": kpi_presidence,
        "state_reaction": state_reaction,
        "focus_72h": focus_72h,
        "institutional_actions": institutional_actions,
        "is_cns": is_cns(request.user),
        "cns_avis_recent": CNSAvis.objects.filter(status="SENT")[:5],
        "zone_evolution_data": json.dumps(zone_evolution, ensure_ascii=True),
        "trace_transmit_count": len(transmit_logs),
        "trace_read_count": len(read_by_target),
        "trace_avg_delay_minutes": avg_delay_minutes,
        "trace_last_read": last_read_log,
        "trace_read_rate": trace_read_rate,
    }
    return render(request, 'agents/presidence_briefing.html', context)

@presidence_required
def presidence_briefing_pdf_view(request):
    """
    Génère un PDF du briefing de la Présidence.
    """
    # --- Journalisation de l'accès ---
    AuditLog.objects.create(
        user=request.user,
        action="VIEW_PRESIDENCE_BRIEFING", # Utilisation de la même action pour l'export
        target_repr="Présidence briefing PDF Export",
        ip_address=request.META.get("REMOTE_ADDR")
    )

    # Récupérer les données de la vue principale
    # Pour éviter la duplication du code de récupération des données
    # nous pouvons appeler presidence_briefing_view pour obtenir le contexte
    # ou dupliquer la logique ici. Pour un objectif de génération de PDF,
    # dupliquer la logique est plus direct que de re-rendre une vue HTML.

    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    last_3d = now - timedelta(days=3)
    last_7d = now - timedelta(days=7)

    # --- Données pour Statut National (dupliquées de presidence_briefing_view) ---
    total_validated_24h = Contribution.objects.filter(statut="VALIDATED", date_creation__gte=last_24h).count()
    total_rejected_7d = Contribution.objects.filter(statut="REJECTED", date_creation__gte=last_7d).count()
    
    missions_failed_active_7d = Mission.objects.filter(
        status="FAILED",
        created_at__gte=last_7d
    ).count()

    contributions_submitted_pending = Contribution.objects.filter(
        statut="SUBMITTED",
        date_creation__lt=last_3d
    ).count()

    national_status = "STABLE"
    national_status_summary = "La situation nationale est stable. Aucun indicateur critique n'est signalé. Une surveillance proactive est maintenue."

    if missions_failed_active_7d >= 2 or total_validated_24h >= 15:
        national_status = "CRITIQUE"
        national_status_summary = "La situation nationale est CRITIQUE. Des signaux d'alerte élevés nécessitent une attention immédiate. Réévaluation des protocoles en cours."
    elif contributions_submitted_pending >= 5 or total_rejected_7d >= 5:
        national_status = "SOUS TENSION"
        national_status_summary = "La situation nationale est sous tension. Plusieurs indicateurs nécessitent une observation renforcée. Des actions correctives sont envisagées."

    # --- ALERTES INTELLIGENTES (dupliquées de presidence_briefing_view) ---
    alert_level = "GREEN"
    alert_reasons = []

    red_failed_missions_count = Mission.objects.filter(
        status="FAILED", completed_at__gte=last_7d
    ).count()
    red_rejected_contributions_count = Contribution.objects.filter(
        statut="REJECTED", validated_at__gte=now - timedelta(hours=48)
    ).count()

    if red_failed_missions_count >= 1:
        alert_level = "RED"
        alert_reasons.append(f"{red_failed_missions_count} mission(s) échouée(s) récemment ({red_failed_missions_count} en 7j).")
    
    if red_rejected_contributions_count >= 3:
        alert_level = "RED"
        alert_reasons.append(f"{red_rejected_contributions_count} contribution(s) refusée(s) en 48h.")

    if alert_level != "RED":
        orange_pending_contributions_count = Contribution.objects.filter(
            statut="SUBMITTED",
            date_creation__gte=now - timedelta(hours=48),
            date_creation__lt=now - timedelta(hours=6)
        ).count()

        orange_overdue_missions_count = Mission.objects.filter(
            due_date__lt=now.date(),
            status__in=['PENDING', 'IN_PROGRESS']
        ).count()

        if orange_pending_contributions_count >= 5:
            alert_level = "ORANGE"
            alert_reasons.append(f"{orange_pending_contributions_count} contribution(s) soumise(s) en attente depuis >6h.")
        
        if orange_overdue_missions_count >= 2:
            alert_level = "ORANGE"
            alert_reasons.append(f"{orange_overdue_missions_count} mission(s) en retard.")

    if not alert_reasons:
        alert_reasons.append("Aucune alerte significative. Opérations normales.")

    # --- Synthèse IA (dupliquée de presidence_briefing_view) ---
    ai_summary = "La situation nationale est " + national_status.lower() + ". "
    if national_status == "CRITIQUE":
        ai_summary += "Des défaillances critiques et un volume anormalement élevé de validations urgentes requièrent une intervention immédiate. "
    elif national_status == "SOUS TENSION":
        ai_summary += "Des retards dans le traitement des contributions et un nombre croissant de rejets indiquent une surcharge opérationnelle ou des problèmes de qualité. "
    else:
        ai_summary += "Les opérations se déroulent selon les prévisions. Les indicateurs sont au vert."
    ai_summary += "Les signaux dominants sont "
    # Pas besoin de tous les détails KPIs ici pour la synthèse simple dans le PDF.

    ai_recommendation = "Recommandation : "
    if national_status == "CRITIQUE":
        ai_recommendation += "Activation du protocole d'urgence et convocation du comité de crise. Prioriser l'analyse des échecs de mission."
    elif national_status == "SOUS TENSION":
        ai_recommendation += "Réaffecter les ressources pour accélérer le traitement des contributions en attente. Analyser les motifs de rejet."
    else:
        ai_recommendation += "Maintenir la vigilance. Optimiser les processus pour réduire les contributions en brouillon."

    ai_projection = "Projection 7 jours (IA) : "
    if national_status == "CRITIQUE" or national_status == "SOUS TENSION":
        ai_projection += "Risque élevé de dégradation si aucune action corrective n'est entreprise."
    else:
        ai_projection += "Stabilité probable avec des risques modérés identifiés. Evolution à surveiller."

    # --- Chronologie (Timeline) ---
    timeline_events_processed = []
    for log_item in AuditLog.objects.filter(timestamp__gte=now - timedelta(hours=72)).order_by('-timestamp')[:10]:
        event_type = "SYSTÈME"
        event_level = "INFO"
        # event_description = log_item.target_repr or log_item.get_action_display()

        if log_item.user and log_item.user.is_superuser:
            event_type = "SUPERUSER"
        elif log_item.user and log_item.user.groups.filter(name="CHEF_SERVICE").exists():
            event_type = "CHEF"
        elif log_item.user:
            event_type = "AGENT"
        
        if log_item.action in ['REJECT_CONTRIBUTION', 'FAILED_MISSION']:
            event_level = "CRITICAL"
        elif log_item.action in ['SUBMIT_CONTRIBUTION', 'UPDATE_MISSION']:
            event_level = "WARNING"
        
        timeline_events_processed.append({
            'timestamp': log_item.timestamp,
            'user': log_item.user,
            'action_display': log_item.get_action_display(),
            'target_repr': log_item.target_repr,
            'ip_address': log_item.ip_address,
            'event_type': event_type,
            'event_description': log_item.target_repr or log_item.get_action_display(), # Utilisation de target_repr ici
            'event_level': event_level,
        })
    
    # Dernières décisions (AuditLog)
    latest_decisions = AuditLog.objects.filter(
        action__in=['VALIDATE_CONTRIBUTION', 'REJECT_CONTRIBUTION']
    ).select_related('user').order_by('-timestamp')[:5]

    # Crée l'objet HttpResponse avec les en-têtes PDF appropriés
    response = HttpResponse(content_type='application/pdf')
    filename = now.strftime("MBONGI-INTEL_Briefing_%Y-%m-%d_%H%M.pdf")
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    # Crée un objet PDF avec ReportLab
    p = canvas.Canvas(response, pagesize=letter)
    width, height = letter
    x_margin = inch
    y_position = height - inch

    # Styles
    p.setFont("Helvetica-Bold", 18)
    p.drawString(x_margin, y_position, "BRIEFING PRÉSIDENCE MBONGI-INTEL")
    y_position -= 0.25 * inch

    p.setFont("Helvetica", 10)
    p.drawString(x_margin, y_position, f"Date et heure : {now.strftime('%d/%m/%Y %H:%M:%S')}")
    y_position -= 0.5 * inch

    # Statut National
    p.setFont("Helvetica-Bold", 14)
    p.drawString(x_margin, y_position, f"Statut National : {national_status}")
    y_position -= 0.2 * inch
    p.setFont("Helvetica", 10)
    p.drawString(x_margin + 0.2*inch, y_position, national_status_summary)
    y_position -= 0.5 * inch

    # Alertes intelligentes
    p.setFont("Helvetica-Bold", 12)
    p.drawString(x_margin, y_position, f"Alertes Intelligentes ({alert_level}) :")
    y_position -= 0.2 * inch
    p.setFont("Helvetica", 10)
    if alert_reasons:
        for reason in alert_reasons:
            p.drawString(x_margin + 0.2*inch, y_position, f"- {reason}")
            y_position -= 0.2 * inch
    else:
        p.drawString(x_margin + 0.2*inch, y_position, "- Aucune alerte significative.")
    y_position -= 0.5 * inch

    # Synthèse IA & projection
    p.setFont("Helvetica-Bold", 12)
    p.drawString(x_margin, y_position, "Synthèse IA & Projection :")
    y_position -= 0.2 * inch
    p.setFont("Helvetica", 10)
    p.drawString(x_margin + 0.2*inch, y_position, ai_summary)
    y_position -= 0.2 * inch
    p.drawString(x_margin + 0.2*inch, y_position, ai_projection)
    y_position -= 0.2 * inch
    p.drawString(x_margin + 0.2*inch, y_position, ai_recommendation)
    y_position -= 0.5 * inch

    # Chronologie Nationale - 72H
    p.setFont("Helvetica-Bold", 12)
    p.drawString(x_margin, y_position, "Chronologie Nationale - 72H :")
    y_position -= 0.2 * inch
    p.setFont("Helvetica", 8)
    if timeline_events_processed:
        for event in timeline_events_processed:
            log_line = f"{event['timestamp'].strftime('%d/%m %H:%M')} - {event['event_type']} ({event['user'].username if event['user'] else 'Système'}) : {event['action_display']} - {event['target_repr']}"
            p.drawString(x_margin + 0.2*inch, y_position, log_line)
            y_position -= 0.15 * inch
            if y_position < inch: # Si la page est pleine, créer une nouvelle page
                p.showPage()
                p.setFont("Helvetica", 8)
                y_position = height - inch
    else:
        p.drawString(x_margin + 0.2*inch, y_position, "Aucune activité récente dans les dernières 72 heures.")
    y_position -= 0.5 * inch

    # Dernières décisions
    p.setFont("Helvetica-Bold", 12)
    p.drawString(x_margin, y_position, "Dernières Décisions :")
    y_position -= 0.2 * inch
    p.setFont("Helvetica", 8)
    if latest_decisions:
        for decision in latest_decisions:
            decision_line = f"{decision.timestamp.strftime('%d/%m %H:%M')} - {decision.user.username if decision.user else 'Système'} : {decision.get_action_display()} - {decision.target_repr}"
            p.drawString(x_margin + 0.2*inch, y_position, decision_line)
            y_position -= 0.15 * inch
            if y_position < inch: # Si la page est pleine, créer une nouvelle page
                p.showPage()
                p.setFont("Helvetica", 8)
                y_position = height - inch
    else:
        p.drawString(x_margin + 0.2*inch, y_position, "Aucune décision récente.")

    p.showPage()
    p.save()
    return response


@require_POST
@login_required
def presidence_cns_avis_read_view(request, pk: int):
    if not (is_presidence(request.user) or is_chef_service(request.user)):
        return HttpResponseForbidden("Accès interdit.")
    avis = get_object_or_404(CNSAvis, pk=pk)
    if avis.status not in ("SENT", "TRANSMITTED"):
        return HttpResponseForbidden("Accès interdit.")
    if avis.read_at is None:
        # Read receipt Chef
        avis.read_at = timezone.now()
        avis.save(update_fields=["read_at"])
        AuditLog.objects.create(
            user=request.user if request.user.is_authenticated else None,
            action="READ",
            target_repr=f"CNSAvis #{avis.id} - {avis.title}",
            ip_address=request.META.get("REMOTE_ADDR"),
        )
    return HttpResponse(status=204)


@require_POST
@login_required
def presidence_cns_avis_decision_view(request, pk: int):
    if not is_chef_service(request.user):
        return HttpResponseForbidden("Accès interdit.")
    avis = get_object_or_404(CNSAvis, pk=pk)
    if avis.status not in ("SENT", "TRANSMITTED"):
        return HttpResponseForbidden("Accès interdit.")
    decision = request.POST.get("decision")
    if decision not in ("APPROVED", "REJECTED"):
        return HttpResponse(status=400)
    if avis.presidency_decision == decision and avis.decision_at is not None:
        return HttpResponse(status=204)
    # Validation Chef
    avis.presidency_decision = decision
    avis.decision_at = timezone.now()
    avis.decision_by = request.user if request.user.is_authenticated else None
    avis.save(update_fields=["presidency_decision", "decision_at", "decision_by"])
    AuditLog.objects.create(
        user=request.user if request.user.is_authenticated else None,
        action="PRES_DECISION",
        target_repr=f"CNSAvis #{avis.id} - {avis.title} - {decision}",
        ip_address=request.META.get("REMOTE_ADDR"),
    )
    return HttpResponse(status=204)
