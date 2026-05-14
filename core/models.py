from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
import uuid


def order_number_default():
    return ''


class User(AbstractUser):
    """Extended user model for online customers and staff."""
    ROLE_CHOICES = [
        ('customer', 'Customer'),
        ('operator', 'Operator'),
        ('manager', 'Manager'),
        ('admin', 'Admin'),
        ('super_admin', 'Super Admin'),
    ]
    TIER_CHOICES = [
        ('bronze', 'Bronze'),
        ('silver', 'Silver'),
        ('gold', 'Gold'),
        ('platinum', 'Platinum'),
    ]

    phone = models.CharField(max_length=20, blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='customer')
    tier = models.CharField(max_length=20, choices=TIER_CHOICES, default='bronze')
    department = models.CharField(max_length=100, blank=True, null=True)
    student_id = models.CharField(max_length=50, blank=True, null=True)
    avatar_url = models.URLField(blank=True, null=True)
    total_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_orders = models.IntegerField(default=0)
    is_banned = models.BooleanField(default=False)
    ban_reason = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)  # admin internal notes
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def display_name(self):
        return self.get_full_name() or self.username or self.email

    @property
    def is_admin_user(self):
        return self.role in ('admin', 'super_admin', 'manager')

    def update_tier(self):
        """Auto-calculate tier based on total_spent."""
        if self.total_spent >= 5000:
            self.tier = 'platinum'
        elif self.total_spent >= 2000:
            self.tier = 'gold'
        elif self.total_spent >= 500:
            self.tier = 'silver'
        else:
            self.tier = 'bronze'
        self.save(update_fields=['tier'])

    def tier_discount(self):
        discounts = {'bronze': 0, 'silver': 3, 'gold': 5, 'platinum': 8}
        return discounts.get(self.tier, 0)


class WalkInCustomer(models.Model):
    """Offline walk-in customers — no login required."""
    TIER_CHOICES = [
        ('bronze', 'Bronze'), ('silver', 'Silver'),
        ('gold', 'Gold'), ('platinum', 'Platinum'),
    ]
    customer_id = models.CharField(max_length=20, unique=True, editable=False)
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, unique=True)
    email = models.EmailField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    tier = models.CharField(max_length=20, choices=TIER_CHOICES, default='bronze')
    total_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_orders = models.IntegerField(default=0)
    online_account = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='walkin_profile', help_text='Linked online account if merged'
    )
    created_at = models.DateTimeField(default=timezone.now)
    last_visit = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.name} ({self.phone})"

    def save(self, *args, **kwargs):
        if not self.customer_id:
            count = WalkInCustomer.objects.count() + 1
            self.customer_id = f'WC-{count:04d}'
        super().save(*args, **kwargs)


class PricingRule(models.Model):
    """Configurable pricing engine."""
    name = models.CharField(max_length=100)
    print_type = models.CharField(max_length=10, choices=[('bw', 'Black & White'), ('color', 'Color')])
    sides = models.CharField(max_length=10, choices=[('single', 'Single Side'), ('double', 'Double Side')])
    paper_size = models.CharField(max_length=10, default='A4')
    price_per_page = models.DecimalField(max_digits=6, decimal_places=2)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('print_type', 'sides', 'paper_size')

    def __str__(self):
        return f"{self.name} — ৳{self.price_per_page}/page"


class AddonService(models.Model):
    """Finishing services like binding, lamination."""
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=200, blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    is_active = models.BooleanField(default=True)
    icon = models.CharField(max_length=50, default='bi-plus-circle')

    def __str__(self):
        return f"{self.name} (+৳{self.price})"


class PromoCode(models.Model):
    code = models.CharField(max_length=50, unique=True)
    discount_type = models.CharField(max_length=10, choices=[('percent', 'Percent'), ('flat', 'Flat Amount')])
    discount_value = models.DecimalField(max_digits=8, decimal_places=2)
    max_uses = models.IntegerField(default=100)
    used_count = models.IntegerField(default=0)
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return self.code

    @property
    def is_valid(self):
        if not self.is_active:
            return False
        if self.used_count >= self.max_uses:
            return False
        if self.valid_until and timezone.now() > self.valid_until:
            return False
        return True


