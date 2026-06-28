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
                if not u.is_active:
                    messages.error(request, 'Your account has been deactivated. Contact support.')
                    record_failed_attempt(request, 'login', django_settings.AUTH_RATE_LIMIT_WINDOW)
                    return render(request, 'auth/login.html')
                if u.is_banned:
                    messages.error(request, 'Your account has been suspended.')
                    record_failed_attempt(request, 'login', django_settings.AUTH_RATE_LIMIT_WINDOW)
                    return render(request, 'auth/login.html')
                if not u.is_email_verified and u.role == 'customer':
                    messages.error(request, 'Please verify your email before logging in. Check your inbox for the verification link.')
                    return redirect('auth_verify_pending' if request.user.is_authenticated else 'auth_login_page')
                user = authenticate(request, username=u.username, password=password)
            except User.DoesNotExist:
                pass

        if user:
            if user.is_banned:
                messages.error(request, 'Your account has been suspended.')
                return redirect('auth_login_page')
            if not user.is_email_verified and user.role == 'customer':
                messages.error(request, 'Please verify your email before logging in. Check your inbox for the verification link.')
                return redirect('auth_verify_pending' if request.user.is_authenticated else 'auth_login_page')
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
            return render(request, 'auth/login.html', {'mode': 'signup'})

        first_name = request.POST.get('first_name', '').strip()[:50]
        last_name = request.POST.get('last_name', '').strip()[:50]
        email = request.POST.get('email', '').strip().lower()[:150]
        phone = request.POST.get('phone', '').strip()[:20]
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')
        
        if not re.match(r'^(\+88)?01[3-9]\d{8}$', phone):
            messages.error(request, 'Invalid Bangladeshi phone number format.')
            return render(request, 'auth/login.html', {
                'mode': 'signup',
                'signup_data': {
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': email,
                    'phone': phone,
                },
            })
            
        # Email validation: format and popular providers
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, email):
            messages.error(request, 'Please provide a valid email address.')
            return render(request, 'auth/login.html', {
                'mode': 'signup',
                'signup_data': {
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': email,
                    'phone': phone,
                },
            })

        popular_domains = ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'icloud.com', 'g.bracu.ac.bd', 'live.com', 'msn.com']
        domain = email.split('@')[-1] if '@' in email else ''
        if domain not in popular_domains:
            messages.error(request, 'Please use an email from a popular provider (e.g., Gmail, Outlook, Yahoo).')
            return render(request, 'auth/login.html', {
                'mode': 'signup',
                'signup_data': {
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': email,
                    'phone': phone,
                },
            })

        if password != password2:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'auth/login.html', {
                'mode': 'signup',
                'signup_data': {
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': email,
                    'phone': phone,
                },
            })
        pwd_err = validate_password_strength(password)
        if pwd_err:
            messages.error(request, pwd_err)
            return render(request, 'auth/login.html', {
                'mode': 'signup',
                'signup_data': {
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': email,
                    'phone': phone,
                },
            })
        if User.objects.filter(email=email).exists() or User.objects.filter(phone=phone).exists():
            messages.error(request, 'This email or phone is already registered.')
            return render(request, 'auth/login.html', {
                'mode': 'signup',
                'signup_data': {
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': email,
                    'phone': phone,
                },
            })
            
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

    # GET: render unified login template; explicitly set mode=signup so signup becomes the active panel
    return render(request, 'auth/login.html', {'mode': 'signup'})


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
    return render(request, 'auth/verify_invalid.html', {'user': user})


def auth_logout(request):
    logout(request)
    return redirect('public_index')


# ─── PUBLIC VIEWS ───────────────────────────────────────────────────────────────

def public_index(request):
    featured_services = Service.objects.filter(is_active=True).prefetch_related('variants').order_by('-created_at')[:4]
    return render(request, 'index.html', {'featured_services': featured_services})


def public_pricing(request):
    addons = AddonService.objects.filter(is_active=True)
    services = Service.objects.filter(is_active=True).prefetch_related('variants').order_by('category', 'name')
    return render(request, 'pricing.html', {'addons': addons, 'services': services})


def public_services_old(request):
    # Legacy – renders same template as public_services
    services = Service.objects.filter(is_active=True).prefetch_related('variants').order_by('category', 'name')
    addons = AddonService.objects.filter(is_active=True)
    return render(request, 'services.html', {'services': services, 'addons': addons})




def public_contact(request):
    return render(request, 'contact.html')


# ─── USER VIEWS ─────────────────────────────────────────────────────────────────

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


