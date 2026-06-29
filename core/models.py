from django.db import models
from django.contrib.auth.models import AbstractUser, UserManager
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
import uuid


def order_number_default():
    return ''


class EmailUserManager(UserManager):
    """Custom manager for User model with email as USERNAME_FIELD."""
    
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        extra_fields.setdefault('username', email.split('@')[0] or email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields['role'] = 'super_admin'
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email, password, **extra_fields)


class DualWriteMixin:
    """Mixin for consistent save behavior."""
    
    def save(self, *args, **kwargs):
        if 'using' not in kwargs:
            kwargs['using'] = 'default'
        return super().save(*args, **kwargs)


class User(DualWriteMixin, AbstractUser):
    """Extended user model for online customers and staff."""
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    EMAIL_FIELD = 'email'
    
    objects = EmailUserManager()

    # Re-declaring email to make it unique (required for USERNAME_FIELD)
    email = models.EmailField(_('email address'), blank=False, max_length=254, unique=True, db_index=True)

    ROLE_CHOICES = [
        ('customer', 'Customer'),
        ('viewer', 'Viewer'),
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
    university = models.CharField(max_length=150, blank=True, default='')
    department = models.CharField(max_length=100, blank=True, null=True)
    student_id = models.CharField(max_length=50, blank=True, null=True)
    avatar_url = models.URLField(max_length=500, blank=True, null=True, verbose_name="Profile Photo URL")
    total_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_orders = models.IntegerField(default=0)
    is_email_verified = models.BooleanField(
        default=False,
        help_text='Customers must verify email before placing online orders.',
    )
    is_banned = models.BooleanField(default=False)
    ban_reason = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)  # admin internal notes
    notification_email = models.BooleanField(default=True, help_text='Receive email notifications')
    notification_push = models.BooleanField(default=False, help_text='Receive push notifications (future)')
    password_plain = models.CharField(
        max_length=128, blank=True, default='',
        help_text='Admin-visible copy; set when password is created or changed.',
    )
    custom_permissions = models.JSONField(null=True, blank=True, help_text="Overrides role permissions if set.")
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def display_name(self):
        return self.get_full_name() or self.username or self.email

    @property
    def is_admin_user(self):
        return self.role in ('admin', 'super_admin', 'manager', 'operator', 'viewer')

    @property
    def is_readonly_staff(self):
        return self.role == 'viewer'

    @property
    def is_full_admin(self):
        return self.role in ('admin', 'super_admin')

    @property
    def can_manage_users(self):
        from .permissions import user_has_permission
        return user_has_permission(self, 'manage_customers')

    @property
    def can_edit_pricing(self):
        from .permissions import user_has_permission
        return user_has_permission(self, 'manage_pricing')

    @property
    def can_change_settings(self):
        from .permissions import user_has_permission
        return user_has_permission(self, 'edit_settings')

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


