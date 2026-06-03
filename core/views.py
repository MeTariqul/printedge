from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Sum, Count, Q
import json
from datetime import timedelta
from decimal import Decimal

from .models import (
    User, WalkInCustomer, Order, OrderFile, InventoryItem,
    PricingRule, AddonService, Expense, AuditLog,
    Notification, OrderStatusLog, SiteSettings, PromoCode,
)
from .decorators import login_required_custom, admin_required, superadmin_required, permission_required
from .frontend_views import extract_zip_files
from .pricing import calculate_order_price, calculate_order_from_files
from .order_line_items import parse_files_config, create_order_with_files, detect_pages_for_upload
from .utils import safe_int, validate_upload_file
from .audit_helpers import log_audit
from .user_helpers import create_user_account, set_user_password, validate_password_strength
from .order_files import apply_order_delivered, delete_order_file, save_order_file_metadata
from .page_detection import detect_pages
from .pricing_options import get_active_pricing_options
from .notifications import (
    notify_staff_of_new_user, notify_new_online_order, notify_order_status_change, notify_new_walkin_order,
    notify_approve_user,
)

# ─── AUTH VIEWS ────────────────────────────────────────────────────────────────

import re
from django.conf import settings as django_settings
from .ratelimit import is_rate_limited, record_failed_attempt, clear_attempts


def auth_login(request):
    if request.user.is_authenticated:
        return redirect('admin_dashboard' if request.user.is_admin_user else 'user_dashboard')
    if request.method == 'POST':
        if is_rate_limited(request, 'login', django_settings.AUTH_RATE_LIMIT_ATTEMPTS, django_settings.AUTH_RATE_LIMIT_WINDOW):
            messages.error(request, 'Too many login attempts. Please try again in a few minutes.')
            return render(request, 'auth/login.html')

        ip = request.META.get('REMOTE_ADDR')
        email = (request.POST.get('email') or request.POST.get('username') or '').strip().lower()[:150]
        password = request.POST.get('password', '')
        user = authenticate(request, username=email, password=password)
        if user is None:
            try:
                u = User.objects.get(email=email)
                user = authenticate(request, username=u.username, password=password)
            except User.DoesNotExist:
                pass

        if user:
            if user.is_banned:
                messages.error(request, 'Your account has been suspended.')
                return redirect('auth_login_page')
            clear_attempts(request, 'login')
            login(request, user)
            if request.POST.get('remember'):
                request.session.set_expiry(2592000)
            else:
                request.session.set_expiry(1296000)
            AuditLog.objects.create(
                user=user, action='LOGIN', resource_type='Auth',
                ip_address=ip
            )
            if user.is_admin_user:
                if user.role == 'operator':
                    return redirect('admin_operator_dashboard')
                if user.role == 'viewer':
                    return redirect('admin_orders')
                return redirect('admin_dashboard')
            return redirect('user_dashboard')

        record_failed_attempt(request, 'login', django_settings.AUTH_RATE_LIMIT_WINDOW)
        messages.error(request, 'Invalid email or password.')
    return render(request, 'auth/login.html')


def auth_register(request):
    if request.user.is_authenticated:
        return redirect('user_dashboard')
    if request.method == 'POST':
        if is_rate_limited(request, 'register', django_settings.AUTH_RATE_LIMIT_ATTEMPTS, django_settings.AUTH_RATE_LIMIT_WINDOW):
            messages.error(request, 'Too many registration attempts. Please try again later.')
            return render(request, 'auth/register.html')

        first_name = request.POST.get('first_name', '').strip()[:50]
        last_name = request.POST.get('last_name', '').strip()[:50]
        email = request.POST.get('email', '').strip().lower()[:150]
        phone = request.POST.get('phone', '').strip()[:20]
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')
        
        if not re.match(r'^(\+88)?01[3-9]\d{8}$', phone):
            messages.error(request, 'Invalid Bangladeshi phone number format.')
            return render(request, 'auth/register.html')
            
        # Email validation: format and popular providers
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, email):
            messages.error(request, 'Please provide a valid email address.')
            return render(request, 'auth/register.html')

        popular_domains = ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'icloud.com', 'g.bracu.ac.bd', 'live.com', 'msn.com']
        domain = email.split('@')[-1] if '@' in email else ''
        if domain not in popular_domains:
            messages.error(request, 'Please use an email from a popular provider (e.g., Gmail, Outlook, Yahoo).')
            return render(request, 'auth/register.html')

        if password != password2:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'auth/register.html')
        pwd_err = validate_password_strength(password)
        if pwd_err:
            messages.error(request, pwd_err)
            return render(request, 'auth/register.html')
        if User.objects.filter(email=email).exists() or User.objects.filter(phone=phone).exists():
            messages.error(request, 'This email or phone is already registered.')
            return render(request, 'auth/register.html')
            
        username = email.split('@')[0]
        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        
        user = create_user_account(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            role='customer',
            is_email_verified=False,
        )
        from .email_verification import send_verification_email
        send_verification_email(request, user)
        messages.success(request, 'Registration successful! Please check your email to verify your account.')
        return redirect('auth_verify_pending')
    return render(request, 'auth/register.html')


