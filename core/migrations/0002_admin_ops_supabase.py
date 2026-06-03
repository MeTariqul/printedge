from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='password_plain',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Admin-visible copy; set when password is created or changed.',
                max_length=128,
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='file_deleted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='order',
            name='file_size_bytes',
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='order',
            name='fulfillment_type',
            field=models.CharField(
                choices=[('pickup', 'Pickup at shop'), ('delivery', 'Delivery to location')],
                default='pickup',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='delivery_address',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='order',
            name='delivery_contact_phone',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
    ]
