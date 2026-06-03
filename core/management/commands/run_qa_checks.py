"""Run automated QA smoke checks (API, security headers, 404)."""

import io

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand
from django.test import Client

User = get_user_model()


class Command(BaseCommand):
    help = 'Run Print-Edge QA smoke checks via Django test client'

    def handle(self, *args, **options):
        client = Client(HTTP_HOST='localhost')
        failures = []
        passed = []

        def check(name, ok, detail=''):
            if ok:
                passed.append(name)
                self.stdout.write(self.style.SUCCESS(f'  PASS: {name}'))
            else:
                failures.append((name, detail))
                self.stdout.write(self.style.ERROR(f'  FAIL: {name} - {detail}'))

        def json_payload(response):
            if 'application/json' not in response.headers.get('Content-Type', ''):
                return None
            try:
                return response.json()
            except ValueError:
                return None

        self.stdout.write('Public pages...')
        for path in [
            '/', '/pricing/', '/services/', '/contact/',
            '/robots.txt', '/sitemap.xml', '/manifest.json',
            '/auth/login/', '/auth/register/',
        ]:
            response = client.get(path)
            check(f'GET {path}', response.status_code == 200, f'status={response.status_code}')

        response = client.get('/nonexistent-page-qa-test/')
        check('404 status', response.status_code == 404, f'status={response.status_code}')

        self.stdout.write('Auth redirects...')
        for path in ['/user/dashboard/', '/user/orders/new/', '/admin/dashboard/']:
            response = client.get(path)
            check(f'GET {path} anonymous', response.status_code in (302, 403), f'status={response.status_code}')

        self.stdout.write('API (unauthenticated)...')
        response = client.get('/api/price/?print_type=bw&sides=single&paper_size=A4&pages=1&copies=1')
        check('GET /api/price/', response.status_code == 200, f'status={response.status_code}')

        response = client.get('/api/admin/quick-search/?q=test')
        check('GET /api/admin/quick-search/ anonymous', response.status_code == 403, f'status={response.status_code}')

        response = client.get('/api/search/?q=test')
        payload = json_payload(response)
        check(
            'GET /api/search/ anonymous',
            payload is not None and payload.get('results') == [],
            f'status={response.status_code}, content_type={response.headers.get("Content-Type", "")}',
        )

        response = client.get('/api/walkin-search/?q=ab')
        check('GET /api/walkin-search/ anonymous', response.status_code == 403, f'status={response.status_code}')

        response = client.post('/api/cron/purge-files/')
        check('POST /api/cron/purge-files/ no secret', response.status_code == 401, f'status={response.status_code}')

        self.stdout.write('Upload validation...')
        from core.utils import validate_upload_file

        fake_pdf = SimpleUploadedFile('evil.pdf', b'not a real pdf', content_type='application/pdf')
        check('Fake PDF rejected', validate_upload_file(fake_pdf) is not None)

        double_ext = SimpleUploadedFile('doc.pdf.exe', b'%PDF-1.4 fake', content_type='application/pdf')
        check('Double extension rejected', validate_upload_file(double_ext) is not None)

        self.stdout.write('Security headers (home)...')
        response = client.get('/')
        for header in ('X-Content-Type-Options', 'X-Frame-Options', 'Referrer-Policy'):
            check(f'Header {header}', header in response, 'missing')

        self.stdout.write('Auth rate limit key...')
        from django.core.cache import cache

        cache.set('ratelimit:test', 1, 60)
        check('Cache backend', cache.get('ratelimit:test') == 1)

        admin = User.objects.filter(role='super_admin').first()
        if admin:
            client.force_login(admin)
            response = client.get('/api/admin/quick-search/?q=order')
            check('GET /api/admin/quick-search/ as admin', response.status_code == 200, f'status={response.status_code}')
            response = client.get('/api/search/?q=order')
            check('GET /api/search/ as admin', response.status_code == 200, f'status={response.status_code}')
            from core.pricing import calculate_order_price
            bw_double = calculate_order_price('bw', 'double', pages=11, copies=1)
            check('B&W double 11 pages = 18', float(bw_double['total']) == 18.0, f"got {bw_double['total']}")
            color_double = calculate_order_price('color', 'double', pages=11, copies=1)
            check('Color double 11 pages = 48', float(color_double['total']) == 48.0, f"got {color_double['total']}")
            response = client.get('/admin/dashboard/')
            check('GET /admin/dashboard/', response.status_code == 200, f'status={response.status_code}')
            response = client.get('/admin/files/')
            check('GET /admin/files/', response.status_code == 200, f'status={response.status_code}')
            response = client.get('/admin/display/')
            check('GET /admin/display/ removed', response.status_code == 404, f'status={response.status_code}')
        else:
            self.stdout.write(self.style.WARNING('  SKIP: no super_admin user - run seed_data first'))

        customer = User.objects.filter(email='qa_customer@test.local').first()
        if customer:
            customer_client = Client(HTTP_HOST='localhost')
            customer_client.force_login(customer)
            from core.models import Order

            response = customer_client.get('/user/dashboard/')
            check('GET /user/dashboard/ as customer', response.status_code == 200, f'status={response.status_code}')

            other_order = Order.objects.exclude(customer=customer).first()
            if other_order:
                response = customer_client.get(f'/user/orders/{other_order.pk}/')
                check('IDOR order detail', response.status_code == 404, f'status={response.status_code}')

            customer_client.logout()
            unverified = User.objects.filter(email='qa_unverified@test.local').first()
            if not unverified:
                from core.user_helpers import create_user_account
                unverified = create_user_account(
                    email='qa_unverified@test.local',
                    password='TestPass123!',
                    first_name='Unverified',
                    last_name='User',
                    phone='01700000099',
                    role='customer',
                    is_email_verified=False,
                )
            uv_client = Client(HTTP_HOST='localhost')
            uv_client.force_login(unverified)
            response = uv_client.post('/user/orders/new/', {'files_config': '[]'})
            check(
                'Unverified blocked from new order POST',
                response.status_code in (302, 403) and '/auth/verify' in (response.url or ''),
                f'status={response.status_code} url={response.url}',
            )

            if customer.is_email_verified:
                cust2 = Client(HTTP_HOST='localhost')
                cust2.force_login(customer)
                avatar = SimpleUploadedFile('avatar.png', self._tiny_png(), content_type='image/png')
                response = cust2.post(
                    '/user/profile/',
                    {'action': 'profile', 'first_name': customer.first_name},
                    FILES={'avatar': avatar},
                )
                check('Profile avatar POST', response.status_code in (302, 200), f'status={response.status_code}')
        else:
            self.stdout.write(self.style.WARNING('  SKIP: run seed_qa_users for customer tests'))

        if customer:
            cust_gate = Client(HTTP_HOST='localhost')
            cust_gate.force_login(customer)
            response = cust_gate.get('/admin/dashboard/')
            check('Customer blocked from admin', response.status_code in (302, 403), f'status={response.status_code}')

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Passed: {len(passed)}'))
        if failures:
            self.stdout.write(self.style.ERROR(f'Failed: {len(failures)}'))
            for name, detail in failures:
                self.stdout.write(f'  - {name}: {detail}')
            raise SystemExit(1)

        self.stdout.write(self.style.SUCCESS('All QA smoke checks passed.'))

    @staticmethod
    def _tiny_png():
        try:
            from PIL import Image
            buf = io.BytesIO()
            Image.new('RGBA', (8, 8), (20, 184, 166, 255)).save(buf, format='PNG')
            return buf.getvalue()
        except Exception:
            return (
                b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
                b'\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
                b'\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4'
                b'\x00\x00\x00\x00IEND\xaeB`\x82'
            )
