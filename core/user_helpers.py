"""User creation and password helpers."""

from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


def set_user_password(user, raw_password):
    user.set_password(raw_password)
    user.password_plain = ''
    user.save(update_fields=['password', 'password_plain'])


def create_user_account(
    *,
    email,
    password,
    first_name='',
    last_name='',
    phone='',
    role='customer',
    is_active=None,
    is_email_verified=None,
):
    email = email.strip().lower()
    if User.objects.filter(email=email).exists():
        raise ValueError('Email already registered.')
    if phone and User.objects.filter(phone=phone).exists():
        raise ValueError('Phone already registered.')
    username = email.split('@')[0]
    base = username
    counter = 1
    while User.objects.filter(username=username).exists():
        username = f'{base}{counter}'
        counter += 1

    # Check if email verification is required
    from .models import SiteSettings
    require_verification = SiteSettings.get().require_email_verification
    if is_active is None:
        is_active = not require_verification or role != 'customer'
    if is_email_verified is None:
        is_email_verified = not require_verification or role != 'customer'

    user = User(
        username=username,
        email=email,
        first_name=first_name.strip()[:50],
        last_name=last_name.strip()[:50],
        phone=phone.strip()[:20] if phone else '',
        role=role,
        is_active=is_active,
        is_email_verified=is_email_verified,
        date_joined=timezone.now(),
    )
    user.password_plain = ''
    user.set_password(password)
    user.save()
    return user


def validate_password_strength(password):
    if len(password) < 8:
        return 'Password must be at least 8 characters.'
    return None
