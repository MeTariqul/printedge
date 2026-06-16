from django.db.models import Sum, Count, Q, F
from django.db.models.functions import TruncDay
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.views.decorators.cache import cache_page
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





def public_index(request):
    featured_services = Service.objects.filter(is_active=True).prefetch_related('variants').order_by('-created_at')[:4]
    return render(request, 'index.html', {'featured_services': featured_services})


@cache_page(60 * 15)
def public_pricing(request):
    addons = AddonService.objects.filter(is_active=True)
    services = Service.objects.filter(is_active=True).prefetch_related('variants').order_by('category', 'name')
    return render(request, 'pricing.html', {'addons': addons, 'services': services})


@cache_page(60 * 15)
def public_services(request):
    # Legacy – renders same template as public_services
    services = Service.objects.filter(is_active=True).prefetch_related('variants').order_by('category', 'name')
    addons = AddonService.objects.filter(is_active=True)
    return render(request, 'services.html', {'services': services, 'addons': addons})




def public_contact(request):
    return render(request, 'contact.html')




# --- PWA MANIFEST ---


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


