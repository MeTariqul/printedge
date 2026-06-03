"""Admin operations: system status, file downloads, cron purge."""

import os
import sys
import time
import socket
import platform

import django
from django.conf import settings
from django.core.cache import cache
from django.db import connections
from django.db.models import Sum, Q
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.contrib import messages
from django.utils import timezone
from django.utils.html import strip_tags
from django.urls import reverse
from django.contrib import messages
from django.utils import timezone

from .decorators import admin_required, superadmin_required, permission_required
from .models import Order, OrderFile, SiteSettings, User, AuditLog, EmailLog, EmailTemplate
from .order_files import (
    purge_expired_order_files,
    orders_eligible_for_purge,
    delete_order_file,
    delete_single_order_file,
)
from .storage import supabase_storage_enabled, supabase_project_url, supabase_s3_endpoint
from .invoice_pdf import generate_order_invoice_pdf
from .system_utils import (
    get_server_info,
    get_database_status,
    get_cache_status,
    get_application_metrics,
)


def _test_storage_connection():
    """Test Supabase S3 storage by listing objects (avoids HeadObject 403)."""
    if not supabase_storage_enabled():
        return {'connected': False, 'error': 'Supabase storage not configured', 'status_detail': None, 'total_files': 0, 'total_size_bytes': 0}
    try:
        import boto3
        from botocore.exceptions import ClientError
        # Build endpoint using project ref from SUPABASE_URL
        supabase_url = supabase_project_url()
        bucket = os.environ.get('SUPABASE_STORAGE_BUCKET', 'order-files')
        project_ref = supabase_url.split('//')[-1].split('.')[0] if '.supabase.co' in supabase_url else ''
        endpoint = f'https://{project_ref}.storage.supabase.co/storage/v1/s3'
        # Use dedicated S3 access keys from env
        access_key = os.environ.get('SUPABASE_S3_ACCESS_KEY_ID', os.environ.get('SUPABASE_SERVICE_ROLE_KEY', ''))
        secret_key = os.environ.get('SUPABASE_S3_SECRET_ACCESS_KEY', os.environ.get('SUPABASE_SERVICE_ROLE_KEY', ''))
        s3 = boto3.client(
            's3',
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name='auto',
            config=boto3.session.Config(signature_version='s3v4'),
        )
        file_count = 0
        total_size = 0
        paginator = s3.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=bucket, PaginationConfig={'MaxItems': 1000}):
            if 'Contents' in page:
                for obj in page['Contents']:
                    file_count += 1
                    total_size += obj.get('Size', 0)
        try:
            s3.head_object(Bucket=bucket, Key='health-check.txt')
            status_detail = 'Operational'
        except ClientError as e:
            err_code = e.response.get('Error', {}).get('Code', '')
            err_msg = e.response.get('Error', {}).get('Message', '')
            if err_code == '404' or err_msg == 'Not Found':
                status_detail = 'Connected (health-check.txt missing - optional file)'
            elif err_code == 'NoSuchBucket':
                status_detail = 'Bucket not found - create order-files bucket in Supabase Dashboard'
            elif err_code == 'InvalidAccessKeyId':
                status_detail = 'Invalid Access Key - check SUPABASE_S3_ACCESS_KEY_ID'
            elif err_code == '403' or 'Forbidden' in err_msg:
                status_detail = 'Permission error - check bucket policy'
            else:
                status_detail = f'HEAD error ({err_code}): {err_msg[:50]}'
        except Exception:
            status_detail = 'Connected'
        return {'connected': True, 'status_detail': status_detail, 'total_files': file_count, 'total_size_bytes': total_size, 'error': None}
    except Exception as exc:
        err_msg = str(exc)
        status = 'Connection Error'
        code = None
        # Extract error code if present
        if 'InvalidAccessKeyId' in err_msg or 'InvalidAccessKey' in err_msg:
            status = 'Invalid Access Key - check SUPABASE_SERVICE_ROLE_KEY'
        elif '403' in err_msg or 'Forbidden' in err_msg:
            status = 'Permission error (403) - check bucket policy'
        elif 'NoSuchBucket' in err_msg or 'Not Found' in err_msg:
            status = 'Bucket not found - create order-files bucket in Supabase'
        return {'connected': False, 'error': err_msg[:200], 'status_detail': status, 'total_files': 0, 'total_size_bytes': 0}


