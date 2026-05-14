from .models import SiteSettings, Notification


def site_settings(request):
    """Inject site settings and unread notification count into every template."""
    ctx = {
        'SITE': SiteSettings.get(),
        'unread_notifications': 0,
    }
    if request.user.is_authenticated and hasattr(request.user, 'notifications'):
        ctx['unread_notifications'] = request.user.notifications.filter(is_read=False).count()
    return ctx
