from django.db import migrations

def create_premium_templates(apps, schema_editor):
    EmailTemplate = apps.get_model('core', 'EmailTemplate')
    
    # 1. Order Confirmation
    EmailTemplate.objects.update_or_create(
        name='order_confirmation',
        defaults={
            'subject': 'Order #{{ order.order_number }} Confirmed – PrintEdge',
            'html_body': '''<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #f1f5f9; margin: 0; padding: 20px; }
        .container { max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }
        .header { background-color: #0f172a; padding: 30px 20px; text-align: center; }
        .header h1 { color: #ffffff; margin: 0; font-size: 24px; font-weight: 700; letter-spacing: 1px; }
        .content { padding: 30px; color: #334155; line-height: 1.6; }
        .content h2 { color: #0f172a; margin-top: 0; }
        .btn { display: inline-block; background-color: #3b82f6; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: 600; margin-top: 20px; }
        .footer { background-color: #1e293b; padding: 20px; text-align: center; color: #94a3b8; font-size: 14px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>PRINT-EDGE</h1>
        </div>
        <div class="content">
            <h2>Order Confirmed!</h2>
            <p>Hi {{ order.customer.first_name|default:"Customer" }},</p>
            <p>We've received your order <strong>#{{ order.order_number }}</strong>. We are currently reviewing it and will begin processing shortly.</p>
            <p>You can track the status of your order or view your online invoice by clicking the button below:</p>
            <a href="{{ tracking_url }}" class="btn" style="color:white !important;">View Order & Invoice</a>
        </div>
        <div class="footer">
            &copy; {{ now.year }} Print-Edge. All rights reserved.
        </div>
    </div>
</body>
</html>'''
        }
    )

    # 2. Email Verification
    EmailTemplate.objects.update_or_create(
        name='verify_email',
        defaults={
            'subject': 'Verify your email – PrintEdge',
            'html_body': '''<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #f1f5f9; margin: 0; padding: 20px; }
        .container { max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }
        .header { background-color: #0f172a; padding: 30px 20px; text-align: center; }
        .header h1 { color: #ffffff; margin: 0; font-size: 24px; font-weight: 700; letter-spacing: 1px; }
        .content { padding: 30px; color: #334155; line-height: 1.6; }
        .content h2 { color: #0f172a; margin-top: 0; }
        .btn { display: inline-block; background-color: #3b82f6; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: 600; margin-top: 20px; }
        .footer { background-color: #1e293b; padding: 20px; text-align: center; color: #94a3b8; font-size: 14px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>PRINT-EDGE</h1>
        </div>
        <div class="content">
            <h2>Welcome to Print-Edge!</h2>
            <p>Hi {{ user.first_name|default:"there" }},</p>
            <p>Thank you for creating an account. Please verify your email address to complete your registration and start ordering.</p>
            <a href="{{ verification_url }}" class="btn" style="color:white !important;">Verify Email Address</a>
        </div>
        <div class="footer">
            &copy; {{ now.year }} Print-Edge. All rights reserved.
        </div>
    </div>
</body>
</html>'''
        }
    )

    # 3. Order Update
    EmailTemplate.objects.update_or_create(
        name='order_update',
        defaults={
            'subject': 'Order #{{ order.order_number }} Status Update – PrintEdge',
            'html_body': '''<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #f1f5f9; margin: 0; padding: 20px; }
        .container { max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }
        .header { background-color: #0f172a; padding: 30px 20px; text-align: center; }
        .header h1 { color: #ffffff; margin: 0; font-size: 24px; font-weight: 700; letter-spacing: 1px; }
        .content { padding: 30px; color: #334155; line-height: 1.6; }
        .content h2 { color: #0f172a; margin-top: 0; }
        .status-box { background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 15px; border-radius: 8px; margin: 20px 0; font-weight: 600; text-transform: uppercase; color: #3b82f6; text-align: center; font-size: 18px; }
        .btn { display: inline-block; background-color: #3b82f6; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: 600; margin-top: 20px; }
        .footer { background-color: #1e293b; padding: 20px; text-align: center; color: #94a3b8; font-size: 14px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>PRINT-EDGE</h1>
        </div>
        <div class="content">
            <h2>Order Status Update</h2>
            <p>Hi {{ order.customer.first_name|default:"Customer" }},</p>
            <p>Your order <strong>#{{ order.order_number }}</strong> has a new status update:</p>
            
            <div class="status-box">
                {{ order.get_status_display }}
            </div>
            
            <p>To view full details or download your invoice, click below:</p>
            <a href="{{ tracking_url }}" class="btn" style="color:white !important;">View Order Details</a>
        </div>
        <div class="footer">
            &copy; {{ now.year }} Print-Edge. All rights reserved.
        </div>
    </div>
</body>
</html>'''
        }
    )

def reverse_templates(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0026_coupon_remove_order_promo_code_and_more'),
    ]

    operations = [
        migrations.RunPython(create_premium_templates, reverse_templates),
    ]