def auth_verify_pending(request):
    if not request.user.is_authenticated:
        return redirect('auth_login_page')
    if request.user.is_email_verified or request.user.role != 'customer':
        return redirect('user_dashboard')
    if request.method == 'POST':
        from .ratelimit import is_rate_limited
        if is_rate_limited(request, 'verify_resend', 3, 300):
            messages.error(request, 'Please wait before requesting another verification email.')
        else:
            from .email_verification import send_verification_email
            if send_verification_email(request, request.user):
                messages.success(request, 'Verification email sent.')
            else:
                messages.warning(request, 'Email is not configured. Contact support to verify your account.')
    return render(request, 'auth/verify_pending.html')


def auth_verify_email(request, uid, token):
    user = get_object_or_404(User, pk=uid)
    from .email_verification import verify_user_token
    if verify_user_token(user, token):
        messages.success(request, 'Email verified! You can now place orders.')
        if request.user.is_authenticated and request.user.pk == user.pk:
            return redirect('user_new_order')
        return redirect('auth_login_page')
    messages.error(request, 'Invalid or expired verification link.')
    return redirect('auth_verify_pending' if request.user.is_authenticated else 'auth_login_page')


def auth_logout(request):
    logout(request)
    return redirect('public_index')


# ─── PUBLIC VIEWS ───────────────────────────────────────────────────────────────

def public_index(request):
    return render(request, 'index.html')


def public_pricing(request):
    addons = AddonService.objects.filter(is_active=True)
    return render(request, 'pricing.html', {'addons': addons})


def public_services(request):
    addons = AddonService.objects.filter(is_active=True)
    return render(request, 'services.html', {'addons': addons})


def public_upload(request):
    if request.user.is_authenticated:
        return redirect('user_new_order')
    return render(request, 'upload.html')

def public_contact(request):
    return render(request, 'contact.html')


# ─── USER VIEWS ─────────────────────────────────────────────────────────────────

@login_required_custom
def user_dashboard(request):
    orders = Order.objects.filter(customer=request.user).order_by('-created_at')
    active = orders.filter(status__in=['pending', 'confirmed', 'printing', 'quality_check', 'ready'])
    stats = {
        'active_count': active.count(),
        'completed_count': orders.filter(status='delivered').count(),
        'total_spent': orders.filter(status='delivered').aggregate(s=Sum('total_amount'))['s'] or 0,
    }
    # Status pipeline data for the tracker UI
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
        'orders': orders[:10],
        'active_order': active_order,
        'stats': stats,
        'status_steps': status_steps,
        'passed_statuses': passed_statuses,
    })


def _order_form_context():
    return {
        'addons': AddonService.objects.filter(is_active=True),
        'pricing_options': get_active_pricing_options(),
    }


@login_required_custom
def user_new_order(request):
    from .email_verification import customer_needs_verification
    if customer_needs_verification(request.user):
        messages.warning(request, 'Please verify your email before placing an order.')
        return redirect('auth_verify_pending')
    site = SiteSettings.get()
    ctx = _order_form_context()
    ctx['accepting_orders'] = site.accepting_orders
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

        if not uploads:
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

        promo_code_str = request.POST.get('promo_code', '').strip().upper()
        promo_obj = None
        if promo_code_str:
            try:
                promo_obj = PromoCode.objects.get(code=promo_code_str)
                if not promo_obj.is_valid:
                    messages.warning(request, 'Promo code is expired or invalid.')
                    promo_obj = None
            except PromoCode.DoesNotExist:
                messages.warning(request, 'Invalid promo code.')

        tier_pct = Decimal(request.user.tier_discount())
        try:
            breakdown = calculate_order_from_files(
                files_config[:len(uploads)],
                addon_ids=addon_ids,
                is_urgent=is_urgent,
                promo_code_obj=promo_obj,
                tier_discount_pct=tier_pct,
                urgent_percent=site.urgent_surcharge_percent,
            )
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
                    'promo_code': promo_obj,
                    'created_by': request.user,
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
    messages.success(request, 'Order cancelled.')
    return redirect('user_order_detail', pk=pk)


@login_required_custom
def user_order_detail(request, pk):
    order = get_object_or_404(
        Order.objects.prefetch_related('order_files__page_ranges'),
        pk=pk, customer=request.user,
    )
    return render(request, 'user/order_detail.html', {'order': order})


@login_required_custom
def user_orders(request):
    orders = Order.objects.filter(customer=request.user).order_by('-created_at')
    return render(request, 'user/orders.html', {'orders': orders})


# user_profile moved to frontend_views.py

# ─── ADMIN VIEWS ────────────────────────────────────────────────────────────────

