from django.db import migrations


def create_premium_email_templates(apps, schema_editor):
    EmailTemplate = apps.get_model('core', 'EmailTemplate')
    
    templates = [
        {
            'name': 'Verification Email',
            'subject': 'Verify your email – PrintEdge',
            'html_body': '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Email Verification - PrintEdge</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f8f9fa; font-family: Arial, Helvetica, sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width: 600px; margin: 0 auto; background-color: #ffffff;">
        <tr>
            <td align="center" style="background: linear-gradient(135deg, #1e293b, #111827); padding: 30px 20px;">
                <a href="https://printedge.vercel.app" style="text-decoration: none;">
                    <img src="https://printedge.vercel.app/static/icons/logo.png" alt="PrintEdge" width="120" style="display: block; margin: 0 auto;">
                </a>
                <h1 style="color: #ffffff; font-size: 24px; font-weight: 600; margin: 20px 0 0 0;">Verify Your Email</h1>
            </td>
        </tr>
        <tr>
            <td style="padding: 40px 30px 30px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                    <tr>
                        <td>
                            <p style="font-size: 16px; line-height: 1.6; color: #333333; margin: 0 0 16px;">Hello {{ user.first_name|default:user.email }},</p>
                            <p style="font-size: 16px; line-height: 1.6; color: #333333; margin: 0 0 24px;">
                                Welcome to PrintEdge! To complete your registration and start placing orders, please verify your email address.
                            </p>
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                                <tr>
                                    <td align="center" style="padding: 10px 0 30px;">
                                        <a href="{{ verification_url }}" style="display: inline-block; background: linear-gradient(135deg, #06b6d4, #0891b4); color: #ffffff; text-decoration: none; font-size: 16px; font-weight: 600; padding: 14px 32px; border-radius: 12px;">
                                            Verify My Email
                                        </a>
                                    </td>
                                </tr>
                            </table>
                            <p style="font-size: 14px; line-height: 1.6; color: #666666; margin: 0;">
                                This verification link will expire in 24 hours.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
        <tr>
            <td style="background-color: #111827; padding: 30px; text-align: center;">
                <p style="font-size: 14px; color: #94a3b8; margin: 0;">PrintEdge &copy; 2026</p>
                <p style="font-size: 12px; color: #64748b; margin: 0;">This is an automated message.</p>
            </td>
        </tr>
    </table>
</body>
</html>''',
        },
        {
            'name': 'Order Confirmation',
            'subject': 'Order #{{ order.order_number }} Confirmed – PrintEdge',
            'html_body': '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Order Confirmation - PrintEdge</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f8f9fa; font-family: Arial, Helvetica, sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width: 600px; margin: 0 auto; background-color: #ffffff;">
        <tr>
            <td align="center" style="background: linear-gradient(135deg, #1e293b, #111827); padding: 30px 20px;">
                <a href="https://printedge.vercel.app" style="text-decoration: none;">
                    <img src="https://printedge.vercel.app/static/icons/logo.png" alt="PrintEdge Logo" width="120" style="display: block; margin: 0 auto;">
                </a>
                <h1 style="color: #ffffff; font-size: 24px; font-weight: 600; margin: 20px 0 0 0;">Order Confirmation</h1>
            </td>
        </tr>
        <tr>
            <td style="padding: 40px 30px 30px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                    <tr>
                        <td>
                            <p style="font-size: 16px; line-height: 1.6; color: #333333; margin: 0 0 16px;">
                                Hello {{ order.customer.first_name|default:order.customer.email }},
                            </p>
                            <p style="font-size: 16px; line-height: 1.6; color: #333333; margin: 0 0 24px;">
                                Your order <strong>#{{ order.order_number }}</strong> has been confirmed.
                            </p>
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f1f5f9; border-radius: 12px; margin-bottom: 24px;">
                                <tr>
                                    <td style="padding: 20px;">
                                        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                                            <tr>
                                                <td style="padding: 8px 0; border-bottom: 1px solid #e2e8f0;">
                                                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                                                        <tr>
                                                            <td style="font-size: 14px; color: #64748b; width: 40%;">Total</td>
                                                            <td style="font-size: 18px; color: #06b6d4; font-weight: 700;">৳{{ order.total_amount|floatformat:0 }}</td>
                                                        </tr>
                                                    </table>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 8px 0;">
                                                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                                                        <tr>
                                                            <td style="font-size: 14px; color: #64748b; width: 40%;">Status</td>
                                                            <td style="font-size: 14px; color: #111827; font-weight: 500;">{{ order.get_payment_status_display }}</td>
                                                        </tr>
                                                    </table>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                                <tr>
                                    <td align="center">
                                        <a href="https://printedge.vercel.app/user/orders/{{ order.pk }}/" style="display: inline-block; background: linear-gradient(135deg, #06b6d4, #0891b4); color: #ffffff; text-decoration: none; font-size: 16px; font-weight: 600; padding: 14px 32px; border-radius: 12px;">
                                            Track Your Order
                                        </a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
        <tr>
            <td style="background-color: #111827; padding: 30px; text-align: center;">
                <p style="font-size: 14px; color: #94a3b8; margin: 0;">PrintEdge &copy; 2026</p>
                <p style="font-size: 12px; color: #64748b; margin: 0;">This is an automated message.</p>
            </td>
        </tr>
    </table>
</body>
</html>''',
        },
        {
            'name': 'Order Status Update',
            'subject': 'Your order #{{ order.order_number }} is now {{ order.get_status_display }}',
            'html_body': '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Order Status Update - PrintEdge</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f8f9fa; font-family: Arial, Helvetica, sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width: 600px; margin: 0 auto; background-color: #ffffff;">
        <tr>
            <td align="center" style="background: linear-gradient(135deg, #1e293b, #111827); padding: 30px 20px;">
                <a href="https://printedge.vercel.app" style="text-decoration: none;">
                    <img src="https://printedge.vercel.app/static/icons/logo.png" alt="PrintEdge Logo" width="120" style="display: block; margin: 0 auto;">
                </a>
                <h1 style="color: #ffffff; font-size: 24px; font-weight: 600; margin: 20px 0 0 0;">Order Update</h1>
            </td>
        </tr>
        <tr>
            <td style="padding: 40px 30px 30px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                    <tr>
                        <td>
                            <p style="font-size: 16px; line-height: 1.6; color: #333333; margin: 0 0 16px;">
                                Hello {{ order.customer.first_name|default:order.customer.email }},
                            </p>
                            <p style="font-size: 16px; line-height: 1.6; color: #333333; margin: 0 0 24px;">
                                Your order <strong>#{{ order.order_number }}</strong> status has been updated to <strong>{{ order.get_status_display }}</strong>.
                            </p>
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                                <tr>
                                    <td align="center">
                                        <a href="https://printedge.vercel.app/user/orders/{{ order.pk }}/" style="display: inline-block; background: linear-gradient(135deg, #06b6d4, #0891b4); color: #ffffff; text-decoration: none; font-size: 16px; font-weight: 600; padding: 14px 32px; border-radius: 12px;">
                                            View Order Details
                                        </a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
        <tr>
            <td style="background-color: #111827; padding: 30px; text-align: center;">
                <p style="font-size: 14px; color: #94a3b8; margin: 0;">PrintEdge &copy; 2026</p>
                <p style="font-size: 12px; color: #64748b; margin: 0;">This is an automated message.</p>
            </td>
        </tr>
    </table>
</body>
</html>''',
        },
        {
            'name': 'Payment Approved',
            'subject': 'Payment Approved for Order #{{ order.order_number }}',
            'html_body': '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Payment Approved - PrintEdge</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f8f9fa; font-family: Arial, Helvetica, sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width: 600px; margin: 0 auto; background-color: #ffffff;">
        <tr>
            <td align="center" style="background: linear-gradient(135deg, #1e293b, #111827); padding: 30px 20px;">
                <a href="https://printedge.vercel.app" style="text-decoration: none;">
                    <img src="https://printedge.vercel.app/static/icons/logo.png" alt="PrintEdge Logo" width="120" style="display: block; margin: 0 auto;">
                </a>
                <h1 style="color: #ffffff; font-size: 24px; font-weight: 600; margin: 20px 0 0 0;">Payment Approved</h1>
            </td>
        </tr>
        <tr>
            <td style="padding: 40px 30px 30px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                    <tr>
                        <td>
                            <p style="font-size: 16px; line-height: 1.6; color: #333333; margin: 0 0 16px;">
                                Hello {{ order.customer.first_name|default:order.customer.email }},
                            </p>
                            <p style="font-size: 16px; line-height: 1.6; color: #333333; margin: 0 0 24px;">
                                Your payment for order <strong>#{{ order.order_number }}</strong> has been approved.
                            </p>
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                                <tr>
                                    <td align="center">
                                        <a href="https://printedge.vercel.app/user/orders/{{ order.pk }}/" style="display: inline-block; background: linear-gradient(135deg, #10b981, #059669); color: #ffffff; text-decoration: none; font-size: 16px; font-weight: 600; padding: 14px 32px; border-radius: 12px;">
                                            Track Order
                                        </a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
        <tr>
            <td style="background-color: #111827; padding: 30px; text-align: center;">
                <p style="font-size: 14px; color: #94a3b8; margin: 0;">PrintEdge &copy; 2026</p>
                <p style="font-size: 12px; color: #64748b; margin: 0;">This is an automated message.</p>
            </td>
        </tr>
    </table>
</body>
</html>''',
        },
        {
            'name': 'Payment Rejected',
            'subject': 'Payment Issue – Order #{{ order.order_number }}',
            'html_body': '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Payment Rejected - PrintEdge</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f8f9fa; font-family: Arial, Helvetica, sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width: 600px; margin: 0 auto; background-color: #ffffff;">
        <tr>
            <td align="center" style="background: linear-gradient(135deg, #1e293b, #111827); padding: 30px 20px;">
                <a href="https://printedge.vercel.app" style="text-decoration: none;">
                    <img src="https://printedge.vercel.app/static/icons/logo.png" alt="PrintEdge Logo" width="120" style="display: block; margin: 0 auto;">
                </a>
                <h1 style="color: #ffffff; font-size: 24px; font-weight: 600; margin: 20px 0 0 0;">Payment Issue</h1>
            </td>
        </tr>
        <tr>
            <td style="padding: 40px 30px 30px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                    <tr>
                        <td>
                            <p style="font-size: 16px; line-height: 1.6; color: #333333; margin: 0 0 16px;">
                                Hello {{ order.customer.first_name|default:order.customer.email }},
                            </p>
                            <p style="font-size: 16px; line-height: 1.6; color: #333333; margin: 0 0 24px;">
                                We encountered an issue with your payment for order <strong>#{{ order.order_number }}</strong>.
                            </p>
                            <p style="font-size: 16px; line-height: 1.6; color: #333333; margin: 0 0 24px;">
                                <strong>Reason:</strong> {{ order.payment_rejection_reason|default:"Please contact us for details." }}
                            </p>
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                                <tr>
                                    <td align="center">
                                        <a href="https://printedge.vercel.app/user/orders/{{ order.pk }}/" style="display: inline-block; background: linear-gradient(135deg, #f97316, #fb923c); color: #ffffff; text-decoration: none; font-size: 16px; font-weight: 600; padding: 14px 32px; border-radius: 12px;">
                                            Repay Now
                                        </a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
        <tr>
            <td style="background-color: #111827; padding: 30px; text-align: center;">
                <p style="font-size: 14px; color: #94a3b8; margin: 0;">PrintEdge &copy; 2026</p>
                <p style="font-size: 12px; color: #64748b; margin: 0;">This is an automated message.</p>
            </td>
        </tr>
    </table>
</body>
</html>''',
        },
        {
            'name': 'Welcome (Admin Approval)',
            'subject': 'Your account has been approved – PrintEdge',
            'html_body': '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Account Approved - PrintEdge</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f8f9fa; font-family: Arial, Helvetica, sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width: 600px; margin: 0 auto; background-color: #ffffff;">
        <tr>
            <td align="center" style="background: linear-gradient(135deg, #1e293b, #111827); padding: 30px 20px;">
                <a href="https://printedge.vercel.app" style="text-decoration: none;">
                    <img src="https://printedge.vercel.app/static/icons/logo.png" alt="PrintEdge Logo" width="120" style="display: block; margin: 0 auto;">
                </a>
                <h1 style="color: #ffffff; font-size: 24px; font-weight: 600; margin: 20px 0 0 0;">Account Approved</h1>
            </td>
        </tr>
        <tr>
            <td style="padding: 40px 30px 30px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                    <tr>
                        <td>
                            <p style="font-size: 16px; line-height: 1.6; color: #333333; margin: 0 0 16px;">
                                Hello {{ user.first_name|default:user.email }},
                            </p>
                            <p style="font-size: 16px; line-height: 1.6; color: #333333; margin: 0 0 24px;">
                                Your account has been approved by an administrator. You can now log in and place orders.
                            </p>
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                                <tr>
                                    <td align="center">
                                        <a href="https://printedge.vercel.app/auth/login/" style="display: inline-block; background: linear-gradient(135deg, #10b981, #059669); color: #ffffff; text-decoration: none; font-size: 16px; font-weight: 600; padding: 14px 32px; border-radius: 12px;">
                                            Log In Now
                                        </a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
        <tr>
            <td style="background-color: #111827; padding: 30px; text-align: center;">
                <p style="font-size: 14px; color: #94a3b8; margin: 0;">PrintEdge &copy; 2026</p>
                <p style="font-size: 12px; color: #64748b; margin: 0;">This is an automated message.</p>
            </td>
        </tr>
    </table>
</body>
</html>''',
        },
        {
            'name': 'Custom Email (Generic)',
            'subject': 'Message from PrintEdge',
            'html_body': '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ subject|default:"Message" }}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f8f9fa; font-family: Arial, Helvetica, sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width: 600px; margin: 0 auto; background-color: #ffffff;">
        <tr>
            <td align="center" style="background: linear-gradient(135deg, #1e293b, #111827); padding: 30px 20px;">
                <a href="https://printedge.vercel.app" style="text-decoration: none;">
                    <img src="https://printedge.vercel.app/static/icons/logo.png" alt="PrintEdge Logo" width="120" style="display: block; margin: 0 auto;">
                </a>
                <h1 style="color: #ffffff; font-size: 24px; font-weight: 600; margin: 20px 0 0 0;">{{ subject|default:"Message from PrintEdge" }}</h1>
            </td>
        </tr>
        <tr>
            <td style="padding: 40px 30px 30px;">
                {{ body|safe }}
            </td>
        </tr>
        <tr>
            <td style="background-color: #111827; padding: 30px; text-align: center;">
                <p style="font-size: 14px; color: #94a3b8; margin: 0;">PrintEdge &copy; 2026</p>
                <p style="font-size: 12px; color: #64748b; margin: 0;">This is an automated message.</p>
            </td>
        </tr>
    </table>
</body>
</html>''',
        },
    ]
    
    for tpl in templates:
        EmailTemplate.objects.update_or_create(
            name=tpl['name'],
            defaults={'subject': tpl['subject'], 'html_body': tpl['html_body']}
        )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0024_create_default_email_templates'),
    ]

    operations = [
        migrations.RunPython(create_premium_email_templates),
    ]