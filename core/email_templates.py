"""Default email templates for Print-Edge."""

from core.models import EmailTemplate

EMAIL_TEMPLATES = {
    'verify_email': {
        'subject': 'Verify your email - Print-Edge',
        'body': '''<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#111827;font-family:Arial,sans-serif;color:#e5e7eb;">
<div style="max-width:600px;margin:0 auto;background:#1f2937;border-radius:8px;overflow:hidden;">
    <div style="background:#0ea5e9;padding:24px;text-align:center;">
        <h1 style="margin:0;color:#fff;font-size:24px;font-weight:bold;">Print-Edge</h1>
    </div>
    <div style="padding:24px;">
        <h2 style="margin:0 0 16px 0;color:#fff;font-size:20px;">Verify your email address</h2>
        <p style="margin:0 0 16px 0;line-height:1.6;">Hi {{ user.first_name|default:"there" }}, thanks for signing up!</p>
        <p style="margin:0 0 16px 0;line-height:1.6;">Please click the button below to verify your email address:</p>
        <div style="text-align:center;margin:24px 0;">
            <a href="{{ verification_url }}" style="display:inline-block;background:#0ea5e9;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:bold;">Verify Email</a>
        </div>
        <p style="margin:0 0 16px 0;line-height:1.6;font-size:12px;color:#9ca3af;">This link expires in 24 hours.</p>
    </div>
    <div style="background:#111827;padding:16px 24px;text-align:center;font-size:12px;color:#6b7280;">
        <p style="margin:0;">Print-Edge - Your Campus Print Shop</p>
    </div>
</div>
</body>
</html>'''
    },
    'order_confirmation': {
        'subject': 'Order #{{ order.order_number }} Confirmed - Print-Edge',
        'body': '''<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#111827;font-family:Arial,sans-serif;color:#e5e7eb;">
<div style="max-width:600px;margin:0 auto;background:#1f2937;border-radius:8px;overflow:hidden;">
    <div style="background:#0ea5e9;padding:24px;">
        <h1 style="margin:0;color:#fff;font-size:24px;font-weight:bold;">Print-Edge</h1>
    </div>
    <div style="padding:24px;">
        <h2 style="margin:0 0 16px 0;color:#fff;font-size:20px;">Order Confirmed</h2>
        <p style="margin:0 0 16px 0;line-height:1.6;">Hi {{ order.customer_name }}, your order has been received!</p>
        <div style="background:#111827;padding:16px;border-radius:6px;margin:16px 0;">
            <p style="margin:4px 0;"><strong>Order #:</strong> {{ order.order_number }}</p>
            <p style="margin:4px 0;"><strong>Total:</strong> ৳{{ order.total_amount|floatformat:0 }}</p>
            <p style="margin:4px 0;"><strong>Status:</strong> {{ order.get_status_display }}</p>
        </div>
        <div style="text-align:center;margin:24px 0;">
            <a href="{{ tracking_url }}" style="display:inline-block;background:#0ea5e9;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:bold;">Track Order</a>
        </div>
    </div>
    <div style="background:#111827;padding:16px 24px;text-align:center;font-size:12px;color:#6b7280;">
        <p style="margin:0;">Print-Edge - Your Campus Print Shop</p>
    </div>
</div>
</body>
</html>'''
    },
    'payment_approved': {
        'subject': 'Payment Approved - Order #{{ order.order_number }}',
        'body': '''<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#111827;font-family:Arial,sans-serif;color:#e5e7eb;">
<div style="max-width:600px;margin:0 auto;background:#1f2937;border-radius:8px;overflow:hidden;">
    <div style="background:#10b981;padding:24px;">
        <h1 style="margin:0;color:#fff;font-size:24px;font-weight:bold;">Print-Edge</h1>
    </div>
    <div style="padding:24px;">
        <h2 style="margin:0 0 16px 0;color:#fff;font-size:20px;">Payment Approved ✓</h2>
        <p style="margin:0 0 16px 0;line-height:1.6;">Your payment for order #{{ order.order_number }} has been approved.</p>
        <div style="background:#111827;padding:16px;border-radius:6px;margin:16px 0;">
            <p style="margin:4px 0;"><strong>Order #:</strong> {{ order.order_number }}</p>
            <p style="margin:4px 0;"><strong>Amount Paid:</strong> ৳{{ order.amount_paid|floatformat:0 }}</p>
        </div>
    </div>
    <div style="background:#111827;padding:16px 24px;text-align:center;font-size:12px;color:#6b7280;">
        <p style="margin:0;">Print-Edge - Your Campus Print Shop</p>
    </div>
</div>
</body>
</html>'''
    },
    'payment_rejected': {
        'subject': 'Payment Rejected - Order #{{ order.order_number }}',
        'body': '''<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#111827;font-family:Arial,sans-serif;color:#e5e7eb;">
<div style="max-width:600px;margin:0 auto;background:#1f2937;border-radius:8px;overflow:hidden;">
    <div style="background:#ef4444;padding:24px;">
        <h1 style="margin:0;color:#fff;font-size:24px;font-weight:bold;">Print-Edge</h1>
    </div>
    <div style="padding:24px;">
        <h2 style="margin:0 0 16px 0;color:#fff;font-size:20px;">Payment Rejected</h2>
        <p style="margin:0 0 16px 0;line-height:1.6;">Your payment for order #{{ order.order_number }} was rejected.</p>
        <div style="background:#111827;padding:16px;border-radius:6px;margin:16px 0;">
            <p style="margin:4px 0;"><strong>Reason:</strong> {{ order.payment_rejection_reason|default:"Please contact support." }}</p>
        </div>
        <div style="text-align:center;margin:24px 0;">
            <a href="{{ tracking_url }}" style="display:inline-block;background:#0ea5e9;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:bold;">View Order</a>
        </div>
    </div>
    <div style="background:#111827;padding:16px 24px;text-align:center;font-size:12px;color:#6b7280;">
        <p style="margin:0;">Print-Edge - Your Campus Print Shop</p>
    </div>
</div>
</body>
</html>'''
    },
    'order_status_update': {
        'subject': 'Order #{{ order.order_number }} Status Update',
        'body': '''<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#111827;font-family:Arial,sans-serif;color:#e5e7eb;">
<div style="max-width:600px;margin:0 auto;background:#1f2937;border-radius:8px;overflow:hidden;">
    <div style="background:#0ea5e9;padding:24px;">
        <h1 style="margin:0;color:#fff;font-size:24px;font-weight:bold;">Print-Edge</h1>
    </div>
    <div style="padding:24px;">
        <h2 style="margin:0 0 16px 0;color:#fff;font-size:20px;">Order Status Updated</h2>
        <p style="margin:0 0 16px 0;line-height:1.6;">Your order #{{ order.order_number }} is now {{ order.get_status_display|lower }}.</p>
        <div style="background:#111827;padding:16px;border-radius:6px;margin:16px 0;">
            <p style="margin:4px 0;"><strong>Current Status:</strong> {{ order.get_status_display }}</p>
            <p style="margin:4px 0;"><strong>Total:</strong> ৳{{ order.total_amount|floatformat:0 }}</p>
        </div>
    </div>
    <div style="background:#111827;padding:16px 24px;text-align:center;font-size:12px;color:#6b7280;">
        <p style="margin:0;">Print-Edge - Your Campus Print Shop</p>
    </div>
</div>
</body>
</html>'''
    },
}

def seed_default_email_templates():
    """Create default email templates if they don't exist."""
    for name, data in EMAIL_TEMPLATES.items():
        EmailTemplate.objects.get_or_create(
            name=name,
            defaults={'subject': data['subject'], 'html_body': data['body']}
        )