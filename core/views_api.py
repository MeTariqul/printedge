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
from .ratelimit import is_rate_limited





def api_price_calculate(request):
    """Live price calculator — GET (legacy) or POST JSON with files[]."""
    if is_rate_limited(request, 'api_price', 60, 60):
        return JsonResponse({'error': 'Too many requests'}, status=429)

    site = SiteSettings.get()
    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        files = data.get('files', [])
        addon_ids = data.get('addon_ids', [])
        variant_ids = data.get('variant_ids', [])
        is_urgent = data.get('is_urgent', False)
        manual_discount = Decimal(str(data.get('manual_discount', 0) or 0))
        promo_code = data.get('promo_code', '').strip().upper()
        coupon_obj = None
        if promo_code:
            coupon_obj = Coupon.objects.filter(code=promo_code, is_active=True).first()
            if not coupon_obj or not coupon_obj.is_valid:
                coupon_obj = None

        tier_pct = Decimal('0')
        if request.user.is_authenticated:
            tier_pct = Decimal(request.user.tier_discount())
        try:
            breakdown = calculate_order_from_files(
                files,
                addon_ids=addon_ids,
                is_urgent=is_urgent,
                manual_discount=manual_discount,
                coupon_obj=coupon_obj,
                tier_discount_pct=tier_pct,
                urgent_percent=site.urgent_surcharge_percent,
            )
            
            # Re-evaluate coupon min amount if any
            if coupon_obj and breakdown.get('total') is not None:
                subtotal_before_discount = breakdown.get('base_price', Decimal('0')) + breakdown.get('addons_price', Decimal('0')) + breakdown.get('urgent_surcharge', Decimal('0'))
                if coupon_obj.min_order_amount is not None and subtotal_before_discount < coupon_obj.min_order_amount:
                    # Coupon shouldn't apply
                    breakdown = calculate_order_from_files(
                        files,
                        addon_ids=addon_ids,
                        is_urgent=is_urgent,
                        manual_discount=manual_discount,
                        coupon_obj=None,
                        tier_discount_pct=tier_pct,
                        urgent_percent=site.urgent_surcharge_percent,
                    )
                    breakdown['coupon_error'] = f'Minimum order amount of ৳{coupon_obj.min_order_amount} required for this coupon.'
                else:
                    breakdown['coupon_applied'] = coupon_obj.code
                    
        except ValueError as exc:
            return JsonResponse({'error': str(exc)}, status=400)
        result = {k: float(v) if hasattr(v, 'quantize') else v for k, v in breakdown.items()}
        result['file_lines'] = [
            {kk: float(vv) if hasattr(vv, 'quantize') else vv for kk, vv in line.items()}
            for line in breakdown.get('file_lines', [])
        ]
        return JsonResponse(result)

    cache_key_parts = [
        request.GET.get('print_type', 'bw'),
        request.GET.get('sides', 'single'),
        request.GET.get('paper_size', 'A4'),
        str(safe_int(request.GET.get('pages', 1))),
        str(safe_int(request.GET.get('copies', 1))),
        '1' if request.GET.get('is_urgent') == '1' else '0',
        '|'.join(sorted(request.GET.getlist('addons'))),
    ]
    cache_key = f'price_calc:{"|".join(cache_key_parts)}'
    result = cache.get(cache_key)
    if result is None:
        breakdown = calculate_order_price(
            request.GET.get('print_type', 'bw'),
            request.GET.get('sides', 'single'),
            request.GET.get('paper_size', 'A4'),
            safe_int(request.GET.get('pages', 1)),
            safe_int(request.GET.get('copies', 1)),
            addon_ids=request.GET.getlist('addons'),
            is_urgent=request.GET.get('is_urgent') == '1',
            urgent_percent=site.urgent_surcharge_percent,
        )
        result = {k: float(v) if hasattr(v, 'quantize') else v for k, v in breakdown.items()}
        cache.set(cache_key, result, 60)
    return JsonResponse(result)


