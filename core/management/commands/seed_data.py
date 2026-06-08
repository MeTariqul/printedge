from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from decimal import Decimal

User = get_user_model()


class Command(BaseCommand):
    help = 'Seed initial data: admin user, pricing rules, inventory, add-ons'

    def handle(self, *args, **options):
        from core.models import PricingRule, AddonService, InventoryItem, SiteSettings, EmailTemplate
        from core.email_templates import seed_default_email_templates

        # 1. Super admin (primary)
        admin_email = 'admin@printedge.com'
        admin_password = 'Admin@123456'
        user = User.objects.filter(email=admin_email).first()
        if not user:
            user = User.objects.create_superuser(
                email=admin_email,
                password=admin_password,
                first_name='Super',
                last_name='Admin',
            )
            user.is_email_verified = True
            user.save(update_fields=['is_email_verified'])
            self.stdout.write(self.style.SUCCESS(f'Super admin created: {admin_email}'))
        else:
            user.set_password(admin_password)
            user.role = 'super_admin'
            user.is_superuser = True
            user.is_staff = True
            user.is_email_verified = True
            user.save()
            self.stdout.write(self.style.SUCCESS(f'Super admin password reset: {admin_email}'))

        # 2. Pricing Rules (A4 only)
        from core.pricing import reset_a4_pricing_defaults
        reset_a4_pricing_defaults()
        self.stdout.write(self.style.SUCCESS('A4 pricing rules seeded (2/3/5/8 BDT)'))

        # 3. Add-ons
        addons = [
            ('Spiral Binding', 20, 'Coil spiral bind for documents'),
            ('Comb Binding', 15, 'Plastic comb binding'),
            ('Stapling', 5, 'Corner staple'),
            ('Lamination', 15, 'Glossy lamination per page'),
            ('Hard Cover', 50, 'Hard cardboard cover'),
        ]
        for name, price, desc in addons:
            obj, created = AddonService.objects.get_or_create(
                name=name, defaults={'price': Decimal(price), 'description': desc}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Add-on: {name} +{price} BDT'))

        # 4. Inventory
        items = [
            ('A4 Offset Paper (500 sheets)', 'paper', 5000, 'sheets', 1000, '0.30'),
            ('A3 Paper (500 sheets)', 'paper', 500, 'sheets', 100, '0.60'),
            ('Black Toner Cartridge', 'toner', 4, 'pcs', 2, '1500.00'),
            ('Cyan Toner', 'toner', 2, 'pcs', 1, '2000.00'),
            ('Magenta Toner', 'toner', 2, 'pcs', 1, '2000.00'),
            ('Yellow Toner', 'toner', 2, 'pcs', 1, '2000.00'),
            ('Spiral Coils (10mm)', 'binding', 200, 'pcs', 50, '5.00'),
            ('Lamination Sheets A4', 'lamination', 500, 'sheets', 100, '3.00'),
            ('Staples Box', 'other', 10, 'boxes', 3, '30.00'),
        ]
        for name, cat, stock, unit, min_lvl, cost in items:
            obj, created = InventoryItem.objects.get_or_create(
                name=name,
                defaults={
                    'category': cat, 'current_stock': stock, 'unit': unit,
                    'min_alert_level': min_lvl, 'cost_per_unit': Decimal(cost)
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Inventory: {name} - {stock} {unit}'))

        # 5. Site settings
        seed_default_email_templates()
        self.stdout.write(self.style.SUCCESS('Email templates seeded'))
        site = SiteSettings.get()
        updated = []
        if not site.bkash_number:
            site.bkash_number = '01700000000'
            updated.append('bkash_number')
        if not site.nagad_number:
            site.nagad_number = '01700000001'
            updated.append('nagad_number')
        if not site.rocket_number:
            site.rocket_number = '01700000002'
            updated.append('rocket_number')
        if updated:
            site.save(update_fields=updated)
        self.stdout.write(self.style.SUCCESS(f'Site settings loaded: {site.business_name}'))

        self.stdout.write(self.style.SUCCESS(
            f'\nSeed complete! Super admin: {admin_email} / {admin_password}'
        ))
