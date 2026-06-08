"""Notification utilities for PrintEdge."""

import logging
from typing import Optional
from django.urls import reverse
from django.conf import settings
from django.utils import timezone
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from .models import User, Notification, Order, EmailLog
from .email_utils import send_brevo_email, send_db_email

logger = logging.getLogger(__name__)


def send_notification(recipient: User, verb: str, target_type: str, target_id: Optional[int], target_url: str, actor: Optional[User] = None, description: str = '', send_email: bool = True, toggle_name: Optional[str] = None) -> None:
    """Create a notification and optionally send email via Brevo."""
    from .models import SiteSettings

    if toggle_name:
        site = SiteSettings.get()
        toggle_map = {
            'send_email_on_registration': site.send_email_on_registration,
            'send_email_on_order_placed': site.send_email_on_order_placed,
            'send_email_on_status_change': site.send_email_on_status_change,
            'send_email_on_payment_approved': site.send_email_on_payment_approved,
            'send_email_on_payment_rejected': site.send_email_on_payment_rejected,
            'send_email_on_admin_approval': site.send_email_on_admin_approval,
        }
        if not toggle_map.get(toggle_name, True):
            send_email = False

    if not recipient or recipient.is_anonymous:
        return None

    notification = Notification.objects.create(
        recipient=recipient,
        actor=actor,
        verb=verb,
        target_type=target_type,
        target_id=target_id,
        target_url=target_url,
        description=description,
    )

    # Send email if recipient has notifications enabled and send_email is True
    if send_email and getattr(recipient, 'notification_email', True) and recipient.email:
        subject = f'PrintEdge - {verb}'
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@printedge.com')
        try:
            html_message = render_to_string('emails/notification.html', {
                'recipient': recipient,
                'verb': verb,
                'description': description,
                'target_url': target_url,
            })
            text_message = strip_tags(html_message)
            success, result = send_brevo_email(recipient.email, subject, html_message, text_message)
        except Exception as exc:
            logger.warning('Notification email failed for %s: %s', recipient.email, exc)
            success, result = False, str(exc)

        EmailLog.objects.create(
            recipient=recipient.email,
            subject=subject,
            body=text_message[:500] if text_message else '',
            status='sent' if success else 'failed',
            error_message='' if success else result,
        )

    return notification


def notify_staff_of_new_user(user: User) -> None:
    """Notify all staff when a new user registers."""
    staff = User.objects.filter(is_staff=True)
    for admin in staff:
        send_notification(
            recipient=admin,
            verb=f'{user.get_full_name() or user.email} signed up',
            target_type='user',
            target_id=user.id,
            target_url=reverse('admin_user_detail', args=[user.id]),
            actor=user,
            toggle_name='send_email_on_registration',
        )


def notify_new_online_order(order: Order) -> None:
    """Notify customer and staff about new online order."""
    from .models import SiteSettings
    site = SiteSettings.get()
    send_email_customer = site.send_email_on_order_placed
    send_email_staff = site.send_email_on_order_placed

    # Notify customer
    if order.customer:
        send_notification(
            recipient=order.customer,
            verb=f'placed order #{order.order_number}',
            target_type='order',
            target_id=order.id,
            target_url=reverse('user_order_detail', args=[order.id]),
            actor=order.customer,
            description=f'Order for {order.pages} pages × {order.copies} copies',
            send_email=send_email_customer,
            toggle_name='send_email_on_order_placed',
        )

    # Notify staff
    staff = User.objects.filter(is_staff=True)
    for admin in staff:
        send_notification(
            recipient=admin,
            verb=f'new order #{order.order_number}',
            target_type='order',
            target_id=order.id,
            target_url=reverse('admin_order_detail', args=[order.id]),
            actor=order.customer,
            description=f'{order.customer.get_full_name() or order.customer.email}',
            send_email=send_email_staff,
            toggle_name='send_email_on_order_placed',
        )


