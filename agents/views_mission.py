from .forms import MissionForm, MissionUpdateForm
from .security import chef_required, is_chef_service
from .views import get_my_agent # Importation de get_my_agent
from django.shortcuts import get_object_or_404
from .models import Mission
from django.utils import timezone
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect
from agents.models import AuditLog



@chef_required
def mission_create_view(request):
    """
    Vue pour un chef pour créer et assigner une mission.
    """
    # Utilisation de get_my_agent pour une récupération robuste
    chef_agent_profile = get_my_agent(request)
    if not chef_agent_profile:
        return redirect('dashboard') # Rediriger si aucun profil agent n'est trouvé

    if request.method == 'POST':
        form = MissionForm(request.POST, service=chef_agent_profile.service)
        if form.is_valid():
            mission = form.save(commit=False)
            mission.created_by = request.user
            mission.save()
            
            # Audit log
            AuditLog.objects.create(
                user=request.user,
                action="CREATE_MISSION",
                target_repr=f"Mission '{mission.titre}' pour {mission.agent_assigned}",
                ip_address=request.META.get("REMOTE_ADDR")
            )
            return redirect('team_view')
    else:
        form = MissionForm(service=chef_agent_profile.service)
        
    return render(request, 'agents/mission_form.html', {'form': form, 'title': 'Créer une Mission'})

def mission_detail_view(request, pk):
    """
    Vue pour un agent pour voir les détails d'une mission et changer son statut.
    """
    mission = get_object_or_404(Mission, pk=pk)
    agent_profile = get_my_agent(request) # Utilisation de la fonction robuste

    if not agent_profile:
        # Rediriger si aucun profil agent n'est trouvé
        return redirect('dashboard')

    # Sécurité: l'agent ne voit que ses missions, le chef que celles de son service
    if is_chef_service(request.user):
        if mission.agent_assigned.service != agent_profile.service:
            return HttpResponseForbidden("Accès non autorisé.")
    elif mission.agent_assigned != agent_profile: # Vérifier si la mission appartient bien à cet agent
        return HttpResponseForbidden("Accès non autorisé.")

    if request.method == 'POST':
        form = MissionUpdateForm(request.POST, instance=mission)
        if form.is_valid():
            old_status = mission.status
            updated_mission = form.save(commit=False)
            
            if updated_mission.status == 'COMPLETED' and not updated_mission.completed_at:
                updated_mission.completed_at = timezone.now()
                updated_mission.reported_at = timezone.now()

            updated_mission.save()

            # Audit log
            details = f"status: {old_status} -> {updated_mission.status}, rapport: {len(updated_mission.report)} chars"
            AuditLog.objects.create(
                user=request.user,
                action="UPDATE_MISSION",
                target_repr=f"{mission.titre} → {mission.get_status_display()}",
                ip_address=request.META.get("REMOTE_ADDR")
            )
            return redirect('agent_profile')
    else:
        form = MissionUpdateForm(instance=mission)

    return render(request, 'agents/mission_detail.html', {'mission': mission, 'form': form})