def api_walkin_search(request):
    if not request.user.is_authenticated or not request.user.is_admin_user:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    from .walkin_helpers import format_walkin_phone_display

    q = request.GET.get('q', '').strip()
    results = []
    if len(q) >= 2:
        customers = WalkInCustomer.objects.filter(
            Q(name__icontains=q) | Q(phone__icontains=q)
        )[:10]
        results = [{
            'id': c.pk,
            'name': c.name,
            'phone': format_walkin_phone_display(c.phone),
            'tier': c.tier,
            'orders_count': c.total_orders,
        } for c in customers]
    return JsonResponse({'results': results})


def api_order_status_update(request, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    if not request.user.is_authenticated or not request.user.is_admin_user:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    if request.user.is_readonly_staff:
        return JsonResponse({'error': 'Read-only access'}, status=403)
    order = get_object_or_404(Order, pk=pk)
    try:
        data = json.loads(request.body)
        new_status = data.get('status')
        valid = [s[0] for s in Order.STATUS_CHOICES]
        if new_status not in valid:
            return JsonResponse({'error': 'Invalid status'}, status=400)
        if new_status == 'cancelled' and order.status != 'pending':
            return JsonResponse({'error': 'Only pending orders can be cancelled'}, status=400)
        old_status = order.status
        order.status = new_status
        if new_status == 'delivered':
            apply_order_delivered(order)
        elif new_status == 'printing' and old_status != 'printing':
            from .inventory_helpers import deduct_inventory_for_order
            deduct_inventory_for_order(order, request.user)
            
        order.save()
        OrderStatusLog.objects.create(
            order=order, old_status=old_status,
            new_status=new_status, changed_by=request.user
        )
        notify_order_status_change(order, old_status, changed_by=request.user)
        return JsonResponse({'success': True, 'status': new_status})
    except (json.JSONDecodeError, KeyError, TypeError):
        return JsonResponse({'error': 'Invalid request data'}, status=400)


@login_required_custom
def api_validate_coupon(request):
    from .ratelimit import is_rate_limited
    if is_rate_limited(request, 'api_coupon', 10, 60):
        return JsonResponse({'valid': False, 'message': 'Too many requests. Try again later.'}, status=429)
    if request.method != 'POST':
        return JsonResponse({'valid': False, 'message': 'Method not allowed'}, status=405)
    try:
        data = json.loads(request.body)
        code = data.get('code', '').strip().upper()
        order_total = Decimal(str(data.get('order_total', 0)))

        if not code:
            return JsonResponse({'valid': False, 'message': 'Coupon code required'}, status=400)
            
        coupon = Coupon.objects.filter(code=code, is_active=True).first()
        if not coupon:
            return JsonResponse({'valid': False, 'message': 'Invalid or inactive coupon'}, status=400)
            
        if not coupon.is_valid:
            return JsonResponse({'valid': False, 'message': 'Coupon is expired or usage limit reached'}, status=400)
            
        if coupon.min_order_amount is not None and order_total < coupon.min_order_amount:
            return JsonResponse({'valid': False, 'message': f'Minimum order amount of ৳{coupon.min_order_amount} required'}, status=400)
            
        discount_amount = Decimal('0')
        if coupon.discount_type == 'percentage':
            discount_amount = (order_total * coupon.discount_value / 100).quantize(Decimal('0.01'))
            msg = f"Coupon applied: {coupon.discount_value}% off"
        else:
            discount_amount = coupon.discount_value
            msg = f"Coupon applied: ৳{coupon.discount_value} off"
            
        if discount_amount > order_total:
            discount_amount = order_total

        return JsonResponse({
            'valid': True,
            'discount_amount': float(discount_amount),
            'message': msg
        })
    except Exception as e:
        return JsonResponse({'valid': False, 'message': str(e)}, status=400)

@login_required_custom
def api_detect_pages(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    if is_rate_limited(request, 'api_detect', 30, 60):
        return JsonResponse({'error': 'Too many requests'}, status=429)
    uploaded = request.FILES.get('file')
    if not uploaded:
        return JsonResponse({'error': 'No file uploaded'}, status=400)
    err = validate_upload_file(uploaded)
    if err:
        return JsonResponse({'error': err}, status=400)
    result = detect_pages(uploaded)
    return JsonResponse(result)


def api_admin_quick_search(request):
    """Fast order search for admin header (orders only, max 10)."""
    if not request.user.is_authenticated or not request.user.is_admin_user:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'results': []})
    orders = Order.objects.filter(
        Q(order_number__icontains=q) |
        Q(customer__first_name__icontains=q) |
        Q(customer__last_name__icontains=q) |
        Q(customer__email__icontains=q) |
        Q(customer__phone__icontains=q) |
        Q(walkin_customer__name__icontains=q) |
        Q(walkin_customer__phone__icontains=q)
    ).select_related('customer', 'walkin_customer').order_by('-created_at')[:10]
    status_labels = dict(Order.STATUS_CHOICES)
    results = [{
        'order_number': o.order_number,
        'customer_name': o.customer_name,
        'status': status_labels.get(o.status, o.status),
        'total_price': float(o.total_amount),
        'url': f'/admin/orders/{o.pk}/',
    } for o in orders]
    return JsonResponse({'results': results})


