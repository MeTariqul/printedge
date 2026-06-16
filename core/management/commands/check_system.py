from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import connections
from django.db.utils import OperationalError
import os

class Command(BaseCommand):
    help = 'Checks system health, environment variables, and database connectivity'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting System Check...'))
        
        # 1. Check Database
        self.stdout.write('Checking database connection...')
        try:
            conn = connections['default']
            conn.ensure_connection()
            self.stdout.write(self.style.SUCCESS('  Database: OK'))
        except OperationalError as e:
            self.stdout.write(self.style.ERROR(f'  Database: FAILED ({e})'))
            
        # 2. Check Critical Settings
        self.stdout.write('Checking critical environment variables...')
        critical_settings = ['SECRET_KEY', 'DATABASE_URL', 'SUPABASE_URL', 'SUPABASE_ANON_KEY', 'BREVO_API_KEY']
        
        for setting in critical_settings:
            # Check os.environ first, then settings
            if os.environ.get(setting) or getattr(settings, setting, None):
                self.stdout.write(self.style.SUCCESS(f'  {setting}: Configured'))
            else:
                self.stdout.write(self.style.WARNING(f'  {setting}: Missing or empty'))
                
        # 3. Check Debug Mode
        if settings.DEBUG:
            self.stdout.write(self.style.WARNING('  DEBUG: True (Warning: Do not use in production!)'))
        else:
            self.stdout.write(self.style.SUCCESS('  DEBUG: False (Production ready)'))
            
        self.stdout.write(self.style.SUCCESS('System Check Complete.'))
