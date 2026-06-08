"""Email verification tokens and Brevo sending."""

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import strip_tags
from django.utils import timezone

from .models import EmailLog
from .email_utils import send_db_email


def build_verification_url(request, user):
    token = default_token_generator.make_token(user)
    path = reverse('auth_verify_email', kwargs={'uid': user.pk, 'token': token})
    return request.build_absolute_uri(path)


def send_verification_email(request, user):
    if user.is_email_verified:
        return True
    if user.role != 'customer':
        user.is_email_verified = True
        user.save(update_fields=['is_email_verified'])
        return True

    link = build_verification_url(request, user)
    subject = 'Verify your email – PrintEdge'
    to_email = user.email

    success, result = send_db_email('verify_email', to_email, {
        'user': user,
        'verification_url': link,
        'now': timezone.now()
    })

    return success


def verify_user_token(user, token):
    if default_token_generator.check_token(user, token):
        if not user.is_email_verified:
            user.is_email_verified = True
            user.is_active = True
            user.save(update_fields=['is_email_verified', 'is_active'])
        return True
    return False


def customer_needs_verification(user):
    return (
        user.is_authenticated
        and user.role == 'customer'
        and not user.is_email_verified
    )