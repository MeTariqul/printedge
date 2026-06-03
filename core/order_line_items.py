"""Create and sync order line items (OrderFile + page ranges)."""
import json
from decimal import Decimal

from django.core.files.base import ContentFile
from django.db import transaction

from .models import Order, OrderFile, OrderFilePageRange
from .page_detection import detect_pages
from .pricing import calculate_order_from_files, calculate_file_base_price
from .utils import secure_storage_name


def parse_files_config(raw):
    """Parse files_config JSON from order form."""
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def detect_pages_for_upload(uploaded):
    if not uploaded:
        return 1
    result = detect_pages(uploaded)
    return max(1, int(result.get('pages', 1)))


def sync_order_summary_from_files(order):
    """Denormalize primary file settings onto Order for list views."""
    files = list(order.order_files.order_by('sort_order', 'pk'))
    if not files:
        return
    primary = next((f for f in files if f.is_primary), files[0])
    order.print_type = primary.print_type
    order.sides = primary.sides
    order.paper_size = primary.paper_size
    order.pages = primary.effective_pages
    order.copies = primary.copies
    total_pages = sum(f.effective_pages * f.copies for f in files)
    if primary.sides == 'double':
        order.total_sheets = sum(f.sheets_for_file() for f in files)
    else:
        order.total_sheets = total_pages


@transaction.atomic
def create_order_with_files(
    order_kwargs,
    uploaded_files,
    files_config,
    breakdown,
    addon_ids=None,
):
    """
    uploaded_files: list of (field_key, django_upload_or_contentfile, file_name)
    files_config: list aligned by index with print settings + ranges
    """
    order = Order.objects.create(**order_kwargs)
    if addon_ids:
        order.addons.set(addon_ids)

    for idx, (key, upload, name) in enumerate(uploaded_files):
        cfg = files_config[idx] if idx < len(files_config) else {}
        pages_detected = cfg.get('pages_detected') or detect_pages_for_upload(upload)
        pages_override = cfg.get('pages_override')
        if pages_override is not None:
            pages_override = int(pages_override) or None

        print_type = cfg.get('print_type', 'bw')
        sides = cfg.get('sides', 'single')
        paper_size = cfg.get('paper_size', 'A4')
        copies = max(1, int(cfg.get('copies', 1)))
        ranges = cfg.get('ranges') or []

        pages = int(pages_override) if pages_override else pages_detected
        line_price = calculate_file_base_price(
            pages, print_type, sides, paper_size, copies, ranges=ranges,
        )

        display_name = name or getattr(upload, 'name', f'file_{idx}')
        storage_name = secure_storage_name(display_name)
        if hasattr(upload, 'name'):
            upload.name = storage_name
        of = OrderFile(
            order=order,
            file=upload,
            file_name=display_name,
            file_type=cfg.get('file_type', ''),
            file_size_bytes=getattr(upload, 'size', None),
            print_type=print_type,
            sides=sides,
            paper_size=paper_size,
            pages_detected=pages_detected,
            pages_override=pages_override,
            copies=copies,
            line_base_price=line_price,
            is_primary=(idx == 0),
            sort_order=idx,
        )
        of.save()

        for r in ranges:
            OrderFilePageRange.objects.create(
                order_file=of,
                start_page=int(r['start_page']),
                end_page=int(r['end_page']),
                print_type=r.get('print_type', print_type),
                sides=r.get('sides', sides),
            )

        if idx == 0 and upload:
            order.file = upload
            order.file_name = of.file_name
            order.file_size_bytes = of.file_size_bytes
            order.file_type = of.file_type

    order.base_price = breakdown['base_price']
    order.addons_price = breakdown['addons_price']
    order.urgent_surcharge = breakdown['urgent_surcharge']
    order.discount_amount = breakdown['total_discount']
    order.total_amount = breakdown['total']
    sync_order_summary_from_files(order)
    order.save()
    return order
