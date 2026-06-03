"""Order attachment storage and retention."""

from django.db.models import Q
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


def _delete_file_field(file_field):
    if file_field and file_field.name:
        try:
            file_field.delete(save=False)
        except Exception:
            pass


def _order_has_stored_files(order):
    if order.file and order.file.name:
        return True
    for of in order.order_files.all():
        if of.file and of.file.name:
            return True
    return False


def delete_single_order_file(order_file, *, request=None, reason='admin_files_tab'):
    """Remove one OrderFile attachment from storage; keep order row."""
    order = order_file.order
    old_name = order_file.file_name or (order_file.file.name if order_file.file else '')
    if order_file.file and order_file.file.name:
        _delete_file_field(order_file.file)
    order_file.file = None
    order_file.save(update_fields=['file'])

    if order_file.is_primary or (order.file and order.file.name):
        if order.file and order.file.name:
            _delete_file_field(order.file)
        order.file = None
        order.file_name = None
        order.file_size_bytes = None
        order.save(update_fields=['file', 'file_name', 'file_size_bytes'])

    if not _order_has_stored_files(order):
        order.file_deleted_at = timezone.now()
        note = 'Files missing (all attachments removed).'
        if order.admin_notes:
            order.admin_notes = f'{order.admin_notes}\n{note}'
        else:
            order.admin_notes = note
        order.save(update_fields=['file_deleted_at', 'admin_notes'])

    if request:
        log_audit(
            request,
            'ORDER_FILE_DELETED',
            'OrderFile',
            order_file.pk,
            old_value=old_name,
            new_value=reason,
        )
    return True


def delete_order_file(order, *, actor=None, request=None, reason=''):
    """Remove all attachments from storage and clear DB fields."""
    changed = False
    for of in order.order_files.all():
        if of.file and of.file.name:
            _delete_file_field(of.file)
            of.file = None
            of.save(update_fields=['file'])
            changed = True
    if order.has_stored_file:
        old_name = order.file_name or order.file.name
        _delete_file_field(order.file)
        order.file = None
        order.file_name = None
        order.file_size_bytes = None
        changed = True
        if request:
            log_audit(
                request,
                'ORDER_FILE_DELETED',
                'Order',
                order.pk,
                old_value=old_name,
                new_value=reason or 'manual',
            )
    if changed or order.file_deleted_at is None:
        order.file_deleted_at = timezone.now()
        order.save(update_fields=['file', 'file_name', 'file_size_bytes', 'file_deleted_at'])
    return changed


def orders_eligible_for_purge():
    days = SiteSettings.get().auto_delete_files_days
    cutoff = timezone.now() - timezone.timedelta(days=days)
    return Order.objects.filter(
        status='delivered',
        completed_at__isnull=False,
        completed_at__lte=cutoff,
        file_deleted_at__isnull=True,
    ).filter(
        Q(file__gt='') | Q(order_files__file__gt=''),
    ).distinct()


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