def notify_new_walkin_order(order: Order, staff_member: User) -> None:
    """Notify staff about new walk-in order."""
    from .models import SiteSettings
    site = SiteSettings.get()
    send_email = site.send_email_on_order_placed
    staff = User.objects.filter(is_staff=True)
    for admin in staff:
        send_notification(
            recipient=admin,
            verb=f'created walk-in order #{order.order_number}',
            target_type='order',
            target_id=order.id,
            target_url=reverse('admin_order_detail', args=[order.id]),
            actor=staff_member,
            description=f'Walk-in order created',
            send_email=send_email,
            toggle_name='send_email_on_order_placed',
        )


def notify_order_status_change(order: Order, old_status: str, changed_by: User) -> None:
    """Notify customer about order status change."""
    if order.customer:
        send_notification(
            recipient=order.customer,
            verb=f'updated to {order.get_status_display()}',
            target_type='order',
            target_id=order.id,
            target_url=reverse('user_order_detail', args=[order.id]),
            actor=changed_by,
            description=f'Status: {old_status} → {order.get_status_display()}',
            send_email=False,
        )
        # Send custom order update email
        tracking_url = reverse('user_order_detail', args=[order.id])
        send_db_email('order_update', order.customer.email, {
            'order': order,
            'tracking_url': tracking_url,
            'now': timezone.now()
        })


def notify_payment_submitted(order: Order, customer: User) -> None:
    """Notify staff that payment screenshot was uploaded."""
    staff = User.objects.filter(is_staff=True)
    for admin in staff:
        send_notification(
            recipient=admin,
            verb='submitted payment',
            target_type='order',
            target_id=order.id,
            target_url=reverse('admin_order_detail', args=[order.id]),
            actor=customer,
            description=f'Payment for order #{order.order_number}',
            send_email=False,
        )


def notify_payment_approved(order: Order, customer: User, approved_by: User, send_email: bool = True) -> None:
    """Notify customer that payment was approved."""
    send_notification(
        recipient=customer,
        verb='approved payment',
        target_type='payment',
        target_id=order.id,
        target_url=reverse('user_order_detail', args=[order.id]),
        actor=approved_by,
        description=f'Payment for order #{order.order_number} approved',
        send_email=send_email,
    )


def notify_payment_rejected(order: Order, customer: User, rejected_by: User, reason: str = '', send_email: bool = True) -> None:
    """Notify customer that payment was rejected."""
    send_notification(
        recipient=customer,
        verb='rejected payment',
        target_type='payment',
        target_id=order.id,
        target_url=reverse('user_order_detail', args=[order.id]),
        actor=rejected_by,
        description=f'Payment rejected. Reason: {reason}',
        send_email=send_email,
    )


def notify_order_cancelled(order: Order, cancelled_by: User, reason: str = '') -> None:
    """Notify customer that order was cancelled."""
    if order.customer:
        send_notification(
            recipient=order.customer,
            verb='cancelled',
            target_type='order',
            target_id=order.id,
            target_url=reverse('user_order_detail', args=[order.id]),
            actor=cancelled_by,
            description=f'Order #{order.order_number} cancelled. {reason}',
        )


def notify_low_stock(item) -> None:
    """Notify staff about low stock."""
    staff = User.objects.filter(is_staff=True)
    for admin in staff:
        send_notification(
            recipient=admin,
            verb=f'low stock on {item.name}',
            target_type='stock',
            target_id=item.id,
            target_url=reverse('admin_inventory'),
            description=f'Stock: {item.current_stock} (min: {item.min_alert_level})',
        )


def notify_file_purge(completed_count: int, deleted_bytes: int) -> None:
    """Notify staff about file purge."""
    staff = User.objects.filter(is_staff=True)
    for admin in staff:
        send_notification(
            recipient=admin,
            verb='file purge completed',
            target_type='system',
            target_id=None,
            target_url=reverse('admin_system_status'),
            description=f'Purged {completed_count} files ({deleted_bytes / 1024 / 1024:.1f} MB)',
        )


def notify_approve_user(user: User) -> None:
    """Notify user that their account has been manually approved by admin."""
    send_notification(
        recipient=user,
        verb='account approved',
        target_type='user',
        target_id=user.id,
        target_url=reverse('user_dashboard'),
        description='Your account was approved. You can now log in and place orders.',
    )