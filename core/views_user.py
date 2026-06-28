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





# user_profile moved to frontend_views.py