def api_global_search(request):
    q = request.GET.get('q', '').strip()
    results = []
    if len(q) >= 2 and request.user.is_authenticated and request.user.is_admin_user:
        quick = api_admin_quick_search(request)
        if quick.status_code == 200:
            import json
            data = json.loads(quick.content)
            for item in data.get('results', []):
                results.append({
                    'type': 'order',
                    'title': item['order_number'],
                    'subtitle': f"{item['customer_name']} · {item['status']} · ৳{item['total_price']:.0f}",
                    'url': item['url'],
                    'icon': 'bi-cart',
                })
        users = User.objects.filter(
            Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q)
        )[:3]
        for u in users:
            results.append({
                'type': 'user',
                'title': u.display_name,
                'subtitle': u.email,
                'url': f'/admin/customers/online/{u.pk}/',
                'icon': 'bi-person',
            })
    return JsonResponse({'results': results})


def api_notifications(request):
    if not request.user.is_authenticated:
        return JsonResponse({'notifications': [], 'unread_count': 0})
    qs = request.user.notifications.select_related('actor').order_by('-created_at')[:15]
    unread = request.user.notifications.filter(is_read=False).count()
    return JsonResponse({
        'unread_count': unread,
        'notifications': [
            {
                'id': n.pk,
                'verb': n.verb,
                'target_type': n.target_type,
                'target_url': n.target_url or '#',
                'description': n.description or '',
                'is_read': n.is_read,
                'created_at': n.created_at.isoformat(),
                'actor_name': n.actor.get_full_name() or n.actor.email if n.actor else None,
            }
            for n in qs
        ],
    })


@login_required_custom
def user_notifications(request):
    """Full notifications page for users/admins."""
    if not request.user.is_authenticated:
        return redirect('auth_login_page')

    notifications = request.user.notifications.select_related('actor').all()
    status_filter = request.GET.get('status', '')
    if status_filter == 'unread':
        notifications = notifications.filter(is_read=False)
    elif status_filter == 'read':
        notifications = notifications.filter(is_read=True)

    if request.method == 'POST':
        if request.POST.get('action') == 'mark_all_read':
            notifications.filter(is_read=False).update(is_read=True)
            return redirect('user_notifications')
        elif request.POST.get('action') == 'delete_selected':
            ids = request.POST.getlist('selected_ids')
            Notification.objects.filter(recipient=request.user, pk__in=ids).delete()
            return redirect('user_notifications')

    from django.core.paginator import Paginator
    paginator = Paginator(notifications, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    return render(request, 'user/notifications.html', {
        'page_obj': page_obj,
        'unread_count': request.user.notifications.filter(is_read=False).count(),
        'status_filter': status_filter,
    })


def api_notification_mark_read(request, pk):
    if request.method != 'POST' or not request.user.is_authenticated:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    n = get_object_or_404(Notification, pk=pk, recipient=request.user)
    n.is_read = True
    n.save(update_fields=['is_read'])
    return JsonResponse({'success': True})


def api_notifications_read_all(request):
    if request.method != 'POST' or not request.user.is_authenticated:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return JsonResponse({'success': True})


def api_notification_delete(request, pk):
    if request.method != 'DELETE' or not request.user.is_authenticated:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    n = get_object_or_404(Notification, pk=pk, recipient=request.user)
    n.delete()
    return JsonResponse({'success': True})


