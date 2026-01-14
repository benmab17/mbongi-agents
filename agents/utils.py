from django.utils import timezone
from datetime import timedelta
from .models import Contribution, Mission

def compute_agent_score(agent):
    """
    Calcule le score de fiabilité d'un agent à la volée.
    Le score est borné entre 0 et 100.
    """
    base_score = 50
    score = base_score

    # === Contributions ===
    contributions = Contribution.objects.filter(agent=agent)
    validated_count = contributions.filter(statut='VALIDATED').count()
    rejected_count = contributions.filter(statut='REJECTED').count()
    
    # Bonus pour contributions validées
    score += validated_count * 10
    
    # Malus pour contributions rejetées
    score -= rejected_count * 15

    # Malus optionnel pour contributions soumises et non traitées depuis plus de 7 jours
    seven_days_ago = timezone.now() - timedelta(days=7)
    old_submitted_count = contributions.filter(
        statut='SUBMITTED',
        date_creation__lt=seven_days_ago
    ).count()
    score -= old_submitted_count * 5

    # === Missions ===
    missions = Mission.objects.filter(agent_assigned=agent)
    completed_count = missions.filter(status='COMPLETED').count()
    failed_count = missions.filter(status='FAILED').count()

    # Bonus pour missions complétées
    score += completed_count * 5

    # Malus pour missions échouées
    score -= failed_count * 5

    # Borner le score entre 0 et 100
    return max(0, min(100, score))
