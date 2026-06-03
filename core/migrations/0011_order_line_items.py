# Generated for per-file order line items

from decimal import Decimal
from django.db import migrations, models
import django.db.models.deletion


def backfill_order_files(apps, schema_editor):
    Order = apps.get_model('core', 'Order')
    OrderFile = apps.get_model('core', 'OrderFile')
    for order in Order.objects.all():
        if OrderFile.objects.filter(order=order).exists():
            continue
        if not order.file and not order.file_name:
            continue
        OrderFile.objects.create(
            order=order,
            file=order.file,
            file_name=order.file_name or 'Document',
            file_type=order.file_type or '',
            file_size_bytes=order.file_size_bytes,
            print_type=order.print_type or 'bw',
            sides=order.sides or 'single',
            paper_size=order.paper_size or 'A4',
            pages_detected=max(1, order.pages or 1),
            copies=max(1, order.copies or 1),
            line_base_price=order.base_price or Decimal('0'),
            is_primary=True,
            sort_order=0,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_frontend_overhaul'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='invoice_file',
            field=models.FileField(blank=True, null=True, upload_to='invoices/%Y/%m/'),
        ),
        migrations.RenameField(
            model_name='orderfile',
            old_name='pages',
            new_name='pages_detected',
        ),
        migrations.AddField(
            model_name='orderfile',
            name='copies',
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name='orderfile',
            name='file_size_bytes',
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='orderfile',
            name='file_type',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
        migrations.AddField(
            model_name='orderfile',
            name='is_primary',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='orderfile',
            name='line_base_price',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name='orderfile',
            name='pages_override',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='orderfile',
            name='paper_size',
            field=models.CharField(default='A4', max_length=10),
        ),
        migrations.AddField(
            model_name='orderfile',
            name='print_type',
            field=models.CharField(choices=[('bw', 'Black & White'), ('color', 'Color')], default='bw', max_length=10),
        ),
        migrations.AddField(
            model_name='orderfile',
            name='sides',
            field=models.CharField(choices=[('single', 'Single Sided'), ('double', 'Double Sided')], default='single', max_length=10),
        ),
        migrations.AlterField(
            model_name='orderfile',
            name='file',
            field=models.FileField(blank=True, null=True, upload_to='uploads/%Y/%m/'),
        ),
        migrations.AlterField(
            model_name='orderfile',
            name='order',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='order_files', to='core.order'),
        ),
        migrations.CreateModel(
            name='OrderFilePageRange',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start_page', models.PositiveIntegerField()),
                ('end_page', models.PositiveIntegerField()),
                ('print_type', models.CharField(choices=[('bw', 'Black & White'), ('color', 'Color')], default='bw', max_length=10)),
                ('sides', models.CharField(choices=[('single', 'Single Sided'), ('double', 'Double Sided')], default='single', max_length=10)),
                ('order_file', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='page_ranges', to='core.orderfile')),
            ],
            options={
                'ordering': ['start_page'],
            },
        ),
        migrations.RunPython(backfill_order_files, migrations.RunPython.noop),
    ]
