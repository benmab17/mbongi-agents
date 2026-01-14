# -*- coding: utf-8 -*-
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from agents.models import Agent, Service


class Command(BaseCommand):
    help = "Create or update test users for DGM and DEMIAP."

    def handle(self, *args, **options):
        password = "Test2026!"
        service_dgm = Service.objects.filter(nom="DGM").first()
        service_demiap = Service.objects.filter(nom="DEMIAP").first()

        if not service_dgm:
            self.stdout.write(
                self.style.ERROR("Service 'DGM' not found. Create it before running.")
            )
            return
        if not service_demiap:
            self.stdout.write(
                self.style.ERROR("Service 'DEMIAP' not found. Create it before running.")
            )
            return

        self._ensure_user_agent(
            username="dgm_test",
            password=password,
            service=service_dgm,
            matricule_prefix="DGM",
            nom="DGM",
            prenom="Test",
        )
        self._ensure_user_agent(
            username="demiap_test",
            password=password,
            service=service_demiap,
            matricule_prefix="DEMIAP",
            nom="DEMIAP",
            prenom="Test",
        )

    def _ensure_user_agent(self, username, password, service, matricule_prefix, nom, prenom):
        User = get_user_model()
        user, created = User.objects.get_or_create(username=username)
        user.set_password(password)
        user.is_active = True
        user.save()

        agent = Agent.objects.filter(user=user).first()
        if not agent:
            matricule_base = f"{matricule_prefix}-0001"
            matricule = matricule_base
            suffix = 1
            while Agent.objects.filter(matricule=matricule).exists():
                suffix += 1
                matricule = f"{matricule_prefix}-{suffix:04d}"
            Agent.objects.create(
                nom=nom,
                prenom=prenom,
                matricule=matricule,
                service=service,
                user=user,
                actif=True,
            )
            status = "created"
        else:
            agent.service = service
            agent.actif = True
            agent.save()
            status = "updated"

        self.stdout.write(
            self.style.SUCCESS(
                f"User {username} {status} - password set - service {service.nom}"
            )
        )
