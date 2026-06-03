"""Role-based permission helpers for PrintEdge staff."""

STAFF_ROLES = ('viewer', 'operator', 'manager', 'admin', 'super_admin')
WRITE_STAFF_ROLES = ('operator', 'manager', 'admin', 'super_admin')
MANAGER_PLUS = ('manager', 'admin', 'super_admin')
FULL_ADMIN = ('admin', 'super_admin')

# permission key -> minimum roles allowed
PERMISSIONS = {
    'view_orders': STAFF_ROLES,
    'update_order_status': WRITE_STAFF_ROLES,
    'walkin_order': WRITE_STAFF_ROLES,
    'operator_dashboard': WRITE_STAFF_ROLES,
    'manage_pricing': WRITE_STAFF_ROLES,
    'view_financial': MANAGER_PLUS,
    'manage_inventory': MANAGER_PLUS,
    'manage_customers': FULL_ADMIN,
    'manage_staff': FULL_ADMIN,
    'view_audit': MANAGER_PLUS,
    'edit_settings': FULL_ADMIN,
    'system_status': FULL_ADMIN,
    'export_reports': MANAGER_PLUS,
}


def user_has_permission(user, permission):
    if not user.is_authenticated:
        return False
    allowed = PERMISSIONS.get(permission, ())
    return user.role in allowed


def is_readonly_staff(user):
    return user.is_authenticated and user.role == 'viewer'
