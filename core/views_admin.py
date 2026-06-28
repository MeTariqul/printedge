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
from .order_service import build_order_form_context as _order_form_context
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


def _build_activity_events(limit=5):
    events = []
    recent_orders = Order.objects.select_related('customer', 'walkin_customer').order_by('-created_at')[:20]
    for o in recent_orders:
        customer_label = o.customer_name or (o.walkin_customer.name if o.walkin_customer else '') or 'Guest'
        events.append({
            'link': reverse('admin_order_detail', args=[o.pk]),
            'icon': 'bi bi-cart-plus',
            'text': "New order #{} placed by {}".format(o.order_number, customer_label),
            'timestamp': o.created_at,
            'time': _relative_time(o.created_at),
        })
    recent_status_logs = OrderStatusLog.objects.select_related('order', 'changed_by').order_by('-timestamp')[:20]
    for log in recent_status_logs:
        events.append({
            'link': reverse('admin_order_detail', args=[log.order_id]),
            'icon': 'bi bi-arrow-repeat',
            'text': "Order #{} status changed to {}".format(log.order.order_number, log.new_status.replace('_', ' ').title()),
            'timestamp': log.timestamp,
            'time': _relative_time(log.timestamp),
        })
    recent_audit = AuditLog.objects.select_related('user').order_by('-timestamp')[:20]
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
        events.append({
            'link': link,
            'icon': icon,
            'text': entry.action.replace('_', ' ').title(),
            'timestamp': entry.timestamp,
            'time': _relative_time(entry.timestamp),
        })
    events = [e for e in events if e.get('timestamp')]
    events.sort(key=lambda x: x['timestamp'], reverse=True)
    return events[:limit]