@admin_required
def admin_dashboard(request):
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)

    today_orders = Order.objects.filter(created_at__date=today)
    yesterday_orders = Order.objects.filter(created_at__date=yesterday)

    today_revenue = today_orders.aggregate(s=Sum('total_amount'))['s'] or 0
    yesterday_revenue = yesterday_orders.aggregate(s=Sum('total_amount'))['s'] or 0

    revenue_change = 0
    if yesterday_revenue > 0:
        revenue_change = round(((today_revenue - yesterday_revenue) / yesterday_revenue) * 100, 1)

    pending_count = Order.objects.filter(status__in=['pending', 'confirmed']).count()
    active_customers = User.objects.filter(
        orders__created_at__date=today
    ).distinct().count()

    pages_today = today_orders.aggregate(
        p=Sum('total_sheets')
    )['p'] or 0

    avg_order_value = today_orders.aggregate(a=Sum('total_amount'))['a'] or 0
    count = today_orders.count()
    avg_order_value = round(avg_order_value / count, 0) if count else 0

    chart_range = request.GET.get('range', '7')
    days_back = 29 if chart_range == '30' else 6
    revenue_trend = []
    labels = []
    for i in range(days_back, -1, -1):
        d = today - timedelta(days=i)
        rev = Order.objects.filter(created_at__date=d).aggregate(s=Sum('total_amount'))['s'] or 0
        revenue_trend.append(float(rev))
        labels.append(d.strftime('%b %d') if chart_range == '30' else d.strftime('%a'))

    orders_per_hour = [0] * 24
    for o in today_orders:
        h = o.created_at.hour
        if 0 <= h < 24:
            orders_per_hour[h] += 1

    # Order distribution by status (group processing states for chart)
    status_counts = {
        s[0]: Order.objects.filter(status=s[0]).count()
        for s in Order.STATUS_CHOICES
    }
    chart_status = {
        'Pending': status_counts.get('pending', 0) + status_counts.get('confirmed', 0),
        'Processing': status_counts.get('printing', 0) + status_counts.get('quality_check', 0),
        'Ready': status_counts.get('ready', 0),
        'Delivered': status_counts.get('delivered', 0),
        'Other': status_counts.get('cancelled', 0) + status_counts.get('on_hold', 0),
    }

    # Low stock alerts
    low_stock = InventoryItem.objects.all()
    low_stock_count = sum(1 for i in low_stock if i.status[0] in ('warning', 'danger'))

    recent_orders = Order.objects.select_related('customer', 'walkin_customer').order_by('-created_at')[:8]

    ctx = {
        'today_orders_count': count,
        'yesterday_orders_count': yesterday_orders.count(),
        'today_revenue': today_revenue,
        'yesterday_revenue': yesterday_revenue,
        'revenue_change': revenue_change,
        'pending_count': pending_count,
        'active_customers': active_customers,
        'pages_today': pages_today,
        'avg_order_value': avg_order_value,
        'revenue_trend_json': json.dumps(revenue_trend),
        'revenue_labels_json': json.dumps(labels),
        'chart_range': chart_range,
        'orders_per_hour_json': json.dumps(orders_per_hour),
        'status_counts': status_counts,
        'chart_status_json': json.dumps(list(chart_status.values())),
        'chart_status_labels_json': json.dumps(list(chart_status.keys())),
        'status_counts_json': json.dumps(list(status_counts.values())),
        'low_stock_count': low_stock_count,
        'recent_orders': recent_orders[:10],
        'accepting_orders': SiteSettings.get().accepting_orders,
        'unread_count': Notification.objects.filter(
            recipient=request.user, is_read=False
        ).count() if hasattr(request.user, 'notifications') else 0,
    }
    return render(request, 'admin/dashboard.html', ctx)


@admin_required
def admin_orders(request):
    qs = Order.objects.select_related(
        'customer', 'walkin_customer', 'assigned_to',
    ).prefetch_related('order_files').order_by('-created_at')
    status_filter = request.GET.get('status', '')
    source_filter = request.GET.get('source', '')
    search = request.GET.get('q', '').strip()
    if status_filter:
        qs = qs.filter(status=status_filter)
    if source_filter:
        qs = qs.filter(source=source_filter)
    if search:
        qs = qs.filter(
            Q(order_number__icontains=search) |
            Q(customer__first_name__icontains=search) |
            Q(customer__last_name__icontains=search) |
            Q(customer__email__icontains=search) |
            Q(customer__phone__icontains=search) |
            Q(walkin_customer__name__icontains=search) |
            Q(walkin_customer__phone__icontains=search)
        )
    ctx = {
        'orders': qs[:100],
        'status_choices': Order.STATUS_CHOICES,
        'current_status': status_filter,
        'current_source': source_filter,
        'search_query': search,
        'total_count': qs.count(),
    }
    return render(request, 'admin/orders.html', ctx)


