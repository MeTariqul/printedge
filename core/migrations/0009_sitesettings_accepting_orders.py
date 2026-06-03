from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_remove_cover_feature'),
    ]

    operations = [
        migrations.AddField(
            model_name='sitesettings',
            name='accepting_orders',
            field=models.BooleanField(
                default=True,
                help_text='When off, customers cannot place new online orders.',
            ),
        ),
    ]
