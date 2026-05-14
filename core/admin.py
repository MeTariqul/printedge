from django.contrib import admin
from .models import (User, WalkInCustomer, Order, InventoryItem,
                     PricingRule, AddonService, PromoCode, Expense,
                     Notification, AuditLog, SiteSettings, OrderStatusLog)

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'get_full_name', 'role', 'tier', 'phone', 'total_spent', 'is_active')
    list_filter = ('role', 'tier', 'is_active', 'is_banned')
    search_fields = ('email', 'first_name', 'last_name', 'phone')

@admin.register(WalkInCustomer)
class WalkInCustomerAdmin(admin.ModelAdmin):
    list_display = ('customer_id', 'name', 'phone', 'tier', 'total_orders', 'total_spent')
    search_fields = ('name', 'phone')

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'source', 'customer_name', 'status', 'total_amount', 'payment_status', 'created_at')
    list_filter = ('status', 'source', 'print_type', 'payment_status')
    search_fields = ('order_number', 'customer__email', 'walkin_customer__phone')
    readonly_fields = ('order_number', 'created_at', 'updated_at')

    def customer_name(self, obj):
        return obj.customer_name

@admin.register(PricingRule)
class PricingRuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'print_type', 'sides', 'paper_size', 'price_per_page', 'is_active')

@admin.register(AddonService)
class AddonServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'is_active')

@admin.register(InventoryItem)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'current_stock', 'unit', 'min_alert_level')

@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_type', 'discount_value', 'used_count', 'max_uses', 'is_active')

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('category', 'description', 'amount', 'date')

@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

admin.site.register(AuditLog)
admin.site.register(Notification)
admin.site.register(OrderStatusLog)