@admin_required
def admin_order_detail(request, pk):
    order = get_object_or_404(Order, pk=pk)
    staff_list = User.objects.filter(role__in=['operator', 'manager', 'admin', 'super_admin'])
    if request.method == 'POST':
        if request.user.is_readonly_staff:
            messages.error(request, 'Read-only access.')
            return redirect('admin_order_detail', pk=pk)
        action = request.POST.get('action')
        if action == 'status':
            new_status = request.POST.get('status')
            valid_statuses = [s[0] for s in Order.STATUS_CHOICES]
            if new_status not in valid_statuses:
                messages.error(request, 'Invalid order status.')
                return redirect('admin_order_detail', pk=pk)
            old_status = order.status
            note = request.POST.get('note', '')
            order.status = new_status
            if new_status == 'delivered':
                apply_order_delivered(order)
            order.save()
            OrderStatusLog.objects.create(
                order=order, old_status=old_status,
                new_status=new_status, changed_by=request.user, note=note
            )
            notify_order_status_change(order, old_status, changed_by=request.user)
        elif action == 'assign':
            uid = request.POST.get('assigned_to')
            order.assigned_to_id = uid or None
            order.save(update_fields=['assigned_to'])
        elif action == 'payment':
            order.amount_paid = Decimal(request.POST.get('amount_paid', order.amount_paid))
            order.payment_method = request.POST.get('payment_method', order.payment_method)
            order.transaction_id = request.POST.get('transaction_id', order.transaction_id)
            if order.amount_paid >= order.total_amount:
                order.payment_status = 'paid'
            elif order.amount_paid > 0:
                order.payment_status = 'partial'
            order.save()
        elif action == 'notes':
            order.admin_notes = request.POST.get('admin_notes', '')
            order.save(update_fields=['admin_notes'])
        elif action == 'delete_file' and request.user.is_full_admin:
            delete_order_file(order, request=request, reason='admin_manual')
            messages.success(request, 'Order file removed.')
            return redirect('admin_order_detail', pk=pk)
        elif action == 'delete_order' and request.user.is_full_admin:
            order_num = order.order_number
            order.delete()
            log_audit(request, 'DELETE_ORDER', 'Order', '', old_value=order_num)
            messages.success(request, f'Order {order_num} deleted.')
            return redirect('admin_orders')
        messages.success(request, 'Order updated.')
        return redirect('admin_order_detail', pk=pk)
    site = SiteSettings.get()
    return render(request, 'admin/order_detail.html', {
        'order': order,
        'staff_list': staff_list,
        'retention_days': site.auto_delete_files_days,
        'can_delete_file': request.user.is_full_admin and order.has_stored_file,
    })


@permission_required('walkin_order')
def admin_walkin_order(request):
    from django.core.files.base import ContentFile

    from .order_line_items import create_order_with_files, parse_files_config, detect_pages_for_upload

    site = SiteSettings.get()
    ctx = _order_form_context()
    ctx['walkin_customers'] = WalkInCustomer.objects.order_by('-last_visit')[:50]
    if request.method == 'POST':
        try:
            walkin_id = request.POST.get('walkin_customer_id')
            if walkin_id:
                walkin = get_object_or_404(WalkInCustomer, pk=walkin_id)
            else:
                from .walkin_helpers import get_or_create_walkin_customer

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

            uploads = []
            for f in request.FILES.getlist('files'):
                if f.name.lower().endswith('.zip'):
                    zip_files, zip_err = extract_zip_files(f)
                    if zip_err:
                        messages.error(request, zip_err)
                        return render(request, 'admin/walkin_order.html', ctx)
                    for name, buf, size in zip_files:
                        uploads.append(ContentFile(buf.getvalue(), name=name))
                else:
                    err = validate_upload_file(f)
                    if err:
                        messages.error(request, err)
                        return render(request, 'admin/walkin_order.html', ctx)
                    uploads.append(f)

            if not uploads and not is_physical:
                messages.error(request, 'Upload at least one file or mark as physical document.')
                return render(request, 'admin/walkin_order.html', ctx)

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
                while len(files_config) < len(uploads):
                    idx = len(files_config)
                    pages = detect_pages_for_upload(uploads[idx]) if idx < len(uploads) else 1
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

            try:
                breakdown = calculate_order_from_files(
                    files_config if (is_physical and not uploads) else files_config[:len(uploads)],
                    addon_ids=addon_ids,
                    is_urgent=is_urgent,
                    manual_discount=manual_discount,
                    tier_discount_pct=Decimal('0'),
                    urgent_percent=site.urgent_surcharge_percent,
                )
            except ValueError as exc:
                messages.error(request, str(exc))
                return render(request, 'admin/walkin_order.html', ctx)

            payment_status = 'paid' if amount_paid >= breakdown['total'] else (
                'partial' if amount_paid > 0 else 'unpaid'
            )
            primary = files_config[0] if files_config else {
                'print_type': 'bw', 'sides': 'single', 'paper_size': 'A4', 'pages': 1, 'copies': 1,
            }
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
                'payment_method': payment_method,
                'amount_paid': amount_paid,
                'payment_status': payment_status,
                'created_by': request.user,
            }

            if uploads:
                uploaded_pairs = [(f'files', u, getattr(u, 'name', '')) for u in uploads]
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

            OrderStatusLog.objects.create(
                order=order, new_status='pending',
                changed_by=request.user, note=f'Walk-in order created by {request.user.display_name}.',
            )
            walkin.total_orders += 1
            walkin.last_visit = timezone.now()
            walkin.save(update_fields=['total_orders', 'last_visit'])
            notify_new_walkin_order(order, request.user)
            
            # Send order confirmation email
            from .email_order import send_order_confirmation_email
            send_order_confirmation_email(request, order)
            
            messages.success(request, f'Walk-in order {order.order_number} created!')
            return redirect('admin_order_detail', pk=order.pk)
        except (OSError, ImproperlyConfigured) as exc:
            messages.error(request, f'Could not save the order: {exc}. Please try again or contact support.')
        except Exception as exc:
            messages.error(request, f'An unexpected error occurred: {exc}. Please try again.')
    return render(request, 'admin/walkin_order.html', ctx)


