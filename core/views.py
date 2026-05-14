from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Sum, Count, Q
from django.db.models.functions import TruncDate
import json
from datetime import timedelta
from decimal import Decimal

from .models import (
    User, WalkInCustomer, Order, InventoryItem,
    PricingRule, AddonService, Expense, AuditLog,
    Notification, OrderStatusLog, SiteSettings, PromoCode
)
from .decorators import login_required_custom, admin_required
from .pricing import calculate_order_price

# ─── AUTH VIEWS ────────────────────────────────────────────────────────────────

import re
from django.core.cache import cache
from django.core.exceptions import ValidationError
import os

def auth_login(request):
    if request.user.is_authenticated:
        return redirect('admin_dashboard' if request.user.is_admin_user else 'user_dashboard')
    if request.method == 'POST':
        ip = request.META.get('REMOTE_ADDR')
        cache_key = f'login_attempts_{ip}'
        attempts = cache.get(cache_key, 0)
        
        if attempts >= 5:
            messages.error(request, 'Too many failed login attempts. Please try again in 15 minutes.')
            return render(request, 'auth/login.html')

        email = request.POST.get('email', '').strip().lower()[:150]
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
            login(request, user)
            cache.delete(cache_key)
            AuditLog.objects.create(
                user=user, action='LOGIN', resource_type='Auth',
                ip_address=ip
            )
            return redirect('admin_dashboard' if user.is_admin_user else 'user_dashboard')
        
        cache.set(cache_key, attempts + 1, 900)
        messages.error(request, 'Invalid email or password.')
    return render(request, 'auth/login.html')


def auth_register(request):
    if request.user.is_authenticated:
        return redirect('user_dashboard')
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()[:100]
        email = request.POST.get('email', '').strip().lower()[:150]
        phone = request.POST.get('phone', '').strip()[:20]
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')
        
        if not re.match(r'^(\+88)?01[3-9]\d{8}$', phone):
            messages.error(request, 'Invalid Bangladeshi phone number format.')
            return render(request, 'auth/register.html')
            
        blocked_domains = ['yopmail.com', 'mailinator.com', 'tempmail.com']
        domain = email.split('@')[-1] if '@' in email else ''
        if domain in blocked_domains:
            messages.error(request, 'Disposable email addresses are not allowed.')
            return render(request, 'auth/register.html')

        if password != password2:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'auth/register.html')
        if len(password) < 8:
            messages.error(request, 'Password must be at least 8 characters.')
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
        parts = name.split(' ', 1)
        user = User.objects.create_user(
            username=username, email=email, password=password,
            first_name=parts[0], last_name=parts[1] if len(parts) > 1 else '',
            phone=phone, role='customer'
        )
        login(request, user)
        messages.success(request, f'Welcome to Print-Edge, {user.first_name}!')
        return redirect('user_dashboard')
    return render(request, 'auth/register.html')


def auth_logout(request):
    logout(request)
    return redirect('public_index')


# ─── PUBLIC VIEWS ───────────────────────────────────────────────────────────────

def public_index(request):
    return render(request, 'index.html')


def public_pricing(request):
    addons = AddonService.objects.filter(is_active=True)
    return render(request, 'pricing.html', {'addons': addons})


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
    return render(request, 'user/dashboard.html', {
        'orders': orders[:10],
        'active_order': active.first(),
        'stats': stats,
    })


