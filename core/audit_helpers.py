"""Audit logging helpers for admin operations."""


def log_audit(request, action, resource_type, resource_id='', old_value='', new_value=''):
    from .models import AuditLog

    user = request.user if getattr(request, 'user', None) and request.user.is_authenticated else None
    ip = request.META.get('REMOTE_ADDR') if request else None
    ua = (request.META.get('HTTP_USER_AGENT') or '')[:300] if request else ''
    AuditLog.objects.create(
        user=user,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id else '',
        old_value=str(old_value)[:2000] if old_value else '',
        new_value=str(new_value)[:2000] if new_value else '',
        ip_address=ip,
        user_agent=ua,
    )
