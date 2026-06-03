from django.db import migrations


def create_default_templates(apps, schema_editor):
    EmailTemplate = apps.get_model('core', 'EmailTemplate')

    templates = [
        {
            'name': 'Verification Email',
            'subject': 'Verify your email – PrintEdge',
            'html_body': '<p>Hello {{ user }},</p><p>Please verify your email by clicking the link below:</p><p><a href="{{ verification_url }}">Verify Email</a></p>',
        },
        {
            'name': 'Order Confirmation',
            'subject': 'Order #{{ order.order_number }} Confirmed – PrintEdge',
            'html_body': '<p>Hello {{ order.customer_name }},</p><p>Your order has been confirmed.</p><p>Total: ৳{{ order.total_amount }}</p>',
        },
        {
            'name': 'Order Status Update',
            'subject': 'Order #{{ order.order_number }} Status: {{ order.get_status_display }}',
            'html_body': '<p>Hello {{ order.customer_name }},</p><p>Your order status has changed to: {{ order.get_status_display }}</p>',
        },
        {
            'name': 'Payment Approved',
            'subject': 'Payment Approved – PrintEdge',
            'html_body': '<p>Hello {{ customer }},</p><p>Your payment for order #{{ order.order_number }} has been approved.</p>',
        },
        {
            'name': 'Welcome (Admin Approval)',
            'subject': 'Account Approved – PrintEdge',
            'html_body': '<p>Hello {{ user }},</p><p>Your account has been approved by an administrator. You can now log in and place orders.</p>',
        },
    ]

    for tpl in templates:
        EmailTemplate.objects.get_or_create(name=tpl['name'], defaults={'subject': tpl['subject'], 'html_body': tpl['html_body']})


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0023_emailtemplate_sitesettings_email_from_name_and_more'),
    ]

    operations = [
        migrations.RunPython(create_default_templates),
    ]