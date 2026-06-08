"""Order confirmation email sending via Brevo API."""

from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils import timezone
from django.contrib.sites.shortcuts import get_current_site

from .models import EmailLog
from .email_utils import send_db_email


def send_order_confirmation_email(request, order):
    """
    Send order confirmation email to the customer via Brevo API.
    For walk-in orders, we might not have an email, but we can still try if email exists.
    """
    # Determine recipient email
    if order.customer:
        recipient_email = order.customer.email
    elif order.walkin_customer and order.walkin_customer.email:
        recipient_email = order.walkin_customer.email
    else:
        return False

    subject = f'Order #{order.order_number} Confirmed – PrintEdge'

    # Build tracking URL using request or fallback
    if request:
        tracking_url = request.build_absolute_uri(f'/user/orders/{order.pk}/')
    else:
        tracking_url = f"https://printedge.vercel.app/user/orders/{order.pk}/"

    # Render HTML template
    success, result = send_db_email('order_confirmation', recipient_email, {
        'order': order,
        'tracking_url': tracking_url,
        'now': timezone.now()
    })

    return success