def order_context_with_service(request):
    """Build order form context with optional preselected service."""
    from .order_service import build_order_form_context
    ctx = build_order_form_context()
    ctx['accepting_orders'] = SiteSettings.get().accepting_orders
    ctx['SITE'] = SiteSettings.get()
    service_id = request.GET.get('service')
    if service_id:
        try:
            ctx['preselected_service'] = Service.objects.get(pk=service_id)
        except Service.DoesNotExist:
            pass
    preselected = ctx.get('preselected_service')
    ctx['service_requires_file'] = preselected and preselected.requires_file
    ctx['show_service_notes'] = preselected and not preselected.requires_file
    ctx['note_categories'] = ['stationery', 'binding', 'lamination']
    return ctx

def public_services(request):
    services = Service.objects.filter(is_active=True).prefetch_related('variants').order_by('category', 'name')
    return render(request, 'services.html', {'services': services})


@login_required_custom
def user_new_order(request):
    from .order_service import place_online_order, OrderCreationError, build_order_form_context
    ctx = build_order_form_context()
    site = SiteSettings.get()
    ctx['accepting_orders'] = site.accepting_orders
    ctx['SITE'] = site

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
    preselected = ctx.get('preselected_service')
    ctx['service_requires_file'] = preselected and preselected.requires_file
    ctx['show_service_notes'] = preselected and not preselected.requires_file
    ctx['note_categories'] = ['stationery', 'binding', 'lamination']

    if request.method == 'POST':
        try:
            order, coupon_warning = place_online_order(request)
            if coupon_warning:
                messages.warning(request, coupon_warning)
            messages.success(request, f'Order {order.order_number} placed successfully!')
            return redirect('user_order_detail', pk=order.pk)
        except OrderCreationError as exc:
            messages.error(request, str(exc))
        except (OSError, ImproperlyConfigured) as exc:
            messages.error(request, f'Could not upload your file. ({exc})')
        except Exception as exc:
            messages.error(request, f'Order could not be placed: {exc}')
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

# ─── ADMIN VIEWS ────────────────────────────────────────────────────────────────

