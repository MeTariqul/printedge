import datetime
from django.test import TestCase
from django.utils import timezone
from core.models import Notification, User
from django.core.management import call_command

class NotificationCleanupTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(email="test@example.com", username="testuser")
        
        # Unread notification (31 days old) - should be deleted
        n1 = Notification.objects.create(
            recipient=self.user,
            verb="Test unread old",
            is_read=False
        )
        n1.created_at = timezone.now() - datetime.timedelta(days=31)
        n1.save()

        # Unread notification (20 days old) - should NOT be deleted
        n2 = Notification.objects.create(
            recipient=self.user,
            verb="Test unread new",
            is_read=False
        )
        n2.created_at = timezone.now() - datetime.timedelta(days=20)
        n2.save()

        # Read notification (8 days old) - should be deleted
        n3 = Notification.objects.create(
            recipient=self.user,
            verb="Test read old",
            is_read=True
        )
        n3.created_at = timezone.now() - datetime.timedelta(days=8)
        n3.save()

        # Read notification (5 days old) - should NOT be deleted
        n4 = Notification.objects.create(
            recipient=self.user,
            verb="Test read new",
            is_read=True
        )
        n4.created_at = timezone.now() - datetime.timedelta(days=5)
        n4.save()

    def test_cleanup_notifications(self):
        self.assertEqual(Notification.objects.count(), 4)
        
        call_command('cleanup_notifications')
        
        remaining = Notification.objects.all()
        self.assertEqual(remaining.count(), 2)
        
        verbs = [n.verb for n in remaining]
        self.assertIn("Test unread new", verbs)
        self.assertIn("Test read new", verbs)
