from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from agents.models import Agent, Service


class Command(BaseCommand):
    help = "Create or update test users for PNC and FARDC with agent profiles."

    def handle(self, *args, **options):
        password = "Test2026!"

        service_pnc = self._get_or_create_service(["PNC", "Police"])
        service_fardc = self._get_or_create_service(["FARDC"])
        service_dgm = self._get_or_create_service(["DGM"])
        service_demiap = self._get_or_create_service(["DEMIAP"])

        results = []
        results.append(self._ensure_user_agent("pnc_test", service_pnc, "PNC"))
        results.append(self._ensure_user_agent("fardc_test", service_fardc, "FARDC"))
        results.append(self._ensure_user_agent("dgm_test", service_dgm, "DGM"))
        results.append(self._ensure_user_agent("demiap_test", service_demiap, "DEMIAP"))

        for status, username, service_name in results:
            self.stdout.write(
                self.style.SUCCESS(
                    f"{status}: username={username} password={password} service={service_name}"
                )
            )

    def _get_or_create_service(self, names):
        for name in names:
            service = Service.objects.filter(nom=name).first()
            if service:
                return service
        return Service.objects.create(nom=names[0])

    def _ensure_user_agent(self, username, service, prefix):
        User = get_user_model()
        user, created = User.objects.get_or_create(username=username)
        user.set_password("Test2026!")
        user.is_active = True
        user.save()

        agent = Agent.objects.filter(user=user).first()
        if not agent:
            matricule = self._next_matricule(prefix)
            Agent.objects.create(
                nom=prefix,
                prenom="Test",
                matricule=matricule,
                service=service,
                user=user,
                actif=True,
            )
            status = "Created"
        else:
            agent.service = service
            agent.actif = True
            agent.save()
            status = "Updated"

        return status, username, service.nom

    def _next_matricule(self, prefix):
        base = f"{prefix}-0001"
        if not Agent.objects.filter(matricule=base).exists():
            return base
        suffix = 1
        while True:
            suffix += 1
            matricule = f"{prefix}-{suffix:04d}"
            if not Agent.objects.filter(matricule=matricule).exists():
                return matricule
