# -*- coding: utf-8 -*-
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from agents.models import Agent, Service


class Command(BaseCommand):
    help = "Create or update a test embassy user and assign to the embassy service."

    def handle(self, *args, **options):
        username = "embassy_be"
        password = "Test2026!"
        service_name = "Ambassade RDC - Belgique"

        service = Service.objects.filter(nom=service_name).first()
        if not service:
            self.stdout.write(
                self.style.ERROR(
                    f"Service '{service_name}' not found. Run seed_external_services first."
                )
            )
            return

        User = get_user_model()
        user, created = User.objects.get_or_create(username=username)
        user.set_password(password)
        user.is_active = True
        user.save()

        agent = Agent.objects.filter(user=user).first()
        if not agent:
            matricule_base = "EMB-BE-0001"
            matricule = matricule_base
            suffix = 1
            while Agent.objects.filter(matricule=matricule).exists():
                suffix += 1
                matricule = f"EMB-BE-{suffix:04d}"
            agent = Agent.objects.create(
                nom="Ambassade",
                prenom="Belgique",
                matricule=matricule,
                service=service,
                user=user,
                actif=True,
            )
        else:
            agent.service = service
            agent.actif = True
            agent.save()

        self.stdout.write(
            self.style.SUCCESS(
                "Test embassy user ready: username=embassy_be password=Test2026!"
            )
        )
