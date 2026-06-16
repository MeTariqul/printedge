# Idempotent schema sync for databases partially migrated outside Django

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
from decimal import Decimal


def sync_schema(apps, schema_editor):
    connection = schema_editor.connection
    vendor = connection.vendor

    def column_exists(table, column):
        with connection.cursor() as c:
            if vendor == 'sqlite':
                c.execute("PRAGMA table_info(" + table + ")")
                return any(row[1] == column for row in c.fetchall())
            c.execute(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_name = %s AND column_name = %s
                """,
                [table, column],
            )
            return c.fetchone() is not None

    def table_exists(table):
        with connection.cursor() as c:
            if vendor == 'sqlite':
                c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", [table])
                return c.fetchone() is not None
            c.execute(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_name = %s
                """,
                [table],
            )
            return c.fetchone() is not None

    with connection.cursor() as c:
        if vendor != 'sqlite':
            if not column_exists('core_user', 'university'):
                c.execute(
                    "ALTER TABLE core_user ADD COLUMN university varchar(150) NOT NULL DEFAULT ''"
                )

            if not column_exists('core_sitesettings', 'chat_provider'):
                c.execute(
                    "ALTER TABLE core_sitesettings ADD COLUMN chat_provider varchar(20) NOT NULL DEFAULT ''"
                )
            if not column_exists('core_sitesettings', 'chat_widget_id'):
                c.execute(
                    "ALTER TABLE core_sitesettings ADD COLUMN chat_widget_id varchar(200) NOT NULL DEFAULT ''"
                )

            if not table_exists('core_useraddress'):
                c.execute("""
                    CREATE TABLE core_useraddress (
                        id bigserial PRIMARY KEY,
                        label varchar(50) NOT NULL DEFAULT 'Home',
                        address text NOT NULL,
                        phone varchar(20) NOT NULL DEFAULT '',
                        is_default boolean NOT NULL DEFAULT false,
                        created_at timestamptz NOT NULL DEFAULT now(),
                        user_id bigint NOT NULL REFERENCES core_user(id) ON DELETE CASCADE
                    )
                """)

            if not column_exists('core_order', 'invoice_file'):
                c.execute(
                    "ALTER TABLE core_order ADD COLUMN invoice_file varchar(100) NULL"
                )

            if column_exists('core_orderfile', 'pages') and not column_exists(
                'core_orderfile', 'pages_detected'
            ):
                c.execute(
                    "ALTER TABLE core_orderfile RENAME COLUMN pages TO pages_detected"
                )

            for col, sql in [
                ('copies', 'ALTER TABLE core_orderfile ADD COLUMN copies integer NOT NULL DEFAULT 1'),
                ('pages_override', 'ALTER TABLE core_orderfile ADD COLUMN pages_override integer NULL'),
                ('paper_size', "ALTER TABLE core_orderfile ADD COLUMN paper_size varchar(10) NOT NULL DEFAULT 'A4'"),
                ('print_type', "ALTER TABLE core_orderfile ADD COLUMN print_type varchar(10) NOT NULL DEFAULT 'bw'"),
                ('sides', "ALTER TABLE core_orderfile ADD COLUMN sides varchar(10) NOT NULL DEFAULT 'single'"),
                ('is_primary', 'ALTER TABLE core_orderfile ADD COLUMN is_primary boolean NOT NULL DEFAULT false'),
            ]:
                if not column_exists('core_orderfile', col):
                    c.execute(sql)

            if not table_exists('core_orderfilepagerange'):
                c.execute("""
                    CREATE TABLE core_orderfilepagerange (
                        id bigserial PRIMARY KEY,
                        start_page integer NOT NULL,
                        end_page integer NOT NULL,
                        print_type varchar(10) NOT NULL DEFAULT 'bw',
                        sides varchar(10) NOT NULL DEFAULT 'single',
                        order_file_id bigint NOT NULL REFERENCES core_orderfile(id) ON DELETE CASCADE
                    )
                """)


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
            file_type=getattr(order, 'file_type', '') or '',
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
        ('core', '0011_order_line_items'),
    ]

    operations = [
        migrations.RunPython(sync_schema, migrations.RunPython.noop),
        migrations.RunPython(backfill_order_files, migrations.RunPython.noop),
    ]