@admin_required
def admin_dashboard(request):
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)
    two_weeks_ago = today - timedelta(days=14)
    month_start = today.replace(day=1)

    cache_key = f'admin_dashboard:{today.isoformat()}:{request.GET.get("range","7")}'
    cached = cache.get(cache_key)
    if cached:
        return cached

    from django.db.models.functions import TruncDay

    today_orders = Order.objects.filter(created_at__date=today).select_related('customer', 'walkin_customer')
    yesterday_orders = Order.objects.filter(created_at__date=yesterday)

    today_revenue = today_orders.aggregate(s=Sum('total_amount'))['s'] or 0
    yesterday_revenue = yesterday_orders.aggregate(s=Sum('total_amount'))['s'] or 0
    revenue_change = 0
    if yesterday_revenue > 0:
        revenue_change = round(((today_revenue - yesterday_revenue) / yesterday_revenue) * 100, 1)

    yesterday_orders_count = yesterday_orders.count()
    orders_today_count = today_orders.count()
    pending_count = Order.objects.filter(status__in=['pending', 'confirmed']).count()
    active_customers = User.objects.filter(orders__created_at__date=today).distinct().count()
    pages_today = today_orders.aggregate(p=Sum('total_sheets'))['p'] or 0
    orders_completed_today = today_orders.filter(status='delivered').count()
    failed_emails_24h = EmailLog.objects.filter(
        created_at__gte=timezone.now() - timedelta(hours=24),
        status='failed'
    ).count()
    low_stock_count = ServiceVariant.objects.filter(stock__lt=F('low_stock_threshold')).count()

    ready_not_picked = Order.objects.filter(
        status='ready', updated_at__lt=timezone.now() - timedelta(hours=24)
    ).count()
    pending_payment_reviews = Order.objects.filter(payment_status='pending_review').count()
    files_cleanup_48h = Order.objects.filter(
        file__isnull=False, file_deleted_at__isnull=True,
        updated_at__lt=timezone.now() - timedelta(hours=48),
    ).count()

    chart_range = request.GET.get('range', '7')
    days_back = 29 if chart_range == '30' else (89 if chart_range == '90' else 6)
    start_date = today - timedelta(days=days_back)

    revenue_by_day = Order.objects.filter(created_at__date__gte=start_date).annotate(
        day=TruncDay('created_at')
    ).values('day').annotate(
        revenue=Sum('total_amount')
    ).order_by('day')
    revenue_trend = [float(row['revenue'] or 0) for row in revenue_by_day]
    labels = [row['day'].strftime('%b %d') for row in revenue_by_day]

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

    volume_by_day = Order.objects.filter(created_at__date__gte=two_weeks_ago).annotate(
        day=TruncDay('created_at')
    ).values('day', 'source').annotate(
        cnt=Count('id')
    ).order_by('day', 'source')
    volume_map = {}
    for row in volume_by_day:
        day_str = row['day'].strftime('%b %d')
        volume_map.setdefault(day_str, {'online': 0, 'offline': 0})
        volume_map[day_str][row['source']] = row['cnt']
    volume_labels = sorted(volume_map.keys())
    online_data = [volume_map[d]['online'] for d in volume_labels]
    walkin_data = [volume_map[d]['offline'] for d in volume_labels]

    category_map = {}
    for sv in ServiceVariant.objects.select_related('service').all():
        cat = sv.service.category if sv.service else 'Other'
        category_map[cat] = category_map.get(cat, 0) + float(sv.price or 0)
    category_labels = list(category_map.keys())
    category_values = list(category_map.values())

    chart_backtests = [
        {'label': '7d', 'value': '7'},
        {'label': '30d', 'value': '30'},
        {'label': '90d', 'value': '90'},
    ]

    top_customers = User.objects.annotate(
        order_count=Count('orders', filter=Q(orders__created_at__date__gte=month_start)),
        revenue_sum=Sum('orders__total_amount', filter=Q(orders__created_at__date__gte=month_start)),
    ).filter(order_count__gt=0).order_by('-revenue_sum')[:5]
    top_customer_names = [c.get_full_name() or c.email for c in top_customers]
    top_customer_counts = [float(c.revenue_sum or 0) for c in top_customers]

    print_type_agg = OrderFile.objects.filter(
        created_at__date=today
    ).values('print_type', 'sides').annotate(
        cnt=Count('id')
    ).order_by('-cnt')
    print_type_labels = [
        f"{'B&W' if r['print_type']=='bw' else 'Color'} {'Single' if r['sides']=='single' else 'Double'}"
        for r in print_type_agg
    ]
    print_type_values = [r['cnt'] for r in print_type_agg]

    recent_orders = Order.objects.select_related('customer', 'walkin_customer').order_by('-created_at')[:10]

    activity_events = []

    def _relative_time(dt):
        now = timezone.now()
        delta = now - dt
        if delta.days > 0:
            return "{} day{} ago".format(delta.days, 's' if delta.days != 1 else '')
        if delta.seconds >= 3600:
            hours = delta.seconds // 3600
            return "{} hour{} ago".format(hours, 's' if hours != 1 else '')
        if delta.seconds >= 60:
            mins = delta.seconds // 60
            return "{} min ago".format(mins)
        return "Just now"

    for o in recent_orders:
        customer_label = o.customer_name
        if not customer_label and o.walkin_customer:
            customer_label = o.walkin_customer.name
        if not customer_label:
            customer_label = 'Guest'
        activity_events.append({
            'link': reverse('admin_order_detail', args=[o.pk]),
            'icon': 'bi bi-cart-plus',
            'text': "New order #{} placed by {}".format(o.order_number, customer_label),
            'timestamp': o.created_at,
            'time': _relative_time(o.created_at),
        })

    recent_status_logs = OrderStatusLog.objects.select_related('order', 'changed_by').order_by('-timestamp')[:10]
    for log in recent_status_logs:
        activity_events.append({
            'link': reverse('admin_order_detail', args=[log.order_id]),
            'icon': 'bi bi-arrow-repeat',
            'text': "Order #{} status changed to {}".format(log.order.order_number, log.new_status.replace('_', ' ').title()),
            'timestamp': log.timestamp,
            'time': _relative_time(log.timestamp),
        })

    recent_audit = AuditLog.objects.select_related('user').order_by('-timestamp')[:10]
    for entry in recent_audit:
        if 'payment' in entry.action.lower():
            icon = 'bi bi-wallet2'
        elif 'user' in entry.action.lower():
            icon = 'bi bi-person-plus'
        else:
            icon = 'bi bi-gear'
        res_id = entry.resource_id or ''
        try:
            res_id_int = int(res_id)
        except (TypeError, ValueError):
            res_id_int = None
        link = reverse('admin_order_detail', args=[res_id_int]) if res_id_int and entry.resource_type == 'order' else '#'
        activity_events.append({
            'link': link,
            'icon': icon,
            'text': entry.action.replace('_', ' ').title(),
            'timestamp': entry.timestamp,
            'time': _relative_time(entry.timestamp),
        })

    combined_activity = sorted(
        [e for e in activity_events if e.get('timestamp')],
        key=lambda x: x.get('timestamp', timezone.now()),
        reverse=True
    )[:5]

    db_status = get_database_status()
    db_healthy = db_status.get('default', {}).get('connected', False)
    db_latency = db_status.get('default', {}).get('latency_ms')

    storage_healthy = supabase_storage_enabled()
    email_healthy = EmailLog.objects.filter(status='failed', created_at__gte=timezone.now() - timedelta(hours=24)).count() == 0
    cache_healthy = bool(cache)
    supabase_auth_healthy = bool(supabase_project_url())

    ctx = {
        'today_orders_count': orders_today_count,
        'yesterday_orders_count': yesterday_orders_count,
        'today_revenue': today_revenue,
        'yesterday_revenue': yesterday_revenue,
        'revenue_change': revenue_change,
        'pending_count': pending_count,
        'active_customers': active_customers,
        'pages_today': pages_today,
        'avg_order_value': round(today_revenue / orders_today_count, 0) if orders_today_count else 0,
        'orders_completed_today': orders_completed_today,
        'failed_emails_24h': failed_emails_24h,
        'low_stock_count': low_stock_count,
        'revenue_trend_json': json.dumps(revenue_trend),
        'revenue_labels_json': json.dumps(labels),
        'chart_range': chart_range,
        'chart_status_json': json.dumps(list(chart_status.values())),
        'chart_status_labels_json': json.dumps(list(chart_status.keys())),
        'daily_volume_labels_json': json.dumps(volume_labels),
        'daily_volume_online_json': json.dumps(online_data),
        'daily_volume_walkin_json': json.dumps(walkin_data),
        'top_customer_names_json': json.dumps(top_customer_names),
        'top_customer_counts_json': json.dumps(top_customer_counts),
        'print_type_labels_json': json.dumps(print_type_labels),
        'print_type_values_json': json.dumps(print_type_values),
        'category_labels_json': json.dumps(category_labels),
        'category_values_json': json.dumps(category_values),
        'chart_backtests': chart_backtests,
        'recent_orders': recent_orders,
        'recent_activity': combined_activity,
        'ready_not_picked': ready_not_picked,
        'pending_payment_reviews': pending_payment_reviews,
        'files_cleanup_48h': files_cleanup_48h,
        'db_healthy': db_healthy,
        'db_latency': db_latency,
        'storage_healthy': storage_healthy,
        'email_healthy': email_healthy,
        'cache_healthy': cache_healthy,
        'supabase_auth_healthy': supabase_auth_healthy,
        'site_settings': SiteSettings.get(),
        'reminders': [
            {
                'label': 'Ready for Pickup',
                'sub': f'{ready_not_picked} orders waiting >24h',
                'count': ready_not_picked,
                'href': '{% url "admin_orders" %}?status=ready',
                'icon': 'bi bi-bag-check',
                'badge_class': 'bg-amber-500/15 text-amber-400 border border-amber-500/25',
            },
            {
                'label': 'Pending Payment Review',
                'sub': f'{pending_payment_reviews} awaiting approval',
                'count': pending_payment_reviews,
                'href': '{% url "admin_orders" %}?payment=pending_review',
                'icon': 'bi bi-wallet2',
                'badge_class': 'bg-brand-500/15 text-cyan-400 border border-cyan-500/25',
            },
            {
                'label': 'Low Stock',
                'sub': f'{low_stock_count} items below threshold',
                'count': low_stock_count,
                'href': '{% url "admin_inventory" %}',
                'icon': 'bi bi-box-seam',
                'badge_class': 'bg-red-500/15 text-red-400 border border-red-500/25',
            },
            {
                'label': 'File Cleanup Soon',
                'sub': f'{files_cleanup_48h} files eligible in 48h',
                'count': files_cleanup_48h,
                'href': '{% url "admin_system_status" %}',
                'icon': 'bi bi-file-earmark-x',
                'badge_class': 'bg-slate-500/15 text-slate-300 border border-slate-500/25',
            },
        ],
        'health_items': [
            {
                'label': 'Database',
                'sub': f'{"Connected" if db_healthy else "Offline"}' + (f' · {db_latency}ms' if db_latency else ''),
                'dot_class': 'bg-emerald-400' if db_healthy else 'bg-red-400',
            },
            {
                'label': 'Storage',
                'sub': 'Supabase S3',
                'dot_class': 'bg-emerald-400' if storage_healthy else 'bg-red-400',
            },
            {
                'label': 'Email',
                'sub': 'Brevo API',
                'dot_class': 'bg-emerald-400' if email_healthy else 'bg-red-400',
            },
            {
                'label': 'Cache',
                'sub': cache.__class__.__name__,
                'dot_class': 'bg-emerald-400' if cache_healthy else 'bg-red-400',
            },
            {
                'label': 'Supabase Auth',
                'sub': 'Configured' if supabase_auth_healthy else 'Not configured',
                'dot_class': 'bg-emerald-400' if supabase_auth_healthy else 'bg-amber-400',
            },
        ],
    }

    response = render(request, 'admin/dashboard.html', ctx)
    cache.set(cache_key, response, 60)
    return response


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

    # ── Bulk actions (POST) ──
    if request.method == 'POST':
        if request.user.is_readonly_staff:
            messages.error(request, 'Read-only access.')
            return redirect('admin_orders')
        bulk_action = request.POST.get('bulk_action')
        selected_ids = request.POST.getlist('selected_orders')
        if not selected_ids:
            messages.warning(request, 'No orders selected.')
            return redirect('admin_orders')
        orders = Order.objects.filter(pk__in=selected_ids)

        if bulk_action == 'bulk_status':
            new_status = request.POST.get('bulk_status_value', '')
            valid = [s[0] for s in Order.STATUS_CHOICES]
            if new_status not in valid:
                messages.error(request, 'Invalid status.')
            else:
                updated = 0
                for order in orders:
                    old_status = order.status
                    order.status = new_status
                    if new_status == 'delivered':
                        apply_order_delivered(order)
                    order.save()
                    OrderStatusLog.objects.create(
                        order=order, old_status=old_status,
                        new_status=new_status, changed_by=request.user,
                        note='Bulk status update.',
                    )
                    notify_order_status_change(order, old_status, changed_by=request.user)
                    updated += 1
                messages.success(request, f'{updated} order(s) updated to {new_status}.')

        elif bulk_action == 'bulk_delete':
            if not request.user.is_full_admin:
                messages.error(request, 'Only admins can delete orders.')
            else:
                count, _ = orders.delete()
                for oid in selected_ids:
                    log_audit(request, 'DELETE_ORDER', 'Order', '', old_value=f'bulk-delete-{oid}')
                messages.success(request, f'{count} order(s) deleted.')

        return redirect(f'{reverse("admin_orders")}?{request.META.get("QUERY_STRING", "")}')

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
        elif action == 'approve_payment':
            if not order.customer:
                messages.error(request, 'Walk-in orders use manual payment recording.')
                return redirect('admin_order_detail', pk=pk)
            order.payment_status = 'paid'
            order.amount_paid = order.total_amount
            order.payment_rejection_reason = ''
            order.save(update_fields=[
                'payment_status', 'amount_paid', 'payment_rejection_reason', 'updated_at',
            ])
            site = SiteSettings.get()
            notify_payment_approved(
                order, order.customer, request.user,
                send_email=site.send_email_on_payment_approved,
            )
            messages.success(request, 'Payment approved.')
            return redirect('admin_order_detail', pk=pk)
        elif action == 'reject_payment':
            if not order.customer:
                messages.error(request, 'Walk-in orders use manual payment recording.')
                return redirect('admin_order_detail', pk=pk)
            reason = request.POST.get('payment_rejection_reason', '').strip()[:500]
            order.payment_status = 'rejected'
            order.payment_rejection_reason = reason or 'Please contact support.'
            order.save(update_fields=['payment_status', 'payment_rejection_reason', 'updated_at'])
            site = SiteSettings.get()
            notify_payment_rejected(
                order, order.customer, request.user, reason=order.payment_rejection_reason,
                send_email=site.send_email_on_payment_rejected,
            )
            messages.warning(request, 'Payment rejected. Customer can resubmit.')
            return redirect('admin_order_detail', pk=pk)
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
    from .order_service import place_walkin_order, OrderCreationError, build_order_form_context
    ctx = build_order_form_context()
    ctx['walkin_customers'] = WalkInCustomer.objects.order_by('-last_visit')[:50]
    ctx['SITE'] = SiteSettings.get()

    if request.method == 'POST':
        try:
            order, coupon_warning, walkin = place_walkin_order(request)
            if coupon_warning:
                messages.warning(request, coupon_warning)
            messages.success(request, f'Walk-in order {order.order_number} created!')
            return redirect('admin_order_detail', pk=order.pk)
        except OrderCreationError as exc:
            messages.error(request, str(exc))
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
    variants = ServiceVariant.objects.select_related('service').all().order_by('service__category', 'service__name', 'name')
    items = InventoryItem.objects.select_related('variant__service').all().order_by('category', 'name')
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
        elif action == 'adjust_variant':
            variant = get_object_or_404(ServiceVariant, pk=request.POST['variant_id'])
            qty = int(request.POST['quantity'])
            move = request.POST['movement']
            note = request.POST.get('note', '')
            if move == 'in':
                variant.stock += qty
            else:
                variant.stock = max(0, variant.stock - qty)
            variant.save(update_fields=['stock', 'updated_at'])
            if note:
                from .notifications import notify_stock_low
                notify_stock_low(variant)
            messages.success(request, f'{variant.name} stock updated to {variant.stock}.')
        return redirect('admin_inventory')
    return render(request, 'admin/inventory.html', {
        'items': items,
        'variants': variants,
    })