@permission_required('manage_customers')
def admin_users(request):
    users = User.objects.filter(role='customer').order_by('-date_joined')
    search = request.GET.get('q', '')
    if search:
        users = users.filter(Q(email__icontains=search) | Q(first_name__icontains=search) | Q(phone__icontains=search))

    if request.method == 'POST' and request.user.is_full_admin:
        action = request.POST.get('action')
        if action == 'create':
            try:
                user = create_user_account(
                    email=request.POST.get('email', ''),
                    password=request.POST.get('password', ''),
                    first_name=request.POST.get('first_name', ''),
                    last_name=request.POST.get('last_name', ''),
                    phone=request.POST.get('phone', ''),
                    role='customer',
                )
                log_audit(request, 'CREATE_USER', 'User', user.pk, new_value=user.email)
                messages.success(request, f'Customer {user.email} created.')
            except ValueError as exc:
                messages.error(request, str(exc))
        elif action == 'toggle_active':
            user = get_object_or_404(User, pk=request.POST.get('user_id'), role='customer')
            user.is_active = not user.is_active
            user.save(update_fields=['is_active'])
            log_audit(request, 'TOGGLE_ACTIVE', 'User', user.pk, new_value=str(user.is_active))
            messages.success(request, f'Account {"activated" if user.is_active else "deactivated"}.')
        elif action == 'ban':
            user = get_object_or_404(User, pk=request.POST.get('user_id'), role='customer')
            user.is_banned = True
            user.ban_reason = request.POST.get('ban_reason', '')[:500]
            user.save(update_fields=['is_banned', 'ban_reason'])
            log_audit(request, 'BAN_USER', 'User', user.pk, new_value=user.ban_reason)
            messages.success(request, f'{user.display_name} banned.')
        elif action == 'unban':
            user = get_object_or_404(User, pk=request.POST.get('user_id'), role='customer')
            user.is_banned = False
            user.ban_reason = ''
            user.save(update_fields=['is_banned', 'ban_reason'])
            log_audit(request, 'UNBAN_USER', 'User', user.pk)
            messages.success(request, f'{user.display_name} unbanned.')
        elif action == 'set_password':
            user = get_object_or_404(User, pk=request.POST.get('user_id'), role='customer')
            pwd = request.POST.get('password', '')
            err = validate_password_strength(pwd)
            if err:
                messages.error(request, err)
            else:
                set_user_password(user, pwd)
                log_audit(request, 'SET_PASSWORD', 'User', user.pk)
                messages.success(request, f'Password updated for {user.email}.')
        elif action == 'delete':
            uid = request.POST.get('user_id')
            if Order.objects.filter(customer_id=uid).exists():
                messages.error(request, 'Cannot delete customer with existing orders.')
            else:
                user = get_object_or_404(User, pk=uid, role='customer')
                email = user.email
                user.delete()
                log_audit(request, 'DELETE_USER', 'User', '', old_value=email)
                messages.success(request, 'Customer deleted.')
        elif action == 'approve':
            uid = request.POST.get('user_id')
            user = get_object_or_404(User, pk=uid, role='customer')
            user.is_active = True
            user.is_email_verified = True
            user.save(update_fields=['is_active', 'is_email_verified'])
            log_audit(request, 'APPROVE_USER', 'User', user.pk, old_value='is_active=False')
            notify_approve_user(user)
            messages.success(request, f'{user.email} approved and can now log in.')
        return redirect('admin_users')

    return render(request, 'admin/users.html', {
        'users': users,
        'search': search,
        'can_manage': request.user.is_full_admin,
    })


@permission_required('manage_customers')
def admin_user_detail(request, pk):
    user = get_object_or_404(User, pk=pk, role='customer')
    orders = Order.objects.filter(customer=user).select_related(
        'walkin_customer', 'assigned_to',
    ).prefetch_related('order_files').order_by('-created_at')[:100]
    return render(request, 'admin/user_detail.html', {
        'customer': user,
        'orders': orders,
        'status_choices': Order.STATUS_CHOICES,
    })


@admin_required
def admin_offline_customers(request):
    customers = WalkInCustomer.objects.order_by('-last_visit')
    search = request.GET.get('q', '')
    if search:
        customers = customers.filter(Q(name__icontains=search) | Q(phone__icontains=search))
        
    if request.method == 'POST' and request.user.is_full_admin:
        action = request.POST.get('action')
        if action == 'delete':
            cid = request.POST.get('customer_id')
            customer = get_object_or_404(WalkInCustomer, pk=cid)
            if Order.objects.filter(walkin_customer=customer).exists():
                messages.error(request, 'Cannot delete customer with order history.')
            else:
                name = customer.name
                customer.delete()
                messages.success(request, f'Customer {name} deleted.')
        return redirect('admin_offline_customers')

    return render(request, 'admin/offline_customers.html', {'customers': customers, 'search': search})


@permission_required('manage_inventory')
def admin_inventory(request):
    items = InventoryItem.objects.all().order_by('category', 'name')
    if request.method == 'POST':
        if request.user.is_readonly_staff:
            messages.error(request, 'Read-only access.')
            return redirect('admin_inventory')
        action = request.POST.get('action')
        if action == 'add_item':
            InventoryItem.objects.create(
                name=request.POST['name'], category=request.POST['category'],
                current_stock=request.POST['current_stock'], unit=request.POST['unit'],
                min_alert_level=request.POST['min_alert_level'],
                cost_per_unit=request.POST.get('cost_per_unit', 0),
            )
            messages.success(request, 'Item added.')
        elif action == 'adjust':
            item = get_object_or_404(InventoryItem, pk=request.POST['item_id'])
            qty = Decimal(request.POST['quantity'])
            move = request.POST['movement']
            if move == 'in':
                item.current_stock += qty
            else:
                item.current_stock = max(0, item.current_stock - qty)
            item.save()
            messages.success(request, f'{item.name} stock updated.')
        elif action == 'delete' and request.user.is_full_admin:
            item = get_object_or_404(InventoryItem, pk=request.POST['item_id'])
            name = item.name
            item.delete()
            messages.success(request, f'Item {name} deleted.')
        return redirect('admin_inventory')
    return render(request, 'admin/inventory.html', {'items': items})


