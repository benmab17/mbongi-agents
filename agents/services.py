from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Q
from django.contrib.auth.models import User

from .models import Contribution, Mission, AuditLog, Agent # Importez Agent pour filtrer par service


# --- 1.4 OBJET "ALERTE PRÉVENTIVE" (Python class - non persistée en DB pour cette phase) ---
class AlertePreventive:
    def __init__(self, type, zone, level, justification, sources_agregees, date_detection, statut="active"):
        self.type = type # social, armé, économique, institutionnel
        self.zone = zone # province, ville (texte libre pour l'instant)
        self.level = level # VERT / JAUNE / ORANGE / ROUGE
        self.justification = justification # TEXTUELLE claire
        self.sources_agregees = sources_agregees # Liste de strings ou dicts (sans exposer les agents)
        self.date_detection = date_detection
        self.statut = statut # active / surveillee / close

    def __repr__(self):
        return f"Alerte({self.type}, {self.zone}, {self.level}, '{self.justification[:50]}...')"


# --- Logique de détection des signaux faibles ---
def detect_weak_signals():
    """
    Détecte les signaux faibles nationaux basés sur les données existantes.
    Retourne une liste d'objets AlertePreventive.
    """
    alerts = []
    now = timezone.now()
    
    # Périodes
    last_6h = now - timedelta(hours=6)
    last_12h = now - timedelta(hours=12)
    last_24h = now - timedelta(hours=24)
    last_48h = now - timedelta(hours=48)
    last_3d = now - timedelta(days=3)
    last_7d = now - timedelta(days=7)
    last_10d = now - timedelta(days=10)
    last_14d = now - timedelta(days=14)

    # Paramètres configurables (seuils indicatifs pour l'instant)
    SEUILS = {
        'JAUNE_CONTRIB_THEME_COUNT': 5, # +5 contributions même thème / 7 jours / même zone
        'ORANGE_CONTRIB_TOTAL_COUNT': 10, # +10 contributions / 14 jours (tous thèmes)
        'ORANGE_SILENCE_ZONE_DAYS': 10, # Silence total zone sensible 10 jours
        'ACCELERATION_FACTOR_CONTRIB': 3, # Rythme x3 en 24h vs 7j
        'ACCELERATION_FACTOR_AUDIT': 5, # Audit critique x5 en 24h vs 7j
        'CRITICAL_SILENCE_AGENT_DAYS': 7, # Agent régulier silencieux depuis 7 jours
        'CRITICAL_CONTRADICTORY_PERCENT': 0.3, # 30% d'infos contradictoires
    }

    # Données agrégées pour la détection
    all_contributions = Contribution.objects.all()
    all_missions = Mission.objects.all()
    all_audit_logs = AuditLog.objects.all()
    all_agents = Agent.objects.all()

    # --- Signaux faibles à détecter ---

    # A) ACCUMULATION ANORMALE (Thème / Zone / Période / Multi-agents)
    # Répétition d'un thème / zone / période courte / multi-agents
    theme_counts_7d = all_contributions.filter(date_creation__gte=last_7d).values('titre', 'agent__service__nom').annotate(count=Count('id'))
    
    for item in theme_counts_7d:
        if item['count'] >= SEUILS['JAUNE_CONTRIB_THEME_COUNT']:
            alerts.append(AlertePreventive(
                type="SOCIAL",
                zone=item['agent__service__nom'] or "NATIONALE",
                level="JAUNE",
                justification=f"Accumulation: {item['count']} contributions sur le thème '{item['titre']}' détectées en 7 jours dans la zone '{item['agent__service__nom']}'.",
                sources_agregees=[f"{item['count']} contributions sur '{item['titre']}'"],
                date_detection=now
            ))
    
    total_contrib_14d = all_contributions.filter(date_creation__gte=last_14d).count()
    if total_contrib_14d >= SEUILS['ORANGE_CONTRIB_TOTAL_COUNT']:
        alerts.append(AlertePreventive(
            type="SOCIAL",
            zone="NATIONALE",
            level="ORANGE",
            justification=f"Accumulation: {total_contrib_14d} contributions tous thèmes détectées en 14 jours.",
            sources_agregees=[f"{total_contrib_14d} contributions"],
            date_detection=now
        ))

    # B) ACCÉLÉRATION (Rythme Contributions / Missions / Audit)
    contrib_24h = all_contributions.filter(date_creation__gte=last_24h).count()
    contrib_7d = all_contributions.filter(date_creation__gte=last_7d).count()
    if contrib_7d > 0 and contrib_24h > (contrib_7d / 7 * SEUILS['ACCELERATION_FACTOR_CONTRIB']):
        alerts.append(AlertePreventive(
            type="INSTITUTIONNEL",
            zone="NATIONALE",
            level="JAUNE",
            justification=f"Accélération: Le rythme des contributions a augmenté de plus de x{SEUILS['ACCELERATION_FACTOR_CONTRIB']} en 24h par rapport à la moyenne 7 jours.",
            sources_agregees=[f"{contrib_24h} contrib. 24h, {contrib_7d} contrib. 7j"],
            date_detection=now
        ))

    # C) SILENCE ANORMAL (Zone / Agent / Province)
    # (Simplifié pour cette V1, nécessite une définition de "zone sensible" et "agent régulier")
    # Pour l'instant, un silence total dans une zone qui a eu de l'activité
    # et un agent qui n'a pas contribué alors qu'il le faisait régulièrement
    
    # Zones sensibles (à définir plus précisément, ici juste un exemple)
    # provinces_actives_last_month = all_contributions.filter(date_creation__gte=now - timedelta(days=30)).values_list('agent__service__nom', flat=True).distinct()
    # for zone in provinces_actives_last_month:
    #     if not all_contributions.filter(agent__service__nom=zone, date_creation__gte=last_10d).exists():
    #         alerts.append(AlertePreventive(
    #             type="SÉCURITÉ ARMÉE",
    #             zone=zone,
    #             level="ORANGE",
    #             justification=f"Silence anormal: Aucune contribution détectée dans la zone '{zone}' depuis 10 jours, alors qu'elle est habituellement active.",
    #             sources_agregees=["Absence de signaux de la zone"],
    #             date_detection=now
    #         ))

    # Agent régulier devenu silencieux
    # (Implique de savoir ce qu'est un "agent régulier" - pour V1, on simplifie)
    # On prend les agents qui ont eu au moins 5 contributions le mois dernier
    active_agents_last_month_ids = all_contributions.filter(date_creation__gte=now - timedelta(days=30)).values('agent').annotate(count=Count('id')).filter(count__gte=5).values_list('agent', flat=True)
    for agent_id in active_agents_last_month_ids:
        if not all_contributions.filter(agent__id=agent_id, date_creation__gte=last_7d).exists():
            agent_obj = Agent.objects.get(id=agent_id)
            alerts.append(AlertePreventive(
                type="INSTITUTIONNEL",
                zone=agent_obj.service.nom or "Inconnue",
                level="CRITICAL",
                justification=f"Silence anormal: L'agent {agent_obj.nom} ({agent_obj.matricule}) habituellement actif est silencieux depuis 7 jours.",
                sources_agregees=[f"Silence agent {agent_obj.matricule}"],
                date_detection=now
            ))

    # D) DIVERGENCE (Infos contradictoires / Décisions sans amélioration)
    # (Simplifié pour V1, nécessite analyse de contenu ou historique décision/terrain)
    # Pour l'instant, détection basique de rejets multiples sur un même thème.
    rejected_themes_7d = all_contributions.filter(statut="REJECTED", date_creation__gte=last_7d).values('titre').annotate(count=Count('id')).filter(count__gte=3)
    for item in rejected_themes_7d:
        alerts.append(AlertePreventive(
            type="INSTITUTIONNEL",
            zone="NATIONALE",
            level="WARNING",
            justification=f"Divergence: {item['count']} rejets de contributions sur le thème '{item['titre']}' en 7 jours, indiquant des informations contradictoires ou des problèmes de clarté.",
            sources_agregees=[f"{item['count']} rejets sur '{item['titre']}'"],
            date_detection=now
        ))

    return alerts


