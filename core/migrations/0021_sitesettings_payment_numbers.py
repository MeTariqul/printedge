# Generated for SiteSettings payment numbers

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0020_notification_model_update'),
    ]

    operations = [
        migrations.AddField(
            model_name='sitesettings',
            name='bkash_number',
            field=models.CharField(blank=True, default='', max_length=20, help_text='bKash number for payments'),
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='nagad_number',
            field=models.CharField(blank=True, default='', max_length=20, help_text='Nagad number for payments'),
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='rocket_number',
            field=models.CharField(blank=True, default='', max_length=20, help_text='Rocket number for payments'),
        ),
    ]