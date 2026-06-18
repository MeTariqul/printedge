# PrintEdge — Deployment Guide

Deployed to **Vercel**. Read this file before deploying to production for the first time.

## Pre-requisites

- A Vercel account connected to your GitHub repository.
- A Supabase project with storage (S3-compatible) and Postgres enabled.

---

## 1. Supabase Storage (file uploads)

All user-uploaded files (order attachments, receipts, cover images) are stored in a
Supabase Storage bucket. The bucket name is set via the `SUPABASE_STORAGE_BUCKET`
environment variable.

### Create the bucket in Supabase

1. Open your Supabase project → **Storage** → **New bucket**.
2. Name: `order-files` (or any name you prefer).
3. Toggle **Public bucket** **OFF** — signed URLs are not required because
   `querystring_auth = False` and `default_acl = public-read` make the bucket
   readable without credentials.
4. Save the bucket.

### Get the S3-compatible credentials

Supabase provides an S3-compatible API at:

```
https://<project-ref>.storage.supabase.co/storage/v1/s3
```

You need two pieces of information:

| Variable | Where to find it |
|---|---|
| `AWS_ACCESS_KEY_ID` | Supabase **Project Settings → API → service_role key** |
| `AWS_SECRET_ACCESS_KEY` | Same key as above |
| `AWS_S3_ENDPOINT_URL` | `https://<project-ref>.storage.supabase.co/storage/v1/s3` |
| `AWS_STORAGE_BUCKET_NAME` | The bucket name you created above |
| `AWS_S3_REGION_NAME` | `auto` (leave as-is) |

---

## 2. Required Vercel Environment Variables

Add these in the Vercel dashboard under **Settings → Environment Variables**
(choose **Production** and **Preview** scopes as needed).

| Key | Example | Required |
|---|---|---|
| `SECRET_KEY` | Any long random string | Yes |
| `DATABASE_URL` | Supabase Postgres pooler URL | Yes |
| `AWS_ACCESS_KEY_ID` | Supabase service-role key | Yes |
| `AWS_SECRET_ACCESS_KEY` | Supabase service-role key | Yes |
| `SUPABASE_STORAGE_BUCKET` | `order-files` | Yes |
| `AWS_S3_ENDPOINT_URL` | `https://<ref>.storage.supabase.co/storage/v1/s3` | Yes |
| `AWS_S3_REGION_NAME` | `auto` | No (default) |
| `ALLOWED_HOSTS` | `your-domain.vercel.app,localhost` | Yes |
| `ADMIN_EMAILS` | `admin@example.com` | Yes |
| `DEFAULT_FROM_EMAIL` | `Print-Edge <noreply@example.com>` | Yes |
| `EMAIL_HOST` | `smtp.gmail.com` | If sending email |
| `EMAIL_HOST_USER` | Your email address | If sending email |
| `EMAIL_HOST_PASSWORD` | App/device password | If sending email |
| `CRON_SECRET` | Any random string | Yes (for cron-purge) |

---

## 3. Database Migrations

Before the first deploy, run:

```bash
python manage.py migrate
```

Vercel runs `build_files.sh` automatically on every deploy, which includes
`python manage.py collectstatic --noinput`.

If you need to run a one-off migration, pull the production env locally and run
migrate against the Supabase Postgres pooler URL, or use the Vercel dashboard
shell (Pro plan):

```bash
vercel env pull .env.production.local
python manage.py migrate
```

---

## 4. First Deploy

1. Push your branch to GitHub — Vercel will detect the push and start a new build.
2. Wait for **Build** → **Ready** in the Vercel dashboard.
3. Visit your production URL. Enable the `/admin/orders/walkin/` route to test file uploads.

---

## 5. File Storage Behaviour

| Environment | Upload destination |
|---|---|
| **Production (Vercel)** | Supabase Storage (`SUPABASE_STORAGE_BUCKET`) |
| **Local dev (no cloud env vars)** | `BASE_DIR / media/` (local filesystem) |
| **Vercel build / collectstatic** | No storage initialisation; static files collected locally |

The switch happens at module-level when Django's settings are first imported,
before any request is handled. `MEDIA_ROOT` is set to `None` in cloud mode so no
local write is ever attempted on Vercel's read-only `/var/task` filesystem.

---

## 6. Static Files

`python manage.py collectstatic --noinput` is executed during the Vercel build.
Static files are output to `staticfiles/` and served via Vercel's Python runtime
handler + `whitenoise`.

---

## 7. Cron: Purge Expired Files

A Vercel Cron job runs `POST /api/cron/purge-files/` every night at 3 AM.
The request must include a valid `Authorization: Bearer <CRON_SECRET>` header,
which is injected by Vercel from the `CRON_SECRET` environment variable.

Set `CRON_SECRET` in **all** environments (and keep the value the same for all).

---

## 8. Troubleshooting

### `OSError: [Errno 30] Read-only filesystem: '/var/task/media'`

This means the Supabase S3 block in `settings.py` did not activate. Check:
1. All five Supabase env vars are defined in Vercel.
2. `AWS_ACCESS_KEY_ID` and `SUPABASE_STORAGE_BUCKET` are non-empty strings.
3. Redeploy after changing env vars (Vercel does not hot-reload env changes).

### `django.core.exceptions.ImproperlyConfigured: Invalid setting 'query_string_authenticated'`

An invalid key was passed to `S3Boto3Storage` in `STORAGES['default']['OPTIONS']`.
Check commit `cc31820` — only whitelisted settings listed in
`S3Boto3Storage.get_default_settings()` may appear there.

### 404 on `/favicon.ico`

`static/favicon.ico` is the canonical favicon file. Copy `static/icons/icon-192.png`
to `static/favicon.ico` if it is missing:

```bash
cp static/icons/icon-192.png static/favicon.ico
```

### `manage.py check` shows `0 issues` locally but 500 on Vercel

Inspect the Vercel function logs. If `django-request` triggers `ModuleNotFoundError`,
add `django-request>=1.7.0` to `requirements.txt` and redeploy. (It is kept in
requirements but `'request'` is excluded from `INSTALLED_APPS` so the app is
safe even if the package is absent.)