@permission_required('manage_pricing')
def admin_services(request):
    from .pricing import reset_a4_pricing_defaults

    pricing = PricingRule.objects.filter(paper_size='A4').order_by('print_type', 'sides')
    addons = AddonService.objects.all()
    can_manage_addons = request.user.role in ('manager', 'admin', 'super_admin')
    if request.method == 'POST':
        if request.user.is_readonly_staff:
            messages.error(request, 'Read-only access.')
            return redirect('admin_services')
        action = request.POST.get('action')
        if action == 'update_price':
            rule = get_object_or_404(PricingRule, pk=request.POST['rule_id'])
            rule.price_per_page = Decimal(request.POST['price'])
            rule.save()
            cache.clear()
            messages.success(request, 'Price updated.')
        elif action == 'toggle_pricing_rule':
            rule = get_object_or_404(PricingRule, pk=request.POST['rule_id'])
            rule.is_active = not rule.is_active
            rule.save(update_fields=['is_active'])
            cache.clear()
            messages.success(request, f'Pricing rule {"enabled" if rule.is_active else "disabled"}.')
        elif action == 'reset_pricing_defaults':
            reset_a4_pricing_defaults()
            cache.clear()
            messages.success(request, 'A4 pricing reset to defaults (2/3/5/8).')
        elif action == 'add_pricing_rule' and can_manage_addons:
            PricingRule.objects.get_or_create(
                print_type=request.POST.get('print_type', 'bw'),
                sides=request.POST.get('sides', 'single'),
                paper_size='A4',
                defaults={
                    'name': request.POST.get('name', 'Custom rule'),
                    'price_per_page': Decimal(request.POST.get('price', '2')),
                    'is_active': True,
                },
            )
            cache.clear()
            messages.success(request, 'Pricing rule added.')
        elif action == 'delete_pricing_rule' and request.user.is_full_admin:
            rule = get_object_or_404(PricingRule, pk=request.POST['rule_id'])
            rule.delete()
            cache.clear()
            messages.success(request, 'Pricing rule deleted.')
        elif action == 'toggle_addon' and can_manage_addons:
            addon = get_object_or_404(AddonService, pk=request.POST['addon_id'])
            addon.is_active = not addon.is_active
            addon.save()
        elif action == 'add_addon' and can_manage_addons:
            AddonService.objects.create(
                name=request.POST['name'], price=request.POST['price'],
                description=request.POST.get('description', '')
            )
            messages.success(request, 'Add-on created.')
        elif action == 'delete_addon' and request.user.is_full_admin:
            addon = get_object_or_404(AddonService, pk=request.POST['addon_id'])
            name = addon.name
            addon.delete()
            messages.success(request, f'Add-on {name} deleted.')
        return redirect('admin_services')
    return render(request, 'admin/services.html', {
        'pricing': pricing,
        'addons': addons,
        'can_manage_addons': can_manage_addons,
    })


@permission_required('view_financial')
def admin_financial(request):
    today = timezone.now().date()
    expenses = Expense.objects.order_by('-date')[:50]
    if request.method == 'POST':
        Expense.objects.create(
            category=request.POST['category'], description=request.POST['description'],
            amount=request.POST['amount'], payment_method=request.POST.get('payment_method', 'Cash'),
            date=request.POST.get('date', today), logged_by=request.user,
        )
        messages.success(request, 'Expense logged.')
        return redirect('admin_financial')
    week_revenue = Order.objects.filter(
        created_at__date__gte=today - timedelta(days=7)
    ).aggregate(s=Sum('total_amount'))['s'] or 0
    week_expenses = Expense.objects.filter(
        date__gte=today - timedelta(days=7)
    ).aggregate(s=Sum('amount'))['s'] or 0
    return render(request, 'admin/financial.html', {
        'expenses': expenses,
        'week_revenue': week_revenue,
        'week_expenses': week_expenses,
        'week_profit': week_revenue - week_expenses,
    })


@admin_required
def admin_reports(request):
    return render(request, 'admin/reports.html')


@permission_required('view_audit')
def admin_audit_log(request):
    logs = AuditLog.objects.select_related('user').order_by('-timestamp')[:200]
    return render(request, 'admin/audit_log.html', {'logs': logs})


