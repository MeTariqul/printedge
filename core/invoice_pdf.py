"""Generate order confirmation invoice PDFs using ReportLab (pure Python, no system dependencies)."""

import io
import requests

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image

from .models import SiteSettings, OrderFile


def _fetch_qr_image(url):
    """Fetch QR code image and return as BytesIO."""
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return io.BytesIO(resp.content)
    except Exception:
        pass
    return None


def _format_ranges(order_file):
    """Format custom page ranges for display."""
    ranges = order_file.page_ranges.all()
    if not ranges:
        return "—"
    parts = []
    for r in ranges:
        parts.append(f"{r.start_page}-{r.end_page} {r.get_print_type_display()} {r.get_sides_display()}")
    return ", ".join(parts)


def generate_order_invoice_pdf(order):
    """Return PDF bytes for an order confirmation invoice using ReportLab."""
    site = SiteSettings.get()

    # Build file lines for invoice
    file_lines = []
    order_files = list(order.order_files.all())

    if not order_files and order.file_name:
        file_lines.append({
            'file_name': order.file_name,
            'pages': order.pages,
            'print_type': order.get_print_type_display(),
            'sides': order.get_sides_display(),
            'paper_size': order.paper_size,
            'ranges': "—",
            'copies': order.copies,
            'unit_price': float(order.base_price / order.copies) if order.copies else 0,
            'line_price': float(order.base_price),
        })
    else:
        for of in order_files:
            try:
                effective_pages = of.effective_pages or of.pages
            except Exception:
                effective_pages = of.pages
            file_lines.append({
                'file_name': of.file_name,
                'pages': effective_pages,
                'print_type': of.get_print_type_display(),
                'sides': of.get_sides_display(),
                'paper_size': of.paper_size,
                'ranges': _format_ranges(of),
                'copies': of.copies,
                'unit_price': float(of.unit_price) if hasattr(of, 'unit_price') else float(of.line_base_price / of.copies) if of.copies else 0,
                'line_price': float(of.line_base_price),
            })

    invoice_number = f"INV-{order.created_at.strftime('%Y%m%d')}-{order.id:04d}"
    invoice_date = order.created_at.strftime('%d %b %Y')
    addons_lines = ", ".join(a.name for a in order.addons.all())
    discount_reason = ""
    if order.discount_amount:
        if order.coupon:
            discount_reason = f"Promo: {order.coupon.code}"
        else:
            discount_reason = "Tier discount"

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm,
    )
    elements = []

    styles = getSampleStyleSheet()

    # Dark header strip
    header_data = [
        ['PrintEdge', f'INVOICE #{invoice_number}', invoice_date],
    ]
    header_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A5F')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, 0), 8),
        ('RIGHTPADDING', (0, 0), (-1, 0), 8),
    ])
    header_table = Table(header_data, colWidths=[60*mm, 80*mm, 40*mm])
    header_table.setStyle(header_style)
    elements.append(header_table)

    # Customer info section
    customer_email = order.customer.email if order.customer else ''
    customer_data = [
        ['Bill To', 'Invoice Details'],
        ['Name:', order.customer_name],
        ['Email:', customer_email or '—'],
        ['Phone:', order.customer_phone or '—'],
    ]
    customer_table = Table(customer_data, colWidths=[30*mm, 80*mm])
    customer_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1E3A5F')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(Spacer(1, 4))
    elements.append(customer_table)

    # Files table header
    elements.append(Spacer(1, 8))
    file_header = Table([
        ['#', 'File / Service', 'Pages', 'Settings', 'Copies', 'Unit Price', 'Subtotal']
    ], colWidths=[8, 50*mm, 15, 30, 15, 20, 20])
    file_header.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A5F')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ]))
    elements.append(file_header)

    # File rows
    file_data = []
    for i, line in enumerate(file_lines, 1):
        file_data.append([
            str(i),
            line['file_name'],
            str(line['pages']),
            f"{line['print_type']} / {line['sides']}",
            str(line['copies']),
            f"৳{line['unit_price']:.2f}",
            f"৳{line['line_price']:.2f}",
        ])

    file_table = Table(file_data, colWidths=[8, 50*mm, 15, 30, 15, 20, 20])
    file_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F5F7FA')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
    ]))
    elements.append(file_table)

    # Totals
    elements.append(Spacer(1, 8))
    totals_data = [
        ['', 'Subtotal', f"৳{order.base_price:.2f}"],
    ]
    if order.addons_price:
        totals_data.append(['', f'Add-ons ({addons_lines})', f"৳{order.addons_price:.2f}"])
    if order.urgent_surcharge:
        totals_data.append(['', f'Urgent (+{site.urgent_surcharge_percent}%)', f"৳{order.urgent_surcharge:.2f}"])
    if order.discount_amount:
        totals_data.append(['', f'Discount ({discount_reason})', f"-৳{order.discount_amount:.2f}"])
    totals_data.append(['', 'GRAND TOTAL', f"৳{order.total_amount:.2f}"])

    totals_table = Table(totals_data, colWidths=[100, 40, 20])
    totals_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTNAME', (1, 0), (-1, -1), 'Helvetica'),
        ('FONTNAME', (1, -1), (-1, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (1, -1), (-1, -1), colors.HexColor('#06b6d4')),
        ('LINEBELOW', (1, -2), (-1, -1), 1, colors.HexColor('#06b6d4')),
        ('RIGHTPADDING', (1, 0), (-1, -1), 4),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
    ]))
    elements.append(totals_table)

    # Payment instructions
    elements.append(Spacer(1, 12))
    payment_note = Paragraph(
        '<b>Payment Instructions</b><br/>'
        'Please send the exact amount to one of the following numbers:',
        ParagraphStyle('Payment', parent=styles['Normal'], fontSize=9, leading=12)
    )
    elements.append(payment_note)

    payment_data = []
    if site.bkash_number:
        payment_data.append(['bKash:', site.bkash_number])
    if site.nagad_number:
        payment_data.append(['Nagad:', site.nagad_number])
    if site.rocket_number:
        payment_data.append(['Rocket:', site.rocket_number])

    if payment_data:
        payment_table = Table(payment_data, colWidths=[25, 50])
        payment_table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#1E3A5F')),
        ]))
        elements.append(Spacer(1, 4))
        elements.append(payment_table)

    # QR code for order tracking
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=100x100&data=https://printedge.vercel.app/user/orders/{order.pk}/"
    qr_img = _fetch_qr_image(qr_url)
    if qr_img:
        elements.append(Spacer(1, 12))
        qr_table = Table([
            [Paragraph('Scan to track order status:', ParagraphStyle('QRNote', parent=styles['Normal'], fontSize=8)),
             Image(qr_img, width=25, height=25)]
        ], colWidths=[80, 25])
        qr_table.setStyle(TableStyle([
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('VALIGN', (0, 0), (0, 0), 'MIDDLE'),
        ]))
        elements.append(qr_table)

    # Footer
    elements.append(Spacer(1, 16))
    footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#1E3A5F'), alignment=1)
    elements.append(Paragraph('Thank you for choosing PrintEdge!', footer_style))
    elements.append(Paragraph('printedge.vercel.app • Computer-generated invoice', 
                            ParagraphStyle('Small', parent=styles['Normal'], fontSize=7, textColor=colors.HexColor('#64748b'), alignment=1)))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()