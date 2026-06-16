# RLS Policies for Supabase PrintEdge

This document describes the Row Level Security (RLS) policies configured in Supabase for the PrintEdge application.

## Quick Start

1. Open **Supabase Dashboard** → **SQL Editor**
2. Paste contents of `supabase_rls_setup.sql`
3. Click **Run**
4. Verify with: `python test_supabase_rls.py`

## Overview

All tables in the `public` schema have RLS enabled. Policies are defined to allow:
- **Admin/Staff roles** (`super_admin`, `admin`, `manager`, `operator`, `finance`, `viewer`) → full CRUD on most tables
- **Customer role** → read-only access to public services/variants/settings; can read only own orders
- **Anonymous** → no access (RLS blocks all)

## Helper Functions

Two SQL functions are created by the setup script:

```sql
is_admin_user()     -- Returns true if auth.uid() is a staff/admin role
is_authenticated_user() -- Returns true if user is logged in
```

## Table Policies

### Core Tables

| Table | Anonymous | Authenticated Customer | Admin/Staff |
|-------|-----------|------------------------|-------------|
| `core_user` | None | None | Read/Update |
| `core_order` | None | Read own orders only | Read/Insert/Update |
| `core_orderfile` | None | None | Read/Insert |
| `core_coupon` | None | Read (public coupons) | Read/Insert/Update |
| `core_service` | None | Read | Read/Insert/Update |
| `core_servicevariant` | None | Read | Read/Insert/Update |
| `core_sitesettings` | None | Read | Read/Update |
| `core_notification` | None | None | Read/Update |
| `core_auditlog` | None | None | Read/Insert |
| `core_emailtemplate` | None | None | Read/Insert/Update |
| `core_inventoryitem` | None | None | Read/Insert/Update |
| `core_walkincustomer` | None | None | Read/Insert/Update |
| `core_emaillog` | None | None | Read |
| `core_orderstatuslog` | None | None | Read/Insert |
| `core_expense` | None | None | Read/Insert/Update |

### Django Internal Tables (No RLS Policies)

The following Django internal tables have **NO RLS policies** — API access is blocked by default:

- `django_migrations`
- `auth_permission`
- `django_content_type`
- `auth_group`
- `auth_group_permissions`
- `django_session`
- `django_admin_log`

## Policy Pattern

All admin policies follow this pattern:

```sql
CREATE POLICY "policy_name" ON table_name
  FOR {SELECT|INSERT|UPDATE|ALL}
  TO authenticated
  USING (is_admin_user())
  WITH CHECK (is_admin_user());  -- For INSERT/UPDATE
```

## Service Role

The `service_role` key in Supabase bypasses RLS entirely. This is used only for server-side operations performed by the Django backend (e.g., file uploads to Storage, server-side data sync).

## Verification

After applying RLS:
1. Open **Supabase Dashboard** → **Database** → **RLS Advisor**
2. All warnings should disappear for the tables listed above
3. No policies should exist for Django internal tables (`django_*`, `auth_*`)
4. Run `python test_supabase_rls.py` to verify from the application side

## Maintenance

- To add a new table: add it to `supabase_rls_setup.sql` and run the script again
- To modify roles: update the `is_admin_user()` function
- To audit: check Supabase Dashboard → Database → Policies
