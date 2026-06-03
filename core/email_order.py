"""Order confirmation email sending via Brevo API."""

from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils import timezone

from .models import EmailLog
from .email_utils import send_brevo_email


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

    # Build tracking URL
    tracking_url = f"https://printedge.vercel.app/user/orders/{order.pk}/"

    # Render HTML template
    html_content = render_to_string('emails/order_confirmation.html', {
        'order': order,
        'tracking_url': tracking_url,
        'now': timezone.now()
    })
    text_content = strip_tags(html_content)

    success, result = send_brevo_email(recipient_email, subject, html_content, text_content)

    EmailLog.objects.create(
        recipient=recipient_email,
        subject=subject,
        body=text_content[:500] if text_content else '',
        status='sent' if success else 'failed',
        error_message='' if success else result,
    )

    return success