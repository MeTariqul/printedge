"""Unified order creation service — shared by online and walk-in flows."""
import json
from decimal import Decimal

from django.core.files.base import ContentFile
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.utils import timezone

from .models import (
    Order, OrderFile, OrderFilePageRange, OrderStatusLog,
    SiteSettings, Coupon, WalkInCustomer, Service,
)
from .frontend_views import extract_zip_files
from .order_line_items import parse_files_config, create_order_with_files, detect_pages_for_upload
from .pricing import calculate_order_from_files
from .utils import validate_upload_file
from .notifications import notify_new_online_order, notify_new_walkin_order


class OrderCreationError(Exception):
    pass


def process_uploaded_files(request_files):
    """Extract ZIPs, validate individual files, return list of file uploads."""
    uploads = []
    for f in request_files:
        if f.name.lower().endswith('.zip'):
            zip_files, zip_err = extract_zip_files(f)
            if zip_err:
                raise OrderCreationError(zip_err)
            for name, buf, size in zip_files:
                uploads.append(ContentFile(buf.getvalue(), name=name))
        else:
            err = validate_upload_file(f)
            if err:
                raise OrderCreationError(err)
            uploads.append(f)
    return uploads


def align_files_config(uploads, files_config):
    """Ensure files_config has entries matching uploads, with detected pages."""
    while len(files_config) < len(uploads):
        idx = len(files_config)
        uploads_cfg = uploads[idx] if idx < len(uploads) else None
        pages = detect_pages_for_upload(uploads_cfg) if uploads_cfg else 1
        files_config.append({
            'print_type': 'bw', 'sides': 'single', 'paper_size': 'A4',
            'copies': 1, 'pages_detected': pages, 'ranges': [],
        })

    for i, cfg in enumerate(files_config[:len(uploads)]):
        cfg['file_name'] = getattr(uploads[i], 'name', f'file_{i}')
        if not cfg.get('pages_detected') and not cfg.get('pages_override'):
            cfg['pages_detected'] = detect_pages_for_upload(uploads[i])
        cfg['pages'] = int(cfg.get('pages_override') or cfg.get('pages_detected') or 1)

    return files_config


def resolve_coupon(code):
    """Look up and validate coupon code. Returns (coupon_obj, error_message)."""
    if not code:
        return None, None
    try:
        obj = Coupon.objects.get(code=code)
        if not obj.is_valid:
            return None, 'Coupon is invalid or expired.'
        return obj, None
    except Coupon.DoesNotExist:
        return None, 'Coupon not found.'


def calculate_breakdown(files_config, addon_ids, is_urgent, coupon_obj, tier_pct, manual_discount, urgent_percent):
    """Calculate pricing. Returns (breakdown, coupon_obj) — coupon may be removed if min order not met."""
    try:
        breakdown = calculate_order_from_files(
            files_config, addon_ids=addon_ids, is_urgent=is_urgent,
            coupon_obj=coupon_obj, tier_discount_pct=tier_pct,
            manual_discount=manual_discount, urgent_percent=urgent_percent,
        )

        if coupon_obj and breakdown.get('total') is not None:
            subtotal = (breakdown.get('base_price', Decimal('0'))
                        + breakdown.get('addons_price', Decimal('0'))
                        + breakdown.get('urgent_surcharge', Decimal('0')))
            if coupon_obj.min_order_amount is not None and subtotal < coupon_obj.min_order_amount:
                breakdown = calculate_order_from_files(
                    files_config, addon_ids=addon_ids, is_urgent=is_urgent,
                    coupon_obj=None, tier_discount_pct=tier_pct,
                    manual_discount=manual_discount, urgent_percent=urgent_percent,
                )
                return breakdown, None, f'Minimum order amount of ৳{coupon_obj.min_order_amount} required for this coupon.'

        return breakdown, coupon_obj, None
    except ValueError as exc:
        raise OrderCreationError(str(exc))


def get_primary_config(files_config):
    """Return first config entry or sensible defaults."""
    if files_config:
        return files_config[0]
    return {
        'print_type': 'bw', 'sides': 'single', 'paper_size': 'A4',
        'pages': 1, 'copies': 1,
    }


