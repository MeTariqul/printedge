"""Order attachment storage and retention."""

from django.utils import timezone

from .models import Order, SiteSettings
from .audit_helpers import log_audit


def apply_order_delivered(order):
    """Side effects when an order is marked delivered."""
    order.completed_at = timezone.now()
    if order.customer_id:
        customer = order.customer
        customer.total_spent += order.total_amount
        customer.save(update_fields=['total_spent'])
        customer.update_tier()
    elif order.walkin_customer_id:
        wc = order.walkin_customer
        wc.total_spent += order.total_amount
        wc.save(update_fields=['total_spent'])


def delete_order_file(order, *, actor=None, request=None, reason=''):
    """Remove attachment from storage and clear DB fields."""
    if not order.has_stored_file:
        return False
    old_name = order.file_name or order.file.name
    try:
        order.file.delete(save=False)
    except Exception:
        pass
    order.file = None
    order.file_name = None
    order.file_size_bytes = None
    order.file_deleted_at = timezone.now()
    order.save(update_fields=['file', 'file_name', 'file_size_bytes', 'file_deleted_at'])
    if request:
        log_audit(
            request,
            'ORDER_FILE_DELETED',
            'Order',
            order.pk,
            old_value=old_name,
            new_value=reason or 'manual',
        )
    return True


def orders_eligible_for_purge():
    days = SiteSettings.get().auto_delete_files_days
    cutoff = timezone.now() - timezone.timedelta(days=days)
    return Order.objects.filter(
        status='delivered',
        completed_at__isnull=False,
        completed_at__lte=cutoff,
        file_deleted_at__isnull=True,
    ).exclude(file='')


def purge_expired_order_files(*, dry_run=False, request=None):
    qs = orders_eligible_for_purge()
    count = 0
    for order in qs.iterator():
        if dry_run:
            count += 1
            continue
        if delete_order_file(order, request=request, reason='auto_retention'):
            count += 1
    if request and count and not dry_run:
        log_audit(request, 'PURGE_ORDER_FILES', 'System', '', new_value=str(count))
    return count


def save_order_file_metadata(order, uploaded_file):
    if uploaded_file:
        order.file_name = uploaded_file.name
        order.file_size_bytes = uploaded_file.size
