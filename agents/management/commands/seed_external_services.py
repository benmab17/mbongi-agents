from django.core.management.base import BaseCommand

from agents.models import Service


class Command(BaseCommand):
    help = "Seed external/embassy services in an idempotent way."

    def handle(self, *args, **options):
        names = [
            "ANR - Service extérieur",
            "Ambassade RDC - Belgique",
            "Ambassade RDC - France",
            "Ambassade RDC - USA",
            "Ambassade RDC - Afrique du Sud",
            "DGM",
            "DEMIAP",
        ]

        created = []
        updated = []

        for name in names:
            obj, was_created = Service.objects.get_or_create(nom=name)
            if was_created:
                created.append(name)
            else:
                updated.append(name)

        if created:
            self.stdout.write(self.style.SUCCESS("Created: " + ", ".join(created)))
        if updated:
            self.stdout.write(self.style.SUCCESS("Existing: " + ", ".join(updated)))
