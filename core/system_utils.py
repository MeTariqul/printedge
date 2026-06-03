"""System monitoring utilities for PrintEdge admin dashboard."""

import os
import sys
import platform
import socket
import time
import smtplib
from datetime import datetime, timedelta

from django.conf import settings
from django.db import connections, OperationalError
from django.core.cache import cache
from django.utils import timezone
from django.db.models import Sum

from .models import Order, User, Notification, AuditLog


def get_server_info():
    """Get server and environment information."""
    info = {}
    try:
        info['hostname'] = socket.gethostname()
        info['ip_address'] = socket.gethostbyname(info['hostname'])
    except Exception:
        info['hostname'] = 'N/A'
        info['ip_address'] = 'N/A'

    try:
        info['os'] = platform.platform()
    except Exception:
        info['os'] = 'N/A'

    try:
        info['python_version'] = sys.version.split()[0]
    except Exception:
        info['python_version'] = 'N/A'

    info['debug'] = settings.DEBUG
    info['environment'] = 'production' if not settings.DEBUG else 'development'
    info['timezone'] = settings.TIME_ZONE
    info['server_time'] = timezone.now()

    return info


def get_database_status():
    """Get status for all database connections."""
    db_status = {}

    for db_name in connections:
        db_conn = connections[db_name]
        try:
            db_conn.ensure_connection()
            t0 = time.perf_counter()

            with db_conn.cursor() as cursor:
                cursor.execute('SELECT 1')  # Basic connectivity test

                vendor = db_conn.vendor

                if vendor in ('postgresql', 'postgres'):
                    cursor.execute("SELECT version()")
                    row = cursor.fetchone()
                    version = row[0][:150] if row else 'PostgreSQL'

                    # Get table count
                    cursor.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'")
                    table_count = cursor.fetchone()[0]

                    # Get database size
                    cursor.execute("SELECT pg_database_size(current_database())")
                    size_bytes = cursor.fetchone()[0] if cursor.rowcount else 0

                else:
                    version = vendor.title()
                    table_count = 'N/A'
                    size_bytes = 0

            latency_ms = round((time.perf_counter() - t0) * 1000, 1)
            db_settings = db_conn.settings_dict

            db_status[db_name] = {
                'connected': True,
                'vendor': vendor,
                'version': version,
                'latency_ms': latency_ms,
                'table_count': table_count,
                'size_mb': round(size_bytes / 1024 / 1024, 1) if isinstance(size_bytes, (int, float)) else 0,
                'host': db_settings.get('HOST', 'N/A'),
                'name': db_settings.get('NAME', 'N/A'),
            }
        except OperationalError as exc:
            db_status[db_name] = {
                'connected': False,
                'vendor': 'unknown',
                'version': str(exc)[:100],
                'latency_ms': None,
                'table_count': 0,
                'size_mb': 0,
                'host': 'N/A',
                'name': 'N/A',
            }
        except Exception as exc:
            db_status[db_name] = {
                'connected': False,
                'vendor': 'unknown',
                'version': str(exc)[:100],
                'latency_ms': None,
                'table_count': 0,
                'size_mb': 0,
                'host': 'N/A',
                'name': 'N/A',
            }

    return db_status


def get_cache_status():
    """Get cache backend status."""
    status = {}

    try:
        from django.core.cache import caches
        default_cache = caches['default']
        status['backend'] = f"{default_cache.__class__.__module__}.{default_cache.__class__.__name__}"

        cache.set('system_test', 'ok', 10)
        test_read = cache.get('system_test') == 'ok'
        status['connected'] = test_read

        # Check for Redis-specific info
        if 'redis' in status['backend'].lower():
            try:
                client = cache._client.get_client()
                info = client.info()
                status['memory_mb'] = round(info.get('used_memory', 0) / 1024 / 1024, 1)
                status['connected_clients'] = info.get('connected_clients', 'N/A')
            except Exception:
                status['memory_mb'] = None
                status['connected_clients'] = 'N/A'
        else:
            status['memory_mb'] = None
            status['connected_clients'] = 'N/A'

    except Exception as exc:
        status['backend'] = 'Unknown'
        status['connected'] = False
        status['memory_mb'] = None
        status['connected_clients'] = 'N/A'

    return status


def get_application_metrics():
    """Get application metrics from the database."""
    today = timezone.now().date()
    month_start = today.replace(day=1)

    return {
        'total_users': User.objects.count(),
        'total_orders': Order.objects.count(),
        'orders_today': Order.objects.filter(created_at__date=today).count(),
        'orders_month': Order.objects.filter(created_at__date__gte=month_start).count(),
        'pending_orders': Order.objects.filter(status__in=['pending', 'confirmed']).count(),
        'total_revenue': Order.objects.filter(payment_status='paid').aggregate(
            total=Sum('total_amount')
        )['total'] or 0,
        'avg_order_value': round(
            (Order.objects.filter(payment_status='paid').aggregate(total=Sum('total_amount'))['total'] or 0)
            / max(Order.objects.filter(payment_status='paid').count(), 1), 0
        ),
        'online_orders': Order.objects.filter(source='online').count(),
        'walkin_orders': Order.objects.filter(source='offline').count(),
    }