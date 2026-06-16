-- PrintEdge Supabase RLS Setup
-- Run this in the Supabase SQL Editor to enable RLS on all public tables.

-- 1. Enable RLS on all tables
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND rowsecurity = false)
    LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', r.tablename);
    END LOOP;
END $$;

-- 2. Helper functions
CREATE OR REPLACE FUNCTION is_admin_user()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT EXISTS (
        SELECT 1 FROM core_user
        WHERE id = auth.uid()
        AND role IN ('super_admin', 'admin', 'manager', 'operator', 'finance', 'viewer')
    )
$$;

CREATE OR REPLACE FUNCTION is_authenticated_user()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT auth.uid() IS NOT NULL
$$;

-- 3. Core user policies
CREATE POLICY "allow_admin_read_users" ON core_user
  FOR SELECT TO authenticated USING (is_admin_user());

CREATE POLICY "allow_admin_update_users" ON core_user
  FOR UPDATE TO authenticated USING (is_admin_user());

-- 4. Order policies
CREATE POLICY "allow_admin_read_orders" ON core_order
  FOR SELECT TO authenticated USING (is_admin_user());

CREATE POLICY "allow_admin_insert_orders" ON core_order
  FOR INSERT TO authenticated WITH CHECK (is_admin_user());

CREATE POLICY "allow_admin_update_orders" ON core_order
  FOR UPDATE TO authenticated USING (is_admin_user());

-- 5. Order file policies
CREATE POLICY "allow_admin_read_orderfiles" ON core_orderfile
  FOR SELECT TO authenticated USING (is_admin_user());

CREATE POLICY "allow_admin_insert_orderfiles" ON core_orderfile
  FOR INSERT TO authenticated WITH CHECK (is_admin_user());

-- 6. Coupon policies
CREATE POLICY "allow_admin_read_coupons" ON core_coupon
  FOR SELECT TO authenticated USING (is_admin_user());

CREATE POLICY "allow_admin_insert_coupons" ON core_coupon
  FOR INSERT TO authenticated WITH CHECK (is_admin_user());

CREATE POLICY "allow_admin_update_coupons" ON core_coupon
  FOR UPDATE TO authenticated USING (is_admin_user());

-- 7. Service policies (read for admins and customers)
CREATE POLICY "allow_public_read_services" ON core_service
  FOR SELECT TO authenticated USING (is_admin_user() OR is_authenticated_user());

CREATE POLICY "allow_admin_insert_services" ON core_service
  FOR INSERT TO authenticated WITH CHECK (is_admin_user());

CREATE POLICY "allow_admin_update_services" ON core_service
  FOR UPDATE TO authenticated USING (is_admin_user());

-- 8. Service variant policies
CREATE POLICY "allow_public_read_servicevariants" ON core_servicevariant
  FOR SELECT TO authenticated USING (is_admin_user() OR is_authenticated_user());

CREATE POLICY "allow_admin_insert_servicevariants" ON core_servicevariant
  FOR INSERT TO authenticated WITH CHECK (is_admin_user());

CREATE POLICY "allow_admin_update_servicevariants" ON core_servicevariant
  FOR UPDATE TO authenticated USING (is_admin_user());

-- 9. Site settings policies
CREATE POLICY "allow_public_read_sitesettings" ON core_sitesettings
  FOR SELECT TO authenticated USING (is_admin_user() OR is_authenticated_user());

CREATE POLICY "allow_admin_update_sitesettings" ON core_sitesettings
  FOR UPDATE TO authenticated USING (is_admin_user());

-- 10. Notification policies
CREATE POLICY "allow_admin_read_notifications" ON core_notification
  FOR SELECT TO authenticated USING (is_admin_user());

CREATE POLICY "allow_admin_update_notifications" ON core_notification
  FOR UPDATE TO authenticated USING (is_admin_user());

-- 11. Audit log policies
CREATE POLICY "allow_admin_read_auditlog" ON core_auditlog
  FOR SELECT TO authenticated USING (is_admin_user());

CREATE POLICY "allow_admin_insert_auditlog" ON core_auditlog
  FOR INSERT TO authenticated WITH CHECK (is_admin_user());

-- 12. Email template policies
CREATE POLICY "allow_admin_read_emailtemplates" ON core_emailtemplate
  FOR SELECT TO authenticated USING (is_admin_user());

CREATE POLICY "allow_admin_insert_emailtemplates" ON core_emailtemplate
  FOR INSERT TO authenticated WITH CHECK (is_admin_user());

CREATE POLICY "allow_admin_update_emailtemplates" ON core_emailtemplate
  FOR UPDATE TO authenticated USING (is_admin_user());

-- 13. Inventory item policies
CREATE POLICY "allow_admin_read_inventoryitems" ON core_inventoryitem
  FOR SELECT TO authenticated USING (is_admin_user());

CREATE POLICY "allow_admin_insert_inventoryitems" ON core_inventoryitem
  FOR INSERT TO authenticated WITH CHECK (is_admin_user());

CREATE POLICY "allow_admin_update_inventoryitems" ON core_inventoryitem
  FOR UPDATE TO authenticated USING (is_admin_user());

-- 14. Additional tables
CREATE POLICY "allow_admin_read_walkincustomers" ON core_walkincustomer
  FOR SELECT TO authenticated USING (is_admin_user());

CREATE POLICY "allow_admin_insert_walkincustomers" ON core_walkincustomer
  FOR INSERT TO authenticated WITH CHECK (is_admin_user());

CREATE POLICY "allow_admin_update_walkincustomers" ON core_walkincustomer
  FOR UPDATE TO authenticated USING (is_admin_user());

CREATE POLICY "allow_admin_read_emaillogs" ON core_emaillog
  FOR SELECT TO authenticated USING (is_admin_user());

CREATE POLICY "allow_admin_read_orderstatuslog" ON core_orderstatuslog
  FOR SELECT TO authenticated USING (is_admin_user());

CREATE POLICY "allow_admin_insert_orderstatuslog" ON core_orderstatuslog
  FOR INSERT TO authenticated WITH CHECK (is_admin_user());

CREATE POLICY "allow_admin_read_expenses" ON core_expense
  FOR SELECT TO authenticated USING (is_admin_user());

CREATE POLICY "allow_admin_insert_expenses" ON core_expense
  FOR INSERT TO authenticated WITH CHECK (is_admin_user());

CREATE POLICY "allow_admin_update_expenses" ON core_expense
  FOR UPDATE TO authenticated USING (is_admin_user());

-- 15. Customer read-only for own orders
CREATE POLICY "allow_customer_read_own_orders" ON core_order
  FOR SELECT TO authenticated USING (
    EXISTS (
      SELECT 1 FROM core_user
      WHERE id = auth.uid()
      AND role = 'customer'
    )
    AND customer_email = (
      SELECT email FROM core_user WHERE id = auth.uid()
    )
  );