class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('printing', 'Printing'),
        ('quality_check', 'Quality Check'),
        ('ready', 'Ready for Pickup'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('on_hold', 'On Hold'),
    ]
    PAYMENT_STATUS = [
        ('unpaid', 'Unpaid'),
        ('partial', 'Partial'),
        ('paid', 'Paid'),
        ('refunded', 'Refunded'),
    ]
    SOURCE_CHOICES = [
        ('online', 'Online'),
        ('offline', 'Walk-in'),
    ]

    # Identification
    order_number = models.CharField(max_length=30, unique=True, editable=False)
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default='online')

    # Customer (online or walk-in)
    customer = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='orders'
    )
    walkin_customer = models.ForeignKey(
        WalkInCustomer, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='orders'
    )

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    priority = models.BooleanField(default=False)
    is_urgent = models.BooleanField(default=False)
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_orders'
    )

    # Print Specs
    print_type = models.CharField(max_length=10, choices=[('bw', 'Black & White'), ('color', 'Color')])
    sides = models.CharField(max_length=10, choices=[('single', 'Single Sided'), ('double', 'Double Sided')])
    paper_size = models.CharField(max_length=10, default='A4')
    pages = models.IntegerField(default=1)
    copies = models.IntegerField(default=1)
    total_sheets = models.IntegerField(default=1)

    # File
    file = models.FileField(upload_to='uploads/%Y/%m/', blank=True, null=True)
    file_name = models.CharField(max_length=255, blank=True, null=True)
    file_type = models.CharField(max_length=20, blank=True, null=True)
    is_physical_document = models.BooleanField(default=False)
    google_drive_link = models.URLField(blank=True, null=True)

    # Add-ons (ManyToMany)
    addons = models.ManyToManyField(AddonService, blank=True)

    # Instructions
    special_instructions = models.TextField(blank=True, null=True)
    admin_notes = models.TextField(blank=True, null=True)

    # Financials
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    addons_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    urgent_surcharge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_reason = models.CharField(max_length=200, blank=True, null=True)
    promo_code = models.ForeignKey(PromoCode, on_delete=models.SET_NULL, null=True, blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Payment
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='unpaid')
    payment_method = models.CharField(max_length=50, blank=True, null=True)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    transaction_id = models.CharField(max_length=100, blank=True, null=True)

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_orders'
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.order_number

    def save(self, *args, **kwargs):
        if not self.order_number:
            from django.utils import timezone as tz
            today = tz.now().strftime('%Y%m%d')
            prefix = 'PE-OFF' if self.source == 'offline' else 'PE-ON'
            count = Order.objects.filter(created_at__date=tz.now().date()).count() + 1
            self.order_number = f'{prefix}-{today}-{count:04d}'
        # Calculate total sheets
        if self.sides == 'double':
            self.total_sheets = (self.pages + 1) // 2 * self.copies
        else:
            self.total_sheets = self.pages * self.copies
        super().save(*args, **kwargs)

    @property
    def customer_name(self):
        if self.customer:
            return self.customer.display_name
        if self.walkin_customer:
            return self.walkin_customer.name
        return 'Unknown'

    @property
    def customer_phone(self):
        if self.customer:
            return self.customer.phone or ''
        if self.walkin_customer:
            return self.walkin_customer.phone
        return ''

    @property
    def amount_due(self):
        return self.total_amount - self.amount_paid


class OrderStatusLog(models.Model):
    """Track every status change with timestamp and actor."""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_logs')
    old_status = models.CharField(max_length=20, blank=True, null=True)
    new_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    note = models.CharField(max_length=255, blank=True, null=True)
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['timestamp']


class InventoryItem(models.Model):
    CATEGORY_CHOICES = [
        ('paper', 'Paper'),
        ('toner', 'Toner/Ink'),
        ('binding', 'Binding'),
        ('lamination', 'Lamination'),
        ('other', 'Other'),
    ]
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    current_stock = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    unit = models.CharField(max_length=20)
    min_alert_level = models.DecimalField(max_digits=10, decimal_places=2, default=10)
    cost_per_unit = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    supplier = models.CharField(max_length=100, blank=True, null=True)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.current_stock} {self.unit})"

    @property
    def status(self):
        if self.current_stock <= 0:
            return ('danger', 'Out of Stock')
        if self.current_stock <= self.min_alert_level:
            return ('warning', 'Low Stock')
        return ('success', 'In Stock')


class InventoryLog(models.Model):
    ACTION_CHOICES = [('restock', 'Restock'), ('usage', 'Usage'), ('adjustment', 'Manual Adjustment')]
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    note = models.CharField(max_length=255, blank=True, null=True)
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(default=timezone.now)


class Expense(models.Model):
    CATEGORY_CHOICES = [
        ('paper', 'Paper Purchase'), ('toner', 'Toner/Ink'),
        ('equipment', 'Equipment'), ('electricity', 'Electricity'),
        ('salary', 'Salary'), ('other', 'Other'),
    ]
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50, default='Cash')
    receipt = models.FileField(upload_to='receipts/', blank=True, null=True)
    logged_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.category} — ৳{self.amount} on {self.date}"


class Notification(models.Model):
    TYPE_CHOICES = [
        ('new_order', 'New Order'), ('status_change', 'Status Change'),
        ('low_stock', 'Low Stock'), ('new_user', 'New User'),
        ('payment', 'Payment'), ('system', 'System'),
    ]
    title = models.CharField(max_length=200)
    body = models.TextField()
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    is_read = models.BooleanField(default=False)
    link = models.CharField(max_length=200, blank=True, null=True)
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']


class SiteSettings(models.Model):
    """Singleton model for business configuration."""
    business_name = models.CharField(max_length=100, default='Print-Edge')
    business_phone = models.CharField(max_length=20, default='+8801700000000')
    business_email = models.EmailField(default='admin@printedge.com')
    business_address = models.TextField(default='Gono Bishwabidyalay, Savar, Dhaka')
    business_hours = models.CharField(max_length=100, default='Sun-Thu 9:00 AM – 5:00 PM')
    logo = models.ImageField(upload_to='branding/', blank=True, null=True)
    urgent_surcharge_percent = models.IntegerField(default=50)
    auto_delete_files_days = models.IntegerField(default=7)
    max_upload_mb = models.IntegerField(default=50)
    currency_symbol = models.CharField(max_length=5, default='৳')
    session_timeout_minutes = models.IntegerField(default=60)
    max_login_attempts = models.IntegerField(default=5)

    class Meta:
        verbose_name = 'Site Settings'

    def __str__(self):
        return self.business_name

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=100)
    resource_type = models.CharField(max_length=50)
    resource_id = models.CharField(max_length=50, blank=True, null=True)
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True, null=True)
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.timestamp:%Y-%m-%d %H:%M}] {self.action} by {self.user}"
