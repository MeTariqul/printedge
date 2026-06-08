from decimal import Decimal
from .models import InventoryItem, InventoryLog, Order

def deduct_inventory_for_order(order, user):
    """
    Deducts inventory (paper, toner, etc.) when order starts printing.
    Creates InventoryLog entries for tracking.
    """
    # Check if we already deducted for this order to prevent double deduction
    # We can check if any InventoryLog exists for this order. We'll add an order field to InventoryLog later if needed, 
    # but for now we can use note field.
    note_prefix = f"Order #{order.order_number} usage"
    if InventoryLog.objects.filter(note__startswith=note_prefix).exists():
        return

    # Total sheets
    # A single order could have multiple files with different paper sizes, but usually we just track overall.
    # Let's deduct based on OrderFile if exists, otherwise Order
    paper_usage = {} # dict of paper_size -> sheets
    color_pages = 0
    bw_pages = 0

    if order.order_files.exists():
        for f in order.order_files.all():
            sheets = f.sheets_for_file()
            paper_usage[f.paper_size] = paper_usage.get(f.paper_size, 0) + sheets
            if f.print_type == 'color':
                color_pages += (f.effective_pages * f.copies)
            else:
                bw_pages += (f.effective_pages * f.copies)
    else:
        # Fallback to order level
        sheets = order.total_sheets
        size = order.paper_size or 'A4'
        paper_usage[size] = paper_usage.get(size, 0) + sheets
        if order.print_type == 'color':
            color_pages += (order.pages * order.copies)
        else:
            bw_pages += (order.pages * order.copies)

    # 1. Deduct Paper
    for size, sheets in paper_usage.items():
        if sheets <= 0: continue
        # Find paper inventory item (name containing size like 'A4' and category 'paper')
        paper_item = InventoryItem.objects.filter(category='paper', name__icontains=size).first()
        if paper_item:
            qty = Decimal(sheets)
            paper_item.current_stock -= qty
            paper_item.save(update_fields=['current_stock'])
            InventoryLog.objects.create(
                item=paper_item,
                action='usage',
                quantity=qty,
                note=f"{note_prefix} ({size})",
                performed_by=user
            )

    # 2. Deduct Toner (approximate usage per page)
    # We could assume 1 page = 1 unit of toner for simplicity, or 0.1, etc. Let's say unit is pages.
    if bw_pages > 0:
        bw_toner = InventoryItem.objects.filter(category='toner', name__icontains='Black').first() or \
                   InventoryItem.objects.filter(category='toner', name__icontains='B&W').first()
        if bw_toner:
            qty = Decimal(bw_pages)
            bw_toner.current_stock -= qty
            bw_toner.save(update_fields=['current_stock'])
            InventoryLog.objects.create(
                item=bw_toner,
                action='usage',
                quantity=qty,
                note=f"{note_prefix} (B&W Toner)",
                performed_by=user
            )
            
    if color_pages > 0:
        color_toner = InventoryItem.objects.filter(category='toner', name__icontains='Color').first()
        if color_toner:
            qty = Decimal(color_pages)
            color_toner.current_stock -= qty
            color_toner.save(update_fields=['current_stock'])
            InventoryLog.objects.create(
                item=color_toner,
                action='usage',
                quantity=qty,
                note=f"{note_prefix} (Color Toner)",
                performed_by=user
            )

