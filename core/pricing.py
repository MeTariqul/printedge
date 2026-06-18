"""
Print-Edge — Pricing Engine (per-file + custom page ranges)
"""
import math
from decimal import Decimal

from .models import AddonService, Service, ServiceVariant

DEFAULT_A4_PRICES = {
    ('bw', 'single'): Decimal('2.00'),
    ('bw', 'double'): Decimal('3.00'),
    ('color', 'single'): Decimal('5.00'),
    ('color', 'double'): Decimal('8.00'),
}

BASE_PRICES = {
    (print_type, sides, 'A4'): price
    for (print_type, sides), price in DEFAULT_A4_PRICES.items()
}

BULK_DISCOUNTS = [
    (200, Decimal('15')),
    (100, Decimal('10')),
    (50, Decimal('5')),
]


def calculate_billable_units(pages, sides):
    """Single-sided: pages; double-sided: sheets = ceil(pages / 2)."""
    pages = max(1, int(pages))
    if sides == 'double':
        return math.ceil(pages / 2)
    return pages


def get_base_price(print_type, sides, paper_size='A4'):
    """Fetch price from ServiceVariant; fallback to default A4 constants when no matching variant exists."""
    paper_size = paper_size or 'A4'
    try:
        variant = ServiceVariant.objects.select_related('service').get(
            specs__print_type=print_type,
            specs__sides=sides,
            specs__paper_size=paper_size,
            is_active=True,
        )
        return variant.effective_price
    except ServiceVariant.DoesNotExist:
        return BASE_PRICES.get((print_type, sides, paper_size), Decimal('2.00'))


def reset_a4_pricing_defaults():
    """Restore A4 pricing variants to business defaults (2, 3, 5, 8)."""
    names = {
        ('bw', 'single'): 'B&W Single Side A4',
        ('bw', 'double'): 'B&W Double Side A4',
        ('color', 'single'): 'Color Single Side A4',
        ('color', 'double'): 'Color Double Side A4',
    }
    service, _ = Service.objects.get_or_create(
        name='Default Printing',
        defaults={
            'category': 'printing',
            'base_price': Decimal('0'),
            'requires_file': True,
        },
    )
    for (print_type, sides), price in DEFAULT_A4_PRICES.items():
        ServiceVariant.objects.update_or_create(
            service=service,
            name=names[(print_type, sides)],
            defaults={
                'price': price,
                'specs': {
                    'print_type': print_type,
                    'sides': sides,
                    'paper_size': 'A4',
                },
                'stock': 9999,
                'low_stock_threshold': 100,
                'is_active': True,
            },
        )


def calculate_bulk_discount_percent(total_pages):
    for threshold, pct in BULK_DISCOUNTS:
        if total_pages >= threshold:
            return pct
    return Decimal('0')


def validate_page_ranges(total_pages, ranges):
    """
    ranges: list of dicts with start_page, end_page.
    Returns (ok, error_message).
    """
    if not ranges:
        return True, ''
    normalized = []
    for r in ranges:
        start = int(r.get('start_page', 0))
        end = int(r.get('end_page', 0))
        if start < 1 or end < 1 or start > end:
            return False, 'Invalid page range.'
        if end > total_pages:
            return False, f'Range {start}-{end} exceeds document page count ({total_pages}).'
        normalized.append((start, end))
    normalized.sort(key=lambda x: x[0])
    for i in range(1, len(normalized)):
        if normalized[i][0] <= normalized[i - 1][1]:
            return False, 'Page ranges cannot overlap.'
    return True, ''


def calculate_file_base_price(
    total_pages,
    print_type,
    sides,
    paper_size,
    copies,
    ranges=None,
):
    """
    Price one file: custom ranges + default settings for uncovered pages, × copies.
    Double-sided pricing uses billable sheets = ceil(page_count / 2).
    """
    total_pages = max(1, int(total_pages))
    copies = max(1, int(copies))
    paper_size = paper_size or 'A4'
    ranges = ranges or []

    ok, err = validate_page_ranges(total_pages, ranges)
    if not ok:
        raise ValueError(err)

    covered = set()
    subtotal = Decimal('0')

    for r in ranges:
        start = int(r['start_page'])
        end = int(r['end_page'])
        r_type = r.get('print_type', print_type)
        r_sides = r.get('sides', sides)
        rate = get_base_price(r_type, r_sides, paper_size)
        count = end - start + 1
        units = calculate_billable_units(count, r_sides)
        subtotal += rate * units
        covered.update(range(start, end + 1))

    uncovered = total_pages - len(covered)
    if uncovered > 0:
        rate = get_base_price(print_type, sides, paper_size)
        units = calculate_billable_units(uncovered, sides)
        subtotal += rate * units

    return (subtotal * copies).quantize(Decimal('0.01'))


