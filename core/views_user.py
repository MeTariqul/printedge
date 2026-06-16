from django.db.models import Sum, Count, Q, F
from django.db.models.functions import TruncDay
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.timesince import timesince
import json
from datetime import timedelta
from decimal import Decimal

from .models import (
    User, WalkInCustomer, Order, OrderFile, InventoryItem,
    AddonService, Expense, AuditLog,
    Notification, OrderStatusLog, SiteSettings, Coupon,
    Service, ServiceVariant, EmailLog,
)
from .decorators import login_required_custom, admin_required, superadmin_required, permission_required
from .frontend_views import extract_zip_files
from .pricing import calculate_order_price, calculate_order_from_files
from .order_line_items import parse_files_config, create_order_with_files, detect_pages_for_upload
from .utils import safe_int, validate_upload_file, validate_payment_screenshot, get_payment_methods
from .audit_helpers import log_audit
from .user_helpers import create_user_account, set_user_password, validate_password_strength
from .order_files import apply_order_delivered, delete_order_file, save_order_file_metadata
from .storage import supabase_storage_enabled, supabase_project_url
from .system_utils import get_database_status
from .page_detection import detect_pages
from .pricing_options import get_active_pricing_options
from .notifications import (
    notify_staff_of_new_user, notify_new_online_order, notify_order_status_change, notify_new_walkin_order,
    notify_approve_user, notify_payment_submitted, notify_payment_approved, notify_payment_rejected,
)





@login_required_custom
def user_dashboard(request):
    orders = Order.objects.filter(customer=request.user).order_by('-created_at')
    active = orders.filter(status__in=['pending', 'confirmed', 'printing', 'quality_check', 'ready'])
    today = timezone.now().date()
    month_start = today.replace(day=1)
    stats = {
        'total_orders': orders.count(),
        'orders_this_month': orders.filter(created_at__date__gte=month_start).count(),
        'active_count': active.count(),
        'pending_count': orders.filter(status='pending').count(),
        'completed_count': orders.filter(status='delivered').count(),
        'total_spent': orders.filter(status='delivered').aggregate(s=Sum('total_amount'))['s'] or 0,
    }
    status_steps = [
        ('pending', 'Pending', 'bi-hourglass-split'),
        ('confirmed', 'Confirmed', 'bi-check-lg'),
        ('printing', 'Printing', 'bi-printer-fill'),
        ('quality_check', 'QC', 'bi-eye-fill'),
        ('ready', 'Ready', 'bi-bag-check-fill'),
    ]
    active_order = active.first()
    passed_statuses = []
    if active_order:
        status_order = ['pending', 'confirmed', 'printing', 'quality_check', 'ready']
        current_idx = status_order.index(active_order.status) if active_order.status in status_order else -1
        passed_statuses = status_order[:current_idx]
    return render(request, 'user/dashboard.html', {
        'orders': orders[:5],
        'active_order': active_order,
        'stats': stats,
        'status_steps': status_steps,
        'passed_statuses': passed_statuses,
    })


def _order_form_context():
    return {
        'addons': AddonService.objects.filter(is_active=True),
        'pricing_options': get_active_pricing_options(),
        'services': Service.objects.filter(is_active=True).prefetch_related('variants'),
    }

def public_services(request):
    services = Service.objects.filter(is_active=True).prefetch_related('variants').order_by('category', 'name')
    return render(request, 'public/services.html', {'services': services})


