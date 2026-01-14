from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from .models import AuditLog

# Create your tests here.


class AuditLogAppendOnlyTests(TestCase):
    def test_auditlog_update_raises(self):
        user = get_user_model().objects.create_user(username="audit_user", password="testpass123")
        log = AuditLog.objects.create(user=user, action="LOGIN", target_repr="Test")
        log.target_repr = "Changed"
        with self.assertRaises(ValidationError):
            log.save()

    def test_auditlog_delete_raises(self):
        user = get_user_model().objects.create_user(username="audit_user2", password="testpass123")
        log = AuditLog.objects.create(user=user, action="LOGIN", target_repr="Test")
        with self.assertRaises(ValidationError):
            log.delete()