import re
from collections import defaultdict
from django.db.models import Avg

def get_weak_signals(last_hours=72, limit=5):
    """
    Détecte les signaux faibles à partir des contributions récentes
    et retourne une liste de dictionnaires formatés.
    """
    now = timezone.now()
    start_date = now - timedelta(hours=last_hours)
    
    # Mots-clés sensibles avec un poids supplémentaire
    sensitive_keywords = {
        "m23": 5, "goma": 4, "bunia": 4, "ituri": 3, "nord-kivu": 3, 
        "sud-kivu": 3, "rwanda": 5, "armes": 4, "enlèvement": 5, 
        "attaque": 5, "explosion": 5, "manifestation": 3, "barrage": 3, 
        "milice": 4
    }

    # Récupérer les contributions pertinentes
    contributions = Contribution.objects.filter(date_creation__gte=start_date)

    # Analyser et regrouper les mots-clés
    keyword_data = defaultdict(lambda: {
        "contrib_ids": [],
        "total_priority": 0,
        "count": 0,
        "last_seen": now,
        "count_last_24h": 0,
        "count_prev_24h": 0,
    })

    # Fenêtres pour le calcul de tendance
    last_24h_start = now - timedelta(hours=24)
    prev_24h_start = now - timedelta(hours=48)

    for contrib in contributions:
        # Concaténer titre et contenu pour une analyse complète
        text_content = (contrib.titre + " " + contrib.contenu).lower()
        
        # Extraire les tokens (mots de 4 caractères ou plus)
        tokens = set(re.findall(r'\b\w{4,}\b', text_content))
        
        for token in tokens:
            data = keyword_data[token]
            if contrib.id not in data["contrib_ids"]:
                data["contrib_ids"].append(contrib.id)
                data["total_priority"] += contrib.priorite
                data["count"] += 1
                if contrib.date_creation > data["last_seen"]:
                    data["last_seen"] = contrib.date_creation

                # Compter pour la tendance
                if contrib.date_creation >= last_24h_start:
                    data["count_last_24h"] += 1
                elif contrib.date_creation >= prev_24h_start:
                    data["count_prev_24h"] += 1

    if not keyword_data:
        return []

    # Calculer le score et formater les signaux
    weak_signals = []
    for keyword, data in keyword_data.items():
        if data["count"] < 2:  # Ignorer les signaux avec une seule occurrence
            continue

        avg_priority = data["total_priority"] / data["count"]
        
        # Calcul du score
        score = (data["count"] * 2) + (avg_priority * 3)
        # Booster avec les mots-clés sensibles
        score += sensitive_keywords.get(keyword, 0)

        # Détermination du niveau
        if score >= 18:
            level = "RED"
        elif score >= 12:
            level = "ORANGE"
        elif score >= 7:
            level = "YELLOW"
        else:
            level = "GREEN"

        # Détermination de la tendance
        trend = "STABLE"
        if data["count_prev_24h"] > 0:
            change_ratio = (data["count_last_24h"] - data["count_prev_24h"]) / data["count_prev_24h"]
            if change_ratio > 0.3:
                trend = "UP"
            elif change_ratio < -0.3:
                trend = "DOWN"
        elif data["count_last_24h"] > 1: # Si pas de données avant mais plusieurs maintenant
            trend = "UP"

        # Formater le signal
        weak_signals.append({
            "score": score,
            "level": level,
            "title": f"Signal: {keyword.upper()}",
            "evidence": f"{data['count']} occurrences, priorité moy. {avg_priority:.1f}",
            "keywords": [keyword],
            "trend": trend,
            "last_seen": data["last_seen"],
            "action_hint": "Analyser les contributions liées et demander un recoupement."
        })

    # Trier par score et retourner le top `limit`
    sorted_signals = sorted(weak_signals, key=lambda x: x["score"], reverse=True)
    
    return sorted_signals[:limit]

