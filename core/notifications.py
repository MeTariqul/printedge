"""Notification utilities for PrintEdge."""

import logging
from typing import Optional
from django.urls import reverse
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from .models import User, Notification, Order, EmailLog
from .email_utils import send_brevo_email

logger = logging.getLogger(__name__)


def send_notification(recipient: User, verb: str, target_type: str, target_id: Optional[int], target_url: str, actor: Optional[User] = None, description: str = '', send_email: bool = True) -> None:
    """Create a notification and optionally send email via Brevo."""
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
        html_message = render_to_string('emails/notification.html', {
            'recipient': recipient,
            'verb': verb,
            'description': description,
            'target_url': target_url,
        })
        text_message = strip_tags(html_message)

        success, result = send_brevo_email(recipient.email, subject, html_message, text_message)

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
        )


def notify_new_online_order(order: Order) -> None:
    """Notify customer and staff about new online order."""
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
        )


def notify_new_walkin_order(order: Order, staff_member: User) -> None:
    """Notify staff about new walk-in order."""
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
        )


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
        )


def notify_payment_approved(order: Order, customer: User, approved_by: User) -> None:
    """Notify customer that payment was approved."""
    send_notification(
        recipient=customer,
        verb='approved payment',
        target_type='payment',
        target_id=order.id,
        target_url=reverse('user_order_detail', args=[order.id]),
        actor=approved_by,
        description=f'Payment for order #{order.order_number} approved',
    )


def notify_payment_rejected(order: Order, customer: User, rejected_by: User, reason: str = '') -> None:
    """Notify customer that payment was rejected."""
    send_notification(
        recipient=customer,
        verb='rejected payment',
        target_type='payment',
        target_id=order.id,
        target_url=reverse('user_order_detail', args=[order.id]),
        actor=rejected_by,
        description=f'Payment rejected. Reason: {reason}',
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