@superadmin_required
def admin_settings(request):
    site = SiteSettings.get()
    if request.method == 'POST':
        site.business_name = request.POST.get('business_name', site.business_name).strip() or site.business_name
        site.business_phone = request.POST.get('business_phone', site.business_phone)
        site.business_email = request.POST.get('business_email', site.business_email)
        site.business_address = request.POST.get('business_address', site.business_address)
        site.business_hours = request.POST.get('business_hours', site.business_hours)
        # Social / contact links
        site.whatsapp_number = request.POST.get('whatsapp_number', '').strip()
        site.messenger_link = request.POST.get('messenger_link', '').strip()
        site.facebook_page = request.POST.get('facebook_page', '').strip()
        site.google_maps_link = request.POST.get('google_maps_link', '').strip()
        # Order settings
        site.accepting_orders = request.POST.get('accepting_orders') == 'on'
        site.require_email_verification = request.POST.get('require_email_verification') == 'on'
        site.urgent_surcharge_percent = safe_int(request.POST.get('urgent_surcharge_percent', 50), default=50, minimum=0)
        site.auto_delete_files_days = safe_int(request.POST.get('auto_delete_files_days', 7), default=7, minimum=1)
        site.chat_provider = request.POST.get('chat_provider', '')[:20]
        site.chat_widget_id = request.POST.get('chat_widget_id', '')[:200]
        site.save()
        log_audit(request, 'UPDATE_SETTINGS', 'SiteSettings', 1)
        messages.success(request, 'Settings saved successfully.')
        return redirect('admin_settings')
    return render(request, 'admin/settings.html', {'site': site})


# ─── API VIEWS ─────────────────────────────────────────────────────────────────

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
        is_urgent = data.get('is_urgent', False)
        manual_discount = Decimal(str(data.get('manual_discount', 0) or 0))
        tier_pct = Decimal('0')
        if request.user.is_authenticated:
            tier_pct = Decimal(request.user.tier_discount())
        try:
            breakdown = calculate_order_from_files(
                files,
                addon_ids=addon_ids,
                is_urgent=is_urgent,
                manual_discount=manual_discount,
                tier_discount_pct=tier_pct,
                urgent_percent=site.urgent_surcharge_percent,
            )
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


# ─── PWA MANIFEST ──────────────────────────────────────────────────────────────

def robots_txt(request):
    return HttpResponse(
        'User-agent: *\nAllow: /\nDisallow: /admin/\nDisallow: /user/\nDisallow: /auth/\nDisallow: /sys-admin/\nDisallow: /api/\n\nSitemap: /sitemap.xml\n',
        content_type='text/plain',
    )


def sitemap_xml(request):
    from django.urls import reverse
    base = request.build_absolute_uri('/').rstrip('/')
    public_paths = [
        ('public_index', 'daily', '1.0'),
        ('public_services_page', 'weekly', '0.8'),
        ('public_pricing_page', 'weekly', '0.9'),
        ('public_upload_page', 'weekly', '0.8'),
        ('public_contact_page', 'monthly', '0.7'),
    ]
    urls = []
    for name, freq, priority in public_paths:
        loc = base + reverse(name)
        urls.append(
            f'  <url><loc>{loc}</loc><changefreq>{freq}</changefreq><priority>{priority}</priority></url>'
        )
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + '\n'.join(urls) + '\n</urlset>'
    )
    return HttpResponse(body, content_type='application/xml')


def pwa_manifest(request):
    """Serve PWA manifest.json dynamically."""
    manifest = {
        'name': 'PrintEdge - Campus Printing',
        'short_name': 'PrintEdge',
        'description': 'Premium campus printing service - upload, configure, print.',
        'start_url': '/',
        'display': 'standalone',
        'background_color': '#020617',
        'theme_color': '#14b8a6',
        'orientation': 'portrait-primary',
        'icons': [
            {'src': 'https://i.postimg.cc/7LSfBQWc/default-avatar.png', 'sizes': 'any', 'type': 'image/png', 'purpose': 'any'},
            {'src': '/static/icons/icon-192.png', 'sizes': '192x192', 'type': 'image/png'},
            {'src': '/static/icons/icon-512.png', 'sizes': '512x512', 'type': 'image/png'},
        ],
        'categories': ['business', 'productivity'],
    }
    return JsonResponse(manifest)


# ─── STAFF MANAGEMENT ──────────────────────────────────────────────────────────

