from django.urls import path
from . import views

urlpatterns = [
    # Admin URLs
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/orders/', views.admin_orders, name='admin_orders'),
    path('admin/orders/walkin/', views.admin_walkin_order, name='admin_walkin_order'),
    path('admin/customers/online/', views.admin_users, name='admin_users'),
    path('admin/customers/offline/', views.admin_offline_customers, name='admin_offline_customers'),
    path('admin/services/', views.admin_services, name='admin_services'),
    path('admin/inventory/', views.admin_inventory, name='admin_inventory'),
    path('admin/financial/', views.admin_financial, name='admin_financial'),
    path('admin/staff/', views.admin_staff, name='admin_staff'),
    path('admin/reports/', views.admin_reports, name='admin_reports'),
    path('admin/audit/', views.admin_audit_log, name='admin_audit_log'),
    path('admin/display/', views.admin_display_mode, name='admin_display_mode'),
    path('admin/settings/', views.admin_settings, name='admin_settings'),
    
    # Auth URLs
    path('auth/login/', views.auth_login, name='auth_login_page'),
    path('auth/register/', views.auth_register, name='auth_register_page'),
    path('auth/logout/', views.auth_logout, name='auth_logout'),
    
    # User URLs
    path('user/dashboard/', views.user_dashboard, name='user_dashboard'),
    
    # Public URLs
    path('', views.public_index, name='public_index'),
    path('pricing/', views.public_pricing, name='public_pricing_page'),

    # API URLs
    path('admin/api/search', views.api_search, name='api_search'),
    path('admin/api/orders/<str:order_id>/status', views.api_order_status, name='api_order_status'),
]
