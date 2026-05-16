"""Admin operations: system status, file downloads, cron purge."""

import os
import sys
import time

import django
from django.conf import settings
from django.db import connection
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.utils import timezone

from .decorators import admin_required, superadmin_required
from .models import Order, SiteSettings, User
from .order_files import purge_expired_order_files, orders_eligible_for_purge, delete_order_file
from .storage import supabase_storage_enabled, supabase_project_url


def _cron_authorized(request):
    secret = getattr(settings, 'CRON_SECRET', '') or os.environ.get('CRON_SECRET', '')
    if not secret:
        return False
    header = request.headers.get('Authorization', '')
    if header.startswith('Bearer '):
        return header[7:] == secret
    return request.headers.get('X-Cron-Secret') == secret or request.GET.get('secret') == secret


@superadmin_required
def admin_system_status(request):
    site = SiteSettings.get()
    db_ok = False
    db_latency_ms = None
    db_version = ''
    try:
        t0 = time.perf_counter()
        with connection.cursor() as cursor:
            cursor.execute('SELECT version()')
            row = cursor.fetchone()
            db_version = (row[0] if row else '')[:120]
        db_latency_ms = round((time.perf_counter() - t0) * 1000, 1)
        db_ok = True
    except Exception as exc:
        db_version = str(exc)[:200]

    pending_purge = orders_eligible_for_purge().count()
    files_with_attachment = Order.objects.filter(file_deleted_at__isnull=True).exclude(file='').count()
    orders_today = Order.objects.filter(created_at__date=timezone.now().date()).count()

    storage_backend = 'Supabase S3' if supabase_storage_enabled() else 'Local filesystem'
    supabase_url = supabase_project_url()

    if request.method == 'POST' and request.POST.get('action') == 'purge_now':
        count = purge_expired_order_files(request=request)
        messages.success(request, f'Purged {count} expired order file(s).')
        return redirect('admin_system_status')

    ctx = {
        'site': site,
        'db_ok': db_ok,
        'db_latency_ms': db_latency_ms,
        'db_version': db_version,
        'django_version': django.get_version(),
        'python_version': sys.version.split()[0],
        'debug': settings.DEBUG,
        'timezone': settings.TIME_ZONE,
        'storage_backend': storage_backend,
        'supabase_url': supabase_url,
        'pending_purge': pending_purge,
        'files_with_attachment': files_with_attachment,
        'orders_today': orders_today,
        'user_count': User.objects.count(),
        'order_count': Order.objects.count(),
        'cron_configured': bool(getattr(settings, 'CRON_SECRET', '')),
    }
    return render(request, 'admin/system_status.html', ctx)


def api_cron_purge_files(request):
    if request.method not in ('GET', 'POST'):
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    if not _cron_authorized(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    dry_run = request.GET.get('dry_run') == '1'
    count = purge_expired_order_files(dry_run=dry_run)
    return JsonResponse({'success': True, 'purged': count, 'dry_run': dry_run})


def _order_file_access_allowed(request, order):
    if request.user.is_authenticated and request.user.is_admin_user:
        return True
    if request.user.is_authenticated and order.customer_id == request.user.id:
        return True
    return False


def order_download_file(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if not _order_file_access_allowed(request, order):
        return JsonResponse({'error': 'Forbidden'}, status=403)
    if not order.has_stored_file:
        raise Http404('File not available.')
    try:
        fh = order.file.open('rb')
        filename = order.file_name or os.path.basename(order.file.name)
        return FileResponse(fh, as_attachment=True, filename=filename)
    except Exception:
        raise Http404('File not found in storage.')


@admin_required
def admin_order_delete_file(request, pk):
    if not request.user.is_full_admin:
        messages.error(request, 'Only admins can delete order files.')
        return redirect('admin_order_detail', pk=pk)
    order = get_object_or_404(Order, pk=pk)
    if request.method == 'POST':
        if delete_order_file(order, request=request, reason='admin_manual'):
            messages.success(request, 'Order file removed from storage.')
        else:
            messages.warning(request, 'No file to delete.')
    return redirect('admin_order_detail', pk=pk)