@transaction.atomic
def finalize_order(order_kwargs, files_config, uploads, breakdown, addon_ids, promo_obj):
    if uploads:
        uploaded_pairs = [('files', u, getattr(u, 'name', '')) for u in uploads]
        order = create_order_with_files(
            order_kwargs=order_kwargs,
            uploaded_files=uploaded_pairs,
            files_config=files_config[:len(uploads)],
            breakdown=breakdown,
            addon_ids=addon_ids,
        )
    else:
        order = Order.objects.create(**order_kwargs)
        order.base_price = breakdown['base_price']
        order.addons_price = breakdown['addons_price']
        order.urgent_surcharge = breakdown['urgent_surcharge']
        order.discount_amount = breakdown['total_discount']
        order.total_amount = breakdown['total']
        order.save()
        if addon_ids:
            order.addons.set(addon_ids)

    if promo_obj:
        promo_obj.used_count += 1
        promo_obj.save(update_fields=['used_count'])

    return order


def place_online_order(request):
    """Full online order flow for logged-in customers."""
    from .email_verification import customer_needs_verification
    from .email_order import send_order_confirmation_email

    if customer_needs_verification(request.user):
        raise OrderCreationError('Please verify your email before placing an order.')

    site = SiteSettings.get()
    if not site.accepting_orders:
        raise OrderCreationError('We are temporarily not accepting new orders.')

    service_id = request.POST.get('service_id')
    preselected_service = None
    if service_id:
        try:
            preselected_service = Service.objects.get(pk=service_id)
        except Service.DoesNotExist:
            pass

    service_requires_file = preselected_service and preselected_service.requires_file
    files_config = parse_files_config(request.POST.get('files_config', '[]'))
    is_urgent = request.POST.get('is_urgent') == 'on'
    addon_ids = request.POST.getlist('addons')
    instructions = request.POST.get('special_instructions', '')[:500]
    fulfillment_type = request.POST.get('fulfillment_type', 'pickup')
    if fulfillment_type not in ('pickup', 'delivery'):
        fulfillment_type = 'pickup'
    delivery_address = request.POST.get('delivery_address', '').strip()[:500]
    delivery_phone = request.POST.get('delivery_contact_phone', '').strip()[:20]

    if fulfillment_type == 'delivery' and not delivery_address:
        raise OrderCreationError('Please enter a delivery address.')

    uploads = process_uploaded_files(request.FILES.getlist('files'))

    if service_requires_file and not uploads:
        raise OrderCreationError('Please upload at least one file.')

    files_config = align_files_config(uploads, files_config)

    promo_obj, coupon_error = resolve_coupon(request.POST.get('promo_code', '').strip().upper())
    if coupon_error:
        raise OrderCreationError(coupon_error)

    tier_pct = Decimal(request.user.tier_discount())
    breakdown, promo_obj, coupon_warning = calculate_breakdown(
        files_config[:len(uploads)], addon_ids, is_urgent, promo_obj,
        tier_pct=tier_pct, manual_discount=Decimal('0'),
        urgent_percent=site.urgent_surcharge_percent,
    )

    primary = get_primary_config(files_config)
    order_kwargs = {
        'source': 'online',
        'customer': request.user,
        'print_type': primary.get('print_type', 'bw'),
        'sides': primary.get('sides', 'single'),
        'paper_size': primary.get('paper_size', 'A4'),
        'pages': primary.get('pages', 1),
        'copies': primary.get('copies', 1),
        'is_urgent': is_urgent,
        'special_instructions': instructions,
        'fulfillment_type': fulfillment_type,
        'delivery_address': delivery_address if fulfillment_type == 'delivery' else '',
        'delivery_contact_phone': delivery_phone if fulfillment_type == 'delivery' else '',
        'coupon': promo_obj,
        'created_by': request.user,
        'service': preselected_service,
    }

    order = finalize_order(order_kwargs, files_config, uploads, breakdown, addon_ids, promo_obj)

    OrderStatusLog.objects.create(
        order=order, new_status='pending',
        changed_by=request.user, note='Order placed by customer.',
    )
    request.user.total_orders += 1
    request.user.save(update_fields=['total_orders'])
    notify_new_online_order(order)
    send_order_confirmation_email(request, order)

    return order, coupon_warning


