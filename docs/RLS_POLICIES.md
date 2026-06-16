# RLS Policies for Supabase PrintEdge

This document describes the Row Level Security (RLS) policies configured in Supabase for the PrintEdge application.

## Overview

All tables in the `public` schema have RLS enabled. Policies are defined to allow authenticated admin users to perform CRUD operations based on their role.

## Admin App Tables

The following tables are accessed by the Android admin app and have policies allowing `super_admin`, `admin`, `manager`, `operator`, `finance`, and `viewer` roles:

### Tables with policies
- `core_user`
- `core_order`
- `core_orderfile`
- `core_coupon`
- `core_service`
- `core_servicevariant`
- `core_sitesettings`
- `core_notification`
- `core_auditlog`
- `core_emailtemplate`
- `core_walkincustomer`
- `core_inventoryitem`
- `core_expense`
- `core_emailtemplate`
- `core_emaillog`
- `core_orderstatuslog`

### Policy pattern

```sql
CREATE POLICY "allow_admin_roles" ON core_user
  FOR ALL
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM core_user cu
      WHERE cu.id = auth.uid()
      AND cu.role IN ('super_admin', 'admin', 'manager', 'operator', 'finance', 'viewer')
    )
  );
```

Each table has a similar policy named `allow_admin_roles` that checks the requesting user's role.

## Django Internal Tables

The following Django internal tables have **NO RLS policies** - API access is blocked by default:

- `django_migrations`
- `auth_permission`
- `django_content_type`
- `auth_group`
- `auth_group_permissions`
- `django_session`
- `django_admin_log`

These tables are not exposed via the Supabase API and should remain without policies.

## Service Role

The `service_role` key in Supabase bypasses RLS entirely. This is used only for server-side operations performed by the Django backend (e.g., file uploads to Storage, server-side data sync).

## Enabling RLS

To enable RLS on all tables, run the following in the Supabase SQL Editor:

