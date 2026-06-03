# Add missing created_at on OrderFile (omitted from 0012_sync_schema)

from django.db import migrations


def add_created_at(apps, schema_editor):
    connection = schema_editor.connection
    with connection.cursor() as c:
        c.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'core_orderfile' AND column_name = 'created_at'
            """
        )
        if c.fetchone() is None:
            c.execute(
                """
                ALTER TABLE core_orderfile
                ADD COLUMN created_at timestamptz NOT NULL DEFAULT now()
                """
            )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0012_sync_schema'),
    ]

    operations = [
        migrations.RunPython(add_created_at, migrations.RunPython.noop),
    ]
