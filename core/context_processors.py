from django.conf import settings

from .models import SiteSettings, Notification


def site_settings(request):
    """Inject site settings and unread notification count into every template."""
    ctx = {
        'SITE': SiteSettings.get(),
        'unread_notifications': 0,
        'user_avatar_url': '',
    }
    if request.user.is_authenticated:
        # Use avatar_url directly if it's a valid URL, otherwise empty
        avatar_url = (request.user.avatar_url or '').strip()
        if avatar_url.startswith('http://') or avatar_url.startswith('https://'):
            ctx['user_avatar_url'] = avatar_url
        if hasattr(request.user, 'notifications'):
            ctx['unread_notifications'] = request.user.notifications.filter(is_read=False).count()
    return ctx


def supabase_config(request):
    return {
        'SUPABASE_URL': getattr(settings, 'SUPABASE_URL', ''),
        'SUPABASE_ANON_KEY': getattr(settings, 'SUPABASE_ANON_KEY', ''),
    }