def _test_email_connection():
    """Test Brevo API email configuration."""
    api_key = getattr(settings, 'BREVO_API_KEY', '') or ''
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', '')
    if not api_key:
        return {'connected': False, 'status': 'Not configured', 'error': 'No BREVO_API_KEY configured', 'from_email': from_email}
    masked_key = api_key[:8] + '****' if api_key else 'Not configured'
    return {'connected': True, 'status': 'Brevo API', 'error': None, 'masked_user': masked_key, 'from_email': from_email}


def _test_cache_connection():
    """Test cache backend status."""
    backend = cache.__class__.__module__ + '.' + cache.__class__.__name__
    is_redis = 'redis' in backend.lower()
    info = {'backend': backend, 'is_redis': is_redis, 'memory_used_mb': None, 'connected': True, 'error': None}
    try:
        cache.set('system_status_test', 'ok', 10)
        if cache.get('system_status_test') == 'ok':
            info['connected'] = True
            if is_redis:
                try:
                    redis_client = cache._client.get_client()
                    info['memory_used_mb'] = round(redis_client.info().get('used_memory', 0) / 1024 / 1024, 1)
                except Exception:
                    info['memory_used_mb'] = None
        else:
            info['connected'] = False
            info['error'] = 'Cache read/write mismatch'
    except Exception as exc:
        info['connected'] = False
        info['error'] = str(exc)[:100]
    return info


def _get_server_info():
    """Get server system information."""
    info = {}
    try:
        info['hostname'] = socket.gethostname()
        info['ip_address'] = socket.gethostbyname(info['hostname'])
    except Exception:
        info['hostname'] = 'N/A'
        info['ip_address'] = 'N/A'
    try:
        info['platform'] = platform.platform()
    except Exception:
        info['platform'] = 'N/A'
    try:
        import psutil
        info['uptime_seconds'] = int(time.time() - psutil.boot_time())
        info['load_avg'] = os.getloadavg()
    except ImportError:
        info['uptime_seconds'] = None
        info['load_avg'] = None
    return info


def _get_auth_status():
    """Check Supabase Auth/JWT configuration."""
    supabase_url = supabase_project_url()
    if not supabase_url:
        return {'connected': False, 'error': 'Supabase URL not configured', 'has_jwt_secret': False}
    anon_key = os.environ.get('SUPABASE_ANON_KEY', '')
    jwt_secret = os.environ.get('SUPABASE_JWT_SECRET', '')
    has_jwt_secret = bool(jwt_secret)
    return {'connected': True, 'error': None, 'has_jwt_secret': has_jwt_secret, 'project_ref': supabase_url.split('//')[-1].split('.')[0] if '.supabase.co' in supabase_url else 'N/A'}


def _get_revenue_today():
    """Calculate revenue for today."""
    today = timezone.now().date()
    return Order.objects.filter(created_at__date=today, payment_status='paid').aggregate(
        total=Sum('total_amount')
    )['total'] or 0


def _get_order_counts():
    """Get order statistics."""
    today = timezone.now().date()
    return {
        'total': Order.objects.count(),
        'today': Order.objects.filter(created_at__date=today).count(),
        'pending': Order.objects.filter(status__in=['pending', 'confirmed']).count(),
        'ready': Order.objects.filter(status__in=['ready', 'delivered']).count(),
    }


def _get_user_counts():
    """Get user statistics."""
    today = timezone.now().date()
    week_ago = timezone.datetime(today.year, today.month, today.day) - timezone.timedelta(days=7)
    return {
        'total': User.objects.filter(role='customer').count(),
        'active_today': User.objects.filter(last_login__date=today).count(),
        'new_this_week': User.objects.filter(date_joined__gte=week_ago.date()).count(),
    }


