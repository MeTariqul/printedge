# Empty migration placeholder after removing the legacy PricingRule model.
# Any live pricing is now managed via core.ServiceVariant.
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0037_add_order_service_variant'),
    ]

    operations = [
    ]