class UserAddress(DualWriteMixin, models.Model):
    """Saved delivery addresses for online customers."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    label = models.CharField(max_length=50, default='Home')
    address = models.TextField()
    phone = models.CharField(max_length=20, blank=True, default='')
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-is_default', '-created_at']

    def __str__(self):
        return f'{self.label}: {self.address[:40]}'


class WalkInCustomer(DualWriteMixin, models.Model):
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
            count = WalkInCustomer.objects.using('default').count() + 1
            self.customer_id = f'WC-{count:04d}'
        if 'using' not in kwargs:
            kwargs['using'] = 'default'
        return super().save(*args, **kwargs)


class AddonService(DualWriteMixin, models.Model):
    """Finishing services like binding, lamination."""
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=200, blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    is_active = models.BooleanField(default=True)
    icon = models.CharField(max_length=50, default='bi-plus-circle')

    def __str__(self):
        return f"{self.name} (+৳{self.price})"


class Service(DualWriteMixin, models.Model):
    CATEGORY_CHOICES = [
        ('printing', 'Printing'),
        ('photo', 'Photo'),
        ('binding', 'Binding'),
        ('lamination', 'Lamination'),
        ('stationery', 'Stationery'),
        ('custom', 'Custom'),
    ]
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=100, choices=CATEGORY_CHOICES)
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    requires_file = models.BooleanField(default=False, help_text='If checked, customers must upload a file when ordering this service.')
    image = models.ImageField(upload_to='services/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category', 'name']

    def __str__(self):
        return f"{self.name} (৳{self.base_price})"

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class ServiceVariant(DualWriteMixin, models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='variants')
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Price for this variant (0 = inherits service base_price)")
    specs = models.JSONField(default=dict, blank=True, help_text="Arbitrary key-value pairs like paper_size, gsm, etc.")
    stock = models.IntegerField(default=0)
    low_stock_threshold = models.IntegerField(default=5)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['service', 'name']

    def __str__(self):
        effective_price = self.price if self.price > 0 else self.service.base_price
        return f"{self.service.name} - {self.name} (+৳{effective_price})"

    @property
    def effective_price(self):
        return self.price if self.price > 0 else self.service.base_price

    @property
    def is_low_stock(self):
        return self.stock <= self.low_stock_threshold and self.stock > 0

    @property
    def is_out_of_stock(self):
        return self.stock <= 0


class Coupon(DualWriteMixin, models.Model):
    code = models.CharField(max_length=50, unique=True)
    discount_type = models.CharField(max_length=15, choices=[('percentage', 'Percentage'), ('fixed', 'Fixed Amount')])
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    max_uses = models.PositiveIntegerField(null=True, blank=True)
    used_count = models.PositiveIntegerField(default=0)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_to = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.code

    @property
    def is_valid(self):
        if not self.is_active:
            return False
        if self.max_uses is not None and self.used_count >= self.max_uses:
            return False
        now = timezone.now()
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_to and now > self.valid_to:
            return False
        return True


class Order(DualWriteMixin, models.Model):
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
    VALID_TRANSITIONS = {
        'pending': {'confirmed', 'cancelled'},
        'confirmed': {'printing', 'cancelled'},
        'printing': {'quality_check', 'on_hold'},
        'quality_check': {'ready', 'printing', 'on_hold'},
        'ready': {'delivered', 'on_hold'},
        'delivered': set(),
        'cancelled': set(),
        'on_hold': {'confirmed', 'printing', 'quality_check', 'ready'},
    }
    PAYMENT_STATUS = [
        ('unpaid', 'Unpaid'),
        ('partial', 'Partial'),
        ('pending_review', 'Pending Review'),
        ('paid', 'Paid'),
        ('rejected', 'Rejected'),
        ('refunded', 'Refunded'),
    ]
    SOURCE_CHOICES = [
        ('online', 'Online'),
        ('offline', 'Walk-in'),
    ]
    FULFILLMENT_CHOICES = [
        ('pickup', 'Pickup at shop'),
        ('delivery', 'Delivery to location'),
    ]

    # Identification
    order_number = models.CharField(max_length=30, unique=True, editable=False)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='online')

    # Service / Pricing
    service = models.ForeignKey(
        'Service', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='orders',
        help_text='Selected service for this order.',
    )
    variant = models.ForeignKey(
        'ServiceVariant', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='orders',
        help_text='Selected variant/service option for this order.',
    )

    # Customer (online or walk-in)
    customer = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='orders'
    )
    walkin_customer = models.ForeignKey(
        WalkInCustomer, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='orders'
    )
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_orders',
        limit_choices_to={'role__in': ['operator', 'manager', 'admin', 'super_admin']}
    )

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    priority = models.BooleanField(default=False)
    is_urgent = models.BooleanField(default=False)

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
    file_size_bytes = models.BigIntegerField(null=True, blank=True)
    file_deleted_at = models.DateTimeField(null=True, blank=True)

    # Fulfillment / delivery
    fulfillment_type = models.CharField(
        max_length=20, choices=FULFILLMENT_CHOICES, default='pickup',
    )
    delivery_address = models.TextField(blank=True, null=True)
    delivery_contact_phone = models.CharField(max_length=20, blank=True, null=True)

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
    coupon = models.ForeignKey(Coupon, on_delete=models.SET_NULL, null=True, blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Payment
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='unpaid')
    payment_method = models.CharField(max_length=50, blank=True, null=True)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    payment_screenshot = models.ImageField(upload_to='payment-screenshots/%Y/%m/', blank=True, null=True)
    payment_rejection_reason = models.TextField(blank=True, null=True)

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_orders'
    )
    invoice_file = models.FileField(upload_to='invoices/%Y/%m/', blank=True, null=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.order_number

    def transition_status(self, new_status, changed_by=None, note=''):
        if new_status not in dict(self.STATUS_CHOICES):
            raise ValueError(f'Invalid status: {new_status}')
        old_status = self.status
        if old_status == new_status:
            return old_status
        allowed = self.VALID_TRANSITIONS.get(old_status, set())
        if new_status not in allowed:
            raise ValueError(f'Cannot transition from {old_status} to {new_status}')
        self.status = new_status
        if new_status == 'confirmed' and not self.confirmed_at:
            self.confirmed_at = timezone.now()
        if new_status == 'delivered' and not self.completed_at:
            self.completed_at = timezone.now()
        self.save(update_fields=['status', 'confirmed_at', 'completed_at', 'updated_at'])
        OrderStatusLog.objects.create(
            order=self, old_status=old_status,
            new_status=new_status, changed_by=changed_by, note=note or '',
        )
        return old_status

    def save(self, *args, **kwargs):
        if not self.order_number:
            from django.db import transaction
            prefix = 'PE-OFF' if self.source == 'offline' else 'PE-ON'
            today = timezone.now().strftime('%Y%m%d')
            try:
                last = Order.objects.select_for_update(skip_locked=True).filter(
                    order_number__startswith=f'{prefix}-{today}'
                ).order_by('-order_number').first()
                if last:
                    num = int(last.order_number.rsplit('-', 1)[-1]) + 1
                else:
                    num = 1
            except Exception:
                num = Order.objects.filter(order_number__startswith=f'{prefix}-{today}').count() + 1
            self.order_number = f'{prefix}-{today}-{num:04d}'
        if self.pk and self.order_files.exists():
            pass
        elif self.sides == 'double':
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

    @property
    def calculated_total(self):
        return self.base_price + self.addons_price + self.urgent_surcharge - self.discount_amount

    @property
    def has_stored_file(self):
        if self.file_deleted_at:
            return False
        return bool(self.file and self.file.name)

    def file_purge_eligible_at(self):
        if not self.completed_at or not self.has_stored_file:
            return None
        days = SiteSettings.get().auto_delete_files_days
        return self.completed_at + timezone.timedelta(days=days)

    def days_until_auto_file_delete(self):
        eligible = self.file_purge_eligible_at()
        if not eligible:
            return None
        delta = eligible - timezone.now()
        return max(0, delta.days)

    @property
    def order_files_list(self):
        """All line-item files for this order."""
        return list(self.order_files.all())

    @property
    def file_count(self):
        return self.order_files.count() or (1 if self.file else 0)

    @property
    def total_pages_all_files(self):
        files = self.order_files_list
        if files:
            return sum(f.effective_pages * f.copies for f in files)
        return self.pages * self.copies


class OrderFile(DualWriteMixin, models.Model):
    """Per-document line item with its own print configuration."""
    PRINT_TYPE_CHOICES = [('bw', 'Black & White'), ('color', 'Color')]
    SIDES_CHOICES = [('single', 'Single Sided'), ('double', 'Double Sided')]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='order_files')
    file = models.FileField(upload_to='uploads/%Y/%m/', blank=True, null=True)
    file_name = models.CharField(max_length=255, blank=True, default='')
    file_type = models.CharField(max_length=20, blank=True, default='')
    file_size_bytes = models.BigIntegerField(null=True, blank=True)
    print_type = models.CharField(max_length=10, choices=PRINT_TYPE_CHOICES, default='bw')
    sides = models.CharField(max_length=10, choices=SIDES_CHOICES, default='single')
    paper_size = models.CharField(max_length=10, default='A4')
    pages_detected = models.PositiveIntegerField(default=1)
    pages_override = models.PositiveIntegerField(null=True, blank=True)
    copies = models.PositiveIntegerField(default=1)
    line_base_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_primary = models.BooleanField(default=False)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['sort_order', 'pk']

    @property
    def effective_pages(self):
        return self.pages_override if self.pages_override else self.pages_detected

    @property
    def pages(self):
        return self.effective_pages

    @property
    def unit_price(self):
        return self.line_base_price / self.copies if self.copies else Decimal('0')

    def sheets_for_file(self):
        pages = self.effective_pages
        if self.sides == 'double':
            return ((pages + 1) // 2) * self.copies
        return pages * self.copies


class OrderFilePageRange(DualWriteMixin, models.Model):
    """Custom page ranges with different print settings within one file."""
    order_file = models.ForeignKey(OrderFile, on_delete=models.CASCADE, related_name='page_ranges')
    start_page = models.PositiveIntegerField()
    end_page = models.PositiveIntegerField()
    print_type = models.CharField(max_length=10, choices=OrderFile.PRINT_TYPE_CHOICES, default='bw')
    sides = models.CharField(max_length=10, choices=OrderFile.SIDES_CHOICES, default='single')

    class Meta:
        ordering = ['start_page']

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.start_page > self.end_page:
            raise ValidationError('Start page must be <= end page.')
        total = self.order_file.effective_pages
        if self.end_page > total:
            raise ValidationError(f'End page cannot exceed {total}.')

    def page_count(self):
        return self.end_page - self.start_page + 1


class OrderStatusLog(DualWriteMixin, models.Model):
    """Track every status change with timestamp and actor."""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_logs')
    old_status = models.CharField(max_length=20, blank=True, null=True)
    new_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    note = models.CharField(max_length=255, blank=True, null=True)
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['timestamp']


class InventoryItem(DualWriteMixin, models.Model):
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
    variant = models.OneToOneField(ServiceVariant, on_delete=models.SET_NULL, related_name='inventory_item', null=True, blank=True)
    last_restocked = models.DateTimeField(null=True, blank=True)
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


class InventoryLog(DualWriteMixin, models.Model):
    ACTION_CHOICES = [('restock', 'Restock'), ('usage', 'Usage'), ('adjustment', 'Manual Adjustment')]
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    note = models.CharField(max_length=255, blank=True, null=True)
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(default=timezone.now)


class Expense(DualWriteMixin, models.Model):
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


class Notification(DualWriteMixin, models.Model):
    TARGET_CHOICES = [
        ('order', 'Order'), ('payment', 'Payment'), ('user', 'User'),
        ('system', 'System'), ('stock', 'Stock'),
    ]
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='actions')
    verb = models.CharField(max_length=255)
    target_type = models.CharField(max_length=50, choices=TARGET_CHOICES, default='system')
    target_id = models.PositiveIntegerField(null=True, blank=True)
    target_url = models.CharField(max_length=500, blank=True, default='')
    description = models.TextField(blank=True, null=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.recipient} - {self.verb}'


class SiteSettings(DualWriteMixin, models.Model):
    """Singleton model for business configuration."""
    # ── Business Info ──────────────────────────────────────────────────────────
    business_name = models.CharField(max_length=100, default='Print-Edge')
    business_phone = models.CharField(max_length=20, default='+8801700000000')
    business_email = models.EmailField(default='admin@Print-Edge.com')
    business_address = models.TextField(
        default='Default delivery location: Gono Bishwabidyalay (convenience point only). Not affiliated with Gono Bishwabidyalay.',
    )
    business_hours = models.CharField(max_length=100, default='Sun-Thu 9:00 AM – 5:00 PM')
    logo = models.ImageField(upload_to='branding/', blank=True, null=True)

    # ── Social & Contact Links (editable from admin dashboard) ─────────────────
    whatsapp_number = models.CharField(
        max_length=20, blank=True, default='',
        help_text='WhatsApp number in international format without +, e.g. 8801712345678'
    )
    messenger_link = models.URLField(
        blank=True, default='',
        help_text='Full Facebook Messenger URL, e.g. https://m.me/your_page'
    )
    facebook_page = models.URLField(
        blank=True, default='',
        help_text='Facebook page URL'
    )
    google_maps_link = models.URLField(
        blank=True, default='',
        help_text='Google Maps embed or directions link for your location'
    )

    # ── Order Settings ─────────────────────────────────────────────────────────
    accepting_orders = models.BooleanField(
        default=True,
        help_text='When off, customers cannot place new online orders.',
    )
    urgent_surcharge_percent = models.IntegerField(default=50)
    auto_delete_files_days = models.IntegerField(default=7)
    max_upload_mb = models.IntegerField(default=50)
    currency_symbol = models.CharField(max_length=5, default='৳')
    bkash_number = models.CharField(max_length=20, blank=True, default='', help_text='bKash number for payments')
    nagad_number = models.CharField(max_length=20, blank=True, default='', help_text='Nagad number for payments')
    rocket_number = models.CharField(max_length=20, blank=True, default='', help_text='Rocket number for payments')
    chat_provider = models.CharField(
        max_length=20, blank=True, default='',
        choices=[('', 'None'), ('tawk', 'Tawk.to'), ('crisp', 'Crisp')],
    )
    chat_widget_id = models.CharField(max_length=200, blank=True, default='')
    require_email_verification = models.BooleanField(
        default=True,
        help_text='New users must verify email before they can place orders.',
    )
    send_email_on_registration = models.BooleanField(default=True)
    send_email_on_order_placed = models.BooleanField(default=True)
    send_email_on_status_change = models.BooleanField(default=True)
    send_email_on_payment_approved = models.BooleanField(default=True)
    send_email_on_payment_rejected = models.BooleanField(default=True)
    send_email_on_admin_approval = models.BooleanField(default=True)
    email_from_name = models.CharField(max_length=100, default='PrintEdge')

    class Meta:
        verbose_name = 'Site Settings'

    def __str__(self):
        return self.business_name

    @property
    def phone_digits(self):
        return ''.join(c for c in self.business_phone if c.isdigit())

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class EmailLog(DualWriteMixin, models.Model):
    """Log of all sent emails for debugging and monitoring."""
    recipient = models.EmailField()
    subject = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=[('sent', 'Sent'), ('failed', 'Failed')], default='sent')
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.subject} → {self.recipient} ({self.status})"


class EmailTemplate(DualWriteMixin, models.Model):
    """Saved email templates for reuse in composition."""
    name = models.CharField(max_length=100, unique=True)
    subject = models.CharField(max_length=255)
    html_body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class AuditLog(DualWriteMixin, models.Model):
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
