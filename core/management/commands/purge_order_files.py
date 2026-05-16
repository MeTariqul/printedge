from django.core.management.base import BaseCommand

from core.order_files import purge_expired_order_files


class Command(BaseCommand):
    help = 'Delete order attachments past retention period after delivery.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Count eligible orders without deleting files.',
        )

    def handle(self, *args, **options):
        count = purge_expired_order_files(dry_run=options['dry_run'])
        if options['dry_run']:
            self.stdout.write(self.style.WARNING(f'Would purge {count} file(s).'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Purged {count} file(s).'))