def get_dashboard_context(user, chart_range='7'):
    role = user.role
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)
    two_weeks_ago = today - timedelta(days=14)
    month_start = today.replace(day=1)
    ctx = {'user_role': role}

    if role in ('super_admin', 'admin', 'manager', 'operator', 'viewer', 'finance'):
        common_kpis = {}
        if role != 'finance':
            today_orders = Order.objects.filter(created_at__date=today).select_related('customer', 'walkin_customer')
            yesterday_orders = Order.objects.filter(created_at__date=yesterday)
            today_revenue = today_orders.aggregate(s=Sum('total_amount'))['s'] or 0
            yesterday_revenue = yesterday_orders.aggregate(s=Sum('total_amount'))['s'] or 0
            revenue_change = 0
            if yesterday_revenue > 0:
                revenue_change = round(((today_revenue - yesterday_revenue) / yesterday_revenue) * 100, 1)
            orders_today_count = today_orders.count()
            pending_count = Order.objects.filter(status__in=['pending', 'confirmed']).count()
            active_customers = User.objects.filter(orders__created_at__date=today).distinct().count()
            pages_today = today_orders.aggregate(p=Sum('total_sheets'))['p'] or 0
            orders_completed_today = today_orders.filter(status='delivered').count()
            common_kpis.update({
                'today_orders_count': orders_today_count,
                'yesterday_orders_count': yesterday_orders.count(),
                'today_revenue': today_revenue,
                'yesterday_revenue': yesterday_revenue,
                'revenue_change': revenue_change,
                'pending_count': pending_count,
                'active_customers': active_customers,
                'pages_today': pages_today,
                'avg_order_value': round(today_revenue / orders_today_count, 0) if orders_today_count else 0,
                'orders_completed_today': orders_completed_today,
            })

        if role in ('super_admin', 'admin', 'manager'):
            failed_emails_24h = EmailLog.objects.filter(
                created_at__gte=timezone.now() - timedelta(hours=24),
                status='failed'
            ).count()
            low_stock_count = ServiceVariant.objects.filter(stock__lt=F('low_stock_threshold')).count()
            common_kpis.update({
                'failed_emails_24h': failed_emails_24h,
                'low_stock_count': low_stock_count,
            })

        if role == 'finance':
            today_revenue_paid = Order.objects.filter(created_at__date=today, payment_status='paid').aggregate(s=Sum('total_amount'))['s'] or 0
            month_revenue = Order.objects.filter(created_at__date__gte=month_start, payment_status='paid').aggregate(s=Sum('total_amount'))['s'] or 0
            total_orders = Order.objects.all().count()
            pending_payments = Order.objects.filter(payment_status__in=['unpaid', 'partial', 'pending_review']).count()
            ctx['today_revenue'] = today_revenue_paid
            ctx['month_revenue'] = month_revenue
            ctx['total_orders'] = total_orders
            ctx['pending_payments'] = pending_payments
        else:
            ctx.update(common_kpis)

        if role not in ('finance', 'operator'):
            spark_start = today - timedelta(days=6)
            spark_days = [spark_start + timedelta(days=i) for i in range(7)]
            spark_orders = Order.objects.filter(created_at__date__gte=spark_start).annotate(
                day=TruncDay('created_at')
            ).values('day').annotate(cnt=Count('id'), rev=Sum('total_amount'), sh=Sum('total_sheets'))
            spark_map = {r['day']: r for r in spark_orders}
            ctx['spark_orders_json'] = json.dumps([spark_map.get(d, {}).get('cnt', 0) for d in spark_days])
            ctx['spark_revenue_json'] = json.dumps([float(spark_map.get(d, {}).get('rev', 0) or 0) for d in spark_days])
            ctx['spark_pages_json'] = json.dumps([spark_map.get(d, {}).get('sh', 0) or 0 for d in spark_days])
            if role in ('super_admin', 'admin', 'manager'):
                heatmap_data = Order.objects.filter(
                    created_at__date__gte=today - timedelta(days=28)
                ).values_list('created_at', flat=True)
                heat_grid = [[0]*24 for _ in range(7)]
                for dt in heatmap_data:
                    heat_grid[dt.weekday()][dt.hour] += 1
                ctx['heatmap_json'] = json.dumps(heat_grid)

        if role in ('super_admin', 'admin', 'manager'):
            days_back = int(chart_range) - 1
            start_date = today - timedelta(days=days_back)
            revenue_by_day = Order.objects.filter(created_at__date__gte=start_date).annotate(
                day=TruncDay('created_at')
            ).values('day').annotate(revenue=Sum('total_amount')).order_by('day')
            revenue_trend = [float(row['revenue'] or 0) for row in revenue_by_day]
            labels = [row['day'].strftime('%b %d') for row in revenue_by_day]
            status_counts = {s[0]: Order.objects.filter(status=s[0]).count() for s in Order.STATUS_CHOICES}
            chart_status = {
                'Pending': status_counts.get('pending', 0) + status_counts.get('confirmed', 0),
                'Processing': status_counts.get('printing', 0) + status_counts.get('quality_check', 0),
                'Ready': status_counts.get('ready', 0),
                'Delivered': status_counts.get('delivered', 0),
                'Other': status_counts.get('cancelled', 0) + status_counts.get('on_hold', 0),
            }
            volume_by_day = Order.objects.filter(created_at__date__gte=two_weeks_ago).annotate(
                day=TruncDay('created_at')
            ).values('day', 'source').annotate(cnt=Count('id')).order_by('day', 'source')
            volume_map = {}
            for row in volume_by_day:
                day_str = row['day'].strftime('%b %d')
                volume_map.setdefault(day_str, {'online': 0, 'offline': 0})
                volume_map[day_str][row['source']] = row['cnt']
            volume_labels = sorted(volume_map.keys())
            online_data = [volume_map[d]['online'] for d in volume_labels]
            walkin_data = [volume_map[d]['offline'] for d in volume_labels]
            ctx.update({
                'revenue_trend_json': json.dumps(revenue_trend),
                'revenue_labels_json': json.dumps(labels),
                'chart_range': chart_range,
                'chart_status_json': json.dumps(list(chart_status.values())),
                'chart_status_labels_json': json.dumps(list(chart_status.keys())),
                'daily_volume_labels_json': json.dumps(volume_labels),
                'daily_volume_online_json': json.dumps(online_data),
                'daily_volume_walkin_json': json.dumps(walkin_data),
            })
            ctx['chart_backtests'] = [
                {'label': '7d', 'value': '7'},
                {'label': '30d', 'value': '30'},
                {'label': '90d', 'value': '90'},
            ]
            if role in ('super_admin', 'admin', 'manager'):
                top_customers = User.objects.annotate(
                    order_count=Count('orders', filter=Q(orders__created_at__date__gte=month_start)),
                    revenue_sum=Sum('orders__total_amount', filter=Q(orders__created_at__date__gte=month_start)),
                ).filter(order_count__gt=0).order_by('-revenue_sum')[:5]
                ctx.update({
                    'top_customer_names_json': json.dumps([c.get_full_name() or c.email for c in top_customers]),
                    'top_customer_counts_json': json.dumps([float(c.revenue_sum or 0) for c in top_customers]),
                })
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
                ctx['print_type_labels_json'] = json.dumps(print_type_labels)
                ctx['print_type_values_json'] = json.dumps(print_type_values)
            if role == 'finance':
                payment_methods = Order.objects.exclude(payment_method__isnull=True).exclude(payment_method='').values('payment_method').annotate(c=Count('id')).order_by('-c')[:10]
                ctx['payment_method_labels_json'] = json.dumps([p['payment_method'] for p in payment_methods])
                ctx['payment_method_values_json'] = json.dumps([p['c'] for p in payment_methods])
                revenue_by_month = Order.objects.filter(created_at__date__gte=month_start, payment_status='paid').annotate(
                    day=TruncDay('created_at')
                ).values('day').annotate(revenue=Sum('total_amount')).order_by('day')
                ctx['revenue_trend_json'] = json.dumps([float(row['revenue'] or 0) for row in revenue_by_month])
                ctx['revenue_labels_json'] = json.dumps([row['day'].strftime('%b %d') for row in revenue_by_month])
                ctx['chart_range'] = 'month'

        recent_activity = _build_activity_events(limit=5)
        if role == 'finance':
            recent_activity = [e for e in recent_activity if 'payment' in e['text'].lower()][:5]
        ctx['recent_activity'] = recent_activity

        if role in ('super_admin', 'admin', 'manager'):
            ready_not_picked = Order.objects.filter(
                status='ready', updated_at__lt=timezone.now() - timedelta(hours=24)
            ).count()
            pending_payment_reviews = Order.objects.filter(payment_status='pending_review').count()
            low_stock_count = ServiceVariant.objects.filter(stock__lt=F('low_stock_threshold')).count()
            files_cleanup_48h = Order.objects.filter(
                file__isnull=False, file_deleted_at__isnull=True,
                updated_at__lt=timezone.now() - timedelta(hours=48),
            ).count()
            ctx.update({
                'ready_not_picked': ready_not_picked,
                'pending_payment_reviews': pending_payment_reviews,
                'files_cleanup_48h': files_cleanup_48h,
            })
            ctx['reminders'] = [
                {'label': 'Ready for Pickup', 'sub': f'{ready_not_picked} orders waiting >24h', 'count': ready_not_picked,
                 'href': reverse('admin_orders') + '?status=ready', 'badge_class': 'bg-amber-500/15 text-amber-400 border border-amber-500/25', 'icon': 'bi bi-bag-check'},
                {'label': 'Pending Payment Review', 'sub': f'{pending_payment_reviews} awaiting approval', 'count': pending_payment_reviews,
                 'href': reverse('admin_orders') + '?payment=pending_review', 'badge_class': 'bg-brand-500/15 text-cyan-400 border border-cyan-500/25', 'icon': 'bi bi-wallet2'},
                {'label': 'Low Stock', 'sub': f'{low_stock_count} items below threshold', 'count': low_stock_count,
                 'href': reverse('admin_inventory'), 'badge_class': 'bg-red-500/15 text-red-400 border border-red-500/25', 'icon': 'bi bi-box-seam'},
                {'label': 'File Cleanup Soon', 'sub': f'{files_cleanup_48h} files eligible in 48h', 'count': files_cleanup_48h,
                 'href': reverse('admin_system_status'), 'badge_class': 'bg-slate-500/15 text-slate-300 border border-slate-500/25', 'icon': 'bi bi-trash'},
            ]

        if role in ('super_admin', 'admin', 'manager', 'viewer'):
            db_status = get_database_status()
            db_healthy = db_status.get('default', {}).get('connected', False)
            db_latency = db_status.get('default', {}).get('latency_ms')
            storage_healthy = supabase_storage_enabled()
            email_healthy = EmailLog.objects.filter(status='failed', created_at__gte=timezone.now() - timedelta(hours=24)).count() == 0
            cache_healthy = bool(cache)
            supabase_auth_healthy = bool(supabase_project_url())
            health_items = [
                {'label': 'Database', 'sub': f'{"Connected" if db_healthy else "Offline"}' + (f' · {db_latency}ms' if db_latency else ''), 'dot_class': 'bg-emerald-400' if db_healthy else 'bg-red-400'},
                {'label': 'Storage', 'sub': 'Supabase S3', 'dot_class': 'bg-emerald-400' if storage_healthy else 'bg-red-400'},
                {'label': 'Email', 'sub': 'Brevo API', 'dot_class': 'bg-emerald-400' if email_healthy else 'bg-red-400'},
                {'label': 'Cache', 'sub': cache.__class__.__name__, 'dot_class': 'bg-emerald-400' if cache_healthy else 'bg-red-400'},
            ]
            if role in ('super_admin', 'admin'):
                health_items.append({'label': 'Supabase Auth', 'sub': 'Configured' if supabase_auth_healthy else 'Not configured', 'dot_class': 'bg-emerald-400' if supabase_auth_healthy else 'bg-amber-400'})
            ctx['health_items'] = health_items

        if role == 'operator':
            qs = Order.objects.exclude(status__in=['cancelled']).select_related('customer', 'walkin_customer', 'assigned_to').prefetch_related('order_files')
            ctx['operator_queue'] = {
                'pending': qs.filter(status__in=['pending', 'confirmed']),
                'printing': qs.filter(status__in=['printing', 'quality_check']),
                'ready': qs.filter(status='ready'),
            }
            today_qs = qs.filter(created_at__date=today)
            ctx['orders_today_count'] = today_qs.count()
            ctx['orders_completed_today_count'] = today_qs.filter(status='delivered').count()
            ctx['pending_orders_count'] = qs.filter(status__in=['pending', 'confirmed']).count()
            ctx['chart_backtests'] = []

    return ctx





@admin_required
def admin_dashboard(request):
    chart_range = request.GET.get('range', '7')
    if chart_range not in ('7', '30', '90'):
        chart_range = '7'
    return render(request, 'admin/dashboard.html', get_dashboard_context(request.user, chart_range))


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




# --- STAFF MANAGEMENT ---


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




# --- REPORTS EXPORT ---


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
