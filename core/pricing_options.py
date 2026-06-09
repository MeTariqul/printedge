"""Build active pricing options for order forms."""

from .models import ServiceVariant

DEFAULT_PAPER_SIZES = ['A4']
DEFAULT_PRINT_TYPES = [('bw', 'Black & White'), ('color', 'Color')]
DEFAULT_SIDES = [('single', 'Single Sided'), ('double', 'Double Sided')]


def get_active_pricing_options():
    """Return dict of active print options from ServiceVariant rows (A4 only)."""
    variants = ServiceVariant.objects.filter(
        is_active=True,
    ).select_related('service')
    if not variants.exists():
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
    for v in variants:
        spec = v.specs or {}
        combinations.append({
            'print_type': spec.get('print_type', 'bw'),
            'sides': spec.get('sides', 'single'),
            'paper_size': spec.get('paper_size', 'A4'),
            'price_per_page': v.effective_price,
        })
        pt = spec.get('print_type', 'bw')
        sd = spec.get('sides', 'single')
        if pt not in seen_pt:
            seen_pt.add(pt)
            print_types.append((pt, dict(DEFAULT_PRINT_TYPES).get(pt, pt)))
        if sd not in seen_sides:
            seen_sides.add(sd)
            sides.append((sd, dict(DEFAULT_SIDES).get(sd, sd)))
    return {
        'paper_sizes': DEFAULT_PAPER_SIZES,
        'print_types': print_types or DEFAULT_PRINT_TYPES,
        'sides': sides or DEFAULT_SIDES,
        'combinations': combinations,
    }
