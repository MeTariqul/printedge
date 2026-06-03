# PrintEdge — Deployment Summary

## What was implemented

- **Supabase Storage**: Uploads use `django-storages` + S3 API when `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `SUPABASE_STORAGE_BUCKET` are set. System Status page includes bucket name and write test.
- **Page count detection**: `POST /api/detect-pages/` (PDF, DOCX, PPTX, images) with manual override on customer and walk-in forms.
- **Invoice PDF**: Download from `/user/orders/<id>/invoice/` and `/admin/orders/<id>/invoice/` (ReportLab).
- **Pricing admin**: Add, toggle active, and update `PricingRule` rows; order forms use active paper sizes from the database.
- **Accepting orders**: `SiteSettings.accepting_orders` toggle in Admin → Settings; blocks customer online orders when off.
- **Notifications**: In-app bell with 30s polling, mark-read APIs, triggers on new orders (admins) and status changes (customers).
- **Logo**: Default `static/icons/logo.png` with alt text "Print Edge" via `partials/site_logo.html`.
- **Walk-in**: Optional file when physical document is checked; page detection on file select.
- **Responsive**: Table scroll helpers and 44px touch targets in admin layout.

## Manual steps for Vercel / Supabase

1. **Vercel environment variables** (Django names, not Flask):

   - `SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS=your-app.vercel.app`
   - `DATABASE_URL` (Supabase Postgres pooler URL)
   - `AWS_ACCESS_KEY_ID` = Supabase service role key
   - `AWS_SECRET_ACCESS_KEY` = same service role key
   - `AWS_S3_ENDPOINT_URL=https://<project-ref>.storage.supabase.co/storage/v1/s3`
   - `SUPABASE_STORAGE_BUCKET=order-files`
   - `AWS_S3_REGION_NAME=auto`
   - `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`
   - `CRON_SECRET`, `ADMIN_EMAILS`

2. **Supabase**: Create storage bucket `order-files` (see `DEPLOY.md`).

3. **Migrations**: Run `python manage.py migrate` on production after deploy.

4. **Security**: Rotate Gmail app password if it was shared in chat; never commit `.env`.

5. **Local setup**:

   ```bash
   python3 -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env   # fill values
   python manage.py migrate
   python manage.py seed_data
   python manage.py collectstatic --noinput
   python manage.py runserver
   ```
