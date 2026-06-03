# Generated migration for Notification model changes and user preferences

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0019_user_email_unique'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='notification',
            name='title',
        ),
        migrations.RemoveField(
            model_name='notification',
            name='body',
        ),
        migrations.RemoveField(
            model_name='notification',
            name='type',
        ),
        migrations.RemoveField(
            model_name='notification',
            name='link',
        ),
        migrations.AddField(
            model_name='notification',
            name='actor',
            field=models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name='triggered_notifications', to='core.user'),
        ),
        migrations.AddField(
            model_name='notification',
            name='description',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='notification',
            name='target_id',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='notification',
            name='target_type',
            field=models.CharField(choices=[('new_order', 'New Order'), ('status_change', 'Status Change'), ('low_stock', 'Low Stock'), ('new_user', 'New User'), ('payment', 'Payment'), ('system', 'System')], default='system', max_length=20),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='notification',
            name='target_url',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AddField(
            model_name='notification',
            name='verb',
            field=models.CharField(default='Notification', max_length=100),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='user',
            name='notification_email',
            field=models.BooleanField(default=True, help_text='Receive email notifications'),
        ),
        migrations.AddField(
            model_name='user',
            name='notification_push',
            field=models.BooleanField(default=False, help_text='Receive push notifications (future)'),
        ),
    ]