import logging
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import Notification

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Cleans up old notifications (read > 7 days, unread > 30 days)'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Dry run without actually deleting anything.')

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        now = timezone.now()
        
        read_threshold = now - timedelta(days=7)
        unread_threshold = now - timedelta(days=30)
        
        old_read = Notification.objects.filter(is_read=True, created_at__lt=read_threshold)
        old_unread = Notification.objects.filter(is_read=False, created_at__lt=unread_threshold)
        
        read_count = old_read.count()
        unread_count = old_unread.count()
        
        if not dry_run:
            old_read.delete()
            old_unread.delete()
            self.stdout.write(self.style.SUCCESS(f'Successfully deleted {read_count} old read notifications and {unread_count} old unread notifications.'))
        else:
            self.stdout.write(self.style.SUCCESS(f'[DRY RUN] Would delete {read_count} old read notifications and {unread_count} old unread notifications.'))
