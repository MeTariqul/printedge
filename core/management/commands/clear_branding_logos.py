"""Remove uploaded SiteSettings logos from storage (legacy branding/)."""

from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand

from core.models import SiteSettings


class Command(BaseCommand):
    help = 'Clear legacy uploaded business logos from SiteSettings'

    def handle(self, *args, **options):
        site = SiteSettings.get()
        if site.logo and site.logo.name:
            try:
                site.logo.delete(save=False)
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f'Could not delete file: {exc}'))
        site.logo = None
        site.save(update_fields=['logo'])
        try:
            _, dirs, _ = default_storage.listdir('branding')
            for name in dirs:
                path = f'branding/{name}'
                if default_storage.exists(path):
                    default_storage.delete(path)
        except Exception:
            pass
        self.stdout.write(self.style.SUCCESS('Branding logos cleared.'))
