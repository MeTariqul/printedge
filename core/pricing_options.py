"""Build active pricing options for order forms."""

from .models import PricingRule

DEFAULT_PAPER_SIZES = ['A4']
DEFAULT_PRINT_TYPES = [('bw', 'Black & White'), ('color', 'Color')]
DEFAULT_SIDES = [('single', 'Single Sided'), ('double', 'Double Sided')]


def get_active_pricing_options():
    """Return dict of active print options from PricingRule rows (A4 only)."""
    rules = PricingRule.objects.filter(
        is_active=True, paper_size='A4',
    ).order_by('print_type', 'sides')
    if not rules.exists():
        return {
            'paper_sizes': DEFAULT_PAPER_SIZES,
            'print_types': DEFAULT_PRINT_TYPES,
            'sides': DEFAULT_SIDES,
            'combinations': [],
        }
    print_types = []
    sides = []
    seen_pt = set()
    seen_sides = set()
    combinations = []
    for r in rules:
        combinations.append({
            'print_type': r.print_type,
            'sides': r.sides,
            'paper_size': r.paper_size,
            'price_per_page': r.price_per_page,
        })
        if r.print_type not in seen_pt:
            seen_pt.add(r.print_type)
            print_types.append((r.print_type, r.get_print_type_display()))
        if r.sides not in seen_sides:
            seen_sides.add(r.sides)
            sides.append((r.sides, r.get_sides_display()))
    return {
        'paper_sizes': DEFAULT_PAPER_SIZES,
        'print_types': print_types or DEFAULT_PRINT_TYPES,
        'sides': sides or DEFAULT_SIDES,
        'combinations': combinations,
    }