@login_required_custom
def user_new_order(request):
    addons = AddonService.objects.filter(is_active=True)
    if request.method == 'POST':
        print_type = request.POST.get('print_type', 'bw')
        sides = request.POST.get('sides', 'single')
        paper_size = request.POST.get('paper_size', 'A4')
        try:
            pages = max(1, int(request.POST.get('pages', 1)))
            copies = max(1, int(request.POST.get('copies', 1)))
        except ValueError:
            pages = 1
            copies = 1
            
        is_urgent = request.POST.get('is_urgent') == 'on'
        addon_ids = request.POST.getlist('addons')
        instructions = request.POST.get('special_instructions', '')[:500]
        file = request.FILES.get('file')
        
        if file:
            if file.size > 50 * 1024 * 1024:
                messages.error(request, 'File size exceeds 50MB limit.')
                return render(request, 'user/new_order.html', {'addons': addons})
            
            ext = os.path.splitext(file.name)[1].lower()
            allowed = ['.pdf', '.doc', '.docx', '.ppt', '.pptx', '.jpg', '.jpeg', '.png']
            if ext not in allowed:
                messages.error(request, 'Invalid file type.')
                return render(request, 'user/new_order.html', {'addons': addons})
                
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
        breakdown = calculate_order_price(
            print_type, sides, paper_size, pages, copies,
            addon_ids=addon_ids, is_urgent=is_urgent,
            promo_code_obj=promo_obj, tier_discount_pct=tier_pct
        )
        order = Order.objects.create(
            source='online', customer=request.user,
            print_type=print_type, sides=sides, paper_size=paper_size,
            pages=pages, copies=copies, is_urgent=is_urgent,
            special_instructions=instructions,
            base_price=breakdown['base_price'],
            addons_price=breakdown['addons_price'],
            urgent_surcharge=breakdown['urgent_surcharge'],
            discount_amount=breakdown['total_discount'],
            total_amount=breakdown['total'],
            promo_code=promo_obj, created_by=request.user,
            file=file, file_name=file.name if file else None,
        )
        if addon_ids:
            order.addons.set(addon_ids)
        if promo_obj:
            promo_obj.used_count += 1
            promo_obj.save(update_fields=['used_count'])
        OrderStatusLog.objects.create(
            order=order, new_status='pending', changed_by=request.user, note='Order placed by customer.'
        )
        request.user.total_orders += 1
        request.user.save(update_fields=['total_orders'])
        messages.success(request, f'Order {order.order_number} placed successfully!')
        return redirect('user_order_detail', pk=order.pk)
    return render(request, 'user/new_order.html', {'addons': addons})


@login_required_custom
def user_order_detail(request, pk):
    order = get_object_or_404(Order, pk=pk, customer=request.user)
    return render(request, 'user/order_detail.html', {'order': order})


@login_required_custom
def user_orders(request):
    orders = Order.objects.filter(customer=request.user).order_by('-created_at')
    return render(request, 'user/orders.html', {'orders': orders})


@login_required_custom
def user_profile(request):
    if request.method == 'POST':
        request.user.first_name = request.POST.get('first_name', request.user.first_name)
        request.user.last_name = request.POST.get('last_name', request.user.last_name)
        request.user.phone = request.POST.get('phone', request.user.phone)
        request.user.department = request.POST.get('department', request.user.department)
        request.user.save()
        messages.success(request, 'Profile updated successfully.')
    return render(request, 'user/profile.html')


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

    # Revenue trend last 7 days
    revenue_trend = []
    labels = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        rev = Order.objects.filter(created_at__date=d).aggregate(s=Sum('total_amount'))['s'] or 0
        revenue_trend.append(float(rev))
        labels.append(d.strftime('%a'))

    # Order distribution by status
    status_counts = {
        s[0]: Order.objects.filter(status=s[0]).count()
        for s in Order.STATUS_CHOICES
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
        'status_counts': status_counts,
        'status_counts_json': json.dumps(list(status_counts.values())),
        'low_stock_count': low_stock_count,
        'recent_orders': recent_orders,
        'unread_count': Notification.objects.filter(
            recipient=request.user, is_read=False
        ).count() if hasattr(request.user, 'notifications') else 0,
    }
    return render(request, 'admin/dashboard.html', ctx)


@admin_required
def admin_orders(request):
    qs = Order.objects.select_related('customer', 'walkin_customer', 'assigned_to').order_by('-created_at')
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
            Q(customer__email__icontains=search) |
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
        action = request.POST.get('action')
        if action == 'status':
            new_status = request.POST.get('status')
            old_status = order.status
            note = request.POST.get('note', '')
            order.status = new_status
            if new_status == 'delivered':
                order.completed_at = timezone.now()
                if order.customer:
                    order.customer.total_spent += order.total_amount
                    order.customer.update_tier()
                elif order.walkin_customer:
                    order.walkin_customer.total_spent += order.total_amount
                    order.walkin_customer.save()
            order.save()
            OrderStatusLog.objects.create(
                order=order, old_status=old_status,
                new_status=new_status, changed_by=request.user, note=note
            )
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
        messages.success(request, 'Order updated.')
        return redirect('admin_order_detail', pk=pk)
    return render(request, 'admin/order_detail.html', {
        'order': order, 'staff_list': staff_list
    })


