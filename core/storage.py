"""Storage configuration helpers for Supabase S3-compatible bucket."""

import os


def supabase_storage_enabled():
    return bool(
        os.environ.get('AWS_ACCESS_KEY_ID')
        and os.environ.get('AWS_SECRET_ACCESS_KEY')
        and os.environ.get('SUPABASE_STORAGE_BUCKET')
    )


def supabase_project_url():
    return (os.environ.get('SUPABASE_URL') or '').rstrip('/')
