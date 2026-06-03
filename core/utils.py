import os
import re
import uuid

ALLOWED_UPLOAD_EXTENSIONS = ('.pdf', '.doc', '.docx', '.ppt', '.pptx', '.jpg', '.jpeg', '.png', '.zip')
DANGEROUS_EXTENSIONS = (
    '.exe', '.bat', '.cmd', '.com', '.msi', '.scr', '.vbs', '.js', '.jar',
    '.php', '.phtml', '.php3', '.php4', '.php5', '.asp', '.aspx', '.jsp', '.sh', '.py', '.rb',
)
MAX_UPLOAD_BYTES = 50 * 1024 * 1024

# Magic-byte signatures for common upload types (first bytes)
_MAGIC_SIGNATURES = (
    (b'%PDF', ('.pdf',)),
    (b'\xd0\xcf\x11\xe0', ('.doc', '.ppt')),  # OLE compound (legacy DOC/PPT)
    (b'PK\x03\x04', ('.docx', '.pptx')),  # ZIP-based Office Open XML
    (b'\xff\xd8\xff', ('.jpg', '.jpeg')),
    (b'\x89PNG\r\n\x1a\n', ('.png',)),
)


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


def _read_file_header(uploaded_file, length=16):
    pos = uploaded_file.tell()
    try:
        uploaded_file.seek(0)
        return uploaded_file.read(length)
    finally:
        uploaded_file.seek(pos)


def _magic_matches_extension(header, ext):
    if not header:
        return False
    for magic, extensions in _MAGIC_SIGNATURES:
        if header.startswith(magic) and ext in extensions:
            return True
    return False


def _filename_parts(name):
    """Return lowercase extension segments from a basename (no path)."""
    base = os.path.basename(name or '')
    if '\x00' in base:
        return None
    parts = [p.lower() for p in re.findall(r'\.[^.]+', base)]
    return parts


def secure_storage_name(original_name):
    """Randomized storage filename preserving allowed extension."""
    base = os.path.basename(original_name or 'file')
    ext = os.path.splitext(base)[1].lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        ext = '.pdf'
    return f'{uuid.uuid4().hex}{ext}'


def validate_upload_file(uploaded_file):
    """Return error message string, or None if valid."""
    if not uploaded_file:
        return 'Please upload a document file.'
    raw_name = getattr(uploaded_file, 'name', '') or ''
    if '\x00' in raw_name:
        return 'Invalid file name.'
    parts = _filename_parts(raw_name)
    if parts is None:
        return 'Invalid file name.'
    if not parts:
        return 'Invalid file type.'
    if any(p in DANGEROUS_EXTENSIONS for p in parts):
        return 'Invalid file type.'
    ext = parts[-1]
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        return 'Invalid file type.'
    if len(parts) > 1 and parts[-2] in DANGEROUS_EXTENSIONS:
        return 'Invalid file type.'
    limit = max_upload_bytes()
    if uploaded_file.size > limit:
        mb = limit // (1024 * 1024)
        return f'File size exceeds {mb}MB limit.'
    header = _read_file_header(uploaded_file)
    if not _magic_matches_extension(header, ext):
        return 'File content does not match its type. Please upload a valid document.'
    return None


def validate_payment_screenshot(uploaded_file):
    """Validate payment screenshot - must be jpg/png under 5MB."""
    if not uploaded_file:
        return 'Please upload a payment screenshot.'
    raw_name = getattr(uploaded_file, 'name', '') or ''
    if '\x00' in raw_name:
        return 'Invalid file name.'
    parts = _filename_parts(raw_name)
    if parts is None:
        return 'Invalid file name.'
    ext = parts[-1] if parts else ''
    if ext not in ('.jpg', '.jpeg', '.png'):
        return 'Only JPG and PNG files are allowed for payment screenshots.'
    limit = 5 * 1024 * 1024  # 5MB
    if uploaded_file.size > limit:
        return 'Payment screenshot must be under 5MB.'
    header = _read_file_header(uploaded_file)
    if ext in ('.jpg', '.jpeg') and not _magic_matches_extension(header, ext):
        return 'Invalid image file. Please upload a valid screenshot.'
    if ext == '.png' and not header.startswith(b'\x89PNG'):
        return 'Invalid image file. Please upload a valid screenshot.'
    return None