@permission_required('manage_pricing')
def admin_services(request):
    from .models import AddonService, Service, ServiceVariant, InventoryItem

    SERVICE_ATTRIBUTE_SPECS = {
        'printing': [
            {'field': 'paper_size', 'label': 'Paper Size', 'type': 'select', 'options': ['A4', 'A3', 'Letter', 'Legal']},
            {'field': 'gsm', 'label': 'GSM', 'type': 'number', 'min': 50, 'max': 400},
            {'field': 'color', 'label': 'Color Type', 'type': 'select', 'options': ['bw', 'color']},
            {'field': 'sides', 'label': 'Sides', 'type': 'select', 'options': ['single', 'double']},
        ],
        'photo': [
            {'field': 'dimensions', 'label': 'Dimensions', 'type': 'text'},
            {'field': 'material', 'label': 'Material', 'type': 'select', 'options': ['Matte', 'Glossy', 'Satin', 'Metallic']},
            {'field': 'paper_type', 'label': 'Paper Type', 'type': 'select', 'options': ['Photo Paper', 'Canvas', 'Glossy Paper', 'Luster Paper']},
        ],
        'binding': [
            {'field': 'binding_type', 'label': 'Binding Type', 'type': 'text'},
            {'field': 'cover_type', 'label': 'Cover Type', 'type': 'select', 'options': ['Hard', 'Soft', 'Spiral']},
            {'field': 'thickness', 'label': 'Thickness', 'type': 'number', 'min': 1, 'max': 100},
        ],
        'lamination': [
            {'field': 'finish', 'label': 'Finish', 'type': 'select', 'options': ['Glossy', 'Matte', 'Satin']},
            {'field': 'thickness', 'label': 'Micron', 'type': 'number', 'min': 50, 'max': 250},
        ],
        'stationery': [
            {'field': 'color', 'label': 'Color', 'type': 'text'},
            {'field': 'brand', 'label': 'Brand', 'type': 'text'},
        ],
        'custom': [],
    }

    addons = AddonService.objects.all()
    services = Service.objects.prefetch_related('variants').all().order_by('category', 'name')
    can_manage_addons = request.user.role in ('manager', 'admin', 'super_admin')
    current_category = request.GET.get('category', 'all')
    if current_category and current_category != 'all':
        services = services.filter(category=current_category)
    category_choices = Service.CATEGORY_CHOICES
    if request.method == 'POST':
        if request.user.is_readonly_staff:
            messages.error(request, 'Read-only access.')
            return redirect('admin_services')
        action = request.POST.get('action')
        if action == 'toggle_addon' and can_manage_addons:
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
        elif action == 'toggle_service' and can_manage_addons:
            service = get_object_or_404(Service, pk=request.POST['service_id'])
            service.is_active = not service.is_active
            service.save()
            messages.success(request, f'Service {"enabled" if service.is_active else "disabled"}.')
        elif action == 'add_service' and can_manage_addons:
            Service.objects.create(
                name=request.POST['name'],
                base_price=request.POST['base_price'],
                category=request.POST.get('category', 'printing'),
                description=request.POST.get('description', ''),
                requires_file = request.POST.get('requires_file') == 'on'
            )
            messages.success(request, 'Service created.')
        elif action == 'delete_service' and request.user.is_full_admin:
            service = get_object_or_404(Service, pk=request.POST['service_id'])
            name = service.name
            service.delete()
            messages.success(request, f'Service {name} deleted.')
        elif action == 'add_variant' and can_manage_addons:
            service = get_object_or_404(Service, pk=request.POST['service_id'])
            specs = {}
            for key, value in request.POST.items():
                if key.startswith('specs_'):
                    specs[key.replace('specs_', '')] = value
            price_val = request.POST.get('price', '0') or '0'
            variant = ServiceVariant.objects.create(
                service=service,
                name=request.POST['name'],
                price=Decimal(price_val),
                specs=specs,
                stock=int(request.POST.get('stock', '0') or '0'),
                low_stock_threshold=int(request.POST.get('low_stock_threshold', '5') or '5')
            )
            messages.success(request, 'Variant created.')
        elif action == 'delete_variant' and request.user.is_full_admin:
            variant = get_object_or_404(ServiceVariant, pk=request.POST['variant_id'])
            variant.delete()
            messages.success(request, 'Variant deleted.')
        elif action == 'edit_service' and can_manage_addons:
            service = get_object_or_404(Service, pk=request.POST['service_id'])
            service.name = request.POST['name']
            service.category = request.POST.get('category', 'printing')
            service.base_price = Decimal(request.POST.get('base_price', '0') or '0')
            service.requires_file = request.POST.get('requires_file') == 'on'
            service.description = request.POST.get('description', '')
            service.save(update_fields=['name', 'category', 'base_price', 'requires_file', 'description', 'updated_at'])
            messages.success(request, 'Service updated.')
        elif action == 'edit_variant' and can_manage_addons:
            variant = get_object_or_404(ServiceVariant, pk=request.POST['variant_id'])
            variant.name = request.POST['name']
            variant.price = Decimal(request.POST.get('price', '0') or '0')
            variant.stock = int(request.POST.get('stock', '0') or '0')
            variant.low_stock_threshold = int(request.POST.get('low_stock_threshold', '5') or '5')
            specs = {}
            for key, value in request.POST.items():
                if key.startswith('specs_'):
                    specs[key.replace('specs_', '')] = value
            variant.specs = specs
            variant.save(update_fields=['name', 'price', 'stock', 'low_stock_threshold', 'specs', 'updated_at'])
            messages.success(request, 'Variant updated.')
        return redirect('admin_services')
    return render(request, 'admin/services.html', {
        'addons': addons,
        'services': services,
        'can_manage_addons': can_manage_addons,
        'service_attribute_specs': SERVICE_ATTRIBUTE_SPECS,
        'category_choices': category_choices,
        'current_category': current_category,
    })


