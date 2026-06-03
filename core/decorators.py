"""
Print-Edge — Decorators and permission helpers
"""
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages

from .permissions import user_has_permission, is_readonly_staff


def login_required_custom(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, 'Please log in to continue.')
            return redirect('auth_login_page')
        if request.user.is_banned:
            messages.error(request, 'Your account has been suspended. Contact support.')
            return redirect('auth_login_page')
        return view_func(request, *args, **kwargs)
    return wrapper


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('auth_login_page')
        if not request.user.is_admin_user:
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('user_dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def permission_required(permission):
    """Staff route gated by permission matrix."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('auth_login_page')
            if not request.user.is_admin_user:
                messages.error(request, 'You do not have permission to access this page.')
                return redirect('user_dashboard')
            if not user_has_permission(request.user, permission):
                messages.error(request, 'Your role cannot access this section.')
                if request.user.role == 'operator':
                    return redirect('admin_operator_dashboard')
                return redirect('admin_dashboard')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def write_staff_required(view_func):
    """Block read-only viewer from mutating actions."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('auth_login_page')
        if is_readonly_staff(request.user):
            messages.error(request, 'Viewer accounts have read-only access.')
            return redirect('admin_orders')
        if request.method == 'POST' and not user_has_permission(request.user, 'update_order_status'):
            messages.error(request, 'You cannot perform this action.')
            return redirect('admin_dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def superadmin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('auth_login_page')
        if request.user.role not in ('super_admin', 'admin'):
            messages.error(request, 'Super Admin access required.')
            return redirect('admin_dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper
