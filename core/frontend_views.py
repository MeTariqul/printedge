"""Views added for frontend overhaul (profiles, operator, exports)."""
import csv
import json
import os
import zipfile
import io
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Sum, Q, Count
from django.core.exceptions import ImproperlyConfigured

from .models import (
    User, WalkInCustomer, Order, OrderFile, UserAddress,
    OrderStatusLog, AuditLog, Notification, SiteSettings, AddonService, Coupon,
)
from .decorators import login_required_custom, admin_required, permission_required, write_staff_required
from .permissions import user_has_permission
from .pricing import calculate_order_price
from .utils import safe_int, validate_upload_file
from .order_files import save_order_file_metadata
from .page_detection import detect_pages
from .pricing_options import get_active_pricing_options
from .notifications import (
    notify_staff_of_new_user, notify_new_online_order, notify_new_walkin_order,
    notify_order_status_change,
)
from .user_helpers import set_user_password, validate_password_strength


def _staff_login_redirect(user):
    if user.role == 'operator':
        return redirect('admin_operator_dashboard')
    if user.role == 'viewer':
        return redirect('admin_orders')
    return redirect('admin_dashboard')


def server_error(request):
    return render(request, '500.html', status=500)


ALLOWED_ZIP_EXTENSIONS = {'.pdf', '.doc', '.docx', '.ppt', '.pptx', '.jpg', '.jpeg', '.png'}


def extract_zip_files(uploaded_zip, max_files=20):
    """Extract valid document files from a ZIP archive."""
    files = []
    try:
        with zipfile.ZipFile(uploaded_zip) as zf:
            for info in zf.infolist():
                if info.is_dir() or info.file_size > 50 * 1024 * 1024:
                    continue
                name = info.filename.split('/')[-1]
                if not name or name.startswith('.'):
                    continue
                ext = ('.' + name.rsplit('.', 1)[-1].lower()) if '.' in name else ''
                if ext not in ALLOWED_ZIP_EXTENSIONS:
                    continue
                data = zf.read(info)
                if len(files) >= max_files:
                    break
                files.append((name, io.BytesIO(data), len(data)))
    except zipfile.BadZipFile:
        return None, 'Invalid ZIP file.'
    if not files:
        return None, 'No supported documents found in ZIP.'
    return files, None


@login_required_custom
def user_profile(request):
    addresses = UserAddress.objects.filter(user=request.user)
    if request.method == 'POST':
        action = request.POST.get('action', 'profile')
        if action == 'password':
            form = PasswordChangeForm(request.user, request.POST)
            if form.is_valid():
                user = form.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Password changed successfully.')
            else:
                messages.error(request, ' '.join(form.errors.get('__all__', form.errors.values())))
            return redirect('user_profile')
        if action == 'address_add':
            UserAddress.objects.create(
                user=request.user,
                label=request.POST.get('label', 'Home')[:50],
                address=request.POST.get('address', '').strip()[:500],
                phone=request.POST.get('phone', '')[:20],
                is_default=request.POST.get('is_default') == 'on',
            )
            messages.success(request, 'Address saved.')
            return redirect('user_profile')
        if action == 'address_delete':
            UserAddress.objects.filter(user=request.user, pk=request.POST.get('address_id')).delete()
            messages.success(request, 'Address removed.')
            return redirect('user_profile')
        request.user.first_name = request.POST.get('first_name', request.user.first_name)[:50]
        request.user.last_name = request.POST.get('last_name', request.user.last_name)[:50]
        request.user.phone = request.POST.get('phone', request.user.phone)[:20]
        request.user.university = request.POST.get('university', '')[:150]
        request.user.department = request.POST.get('department', '')[:100]
        request.user.student_id = request.POST.get('student_id', '')[:50]
        request.user.notification_email = request.POST.get('notification_email') == 'on'
        avatar_url = request.POST.get('avatar_url', '').strip()
        if avatar_url:
            request.user.avatar_url = avatar_url
        request.user.save()
        messages.success(request, 'Profile updated successfully.')
        return redirect('user_profile')
    return render(request, 'user/profile.html', {
        'addresses': addresses,
        'password_form': PasswordChangeForm(request.user),
    })