def _get_file_stats():
    """Get file storage statistics."""
    total_size = 0
    count = OrderFile.objects.exclude(file='').exclude(file__isnull=True).count()
    legacy = Order.objects.exclude(file='').exclude(file__isnull=True).count()
    return {'file_count': count + legacy, 'total_size_bytes': total_size}


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

    # Use helper functions from system_utils
    server_info = get_server_info()
    db_status = get_database_status()
    cache_status = get_cache_status()
    app_metrics = get_application_metrics()

    # Ensure supabase key exists for template - check API config, not DB
    if 'supabase' not in db_status:
        # Check Supabase API connectivity
        supabase_url = os.environ.get('SUPABASE_URL', '')
        supabase_anon_key = os.environ.get('SUPABASE_ANON_KEY', '')
        if supabase_url and supabase_anon_key:
            db_status['supabase'] = {
                'connected': True,
                'vendor': 'supabase_api',
                'version': 'Configured (API)',
                'latency_ms': None,
                'table_count': 0,
                'size_mb': 0,
            }
        else:
            db_status['supabase'] = {
                'connected': False,
                'vendor': 'not_configured',
                'version': 'Not configured',
                'latency_ms': None,
                'table_count': 0,
                'size_mb': 0,
            }

    storage_status = _test_storage_connection()
    email_status = _test_email_connection()
    auth_status = _get_auth_status()
    file_stats = _get_file_stats()

    # Calculate health status
    db_ok = db_status.get('default', {}).get('connected', False)
    supabase_ok = db_status.get('supabase', {}).get('connected', False)

    subsystems = {
        'database': db_ok,
        'supabase': supabase_ok,
        'storage': storage_status.get('connected', False),
        'email': email_status.get('connected', False),
        'cache': cache_status.get('connected', True),
    }
    all_ok = all(subsystems.values())
    has_warning = any(not v for v in subsystems.values())
    if all_ok:
        health_status = 'operational'
        health_emoji = '🟢'
    elif has_warning:
        health_status = 'degraded'
        health_emoji = '🟡'
    else:
        health_status = 'outage'
        health_emoji = '🔴'

    pending_purge = orders_eligible_for_purge().count()
    files_with_attachment = Order.objects.filter(file_deleted_at__isnull=True).exclude(file='').count()

    # Email failure stats
    from django.utils import timezone
    from datetime import timedelta
    from .models import EmailLog
    failed_emails_24h = EmailLog.objects.filter(
        status='failed', created_at__gte=timezone.now() - timedelta(hours=24)
    ).count()

    # Security info
    security_status = {
        'debug': settings.DEBUG,
        'csrf_enabled': True,  # Always enabled in Django
        'ssl_secured': request.is_secure() if request else False,
        'allowed_hosts': list(getattr(settings, 'ALLOWED_HOSTS', [])),
        'session_timeout': settings.SESSION_COOKIE_AGE,
    }

    # Recent activity
    recent_audits = AuditLog.objects.select_related('user').order_by('-timestamp')[:5]
    recent_orders = Order.objects.select_related('customer', 'walkin_customer').order_by('-created_at')[:5]

    if request.method == 'POST' and request.POST.get('action') == 'purge_now':
        count = purge_expired_order_files(request=request)
        messages.success(request, f'Purged {count} expired order file(s).')
        return redirect('admin_system_status')

    ctx = {
        'site': site,
        'server_info': server_info,
        'db_status': db_status,
        'cache_status': cache_status,
        'storage_status': storage_status,
        'email_status': email_status,
        'auth_status': auth_status,
        'app_metrics': app_metrics,
        'file_stats': file_stats,
        'security_status': security_status,
        'recent_audits': recent_audits,
        'recent_orders': recent_orders,
        'pending_purge': pending_purge,
        'files_with_attachment': files_with_attachment,
        'failed_emails_24h': failed_emails_24h,
        'supabase_url': supabase_project_url(),
        'storage_bucket': os.environ.get('SUPABASE_STORAGE_BUCKET', ''),
        'cron_configured': bool(getattr(settings, 'CRON_SECRET', '')),
        'health_status': health_status,
        'health_emoji': health_emoji,
        'django_version': django.get_version(),
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


def order_invoice_pdf(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if not _order_file_access_allowed(request, order):
        messages.error(request, 'You do not have permission to view this invoice.')
        return redirect('auth_login_page' if not request.user.is_authenticated else 'user_dashboard')
    try:
        pdf_bytes = generate_order_invoice_pdf(order)
    except Exception as exc:
        messages.error(request, f'Could not generate invoice: {exc}')
        if request.user.is_admin_user:
            return redirect('admin_order_detail', pk=pk)
        return redirect('user_order_detail', pk=pk)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="invoice-{order.order_number}.pdf"'
    return response


def order_download_file(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if not _order_file_access_allowed(request, order):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'Forbidden'}, status=403)
        from django.contrib import messages
        messages.error(request, 'You do not have permission to download this file.')
        return redirect('auth_login_page' if not request.user.is_authenticated else 'user_dashboard')

    file_id = request.GET.get('file_id')
    if file_id:
        from .models import OrderFile
        of = get_object_or_404(OrderFile, pk=file_id, order=order)
        if not of.file or not of.file.name:
            raise Http404('File not available.')
        try:
            fh = of.file.open('rb')
            return FileResponse(fh, as_attachment=True, filename=of.file_name or os.path.basename(of.file.name))
        except Exception:
            raise Http404('File not found in storage.')

    if not order.has_stored_file:
        raise Http404('File not available.')
    try:
        fh = order.file.open('rb')
        filename = order.file_name or os.path.basename(order.file.name)
        return FileResponse(fh, as_attachment=True, filename=filename)
    except Exception:
        raise Http404('File not found in storage.')


@permission_required('view_orders')
def admin_uploaded_files(request):
    files_qs = (
        OrderFile.objects
        .select_related('order', 'order__customer', 'order__walkin_customer')
        .exclude(file='')
        .order_by('-created_at')
    )
    legacy_order_ids = set(files_qs.values_list('order_id', flat=True))
    legacy = (
        Order.objects
        .exclude(file='')
        .exclude(pk__in=legacy_order_ids)
        .select_related('customer', 'walkin_customer')
        .order_by('-created_at')
    )
    if request.method == 'POST':
        if request.user.is_readonly_staff:
            messages.error(request, 'Read-only access.')
            return redirect('admin_uploaded_files')
        file_id = request.POST.get('file_id')
        order_id = request.POST.get('order_id')
        if file_id:
            order_file = get_object_or_404(OrderFile, pk=file_id)
            delete_single_order_file(order_file, request=request)
            messages.success(request, f'File "{order_file.file_name}" removed from storage.')
        elif order_id:
            order = get_object_or_404(Order, pk=order_id)
            if delete_order_file(order, request=request, reason='admin_files_tab'):
                messages.success(request, f'Files for order {order.order_number} removed.')
            else:
                messages.warning(request, 'No file to delete.')
        return redirect('admin_uploaded_files')

    return render(request, 'admin/uploaded_files.html', {
        'order_files': files_qs,
        'legacy_orders': legacy,
    })


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


@admin_required
def admin_email_logs(request):
    status_filter = request.GET.get('status', '')
    logs_qs = EmailLog.objects.all().order_by('-created_at')
    if status_filter in ('sent', 'failed'):
        logs_qs = logs_qs.filter(status=status_filter)
    return render(request, 'admin/email_logs.html', {
        'logs': logs_qs[:200],
        'current_status': status_filter,
    })


@admin_required
def admin_mail_dashboard(request):
    from django.db.models import Count
    from django.utils import timezone
    from datetime import timedelta
    import json

    now = timezone.now()
    today = now.date()
    thirty_days_ago = now - timedelta(days=30)

    # Statistics
    total_emails = EmailLog.objects.count()
    emails_today = EmailLog.objects.filter(created_at__date=today).count()
    failed_today = EmailLog.objects.filter(status='failed', created_at__date=today).count()

    # Daily email volume (last 30 days)
    daily_data = EmailLog.objects.filter(created_at__gte=thirty_days_ago).extra(
        select={'day': 'date(created_at)'}
    ).values('day').annotate(
        sent=Count('id', filter=Q(status='sent')),
        failed=Count('id', filter=Q(status='failed'))
    ).order_by('day')

    # Delivery status distribution
    sent_count = EmailLog.objects.filter(status='sent').count()
    failed_count = EmailLog.objects.filter(status='failed').count()

    # Recent emails
    recent_emails = EmailLog.objects.all().order_by('-created_at')[:10]

    chart_labels = json.dumps([str(d['day']) for d in daily_data])
    chart_sent = json.dumps([d['sent'] for d in daily_data])
    chart_failed = json.dumps([d['failed'] for d in daily_data])

    return render(request, 'admin/mail_dashboard.html', {
        'total_emails': total_emails,
        'emails_today': emails_today,
        'failed_today': failed_today,
        'chart_labels': chart_labels,
        'chart_sent': chart_sent,
        'chart_failed': chart_failed,
        'sent_count': sent_count,
        'failed_count': failed_count,
        'recent_emails': recent_emails,
    })


@admin_required
def admin_mail_compose(request):
    from .email_utils import send_brevo_email
    from django.template.loader import render_to_string

    templates = EmailTemplate.objects.all().order_by('name')
    users_list = User.objects.filter(role='customer').order_by('email')[:100]
    staff_list = User.objects.filter(is_staff=True).order_by('email')[:100]

    if request.method == 'POST':
        action = request.POST.get('action', 'send')

        if action == 'send':
            recipients_raw = request.POST.get('recipients', '')
            recipient_type = request.POST.get('recipient_type', 'individual')
            subject = request.POST.get('subject', '').strip()
            body = request.POST.get('body', '').strip()

            recipients_emails = []
            if recipient_type == 'all_customers':
                recipients_emails = list(User.objects.filter(role='customer').values_list('email', flat=True))
            elif recipient_type == 'all_admins':
                recipients_emails = list(User.objects.filter(is_staff=True).values_list('email', flat=True))
            elif recipient_type == 'all_staff':
                recipients_emails = list(User.objects.filter(role__in=['operator', 'manager', 'admin', 'super_admin']).values_list('email', flat=True))
            elif recipient_type == 'online_customers':
                recipients_emails = list(User.objects.filter(role='customer', is_active=True).values_list('email', flat=True))
            else:
                recipient_ids = [int(uid) for uid in recipients_raw.split(',') if uid.isdigit()]
                recipients_emails = list(User.objects.filter(pk__in=recipient_ids).values_list('email', flat=True))

            if not recipients_emails or not subject:
                messages.error(request, 'Recipients and subject are required.')
                return redirect('admin_mail_compose')

            sent_count = 0
            failed_count = 0
            for email_addr in recipients_emails:
                text_content = strip_tags(body)
                success, result = send_brevo_email(email_addr, subject, body, text_content)
                EmailLog.objects.create(
                    recipient=email_addr,
                    subject=subject,
                    body=body[:500],
                    status='sent' if success else 'failed',
                    error_message='' if success else result,
                )
                if success:
                    sent_count += 1
                    # Create in-app notification
                    user = User.objects.filter(email=email_addr).first()
                    if user:
                        from .notifications import send_notification
                        send_notification(
                            recipient=user,
                            verb='New message',
                            target_type='system',
                            target_id=None,
                            target_url=reverse('user_dashboard'),
                            description=subject,
                        )
                else:
                    failed_count += 1

            messages.success(request, f'Sent to {sent_count} recipient(s). {failed_count} failed.')
            return redirect('admin_mail_dashboard')

        elif action == 'test':
            subject = request.POST.get('subject', '').strip()
            body = request.POST.get('body', '').strip()
            test_email = request.user.email

            if not test_email or not subject:
                messages.error(request, 'Subject is required for test email.')
                return redirect('admin_mail_compose')

            text_content = strip_tags(body)
            success, result = send_brevo_email(test_email, subject, body, text_content)
            EmailLog.objects.create(
                recipient=test_email,
                subject=f'[TEST] {subject}',
                body=body[:500],
                status='sent' if success else 'failed',
                error_message='' if success else result,
            )

            if success:
                messages.success(request, f'Test email sent to {test_email}')
            else:
                messages.error(request, f'Test email failed: {result}')
            return redirect('admin_mail_compose')

    return render(request, 'admin/mail_compose.html', {
        'templates': templates,
        'users_list': users_list,
        'staff_list': staff_list,
    })


@admin_required
def admin_mail_logs(request):
    status_filter = request.GET.get('status', '')
    recipient_filter = request.GET.get('recipient', '').strip()
    subject_filter = request.GET.get('subject', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()

    logs_qs = EmailLog.objects.all().order_by('-created_at')

    if status_filter in ('sent', 'failed'):
        logs_qs = logs_qs.filter(status=status_filter)
    if recipient_filter:
        logs_qs = logs_qs.filter(recipient__icontains=recipient_filter)
    if subject_filter:
        logs_qs = logs_qs.filter(subject__icontains=subject_filter)
    if date_from:
        logs_qs = logs_qs.filter(created_at__date__gte=date_from)
    if date_to:
        logs_qs = logs_qs.filter(created_at__date__lte=date_to)

    if request.method == 'POST':
        action = request.POST.get('action', '')
        if action == 'resend':
            log_id = request.POST.get('log_id')
            email_log = get_object_or_404(EmailLog, pk=log_id)
            text_content = strip_tags(email_log.body)[:2000]
            success, result = send_brevo_email(email_log.recipient, email_log.subject, f'[Resent] {email_log.body[:2000]}', text_content)
            EmailLog.objects.create(
                recipient=email_log.recipient,
                subject=f'[RESEND] {email_log.subject}',
                body=email_log.body,
                status='sent' if success else 'failed',
                error_message='' if success else result,
            )
            messages.success(request, 'Email resent.')
            return redirect('admin_mail_logs')
        elif action == 'bulk_resend':
            log_ids = request.POST.getlist('log_ids')
            for log_id in log_ids:
                email_log = get_object_or_404(EmailLog, pk=log_id)
                text_content = strip_tags(email_log.body)[:2000]
                success, result = send_brevo_email(email_log.recipient, email_log.subject, f'[Resent] {email_log.body[:2000]}', text_content)
                EmailLog.objects.create(
                    recipient=email_log.recipient,
                    subject=f'[RESEND] {email_log.subject}',
                    body=email_log.body,
                    status='sent' if success else 'failed',
                    error_message='' if success else result,
                )
            messages.success(request, f'Resent {len(log_ids)} email(s).')
            return redirect('admin_mail_logs')
        elif action == 'bulk_delete':
            log_ids = request.POST.getlist('log_ids')
            EmailLog.objects.filter(pk__in=log_ids).delete()
            messages.success(request, f'Deleted {len(log_ids)} log(s).')
            return redirect('admin_mail_logs')
        elif action == 'export_csv':
            import csv
            from django.http import HttpResponse
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="email_logs.csv"'
            writer = csv.writer(response)
            writer.writerow(['ID', 'Recipient', 'Subject', 'Status', 'Error Message', 'Created At'])
            for log in logs_qs:
                writer.writerow([log.id, log.recipient, log.subject, log.status, log.error_message, log.created_at])
            return response

    return render(request, 'admin/mail_logs.html', {
        'logs': logs_qs[:100],
        'current_status': status_filter,
        'current_recipient': recipient_filter,
        'current_subject': subject_filter,
        'date_from': date_from,
        'date_to': date_to,
    })


@admin_required
def admin_mail_templates(request):
    templates = EmailTemplate.objects.all().order_by('name')

    if request.method == 'POST' and request.user.is_full_admin:
        action = request.POST.get('action', '')

        if action == 'add':
            name = request.POST.get('name', '').strip()
            subject = request.POST.get('subject', '').strip()
            html_body = request.POST.get('html_body', '').strip()
            if name:
                EmailTemplate.objects.create(name=name, subject=subject, html_body=html_body)
                messages.success(request, f'Template "{name}" created.')

        elif action == 'delete':
            tpl_id = request.POST.get('template_id')
            EmailTemplate.objects.filter(pk=tpl_id).delete()
            messages.success(request, 'Template deleted.')

        elif action == 'edit':
            tpl = get_object_or_404(EmailTemplate, pk=request.POST.get('template_id'))
            tpl.name = request.POST.get('name', tpl.name).strip()
            tpl.subject = request.POST.get('subject', tpl.subject)
            tpl.html_body = request.POST.get('html_body', tpl.html_body)
            tpl.save()
            messages.success(request, f'Template "{tpl.name}" updated.')

        return redirect('admin_mail_templates')

    return render(request, 'admin/mail_templates.html', {
        'templates': templates,
    })


@superadmin_required
def admin_mail_settings(request):
    site = SiteSettings.get()
    if request.method == 'POST':
        site.send_email_on_registration = request.POST.get('send_email_on_registration') == 'on'
        site.send_email_on_order_placed = request.POST.get('send_email_on_order_placed') == 'on'
        site.send_email_on_status_change = request.POST.get('send_email_on_status_change') == 'on'
        site.send_email_on_payment_approved = request.POST.get('send_email_on_payment_approved') == 'on'
        site.send_email_on_payment_rejected = request.POST.get('send_email_on_payment_rejected') == 'on'
        site.send_email_on_admin_approval = request.POST.get('send_email_on_admin_approval') == 'on'
        site.email_from_name = request.POST.get('email_from_name', site.email_from_name).strip() or site.email_from_name
        site.save()
        messages.success(request, 'Mail settings saved.')
        return redirect('admin_mail_settings')

    api_configured = bool(settings.BREVO_API_KEY)
    return render(request, 'admin/mail_settings.html', {
        'site': site,
        'api_configured': api_configured,
    })