def calculate_order_from_files(
    file_specs,
    addon_ids=None,
    variant_ids=None,
    is_urgent=False,
    coupon_obj=None,
    manual_discount=Decimal('0'),
    tier_discount_pct=Decimal('0'),
    urgent_percent=50,
):
    """
    file_specs: list of dicts with keys:
      pages, print_type, sides, paper_size, copies, ranges (optional)
    """
    file_lines = []
    base_price = Decimal('0')
    total_billable_pages = 0

    for spec in file_specs:
        pages = max(1, int(spec.get('pages', 1)))
        copies = max(1, int(spec.get('copies', 1)))
        print_type = spec.get('print_type', 'bw')
        sides = spec.get('sides', 'single')
        paper_size = spec.get('paper_size', 'A4')
        ranges = spec.get('ranges') or []

        line_price = calculate_file_base_price(
            pages, print_type, sides, paper_size, copies, ranges=ranges,
        )
        billable = pages * copies
        total_billable_pages += billable
        base_price += line_price
        file_lines.append({
            'file_name': spec.get('file_name', 'Document'),
            'pages': pages,
            'copies': copies,
            'print_type': print_type,
            'sides': sides,
            'paper_size': paper_size,
            'line_price': line_price,
            'ranges': ranges,
        })

    bulk_pct = calculate_bulk_discount_percent(total_billable_pages)
    effective_discount_pct = max(bulk_pct, Decimal(str(tier_discount_pct)))
    auto_discount = (base_price * effective_discount_pct / 100).quantize(Decimal('0.01'))

    addons_price = Decimal('0')
    addon_names = []
    if addon_ids:
        addons = AddonService.objects.filter(id__in=addon_ids, is_active=True)
        for addon in addons:
            addons_price += addon.price
            addon_names.append(addon.name)

    if variant_ids:
        from .models import ServiceVariant
        variants = ServiceVariant.objects.filter(id__in=variant_ids, is_active=True).select_related('service')
        for variant in variants:
            addons_price += variant.effective_price
            addon_names.append(f"{variant.service.name} - {variant.name}")

    urgent_surcharge = Decimal('0')
    if is_urgent:
        pct = Decimal(str(urgent_percent))
        urgent_surcharge = (base_price * pct / 100).quantize(Decimal('0.01'))

    subtotal = base_price + addons_price + urgent_surcharge

    promo_discount = Decimal('0')
    if coupon_obj and coupon_obj.is_valid:
        if coupon_obj.discount_type == 'percentage':
            promo_discount = (subtotal * coupon_obj.discount_value / 100).quantize(Decimal('0.01'))
        else:
            promo_discount = coupon_obj.discount_value

    total_discount = auto_discount + promo_discount + manual_discount
    total = max(subtotal - total_discount, Decimal('0'))

    return {
        'file_lines': file_lines,
        'base_price': base_price,
        'total_pages': total_billable_pages,
        'bulk_discount_pct': bulk_pct,
        'tier_discount_pct': tier_discount_pct,
        'auto_discount': auto_discount,
        'addons_price': addons_price,
        'addon_names': addon_names,
        'urgent_surcharge': urgent_surcharge,
        'promo_discount': promo_discount,
        'manual_discount': manual_discount,
        'total_discount': total_discount,
        'total': total,
    }


def calculate_order_price(
    print_type, sides, paper_size='A4',
    pages=1, copies=1, addon_ids=None,
    is_urgent=False, coupon_obj=None,
    manual_discount=Decimal('0'), tier_discount_pct=Decimal('0'),
    urgent_percent=50,
):
    """Legacy single-file API — wraps calculate_order_from_files."""
    return calculate_order_from_files(
        [{
            'pages': pages,
            'copies': copies,
            'print_type': print_type,
            'sides': sides,
            'paper_size': paper_size,
            'ranges': [],
        }],
        addon_ids=addon_ids,
        is_urgent=is_urgent,
        coupon_obj=coupon_obj,
        manual_discount=manual_discount,
        tier_discount_pct=tier_discount_pct,
        urgent_percent=urgent_percent,
    )
