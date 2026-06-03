# Generated manually for Cover Studio MVP

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_remove_sitesettings_max_login_attempts_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='source',
            field=models.CharField(
                choices=[
                    ('online', 'Online'),
                    ('offline', 'Walk-in'),
                    ('cover_tool', 'Cover Studio'),
                ],
                default='online',
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name='AcademicProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('university', models.CharField(blank=True, default='', max_length=200)),
                ('department', models.CharField(blank=True, default='', max_length=200)),
                ('student_id', models.CharField(blank=True, default='', max_length=50)),
                ('batch', models.CharField(blank=True, default='', max_length=50)),
                ('semester', models.CharField(blank=True, default='', max_length=80)),
                ('section', models.CharField(blank=True, default='', max_length=50)),
                ('supervisor_name', models.CharField(blank=True, default='', max_length=120)),
                ('supervisor_designation', models.CharField(blank=True, default='', max_length=120)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='academic_profile', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='CoverTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slug', models.SlugField(max_length=40, unique=True)),
                ('name', models.CharField(max_length=120)),
                ('description', models.TextField(blank=True, default='')),
                ('category', models.CharField(choices=[('formal', 'University Formal'), ('creative', 'Modern Creative'), ('minimal', 'Minimalist'), ('project', 'Project / Internship'), ('thesis', 'Thesis / Dissertation')], default='formal', max_length=20)),
                ('css_class', models.CharField(help_text='CSS class suffix, e.g. classic -> template-classic', max_length=40)),
                ('university_tag', models.CharField(blank=True, default='generic', max_length=40)),
                ('thumbnail', models.ImageField(blank=True, null=True, upload_to='cover_templates/')),
                ('is_featured', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
                ('sort_order', models.PositiveIntegerField(default=0)),
            ],
            options={
                'ordering': ['sort_order', 'name'],
            },
        ),
        migrations.CreateModel(
            name='CoverPhrase',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(default='general', max_length=40)),
                ('text', models.TextField()),
                ('is_active', models.BooleanField(default=True)),
                ('sort_order', models.PositiveIntegerField(default=0)),
            ],
            options={
                'ordering': ['sort_order', 'category'],
            },
        ),
        migrations.CreateModel(
            name='CoverDesign',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(blank=True, default='', max_length=200)),
                ('template_slug', models.CharField(default='classic', max_length=40)),
                ('draft_json', models.JSONField(blank=True, default=dict)),
                ('pdf_file', models.FileField(blank=True, null=True, upload_to='covers/%Y/%m/')),
                ('preview_png', models.ImageField(blank=True, null=True, upload_to='covers/previews/%Y/%m/')),
                ('source', models.CharField(default='editor', max_length=20)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('linked_order', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cover_designs', to='core.order')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='cover_designs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-updated_at'],
            },
        ),
        migrations.CreateModel(
            name='CoverPageEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_type', models.CharField(choices=[('view', 'Page View'), ('export_pdf', 'Export PDF'), ('export_png', 'Export PNG'), ('order_print', 'Order Print'), ('save_cloud', 'Save to Cloud')], max_length=20)),
                ('template_slug', models.CharField(blank=True, default='', max_length=40)),
                ('session_key', models.CharField(blank=True, default='', max_length=64)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['event_type', 'created_at'], name='core_coverp_event_t_8a0f0d_idx'),
                    models.Index(fields=['template_slug'], name='core_coverp_templat_6c8e8a_idx'),
                ],
            },
        ),
    ]