@permission_required('manage_pricing')
def admin_coupons(request):
    """Admin view to list and manage coupons."""
    coupons = Coupon.objects.all().order_by('-id')
    if request.method == 'POST':
        if request.user.is_readonly_staff:
            messages.error(request, 'Read-only access.')
            return redirect('admin_coupons')
        action = request.POST.get('action')
        if action == 'create':
            code = request.POST.get('code', '').strip().upper()
            if Coupon.objects.filter(code=code).exists():
                messages.error(request, 'Coupon code already exists.')
            else:
                min_amt = request.POST.get('min_order_amount')
                max_us = request.POST.get('max_uses')
                valid_from_val = request.POST.get('valid_from')
                valid_to_val = request.POST.get('valid_to')
                Coupon.objects.create(
                    code=code,
                    discount_type=request.POST.get('discount_type', 'percentage'),
                    discount_value=Decimal(request.POST.get('discount_value', '0')),
                    min_order_amount=Decimal(min_amt) if min_amt else None,
                    max_uses=int(max_us) if max_us else None,
                    valid_from=valid_from_val if valid_from_val else timezone.now(),
                    valid_to=valid_to_val if valid_to_val else None,
                    is_active=True
                )
                messages.success(request, f'Coupon {code} created.')
        elif action == 'edit':
            coupon = get_object_or_404(Coupon, pk=request.POST.get('coupon_id'))
            code = request.POST.get('code', '').strip().upper()
            if Coupon.objects.filter(code=code).exclude(pk=coupon.pk).exists():
                messages.error(request, 'Coupon code already exists.')
            else:
                coupon.code = code
                coupon.discount_type = request.POST.get('discount_type', 'percentage')
                coupon.discount_value = Decimal(request.POST.get('discount_value', '0'))
                min_amt = request.POST.get('min_order_amount')
                coupon.min_order_amount = Decimal(min_amt) if min_amt else None
                max_us = request.POST.get('max_uses')
                coupon.max_uses = int(max_us) if max_us else None
                valid_from = request.POST.get('valid_from')
                coupon.valid_from = valid_from if valid_from else timezone.now()
                valid_to = request.POST.get('valid_to')
                coupon.valid_to = valid_to if valid_to else None
                coupon.save()
                messages.success(request, f'Coupon {code} updated.')
        elif action == 'toggle':
            coupon = get_object_or_404(Coupon, pk=request.POST.get('coupon_id'))
            coupon.is_active = not coupon.is_active
            coupon.save(update_fields=['is_active'])
            messages.success(request, f'Coupon {coupon.code} updated.')
        elif action == 'delete' and request.user.is_full_admin:
            coupon = get_object_or_404(Coupon, pk=request.POST.get('coupon_id'))
            code = coupon.code
            coupon.delete()
            messages.success(request, f'Coupon {code} deleted.')
        return redirect('admin_coupons')
    return render(request, 'admin/coupons.html', {'coupons': coupons})


