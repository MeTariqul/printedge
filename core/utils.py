import os

ALLOWED_UPLOAD_EXTENSIONS = ('.pdf', '.doc', '.docx', '.ppt', '.pptx', '.jpg', '.jpeg', '.png')
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def max_upload_bytes():
    try:
        from .models import SiteSettings
        mb = SiteSettings.get().max_upload_mb
        return max(1, int(mb)) * 1024 * 1024
    except Exception:
        return MAX_UPLOAD_BYTES


def safe_int(value, default=1, minimum=1):
    try:
        return max(minimum, int(value))
    except (TypeError, ValueError):
        return default


def validate_upload_file(uploaded_file):
    """Return error message string, or None if valid."""
    if not uploaded_file:
        return None
    limit = max_upload_bytes()
    if uploaded_file.size > limit:
        mb = limit // (1024 * 1024)
        return f'File size exceeds {mb}MB limit.'
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        return 'Invalid file type.'
    return None
