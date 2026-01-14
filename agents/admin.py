from django.contrib import admin
from .models import Service, Agent, Contribution, Mission, MicroMission


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("id", "nom")
    search_fields = ("nom",)


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "matricule",
        "prenom",
        "nom",
        "service",
        "unite",
        "fonction",
        "actif",
        "date_creation",
    )
    search_fields = (
        "matricule",
        "nom",
        "prenom",
        "unite",
        "fonction",
    )
    list_filter = (
        "service",
        "actif",
        "date_creation",
    )
    ordering = ("nom", "prenom")


@admin.register(Contribution)
class ContributionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "titre",
        "agent",
        "statut",
        "priorite",
        "date_creation",
    )
    list_filter = (
        "statut",
        "priorite",
        "agent__service",
    )
    search_fields = (
        "titre",
        "contenu",
        "agent__matricule",
        "agent__nom",
        "agent__prenom",
    )
    ordering = ("-date_creation",)


admin.site.register(Mission)


@admin.register(MicroMission)
class MicroMissionAdmin(admin.ModelAdmin):
    list_display = ("agent", "title", "status", "created_at")