@login_required_custom
def user_new_order(request):
    from .email_verification import customer_needs_verification
    from .models import Service
    if customer_needs_verification(request.user):
        messages.warning(request, 'Please verify your email before placing an order.')
        return redirect('auth_verify_pending')
    site = SiteSettings.get()
    ctx = _order_form_context()
    ctx['accepting_orders'] = site.accepting_orders
    
    service_id = request.GET.get('service')
    if service_id:
        try:
            ctx['preselected_service'] = Service.objects.get(pk=service_id)
        except Service.DoesNotExist:
            pass
    else:
        if request.method == 'GET':
            messages.info(request, 'Please select a service first.')
            return redirect('public_services_page')
    preselected_service = ctx.get('preselected_service')
    service_requires_file = preselected_service and preselected_service.requires_file
    ctx['service_requires_file'] = service_requires_file
    ctx['show_service_notes'] = preselected_service and not service_requires_file
    note_categories = ['stationery', 'binding', 'lamination']
    ctx['note_categories'] = note_categories
    if request.method == 'POST':
        if not site.accepting_orders:
            messages.error(request, 'We are temporarily not accepting new orders. Please check back later.')
            return render(request, 'user/new_order.html', ctx)

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
            messages.error(request, 'Please enter a delivery address.')
            return render(request, 'user/new_order.html', ctx)

        from django.core.files.base import ContentFile
        uploads = []
        for f in request.FILES.getlist('files'):
            if f.name.lower().endswith('.zip'):
                zip_files, zip_err = extract_zip_files(f)
                if zip_err:
                    messages.error(request, zip_err)
                    return render(request, 'user/new_order.html', ctx)
                for name, buf, size in zip_files:
                    uploads.append(ContentFile(buf.getvalue(), name=name))
            else:
                err = validate_upload_file(f)
                if err:
                    messages.error(request, err)
                    return render(request, 'user/new_order.html', ctx)
                uploads.append(f)

        if service_requires_file and not uploads:
            messages.error(request, 'Please upload at least one file.')
            return render(request, 'user/new_order.html', ctx)

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
            pages = int(cfg.get('pages_override') or cfg.get('pages_detected') or 1)
            cfg['pages'] = pages

        coupon_str = request.POST.get('promo_code', '').strip().upper()
        promo_obj = None
        if coupon_str:
            try:
                promo_obj = Coupon.objects.get(code=coupon_str)
                if not promo_obj.is_valid:
                    messages.error(request, 'Coupon is invalid or expired.')
                    promo_obj = None
            except Coupon.DoesNotExist:
                messages.error(request, 'Coupon not found.')

        tier_pct = Decimal(request.user.tier_discount())
        try:
            breakdown = calculate_order_from_files(
                files_config[:len(uploads)],
                addon_ids=addon_ids,
                is_urgent=is_urgent,
                coupon_obj=promo_obj,
                tier_discount_pct=tier_pct,
                urgent_percent=site.urgent_surcharge_percent,
            )
            
            if promo_obj and breakdown.get('total') is not None:
                subtotal_before_discount = breakdown.get('base_price', Decimal('0')) + breakdown.get('addons_price', Decimal('0')) + breakdown.get('urgent_surcharge', Decimal('0'))
                if promo_obj.min_order_amount is not None and subtotal_before_discount < promo_obj.min_order_amount:
                    min_amt = promo_obj.min_order_amount
                    breakdown = calculate_order_from_files(
                        files_config[:len(uploads)],
                        addon_ids=addon_ids,
                        is_urgent=is_urgent,
                        coupon_obj=None,
                        tier_discount_pct=tier_pct,
                        urgent_percent=site.urgent_surcharge_percent,
                    )
                    promo_obj = None
                    messages.warning(request, f'Minimum order amount of ৳{min_amt} required for this coupon.')
            
        except ValueError as exc:
            messages.error(request, str(exc))
            return render(request, 'user/new_order.html', ctx)

        primary = files_config[0]
        uploaded_pairs = [(f'files', u, getattr(u, 'name', '')) for u in uploads]
        try:
            order = create_order_with_files(
                order_kwargs={
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
                    'service': preselected_service if preselected_service else None,
                },
                uploaded_files=uploaded_pairs,
                files_config=files_config[:len(uploads)],
                breakdown=breakdown,
                addon_ids=addon_ids,
            )
        except (OSError, ImproperlyConfigured) as exc:
            messages.error(request, f'Could not upload your file. ({exc})')
            return render(request, 'user/new_order.html', ctx)
        except Exception as exc:
            messages.error(request, f'Order could not be placed: {exc}')
            return render(request, 'user/new_order.html', ctx)

        if promo_obj:
            promo_obj.used_count += 1
            promo_obj.save(update_fields=['used_count'])
        OrderStatusLog.objects.create(
            order=order, new_status='pending', changed_by=request.user, note='Order placed by customer.'
        )
        request.user.total_orders += 1
        request.user.save(update_fields=['total_orders'])
        notify_new_online_order(order)
        
        # Send order confirmation email
        from .email_order import send_order_confirmation_email
        send_order_confirmation_email(request, order)
        
        messages.success(request, f'Order {order.order_number} placed successfully!')
        return redirect('user_order_detail', pk=order.pk)
    return render(request, 'user/new_order.html', ctx)


