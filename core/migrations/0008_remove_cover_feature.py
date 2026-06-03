from django.db import migrations, models


def remove_cover_feature_data(apps, schema_editor):
    Order = apps.get_model('core', 'Order')
    AddonService = apps.get_model('core', 'AddonService')

    Order.objects.filter(source='cover_tool').update(source='online')
    AddonService.objects.filter(name='Color Cover Page').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_cover_studio'),
    ]

    operations = [
        migrations.RunPython(remove_cover_feature_data, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='order',
            name='source',
            field=models.CharField(
                choices=[
                    ('online', 'Online'),
                    ('offline', 'Walk-in'),
                ],
                default='online',
                max_length=20,
            ),
        ),
        migrations.DeleteModel(
            name='AcademicProfile',
        ),
        migrations.DeleteModel(
            name='CoverPageEvent',
        ),
        migrations.DeleteModel(
            name='CoverDesign',
        ),
        migrations.DeleteModel(
            name='CoverPhrase',
        ),
        migrations.DeleteModel(
            name='CoverTemplate',
        ),
    ]
