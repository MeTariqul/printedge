"""Walk-in customer helpers for POS."""

import uuid

from .models import WalkInCustomer

NO_PHONE_PREFIX = 'NO-PHONE-'


def is_synthetic_phone(phone):
    return bool(phone) and phone.startswith(NO_PHONE_PREFIX)


def format_walkin_phone_display(phone):
    if not phone or is_synthetic_phone(phone):
        return ''
    return phone


def get_or_create_walkin_customer(name='', phone=''):
    """Create or match a walk-in customer; phone is optional."""
    name = (name or '').strip()
    phone = (phone or '').strip()

    if phone:
        walkin, _created = WalkInCustomer.objects.get_or_create(
            phone=phone,
            defaults={'name': name or phone},
        )
        if name and walkin.name != name:
            walkin.name = name
            walkin.save(update_fields=['name'])
        return walkin

    display_name = name or 'Walk-in Customer – No Phone'
    synthetic = f'{NO_PHONE_PREFIX}{uuid.uuid4().hex[:10]}'
    return WalkInCustomer.objects.create(name=display_name, phone=synthetic)
