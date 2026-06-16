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
            if user.role == 'finance':
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
    return render(request, 'auth/verify_invalid.html', {'user': user})


def auth_logout(request):
    logout(request)
    return redirect('public_index')


