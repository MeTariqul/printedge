from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from decimal import Decimal

User = get_user_model()


class Command(BaseCommand):
    help = 'Seed initial data: admin user, pricing rules, inventory, add-ons'

    def handle(self, *args, **options):
        from core.models import PricingRule, AddonService, InventoryItem, SiteSettings

        # 1. Create admin user
        if not User.objects.filter(email='gbtarif37@gmail.com').exists():
            user = User.objects.create_superuser(
                username='admin',
                email='gbtarif37@gmail.com',
                password='admin123',
                first_name='Admin',
                last_name='User',
                role='super_admin',
            )
            self.stdout.write(self.style.SUCCESS('✅ Admin user created: gbtarif37@gmail.com / admin123'))
        else:
            self.stdout.write('ℹ️  Admin user already exists.')

        # 2. Pricing Rules
        rules = [
            ('B&W Single Side A4', 'bw', 'single', 'A4', '2.00'),
            ('B&W Double Side A4', 'bw', 'double', 'A4', '3.00'),
            ('Color Single Side A4', 'color', 'single', 'A4', '5.00'),
            ('Color Double Side A4', 'color', 'double', 'A4', '7.00'),
            ('B&W Single Side A3', 'bw', 'single', 'A3', '4.00'),
            ('B&W Double Side A3', 'bw', 'double', 'A3', '6.00'),
            ('Color Single Side A3', 'color', 'single', 'A3', '10.00'),
            ('Color Double Side A3', 'color', 'double', 'A3', '14.00'),
        ]
        for name, pt, sides, size, price in rules:
            obj, created = PricingRule.objects.get_or_create(
                print_type=pt, sides=sides, paper_size=size,
                defaults={'name': name, 'price_per_page': Decimal(price)}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'✅ Price rule: {name} — ৳{price}'))

        # 3. Add-ons
        addons = [
            ('Spiral Binding', 20, 'Coil spiral bind for documents'),
            ('Comb Binding', 15, 'Plastic comb binding'),
            ('Stapling', 5, 'Corner staple'),
            ('Lamination', 15, 'Glossy lamination per page'),
            ('Color Cover Page', 10, 'Printed color cover sheet'),
            ('Hard Cover', 50, 'Hard cardboard cover'),
        ]
        for name, price, desc in addons:
            obj, created = AddonService.objects.get_or_create(
                name=name, defaults={'price': Decimal(price), 'description': desc}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'✅ Add-on: {name} +৳{price}'))

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
                self.stdout.write(self.style.SUCCESS(f'✅ Inventory: {name} — {stock} {unit}'))

        # 5. Site settings
        settings = SiteSettings.get()
        self.stdout.write(self.style.SUCCESS(f'✅ Site settings loaded: {settings.business_name}'))

        self.stdout.write(self.style.SUCCESS('\n🎉 Seed complete! Login at /auth/login/ with gbtarif37@gmail.com / admin123'))
