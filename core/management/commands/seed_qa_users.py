"""Create role-based test accounts for QA (password: TestPass123!)."""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

QA_USERS = [
    ('qa_customer@test.local', 'customer', 'QA', 'Customer', '01700000001'),
    ('qa_operator@test.local', 'operator', 'QA', 'Operator', '01700000002'),
    ('qa_manager@test.local', 'manager', 'QA', 'Manager', '01700000003'),
    ('qa_admin@test.local', 'admin', 'QA', 'Admin', '01700000004'),
]


class Command(BaseCommand):
    help = 'Seed QA test users for each role (password: TestPass123!)'

    def handle(self, *args, **options):
        from core.user_helpers import create_user_account, set_user_password

        password = 'TestPass123!'
        for email, role, first, last, phone in QA_USERS:
            if User.objects.filter(email=email).exists():
                user = User.objects.get(email=email)
                user.role = role
                user.is_staff = role != 'customer'
                user.is_active = True
                user.is_email_verified = True
                if phone and user.phone != phone:
                    if not User.objects.filter(phone=phone).exclude(pk=user.pk).exists():
                        user.phone = phone
                user.save(update_fields=['role', 'is_staff', 'is_active', 'is_email_verified', 'phone'])
                set_user_password(user, password)
                self.stdout.write(f'Updated {email} ({role})')
            else:
                user = create_user_account(
                    email=email,
                    password=password,
                    first_name=first,
                    last_name=last,
                    phone=phone,
                    role=role,
                    is_email_verified=True,
                )
                user.is_staff = role != 'customer'
                user.save(update_fields=['is_staff'])
                self.stdout.write(self.style.SUCCESS(f'Created {email} ({role})'))

        self.stdout.write(self.style.SUCCESS('\nQA users ready. Password for all: TestPass123!'))
