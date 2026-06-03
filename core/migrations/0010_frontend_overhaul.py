# Generated manually for frontend overhaul

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_sitesettings_accepting_orders'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='university',
            field=models.CharField(blank=True, default='', max_length=150),
        ),
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(
                choices=[
                    ('customer', 'Customer'),
                    ('viewer', 'Viewer'),
                    ('operator', 'Operator'),
                    ('manager', 'Manager'),
                    ('admin', 'Admin'),
                    ('super_admin', 'Super Admin'),
                ],
                default='customer',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='chat_provider',
            field=models.CharField(
                blank=True,
                choices=[('', 'None'), ('tawk', 'Tawk.to'), ('crisp', 'Crisp')],
                default='',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='chat_widget_id',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
        migrations.CreateModel(
            name='UserAddress',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(default='Home', max_length=50)),
                ('address', models.TextField()),
                ('phone', models.CharField(blank=True, default='', max_length=20)),
                ('is_default', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='addresses', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-is_default', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='OrderFile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='uploads/%Y/%m/')),
                ('file_name', models.CharField(blank=True, default='', max_length=255)),
                ('pages', models.PositiveIntegerField(default=1)),
                ('sort_order', models.PositiveSmallIntegerField(default=0)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='extra_files', to='core.order')),
            ],
            options={
                'ordering': ['sort_order', 'pk'],
            },
        ),
    ]
