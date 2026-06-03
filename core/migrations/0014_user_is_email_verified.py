from django.db import migrations, models


def mark_staff_verified(apps, schema_editor):
    User = apps.get_model('core', 'User')
    User.objects.exclude(role='customer').update(is_email_verified=True)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0013_orderfile_created_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='is_email_verified',
            field=models.BooleanField(
                default=False,
                help_text='Customers must verify email before placing online orders.',
            ),
        ),
        migrations.RunPython(mark_staff_verified, migrations.RunPython.noop),
    ]
