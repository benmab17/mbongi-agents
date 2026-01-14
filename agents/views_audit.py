from django.shortcuts import render
from django.contrib.auth.models import User
from .models import AuditLog
from .security import chef_required

@chef_required
def audit_log_view(request):
    """
    Affiche le journal d'audit global.
    """
    logs = AuditLog.objects.all().select_related('user')
    
    # --- Journalisation de l'accès à l'audit ---
    AuditLog.objects.create(
        user=request.user,
        action="VIEW_AUDIT",
        ip_address=request.META.get("REMOTE_ADDR"),
        target_repr="Journal d'audit"
    )

    # Filtres
    action_filter = request.GET.get('action')
    user_filter = request.GET.get('user')

    if action_filter:
        logs = logs.filter(action=action_filter)
    if user_filter:
        logs = logs.filter(user__id=user_filter)

    # Pour les menus déroulants du filtre
    actions = AuditLog.ACTION_CHOICES
    users = User.objects.filter(id__in=AuditLog.objects.values_list('user_id', flat=True).distinct())

    context = {
        'logs': logs[:200],  # Limite à 200 entrées pour la performance
        'actions': actions,
        'users': users,
        'current_action': action_filter,
        'current_user': int(user_filter) if user_filter else None,
    }
    return render(request, "agents/audit_log.html", context)