@admin_required
def admin_walkin_order(request):
    addons = AddonService.objects.filter(is_active=True)
    if request.method == 'POST':
        # Customer
        walkin_id = request.POST.get('walkin_customer_id')
        if walkin_id:
            walkin = get_object_or_404(WalkInCustomer, pk=walkin_id)
        else:
            name = request.POST.get('customer_name', '').strip()
            phone = request.POST.get('customer_phone', '').strip()
            walkin, _ = WalkInCustomer.objects.get_or_create(phone=phone, defaults={'name': name})
        print_type = request.POST.get('print_type', 'bw')
        sides = request.POST.get('sides', 'single')
        paper_size = request.POST.get('paper_size', 'A4')
        pages = int(request.POST.get('pages', 1))
        copies = int(request.POST.get('copies', 1))
        is_urgent = request.POST.get('is_urgent') == 'on'
        is_physical = request.POST.get('is_physical_document') == 'on'
        addon_ids = request.POST.getlist('addons')
        manual_discount = Decimal(request.POST.get('manual_discount', '0') or '0')
        payment_method = request.POST.get('payment_method', 'Cash')
        amount_paid = Decimal(request.POST.get('amount_paid', '0') or '0')
        breakdown = calculate_order_price(
            print_type, sides, paper_size, pages, copies,
            addon_ids=addon_ids, is_urgent=is_urgent,
            manual_discount=manual_discount,
            tier_discount_pct=Decimal('0')
        )
        payment_status = 'paid' if amount_paid >= breakdown['total'] else ('partial' if amount_paid > 0 else 'unpaid')
        order = Order.objects.create(
            source='offline', walkin_customer=walkin,
            print_type=print_type, sides=sides, paper_size=paper_size,
            pages=pages, copies=copies, is_urgent=is_urgent,
            is_physical_document=is_physical,
            base_price=breakdown['base_price'],
            addons_price=breakdown['addons_price'],
            urgent_surcharge=breakdown['urgent_surcharge'],
            discount_amount=breakdown['total_discount'],
            discount_reason=request.POST.get('discount_reason', ''),
            total_amount=breakdown['total'],
            payment_method=payment_method,
            amount_paid=amount_paid,
            payment_status=payment_status,
            created_by=request.user,
            file=request.FILES.get('file'),
        )
        if addon_ids:
            order.addons.set(addon_ids)
        OrderStatusLog.objects.create(
            order=order, new_status='pending',
            changed_by=request.user, note=f'Walk-in order created by {request.user.display_name}.'
        )
        walkin.total_orders += 1
        walkin.last_visit = timezone.now()
        walkin.save(update_fields=['total_orders', 'last_visit'])
        messages.success(request, f'Walk-in order {order.order_number} created!')
        return redirect('admin_order_detail', pk=order.pk)
    walkin_customers = WalkInCustomer.objects.order_by('-last_visit')[:50]
    return render(request, 'admin/walkin_order.html', {
        'addons': addons, 'walkin_customers': walkin_customers
    })


@admin_required
def admin_users(request):
    users = User.objects.filter(role='customer').order_by('-date_joined')
    search = request.GET.get('q', '')
    if search:
        users = users.filter(Q(email__icontains=search) | Q(first_name__icontains=search) | Q(phone__icontains=search))
    return render(request, 'admin/users.html', {'users': users, 'search': search})


@admin_required
def admin_offline_customers(request):
    customers = WalkInCustomer.objects.order_by('-last_visit')
    search = request.GET.get('q', '')
    if search:
        customers = customers.filter(Q(name__icontains=search) | Q(phone__icontains=search))
    return render(request, 'admin/offline_customers.html', {'customers': customers, 'search': search})


@admin_required
def admin_inventory(request):
    items = InventoryItem.objects.all().order_by('category', 'name')
    if request.method == 'POST':
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
        return redirect('admin_inventory')
    return render(request, 'admin/inventory.html', {'items': items})


@admin_required
def admin_services(request):
    pricing = PricingRule.objects.all()
    addons = AddonService.objects.all()
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'update_price':
            rule = get_object_or_404(PricingRule, pk=request.POST['rule_id'])
            rule.price_per_page = Decimal(request.POST['price'])
            rule.save()
            messages.success(request, 'Price updated.')
        elif action == 'toggle_addon':
            addon = get_object_or_404(AddonService, pk=request.POST['addon_id'])
            addon.is_active = not addon.is_active
            addon.save()
        elif action == 'add_addon':
            AddonService.objects.create(
                name=request.POST['name'], price=request.POST['price'],
                description=request.POST.get('description', '')
            )
            messages.success(request, 'Add-on created.')
        return redirect('admin_services')
    return render(request, 'admin/services.html', {'pricing': pricing, 'addons': addons})


@admin_required
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


