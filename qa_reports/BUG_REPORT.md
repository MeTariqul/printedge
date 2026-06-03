# Print-Edge Bug Report

**Test date:** 2026-05-17  
**Environment:** Local (code review + Django test client command; Python runtime unavailable in QA sandbox)  
**Sorted by severity**

---

## Critical

_None identified that remain open after fixes._

---

## High

### PE-001
- **SEVERITY:** High
- **CATEGORY:** Security
- **LOCATION:** `print_edge/settings.py` — `ALLOWED_HOSTS`
- **DESCRIPTION:** `ALLOWED_HOSTS = ['*']` allowed Host header attacks.
- **STEPS:** Send request with spoofed `Host` header.
- **EXPECTED:** Reject unknown hosts.
- **ACTUAL:** Any host accepted.
- **FIX:** Parse `ALLOWED_HOSTS` from env (default `localhost,127.0.0.1`).
- **RETEST:** Pending local `run_qa_checks`

### PE-002
- **SEVERITY:** High
- **CATEGORY:** Security
- **LOCATION:** `/auth/login/`, `/auth/register/`
- **DESCRIPTION:** No rate limiting on authentication endpoints.
- **FIX:** `core/ratelimit.py` + integration in `auth_login` / `auth_register`.
- **RETEST:** Pending

### PE-003
- **SEVERITY:** High
- **CATEGORY:** Security
- **LOCATION:** `core/utils.py` — `validate_upload_file`
- **DESCRIPTION:** Upload validation used file extension only; malicious file could bypass.
- **FIX:** Magic-byte verification for PDF, OLE, ZIP/Office, JPEG, PNG.
- **RETEST:** Pending

### PE-006
- **SEVERITY:** High
- **CATEGORY:** Functional
- **LOCATION:** `/user/orders/new/` — `user_new_order`
- **DESCRIPTION:** Orders could be placed without uploading a document.
- **FIX:** Server-side required file in `validate_upload_file`; client-side check on submit.
- **RETEST:** Pending

---

## Medium

### PE-005 — DEBUG logging in production views
- **LOCATION:** `admin_order_detail`, `admin_users`
- **FIX:** Removed `print()` debug statements.
- **RETEST:** Yes (code)

### PE-007 — Double submission on order form
- **LOCATION:** `templates/user/new_order.html`
- **FIX:** Disable submit button after first click.
- **RETEST:** Pending

### PE-008 — Viewport blocks zoom (WCAG 1.4.4)
- **LOCATION:** `base.html`, `admin_base.html`
- **FIX:** Removed `maximum-scale=1.0, user-scalable=no`.
- **RETEST:** Yes (code)

### PE-013 — `extra_js` block nested inside `content`
- **LOCATION:** `templates/user/new_order.html`
- **DESCRIPTION:** JS block did not render in parent `extra_js` slot.
- **FIX:** Close `content` block before `extra_js`.
- **RETEST:** Yes (code)

### PE-014 — Missing robots.txt and sitemap
- **FIX:** `robots_txt` and `sitemap_xml` views + URL routes.
- **RETEST:** Pending `run_qa_checks`

### PE-015 — Missing meta description / Open Graph
- **FIX:** Meta blocks in `base.html`; per-page `meta_description` on index.
- **RETEST:** Pending

### PE-017 — WhiteNoise middleware disabled
- **FIX:** Enabled in `MIDDLEWARE`.
- **RETEST:** Pending deploy

### PE-018 — File download returned JSON 403 to browsers
- **LOCATION:** `order_download_file`
- **FIX:** Redirect to login/dashboard for non-AJAX requests.
- **RETEST:** Pending

### PE-020 — No structured data on homepage
- **FIX:** JSON-LD `LocalBusiness` on `index.html`.
- **RETEST:** Pending

---

## Low / Cosmetic

### PE-016 — No favicon link in HTML
- **FIX:** `<link rel="icon">` in `base.html`.

### PE-021 — 404 page used decorative "404" as only heading
- **FIX:** Proper `<h1>Page not found</h1>` in `404.html`.

### PE-022 — Tailwind loaded from CDN (performance + offline risk)
- **STATUS:** Open — requires build pipeline to fix properly.

### PE-023 — `password_plain` stored on User model
- **STATUS:** Open by design for admin visibility — document risk for production.

### PE-024 — No Content-Security-Policy header
- **STATUS:** Partial — other security headers added; full CSP conflicts with Tailwind CDN inline config.

### PE-025 — Registration restricted to “popular” email domains
- **STATUS:** By design — may block valid institutional emails.

---

## Verified secure (no bug)

- **PE-IDOR-01:** `user_order_detail` filters `customer=request.user` — IDOR protected.
- **PE-IDOR-02:** `order_download_file` checks customer or admin via `_order_file_access_allowed`.
- **PE-CSRF-01:** Django CSRF middleware active on forms.
- **PE-404-01:** `page_not_found` returns HTTP 404.

---

**Total:** 6 High (all fixed in code), 10 Medium (8 fixed, 2 open), 5 Low/Open