@admin_required
def admin_profile(request):
    logs = AuditLog.objects.filter(user=request.user).order_by('-timestamp')[:20]
    if request.method == 'POST':
        action = request.POST.get('action', 'profile')
        if action == 'password':
            form = PasswordChangeForm(request.user, request.POST)
            if form.is_valid():
                user = form.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Password changed.')
            else:
                messages.error(request, 'Could not change password.')
            return redirect('admin_profile')
        request.user.first_name = request.POST.get('first_name', request.user.first_name)[:50]
        request.user.last_name = request.POST.get('last_name', request.user.last_name)[:50]
        request.user.phone = request.POST.get('phone', '')[:20]
        avatar_url = request.POST.get('avatar_url', '').strip()
        if avatar_url:
            request.user.avatar_url = avatar_url
        request.user.save()
        messages.success(request, 'Profile updated.')
        return redirect('admin_profile')
    return render(request, 'admin/profile.html', {
        'activity_logs': logs,
        'password_form': PasswordChangeForm(request.user),
    })


@permission_required('operator_dashboard')
def admin_operator_dashboard(request):
    today = timezone.now().date()
    qs = Order.objects.exclude(status__in=['cancelled']).select_related(
        'customer', 'walkin_customer', 'assigned_to',
    ).prefetch_related('order_files')
    mine = request.GET.get('mine') == '1'
    print_type = request.GET.get('print_type', '')
    fulfillment = request.GET.get('fulfillment', '')
    if mine:
        qs = qs.filter(assigned_to=request.user)
    if print_type:
        qs = qs.filter(print_type=print_type)
    if fulfillment:
        qs = qs.filter(fulfillment_type=fulfillment)

    today_qs = qs.filter(created_at__date=today)
    columns = {
        'pending': qs.filter(status__in=['pending', 'confirmed']),
        'printing': qs.filter(status__in=['printing', 'quality_check']),
        'ready': qs.filter(status='ready'),
    }
    return render(request, 'admin/operator_dashboard.html', {
        'columns': columns,
        'today_count': today_qs.count(),
        'mine': mine,
        'print_type': print_type,
        'fulfillment': fulfillment,
    })


@permission_required('operator_dashboard')
def api_operator_optimize_queue(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    qs = Order.objects.filter(
        status__in=['pending', 'confirmed', 'printing', 'quality_check']
    ).order_by('paper_size', 'print_type', 'sides', 'created_at')
    order_ids = list(qs.values_list('pk', flat=True))
    return JsonResponse({
        'order_ids': order_ids,
        'message': f'Optimized {len(order_ids)} orders by paper and print settings.',
    })


@admin_required
def api_system_status(request):
    from django.db import connection
    import django
    from .storage import supabase_project_url
    return JsonResponse({
        'database': connection.vendor,
        'django_version': django.get_version(),
        'debug': settings.DEBUG,
        'time': timezone.now().isoformat(),
        'supabase_url': supabase_project_url(),
    })


@permission_required('export_reports')
def admin_orders_export(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = (
        f'attachment; filename="orders_{timezone.now().strftime("%Y%m%d")}.csv"'
    )
    writer = csv.writer(response)
    writer.writerow([
        'Order #', 'Source', 'Customer', 'Phone', 'Print Type', 'Pages', 'Copies',
        'Total', 'Status', 'Created',
    ])
    qs = Order.objects.select_related('customer', 'walkin_customer').order_by('-created_at')
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
            Q(walkin_customer__name__icontains=search)
        )
    for o in qs[:2000]:
        writer.writerow([
            o.order_number, o.source, o.customer_name, o.customer_phone,
            o.get_print_type_display(), o.pages, o.copies,
            float(o.total_amount), o.get_status_display(),
            o.created_at.strftime('%Y-%m-%d %H:%M'),
        ])
    return response


@permission_required('manage_customers')
def admin_walkin_merge(request, pk):
    walkin = get_object_or_404(WalkInCustomer, pk=pk)
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        user = get_object_or_404(User, pk=user_id, role='customer')
        walkin.online_account = user
        walkin.save(update_fields=['online_account'])
        Order.objects.filter(walkin_customer=walkin).update(customer=user, walkin_customer=None)
        messages.success(request, f'Merged walk-in {walkin.name} with {user.email}.')
        return redirect('admin_offline_customers')
    online_users = User.objects.filter(role='customer').order_by('email')[:100]
    orders = Order.objects.filter(walkin_customer=walkin).order_by('-created_at')[:20]
    return render(request, 'admin/walkin_detail.html', {
        'walkin': walkin,
        'orders': orders,
        'online_users': online_users,
    })