@admin_required
def admin_audit_log(request):
    logs = AuditLog.objects.select_related('user').order_by('-timestamp')[:200]
    return render(request, 'admin/audit_log.html', {'logs': logs})


@admin_required
def admin_settings(request):
    site = SiteSettings.get()
    if request.method == 'POST':
        site.business_name = request.POST.get('business_name', site.business_name)
        site.business_phone = request.POST.get('business_phone', site.business_phone)
        site.business_email = request.POST.get('business_email', site.business_email)
        site.business_address = request.POST.get('business_address', site.business_address)
        site.business_hours = request.POST.get('business_hours', site.business_hours)
        site.urgent_surcharge_percent = int(request.POST.get('urgent_surcharge_percent', 50))
        site.auto_delete_files_days = int(request.POST.get('auto_delete_files_days', 7))
        site.save()
        messages.success(request, 'Settings saved.')
        return redirect('admin_settings')
    return render(request, 'admin/settings.html', {'site': site})


@admin_required
def admin_display_mode(request):
    ready_orders = Order.objects.filter(status='ready').select_related('customer', 'walkin_customer')
    printing_orders = Order.objects.filter(status='printing').select_related('customer', 'walkin_customer')
    return render(request, 'admin/display.html', {
        'ready_orders': ready_orders, 'printing_orders': printing_orders
    })


# ─── API VIEWS ─────────────────────────────────────────────────────────────────

def api_price_calculate(request):
    """Live price calculator — called via AJAX."""
    print_type = request.GET.get('print_type', 'bw')
    sides = request.GET.get('sides', 'single')
    paper_size = request.GET.get('paper_size', 'A4')
    pages = int(request.GET.get('pages', 1) or 1)
    copies = int(request.GET.get('copies', 1) or 1)
    is_urgent = request.GET.get('is_urgent') == '1'
    addon_ids = request.GET.getlist('addons')
    breakdown = calculate_order_price(print_type, sides, paper_size, pages, copies, addon_ids=addon_ids, is_urgent=is_urgent)
    return JsonResponse({k: float(v) if hasattr(v, 'quantize') else v for k, v in breakdown.items()})


def api_walkin_search(request):
    q = request.GET.get('q', '').strip()
    results = []
    if len(q) >= 2:
        customers = WalkInCustomer.objects.filter(
            Q(name__icontains=q) | Q(phone__icontains=q)
        )[:10]
        results = [{'id': c.pk, 'name': c.name, 'phone': c.phone, 'tier': c.tier} for c in customers]
    return JsonResponse({'results': results})


def api_order_status_update(request, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    if not request.user.is_authenticated or not request.user.is_admin_user:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    order = get_object_or_404(Order, pk=pk)
    try:
        data = json.loads(request.body)
        new_status = data.get('status')
        valid = [s[0] for s in Order.STATUS_CHOICES]
        if new_status not in valid:
            return JsonResponse({'error': 'Invalid status'}, status=400)
        old_status = order.status
        order.status = new_status
        order.save(update_fields=['status'])
        OrderStatusLog.objects.create(
            order=order, old_status=old_status,
            new_status=new_status, changed_by=request.user
        )
        return JsonResponse({'success': True, 'status': new_status})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


def api_global_search(request):
    q = request.GET.get('q', '').strip()
    results = []
    if len(q) >= 2 and request.user.is_authenticated and request.user.is_admin_user:
        orders = Order.objects.filter(
            Q(order_number__icontains=q) |
            Q(customer__first_name__icontains=q) |
            Q(walkin_customer__name__icontains=q)
        )[:5]
        for o in orders:
            results.append({'type': 'order', 'title': o.order_number,
                            'subtitle': f'{o.customer_name} · ৳{o.total_amount}',
                            'url': f'/admin/orders/{o.pk}/', 'icon': 'bi-cart'})
        users = User.objects.filter(
            Q(email__icontains=q) | Q(first_name__icontains=q)
        )[:5]
        for u in users:
            results.append({'type': 'user', 'title': u.display_name,
                            'subtitle': u.email, 'url': '/admin/customers/online/', 'icon': 'bi-person'})
    return JsonResponse({'results': results})


def api_notifications(request):
    if not request.user.is_authenticated:
        return JsonResponse({'notifications': []})
    notifs = request.user.notifications.filter(is_read=False).order_by('-created_at')[:10]
    return JsonResponse({'notifications': [
        {'id': n.pk, 'title': n.title, 'body': n.body, 'type': n.type, 'link': n.link or '#'}
        for n in notifs
    ]})