```sql
-- Enable RLS on all tables
ALTER TABLE core_user ENABLE ROW LEVEL SECURITY;
ALTER TABLE core_order ENABLE ROW LEVEL SECURITY;
ALTER TABLE core_orderfile ENABLE ROW LEVEL SECURITY;
ALTER TABLE core_coupon ENABLE ROW LEVEL SECURITY;
ALTER TABLE core_service ENABLE ROW LEVEL SECURITY;
ALTER TABLE core_servicevariant ENABLE ROW LEVEL SECURITY;
ALTER TABLE core_sitesettings ENABLE ROW LEVEL SECURITY;
ALTER TABLE core_notification ENABLE ROW LEVEL SECURITY;
ALTER TABLE core_auditlog ENABLE ROW LEVEL SECURITY;
ALTER TABLE core_emailtemplate ENABLE ROW LEVEL SECURITY;
ALTER TABLE core_emaillog ENABLE ROW LEVEL SECURITY;
ALTER TABLE core_orderstatuslog ENABLE ROW LEVEL SECURITY;
ALTER TABLE core_walkincustomer ENABLE ROW LEVEL SECURITY;
ALTER TABLE core_inventoryitem ENABLE ROW LEVEL SECURITY;
ALTER TABLE core_expense ENABLE ROW LEVEL SECURITY;

-- Create admin role policies
CREATE POLICY "allow_admin_roles" ON core_user FOR ALL TO authenticated USING (
  EXISTS (SELECT 1 FROM core_user cu WHERE cu.id = auth.uid() AND cu.role IN ('super_admin','admin','manager','operator','finance','viewer'))
);

CREATE POLICY "allow_admin_roles" ON core_order FOR ALL TO authenticated USING (
  EXISTS (SELECT 1 FROM core_user cu WHERE cu.id = auth.uid() AND cu.role IN ('super_admin','admin','manager','operator','finance','viewer'))
);

CREATE POLICY "allow_admin_roles" ON core_orderfile FOR ALL TO authenticated USING (
  EXISTS (SELECT 1 FROM core_user cu WHERE cu.id = auth.uid() AND cu.role IN ('super_admin','admin','manager','operator','finance','viewer'))
);

CREATE POLICY "allow_admin_roles" ON core_service FOR ALL TO authenticated USING (
  EXISTS (SELECT 1 FROM core_user cu WHERE cu.id = auth.uid() AND cu.role IN ('super_admin','admin','manager','operator','finance','viewer'))
);

CREATE POLICY "allow_admin_roles" ON core_servicevariant FOR ALL TO authenticated USING (
  EXISTS (SELECT 1 FROM core_user cu WHERE cu.id = auth.uid() AND cu.role IN ('super_admin','admin','manager','operator','finance','viewer'))
);

CREATE POLICY "allow_admin_roles" ON core_coupon FOR ALL TO authenticated USING (
  EXISTS (SELECT 1 FROM core_user cu WHERE cu.id = auth.uid() AND cu.role IN ('super_admin','admin','manager','operator','finance','viewer'))
);

CREATE POLICY "allow_admin_roles" ON core_sitesettings FOR ALL TO authenticated USING (
  EXISTS (SELECT 1 FROM core_user cu WHERE cu.id = auth.uid() AND cu.role IN ('super_admin','admin','manager','operator','finance','viewer'))
);

CREATE POLICY "allow_admin_roles" ON core_notification FOR ALL TO authenticated USING (
  EXISTS (SELECT 1 FROM core_user cu WHERE cu.id = auth.uid() AND cu.role IN ('super_admin','admin','manager','operator','finance','viewer'))
);

CREATE POLICY "allow_admin_roles" ON core_auditlog FOR ALL TO authenticated USING (
  EXISTS (SELECT 1 FROM core_user cu WHERE cu.id = auth.uid() AND cu.role IN ('super_admin','admin','manager','operator','finance','viewer'))
);

CREATE POLICY "allow_admin_roles" ON core_emailtemplate FOR ALL TO authenticated USING (
  EXISTS (SELECT 1 FROM core_user cu WHERE cu.id = auth.uid() AND cu.role IN ('super_admin','admin','manager','operator','finance','viewer'))
);

CREATE POLICY "allow_admin_roles" ON core_emaillog FOR ALL TO authenticated USING (
  EXISTS (SELECT 1 FROM core_user cu WHERE cu.id = auth.uid() AND cu.role IN ('super_admin','admin','manager','operator','finance','viewer'))
);

CREATE POLICY "allow_admin_roles" ON core_orderstatuslog FOR ALL TO authenticated USING (
  EXISTS (SELECT 1 FROM core_user cu WHERE cu.id = auth.uid() AND cu.role IN ('super_admin','admin','manager','operator','finance','viewer'))
);

CREATE POLICY "allow_admin_roles" ON core_walkincustomer FOR ALL TO authenticated USING (
  EXISTS (SELECT 1 FROM core_user cu WHERE cu.id = auth.uid() AND cu.role IN ('super_admin','admin','manager','operator','finance','viewer'))
);

CREATE POLICY "allow_admin_roles" ON core_inventoryitem FOR ALL TO authenticated USING (
  EXISTS (SELECT 1 FROM core_user cu WHERE cu.id = auth.uid() AND cu.role IN ('super_admin','admin','manager','operator','finance','viewer'))
);

CREATE POLICY "allow_admin_roles" ON core_expense FOR ALL TO authenticated USING (
  EXISTS (SELECT 1 FROM core_user cu WHERE cu.id = auth.uid() AND cu.role IN ('super_admin','admin','manager','operator','finance','viewer'))
);
```

## Verification

After applying RLS:
1. Open Supabase Dashboard → Database → RLS Advisor
2. All warnings should disappear for the tables listed above
3. No policies should exist for Django internal tables (`django_*`, `auth_*`)
