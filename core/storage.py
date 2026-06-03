"""Storage configuration helpers for Supabase S3-compatible bucket."""

import os


def supabase_s3_endpoint():
    explicit = (os.environ.get('AWS_S3_ENDPOINT_URL') or '').strip()
    if explicit:
        return explicit.rstrip('/')
    base = (os.environ.get('SUPABASE_URL') or '').rstrip('/')
    if not base or '.supabase.co' not in base:
        return ''
    host = base.split('//', 1)[-1]
    project_ref = host.split('.')[0]
    return f'https://{project_ref}.storage.supabase.co/storage/v1/s3'


def supabase_storage_enabled():
    s3_key = os.environ.get('SUPABASE_S3_ACCESS_KEY_ID', '') or os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
    s3_secret = os.environ.get('SUPABASE_S3_SECRET_ACCESS_KEY', '') or os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
    bucket = os.environ.get('SUPABASE_STORAGE_BUCKET', 'order-files')
    endpoint = supabase_s3_endpoint()
    return bool(s3_key and s3_secret and bucket and endpoint)


def supabase_project_url():
    return (os.environ.get('SUPABASE_URL') or '').rstrip('/')