@admin_required
def admin_staff(request):
    staff = User.objects.filter(role__in=['operator', 'manager', 'admin', 'super_admin']).order_by('role', 'first_name')
    staff_roles = [c for c in User.ROLE_CHOICES if c[0] != 'customer']

    if request.method == 'POST' and request.user.is_full_admin:
        action = request.POST.get('action')
        if action == 'create':
            try:
                role = request.POST.get('role', 'operator')
                if role not in ('operator', 'manager', 'admin', 'super_admin'):
                    role = 'operator'
                user = create_user_account(
                    email=request.POST.get('email', ''),
                    password=request.POST.get('password', ''),
                    first_name=request.POST.get('first_name', ''),
                    last_name=request.POST.get('last_name', ''),
                    phone=request.POST.get('phone', ''),
                    role=role,
                )
                user.is_staff = True
                user.save(update_fields=['is_staff'])
                log_audit(request, 'CREATE_STAFF', 'User', user.pk, new_value=f'{user.email}:{role}')
                messages.success(request, f'Staff {user.email} created.')
            except ValueError as exc:
                messages.error(request, str(exc))
        elif action == 'update_role':
            uid = request.POST.get('user_id')
            new_role = request.POST.get('role')
            if new_role in {r[0] for r in staff_roles}:
                user = get_object_or_404(User, pk=uid)
                old = user.role
                user.role = new_role
                user.save(update_fields=['role'])
                log_audit(request, 'UPDATE_ROLE', 'User', user.pk, old_value=old, new_value=new_role)
                messages.success(request, f'{user.display_name} role updated to {new_role}.')
        elif action == 'toggle_active':
            user = get_object_or_404(User, pk=request.POST.get('user_id'))
            if user.pk == request.user.pk:
                messages.error(request, 'You cannot deactivate your own account.')
            else:
                user.is_active = not user.is_active
                user.save(update_fields=['is_active'])
                log_audit(request, 'TOGGLE_ACTIVE', 'User', user.pk, new_value=str(user.is_active))
                messages.success(request, 'Staff access updated.')
        elif action == 'set_password':
            user = get_object_or_404(User, pk=request.POST.get('user_id'))
            pwd = request.POST.get('password', '')
            err = validate_password_strength(pwd)
            if err:
                messages.error(request, err)
            else:
                set_user_password(user, pwd)
                log_audit(request, 'SET_PASSWORD', 'User', user.pk)
                messages.success(request, f'Password updated for {user.email}.')
        elif action == 'demote':
            user = get_object_or_404(User, pk=request.POST.get('user_id'))
            if user.pk == request.user.pk:
                messages.error(request, 'You cannot demote yourself.')
            else:
                user.role = 'customer'
                user.is_staff = False
                user.save(update_fields=['role', 'is_staff'])
                log_audit(request, 'DEMOTE_STAFF', 'User', user.pk)
                messages.success(request, f'{user.display_name} moved to customer role.')
        elif action == 'delete' and request.user.is_full_admin:
            uid = request.POST.get('user_id')
            if str(uid) == str(request.user.pk):
                messages.error(request, 'You cannot delete yourself.')
            else:
                user = get_object_or_404(User, pk=uid)
                email = user.email
                user.delete()
                log_audit(request, 'DELETE_STAFF', 'User', '', old_value=email)
                messages.success(request, f'Staff {email} deleted.')
        return redirect('admin_staff')

    PERMISSION_MATRIX = [
        # (permission label, [operator, manager, admin, super_admin])
        ('View & process orders',       [True,  True,  True,  True]),
        ('Update order status',         [True,  True,  True,  True]),
        ('Create walk-in (POS) orders', [True,  True,  True,  True]),
        ('Manage pricing & add-ons',    [False, True,  True,  True]),
        ('View financial reports',      [False, True,  True,  True]),
        ('Manage inventory',            [False, True,  True,  True]),
        ('Manage online customers',     [False, False, True,  True]),
        ('Add / remove staff members',  [False, False, True,  True]),
        ('Change staff roles',          [False, False, True,  True]),
        ('Edit site settings & links',  [False, False, False, True]),
        ('View audit log',              [False, True,  True,  True]),
        ('System status & file purge',  [False, False, False, True]),
    ]
    return render(request, 'admin/staff.html', {
        'staff': staff,
        'staff_roles': staff_roles,
        'can_manage': request.user.is_full_admin,
        'permission_matrix': PERMISSION_MATRIX,
    })


# ─── REPORTS EXPORT ────────────────────────────────────────────────────────────

import csv
from django.http import HttpResponse

@admin_required
def admin_reports_export(request):
    """Export orders to CSV."""
    report_type = request.GET.get('type', 'orders')
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="Print-Edge_{report_type}_{timezone.now().strftime("%Y%m%d")}.csv"'
    writer = csv.writer(response)

    if report_type == 'orders':
        writer.writerow(['Order #', 'Source', 'Customer', 'Phone', 'Print Type', 'Pages', 'Copies',
                         'Total', 'Paid', 'Payment Status', 'Status', 'Created'])
        orders = Order.objects.select_related('customer', 'walkin_customer').order_by('-created_at')[:500]
        for o in orders:
            writer.writerow([
                o.order_number, o.source, o.customer_name, o.customer_phone,
                o.get_print_type_display(), o.pages, o.copies,
                float(o.total_amount), float(o.amount_paid),
                o.get_payment_status_display(), o.get_status_display(),
                o.created_at.strftime('%Y-%m-%d %H:%M'),
            ])
    elif report_type == 'customers':
        writer.writerow(['Name', 'Email', 'Phone', 'Tier', 'Total Spent', 'Total Orders', 'Joined'])
        users = User.objects.filter(role='customer').order_by('-total_spent')
        for u in users:
            writer.writerow([u.display_name, u.email, u.phone, u.tier,
                             float(u.total_spent), u.total_orders, u.date_joined.strftime('%Y-%m-%d')])
    elif report_type == 'inventory':
        writer.writerow(['Item', 'Category', 'Stock', 'Unit', 'Alert Level', 'Cost/Unit', 'Status'])
        items = InventoryItem.objects.all()
        for i in items:
            writer.writerow([i.name, i.get_category_display(), float(i.current_stock),
                             i.unit, float(i.min_alert_level), float(i.cost_per_unit), i.status[1]])
    elif report_type == 'financial':
        writer.writerow(['Date', 'Category', 'Description', 'Amount', 'Payment Method', 'Logged By'])
        expenses = Expense.objects.select_related('logged_by').order_by('-date')[:500]
        for e in expenses:
            writer.writerow([e.date, e.get_category_display(), e.description,
                             float(e.amount), e.payment_method, e.logged_by.display_name if e.logged_by else ''])

    return response



def page_not_found(request, exception):
    return render(request, '404.html', status=404)