def place_walkin_order(request):
    """Full walk-in POS order flow for staff."""
    from .walkin_helpers import get_or_create_walkin_customer
    from .email_order import send_order_confirmation_email

    site = SiteSettings.get()

    walkin_id = request.POST.get('walkin_customer_id')
    if walkin_id:
        walkin = WalkInCustomer.objects.get(pk=walkin_id)
    else:
        name = request.POST.get('customer_name', '').strip()
        phone = request.POST.get('customer_phone', '').strip()
        walkin = get_or_create_walkin_customer(name=name, phone=phone)

    files_config = parse_files_config(request.POST.get('files_config', '[]'))
    is_urgent = request.POST.get('is_urgent') == 'on'
    is_physical = request.POST.get('is_physical_document') == 'on'
    addon_ids = request.POST.getlist('addons')
    manual_discount = Decimal(request.POST.get('manual_discount', '0') or '0')
    payment_method = request.POST.get('payment_method', 'Cash')
    amount_paid = Decimal(request.POST.get('amount_paid', '0') or '0')

    uploads = process_uploaded_files(request.FILES.getlist('files'))

    if not uploads and not is_physical:
        raise OrderCreationError('Upload at least one file or mark as physical document.')

    physical_description = request.POST.get('physical_description', '').strip()

    if is_physical and not uploads:
        physical_pages = max(1, int(request.POST.get('physical_pages', 1) or 1))
        physical_print_type = request.POST.get('physical_print_type', 'bw')
        physical_sides = request.POST.get('physical_sides', 'single')
        physical_copies = max(1, int(request.POST.get('physical_copies', 1) or 1))
        files_config = [{
            'print_type': physical_print_type,
            'sides': physical_sides,
            'paper_size': 'A4',
            'copies': physical_copies,
            'pages': physical_pages,
            'pages_detected': physical_pages,
            'file_name': physical_description or 'Physical document',
            'ranges': [],
        }]
    elif uploads:
        files_config = align_files_config(uploads, files_config)

    promo_obj, coupon_error = resolve_coupon(request.POST.get('promo_code', '').strip().upper())
    if coupon_error:
        raise OrderCreationError(coupon_error)

    breakdown, promo_obj, coupon_warning = calculate_breakdown(
        files_config if (is_physical and not uploads) else files_config[:len(uploads)],
        addon_ids, is_urgent, promo_obj,
        tier_pct=Decimal('0'), manual_discount=manual_discount,
        urgent_percent=site.urgent_surcharge_percent,
    )

    payment_status = 'paid' if amount_paid >= breakdown['total'] else (
        'partial' if amount_paid > 0 else 'unpaid'
    )

    primary = get_primary_config(files_config)
    order_kwargs = {
        'source': 'offline',
        'walkin_customer': walkin,
        'print_type': primary.get('print_type', 'bw'),
        'sides': primary.get('sides', 'single'),
        'paper_size': primary.get('paper_size', 'A4'),
        'pages': primary.get('pages', 1),
        'copies': primary.get('copies', 1),
        'is_urgent': is_urgent,
        'is_physical_document': is_physical,
        'special_instructions': physical_description if is_physical else '',
        'discount_reason': request.POST.get('discount_reason', ''),
        'coupon': promo_obj,
        'payment_method': payment_method,
        'amount_paid': amount_paid,
        'payment_status': payment_status,
        'created_by': request.user,
    }

    order = finalize_order(order_kwargs, files_config, uploads, breakdown, addon_ids, promo_obj)

    OrderStatusLog.objects.create(
        order=order, new_status='pending',
        changed_by=request.user,
        note=f'Walk-in order created by {request.user.display_name}.',
    )
    walkin.total_orders += 1
    walkin.last_visit = timezone.now()
    walkin.save(update_fields=['total_orders', 'last_visit'])
    notify_new_walkin_order(order, request.user)
    send_order_confirmation_email(request, order)

    return order, coupon_warning, walkin


def build_order_form_context():
    """Shared context for order form templates."""
    from .pricing_options import get_active_pricing_options
    from .models import AddonService, Service
    return {
        'addons': AddonService.objects.filter(is_active=True),
        'pricing_options': get_active_pricing_options(),
        'services': Service.objects.filter(is_active=True).prefetch_related('variants'),
    }
