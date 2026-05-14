from django.urls import path
from . import views

urlpatterns = [
    # Public
    path('', views.public_index, name='public_index'),
    path('pricing/', views.public_pricing, name='public_pricing_page'),

    # Auth
    path('auth/login/', views.auth_login, name='auth_login_page'),
    path('auth/register/', views.auth_register, name='auth_register_page'),
    path('auth/logout/', views.auth_logout, name='auth_logout'),

    # User
    path('user/dashboard/', views.user_dashboard, name='user_dashboard'),
    path('user/orders/', views.user_orders, name='user_orders'),
    path('user/orders/new/', views.user_new_order, name='user_new_order'),
    path('user/orders/<int:pk>/', views.user_order_detail, name='user_order_detail'),
    path('user/profile/', views.user_profile, name='user_profile'),

    # Admin
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/orders/', views.admin_orders, name='admin_orders'),
    path('admin/orders/<int:pk>/', views.admin_order_detail, name='admin_order_detail'),
    path('admin/orders/walkin/', views.admin_walkin_order, name='admin_walkin_order'),
    path('admin/customers/online/', views.admin_users, name='admin_users'),
    path('admin/customers/offline/', views.admin_offline_customers, name='admin_offline_customers'),
    path('admin/inventory/', views.admin_inventory, name='admin_inventory'),
    path('admin/services/', views.admin_services, name='admin_services'),
    path('admin/financial/', views.admin_financial, name='admin_financial'),
    path('admin/reports/', views.admin_reports, name='admin_reports'),
    path('admin/audit/', views.admin_audit_log, name='admin_audit_log'),
    path('admin/display/', views.admin_display_mode, name='admin_display_mode'),
    path('admin/settings/', views.admin_settings, name='admin_settings'),

    # API
    path('api/price/', views.api_price_calculate, name='api_price_calculate'),
    path('api/walkin-search/', views.api_walkin_search, name='api_walkin_search'),
    path('api/orders/<int:pk>/status/', views.api_order_status_update, name='api_order_status'),
    path('api/search/', views.api_global_search, name='api_global_search'),
    path('api/notifications/', views.api_notifications, name='api_notifications'),
]