@login_required_custom
def user_cancel_order(request, pk):
    if request.method != 'POST':
        return redirect('user_order_detail', pk=pk)
    order = get_object_or_404(Order, pk=pk, customer=request.user)
    if order.status != 'pending':
        messages.error(request, 'Only pending orders can be cancelled.')
        return redirect('user_order_detail', pk=pk)
    old = order.status
    order.status = 'cancelled'
    order.save(update_fields=['status', 'updated_at'])
    OrderStatusLog.objects.create(
        order=order, old_status=old, new_status='cancelled',
        changed_by=request.user, note='Cancelled by customer.',
    )
    from .notifications import notify_order_cancelled
    notify_order_cancelled(order, cancelled_by=request.user)
    messages.success(request, 'Order cancelled.')
    return redirect('user_order_detail', pk=pk)


@login_required_custom
def user_order_detail(request, pk):
    order = get_object_or_404(
        Order.objects.prefetch_related('order_files__page_ranges'),
        pk=pk, customer=request.user,
    )
    status_steps = [
        ('pending', 'Pending', 'bi-hourglass-split'),
        ('confirmed', 'Confirmed', 'bi-check-lg'),
        ('printing', 'Printing', 'bi-printer-fill'),
        ('quality_check', 'Quality Check', 'bi-eye-fill'),
        ('ready', 'Ready', 'bi-bag-check-fill'),
        ('delivered', 'Delivered', 'bi-check-circle-fill'),
    ]
    status_order = ['pending', 'confirmed', 'printing', 'quality_check', 'ready', 'delivered']
    current_idx = status_order.index(order.status) if order.status in status_order else -1
    passed_statuses = status_order[:current_idx] if current_idx > 0 else []
    return render(request, 'user/order_detail.html', {
        'order': order,
        'status_steps': status_steps,
        'passed_statuses': passed_statuses,
    })


@login_required_custom
def user_order_payment(request, pk):
    order = get_object_or_404(Order, pk=pk, customer=request.user)
    if order.payment_status in ('paid', 'pending_review'):
        messages.info(request, 'Payment has already been submitted or completed for this order.')
        return redirect('user_order_detail', pk=pk)
    if order.status == 'cancelled':
        messages.error(request, 'This order was cancelled.')
        return redirect('user_order_detail', pk=pk)

    site = SiteSettings.get()
    payment_methods = get_payment_methods(site)
    active_method = request.GET.get('method', 'bkash')
    valid_slugs = {m[0] for m in payment_methods}
    if active_method not in valid_slugs:
        active_method = next((m[0] for m in payment_methods if m[2]), 'bkash')

    if request.method == 'POST':
        screenshot = request.FILES.get('payment_screenshot')
        err = validate_payment_screenshot(screenshot)
        if err:
            messages.error(request, err)
            return redirect('user_order_payment', pk=pk)
        if hasattr(screenshot, 'seek'):
            screenshot.seek(0)

        method = request.POST.get('payment_method', active_method)
        if method not in valid_slugs:
            method = active_method
        method_labels = {'bkash': 'bKash', 'nagad': 'Nagad', 'rocket': 'Rocket'}

        if order.payment_screenshot:
            order.payment_screenshot.delete(save=False)
        order.payment_screenshot = screenshot
        order.payment_method = method_labels.get(method, method.title())
        order.payment_status = 'pending_review'
        order.payment_rejection_reason = ''
        try:
            order.save(update_fields=[
                'payment_screenshot', 'payment_method', 'payment_status', 'payment_rejection_reason', 'updated_at',
            ])
        except Exception as exc:
            messages.error(request, f'Could not save payment screenshot. ({exc})')
            return redirect('user_order_payment', pk=pk)
        notify_payment_submitted(order, request.user)
        messages.success(request, 'Payment screenshot submitted. We will review it shortly.')
        return redirect('user_order_detail', pk=pk)

    return render(request, 'user/order_payment.html', {
        'order': order,
        'payment_methods': payment_methods,
        'active_method': active_method,
    })


@login_required_custom
def user_orders(request):
    orders = Order.objects.filter(customer=request.user).order_by('-created_at')
    status_filter = request.GET.get('status', '').strip()
    if status_filter and status_filter in dict(Order.STATUS_CHOICES):
        orders = orders.filter(status=status_filter)
    from django.core.paginator import Paginator
    paginator = Paginator(orders, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'user/orders.html', {
        'orders': page_obj,
        'page_obj': page_obj,
        'status_filter': status_filter,
        'status_choices': Order.STATUS_CHOICES,
    })


# user_profile moved to frontend_views.py

