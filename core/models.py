from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

class User(AbstractUser):
    # Extending the default Django user
    phone = models.CharField(max_length=20, blank=True, null=True)
    is_offline_customer = models.BooleanField(default=False)
    student_id = models.CharField(max_length=50, blank=True, null=True)
    department = models.CharField(max_length=100, blank=True, null=True)
    tier = models.CharField(max_length=20, default='Bronze', choices=[
        ('Bronze', 'Bronze'),
        ('Silver', 'Silver'),
        ('Gold', 'Gold'),
        ('Platinum', 'Platinum'),
    ])
    total_spent = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    def __str__(self):
        return self.username or self.email

class InventoryItem(models.Model):
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=50, choices=[
        ('Paper', 'Paper'),
        ('Toner', 'Toner'),
        ('Binding', 'Binding'),
        ('Lamination', 'Lamination'),
        ('Other', 'Other')
    ])
    current_stock = models.IntegerField(default=0)
    min_alert_level = models.IntegerField(default=10)
    unit = models.CharField(max_length=20)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.current_stock} {self.unit})"

class Order(models.Model):
    ORDER_STATUS = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('printing', 'Printing'),
        ('quality_check', 'Quality Check'),
        ('ready', 'Ready'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled')
    ]
    
    order_number = models.CharField(max_length=50, unique=True)
    customer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    customer_name_fallback = models.CharField(max_length=100, blank=True, null=True)
    customer_phone_fallback = models.CharField(max_length=20, blank=True, null=True)
    
    is_offline = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=ORDER_STATUS, default='pending')
    
    # Print Specs
    print_type = models.CharField(max_length=20, choices=[('bw', 'Black & White'), ('color', 'Color')])
    sides = models.CharField(max_length=20, choices=[('single', 'Single Sided'), ('double', 'Double Sided')])
    paper_size = models.CharField(max_length=20, default='A4')
    pages = models.IntegerField(default=1)
    copies = models.IntegerField(default=1)
    is_urgent = models.BooleanField(default=False)
    
    # File Info
    file = models.FileField(upload_to='uploads/', blank=True, null=True)
    is_physical_document = models.BooleanField(default=False)
    
    # Financials
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    addons_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Payment
    payment_method = models.CharField(max_length=50, blank=True, null=True)
    payment_status = models.CharField(max_length=20, default='unpaid')
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    transaction_id = models.CharField(max_length=100, blank=True, null=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.order_number

class Expense(models.Model):
    category = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid_from = models.CharField(max_length=50)
    notes = models.TextField(blank=True, null=True)
    date = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.category} - ৳{self.amount}"

class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=50)
    resource = models.CharField(max_length=50)
    details = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.action} on {self.resource} by {self.user}"
