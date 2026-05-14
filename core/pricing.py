"""
Print-Edge — Pricing Engine
"""
from decimal import Decimal
from .models import PricingRule, AddonService


BASE_PRICES = {
    ('bw', 'single', 'A4'): Decimal('2.00'),
    ('bw', 'double', 'A4'): Decimal('3.00'),
    ('color', 'single', 'A4'): Decimal('5.00'),
    ('color', 'double', 'A4'): Decimal('7.00'),
    ('bw', 'single', 'A3'): Decimal('4.00'),
    ('bw', 'double', 'A3'): Decimal('6.00'),
    ('color', 'single', 'A3'): Decimal('10.00'),
    ('color', 'double', 'A3'): Decimal('14.00'),
}

BULK_DISCOUNTS = [
    (200, Decimal('15')),
    (100, Decimal('10')),
    (50, Decimal('5')),
]


def get_base_price(print_type, sides, paper_size='A4'):
    """Try DB first, fall back to hardcoded defaults."""
    try:
        rule = PricingRule.objects.get(
            print_type=print_type, sides=sides,
            paper_size=paper_size, is_active=True
        )
        return rule.price_per_page
    except PricingRule.DoesNotExist:
        return BASE_PRICES.get((print_type, sides, paper_size), Decimal('2.00'))


def calculate_bulk_discount_percent(total_pages):
    for threshold, pct in BULK_DISCOUNTS:
        if total_pages >= threshold:
            return pct
    return Decimal('0')


def calculate_order_price(
    print_type, sides, paper_size='A4',
    pages=1, copies=1, addon_ids=None,
    is_urgent=False, promo_code_obj=None,
    manual_discount=Decimal('0'), tier_discount_pct=Decimal('0')
):
    """
    Returns a detailed price breakdown dict.
    """
    base_rate = get_base_price(print_type, sides, paper_size)
    total_pages = pages * copies
    base_price = base_rate * total_pages

    # Bulk discount
    bulk_pct = calculate_bulk_discount_percent(total_pages)

    # Tier discount (best of bulk or tier)
    effective_discount_pct = max(bulk_pct, tier_discount_pct)
    auto_discount = (base_price * effective_discount_pct / 100).quantize(Decimal('0.01'))

    # Add-ons
    addons_price = Decimal('0')
    addon_names = []
    if addon_ids:
        addons = AddonService.objects.filter(id__in=addon_ids, is_active=True)
        for addon in addons:
            addons_price += addon.price
            addon_names.append(addon.name)

    # Urgent surcharge (50%)
    urgent_surcharge = Decimal('0')
    if is_urgent:
        urgent_surcharge = (base_price * Decimal('50') / 100).quantize(Decimal('0.01'))

    subtotal = base_price + addons_price + urgent_surcharge

    # Promo code
    promo_discount = Decimal('0')
    if promo_code_obj and promo_code_obj.is_valid:
        if promo_code_obj.discount_type == 'percent':
            promo_discount = (subtotal * promo_code_obj.discount_value / 100).quantize(Decimal('0.01'))
        else:
            promo_discount = promo_code_obj.discount_value

    total_discount = auto_discount + promo_discount + manual_discount
    total = max(subtotal - total_discount, Decimal('0'))

    return {
        'base_rate': base_rate,
        'total_pages': total_pages,
        'base_price': base_price,
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
