# -*- coding: utf-8 -*-
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create or update a CNS test user and assign to CNS group."

    def handle(self, *args, **options):
        username = "cns_test"
        password = "Test2026!"

        group, created_group = Group.objects.get_or_create(name="CNS")
        self.stdout.write(
            self.style.SUCCESS(
                f"Group CNS {'created' if created_group else 'existing'}"
            )
        )

        User = get_user_model()
        user, created_user = User.objects.get_or_create(username=username)
        user.set_password(password)
        user.is_active = True
        user.save()

        user.groups.clear()
        user.groups.add(group)

        self.stdout.write(
            self.style.SUCCESS(
                f"User {username} {'created' if created_user else 'updated'}"
            )
        )
        self.stdout.write(self.style.SUCCESS(f"Password set: {password}"))
        self.stdout.write(self.style.SUCCESS("CNS user ready"))
