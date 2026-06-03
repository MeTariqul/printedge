"""Simple cache-based rate limiting for auth endpoints."""

from django.core.cache import cache


def _client_key(request, prefix):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    ip = forwarded.split(',')[0].strip() if forwarded else request.META.get('REMOTE_ADDR', 'unknown')
    return f'ratelimit:{prefix}:{ip}'


def is_rate_limited(request, prefix, max_attempts=5, window_seconds=300):
    key = _client_key(request, prefix)
    attempts = cache.get(key, 0)
    return attempts >= max_attempts


def record_failed_attempt(request, prefix, window_seconds=300):
    key = _client_key(request, prefix)
    attempts = cache.get(key, 0) + 1
    cache.set(key, attempts, window_seconds)


def clear_attempts(request, prefix):
    cache.delete(_client_key(request, prefix))