@permission_required('view_financial')
def admin_financial(request):
    today = timezone.now().date()
    expenses = Expense.objects.order_by('-date')[:50]
    if request.method == 'POST':
        if request.user.is_readonly_staff:
            messages.error(request, 'Read-only access.')
            return redirect('admin_financial')
        action = request.POST.get('action')
        if action == 'log_expense':
            Expense.objects.create(
                category=request.POST['category'], description=request.POST['description'],
                amount=request.POST['amount'], payment_method=request.POST.get('payment_method', 'Cash'),
                date=request.POST.get('date', today), logged_by=request.user,
            )
            messages.success(request, 'Expense logged.')
        elif action == 'mark_paid':
            order = get_object_or_404(Order, pk=request.POST.get('order_id'))
            order.payment_status = 'paid'
            order.amount_paid = order.total_amount
            order.save(update_fields=['payment_status', 'amount_paid', 'updated_at'])
            messages.success(request, f'Order {order.order_number} marked as paid.')
        elif action == 'send_reminder':
            from .notifications import send_notification
            order = get_object_or_404(Order, pk=request.POST.get('order_id'))
            if order.customer:
                send_notification(
                    recipient=order.customer,
                    verb=f'payment reminder for order #{order.order_number}',
                    target_type='payment',
                    target_id=order.id,
                    target_url=reverse('user_order_payment', args=[order.id]),
                    actor=request.user,
                    description=f'Please complete the payment of ৳{order.amount_due} for order #{order.order_number}.',
                )
                messages.success(request, f'Reminder sent to {order.customer_name}.')
            else:
                messages.warning(request, 'Walk-in orders cannot receive in-app reminders.')
        return redirect('admin_financial')

    week_revenue = Order.objects.filter(
        created_at__date__gte=today - timedelta(days=7)
    ).aggregate(s=Sum('total_amount'))['s'] or 0
    week_expenses = Expense.objects.filter(
        date__gte=today - timedelta(days=7)
    ).aggregate(s=Sum('amount'))['s'] or 0

    # Due / outstanding payments
    due_orders = list(Order.objects.filter(
        payment_status__in=['unpaid', 'partial', 'pending_review', 'rejected'],
        status__in=['pending', 'confirmed', 'printing', 'quality_check', 'ready', 'on_hold'],
    ).exclude(total_amount=0).select_related('customer', 'walkin_customer').order_by('-created_at')[:100])
    total_outstanding = sum((o.amount_due for o in due_orders), Decimal('0'))

    return render(request, 'admin/financial.html', {
        'expenses': expenses,
        'week_revenue': week_revenue,
        'week_expenses': week_expenses,
        'week_profit': week_revenue - week_expenses,
        'due_orders': due_orders,
        'total_outstanding': total_outstanding,
        'due_count': len(due_orders),
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
        site.bkash_number = request.POST.get('bkash_number', '').strip()
        site.nagad_number = request.POST.get('nagad_number', '').strip()
        site.rocket_number = request.POST.get('rocket_number', '').strip()
        site.max_upload_mb = safe_int(request.POST.get('max_upload_mb', 50), default=50, minimum=1)
        site.currency_symbol = request.POST.get('currency_symbol', '৳')[:5] or '৳'
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

@permission_required('manage_staff')
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
        elif action == 'update_custom_permissions' and request.user.role == 'super_admin':
            user = get_object_or_404(User, pk=request.POST.get('user_id'))
            perms = request.POST.getlist('permissions')
            user.custom_permissions = perms if perms else None
            user.save(update_fields=['custom_permissions'])
            log_audit(request, 'UPDATE_PERMISSIONS', 'User', user.pk, new_value=str(perms))
            messages.success(request, f'Custom permissions updated for {user.display_name}.')
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
    from .permissions import PERMISSIONS
    permissions_list = list(PERMISSIONS.keys())
    return render(request, 'admin/staff.html', {
        'staff': staff,
        'staff_roles': staff_roles,
        'can_manage': request.user.is_full_admin,
        'permission_matrix': PERMISSION_MATRIX,
        'permissions_list': permissions_list,
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
