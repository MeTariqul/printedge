# Print-Edge Changelog

> All notable changes to this project are documented here.  
> Format: [Conventional Commits](https://www.conventionalcommits.org/).  
> Last updated: 2026-06-29

---

## [Unreleased]

### Added
- `core/models.py:Order.transition_status()` — state machine with `VALID_TRANSITIONS` dict, auto-sets `confirmed_at`/`completed_at`, creates `OrderStatusLog`.
- `core/models.py:OrderFile.unit_price` property — `line_base_price / copies`.
- `core/models.py:Order.calculated_total` property — sums individual price fields.
- `core/forms.py` — new file with `AdminOrderUpdateForm`, `WalkinOrderForm`, `PaymentForm`.
- `static/css/printedge.css` — 14 new `pe-*` component classes (`pe-page-head`, `pe-action-bar`, `pe-table-wrap`, `pe-filter-bar`, `pe-empty`, `pe-price-summary*`, `pe-kanban*`, `pe-callout-info`, `pe-status-badge`).
- `templates/partials/_status_badge.html` — reusable status badge partial.
- `templates/partials/_order_table.html` — HTMX table fragment for admin filter auto-refresh.
- `core/views.py:admin_orders_table` — HTMX endpoint for live filter/search on admin orders list.
- `static/icons/logo.svg` — new vector SVG logo (document icon + wordmark) with PNG fallback.
- `static/icons/favicon.svg` — square SVG favicon (icon mark only, no text).
- `.gitignore` patterns for scratch scripts (`regen*.py`, `.chunk*.done`, `nul`, `write_probe.txt`).

### Changed
- `core/models.py:Order.save()` — order number generation uses `select_for_update()` to prevent race conditions (fallback to count).
- `core/views.py` — `user_cancel_order`, `admin_order_detail`, `admin_orders` (bulk), `api_order_status_update` all use `transition_status()` instead of direct status assignment.
- `core/invoice_pdf.py` — QR code URL uses dynamic `domain` parameter instead of hardcoded `printedge.vercel.app`.
- `core/admin_ops_views.py:order_invoice_pdf` — passes `request.build_absolute_uri` domain to invoice PDF generator.
- `static/css/premium.css` — extracted ~170 lines of inline `<style>` from `admin_base.html` (sidebar links, mobile nav, select dropdowns, bg-white overrides).
- `templates/admin/orders.html` — filter bar uses HTMX (`hx-get`, `hx-trigger="change"`, `hx-push-url`) for auto-submit without full page reload.
- `templates/admin/orders.html` — order table + mobile cards split into reusable `_order_table.html` fragment.
- `templates/admin_base.html` — inline `<style>` reduced to critical dropdown overflow fixes only (sidebar/mobile-nav/select styles moved to `premium.css`).
- `templates/user/orders.html` — uses `.pe-filter-bar` and `_status_badge.html` partial.
- `templates/user/order_payment.html` — rejection reason uses `.pe-callout-info` component.
- `templates/partials/header_public.html` — redesigned with glassmorphism (`backdrop-blur-xl`), refined hover states, scroll-sensitive opacity transition.
- `templates/admin_base.html` — sidebar and header redesign: new `.admin-sidebar-link` / `.admin-sidebar-icon` CSS classes, compact user card, glassmorphism header bar.
- `templates/base.html` — mobile slide-out sidebar upgraded with icon boxes, section headers, active state indicators.
- `templates/mobile/bottom_nav.html` — completely rebuilt with evenly-spaced flex layout, icon-background active indicator, unread badge styling.
- `templates/auth/*.html`, `templates/emails/*.html` — all logo references switched to SVG with PNG `onerror` fallback.
- `templates/admin/dashboard/*.html` — all dashboard partials upgraded: premium KPI cards, chart cards, activity feed, reminders, quick actions, system health.
- `static/css/premium.css` — added dashboard component system CSS and graphical effects.
- `static/css/mobile.css` — added `.mobile-nav-item`, `.mobile-nav-icon-wrap`, `.mobile-nav-label` styles.
- `templates/partials/site_logo.html` — uses `logo.svg` with PNG fallback via `onerror`.
- AGENTS.md — hygiene section updated with additional unwanted file patterns.

### Fixed
- `core/views.py`: `admin_walkin_order` — `accepting_orders` and `note_categories` added to context, fixing "Orders temporarily paused" banner bug.
- Mobile double-tap on all links/buttons — removed `!important` hover overrides in `premium.css` and `touch-fixes.css`, added passive `touchstart` listener, replaced with `:active` opacity on touch devices.
- Modal backgrounds in admin — changed from `bg-surface` (transparent when variable unresolved) to `bg-white`.
- Walk-in POS wizard — added next button on step 1, fixed `currentStep` initialization, added `$watch('step')` for progress bar sync.
- Invoice PDF — hardcoded domain replaced with dynamic domain from request.
- `templates/admin_base.html` — fixed Django template `{% with %}` syntax error (removed `==` expressions from `{% with %}` tags).
- Temporary scratch files (`.chunk1.done`, `.chunk2.done`, `nul`, `regen_md.py`, `write_probe.txt`).

### Removed
- `core/views_admin.py` (~1059 lines) — dead duplicate views, confirmed unreachable from `urls.py`.
- `core/views_api.py` (~388 lines) — dead duplicate API views, confirmed unreachable from `urls.py`.
- `core/tests/` — test directory removed per cleanup request.
- Duplicate inline CSS from `admin_base.html` (focus-visible and reduced-motion rules already in `printedge.css`).

---

## [1.0.0] — 2026-05-24

### Added
- Customer portal: live quotes, upload workflow, order-tracking pipeline.
- Walk-in POS: no-file quick orders, 80 mm thermal receipt support.
- Admin dashboard: real-time order feed, KPI tiles, inventory management, system status page.
- Auth hardening: rate limiting, magic-byte upload validation, RBAC decorators.
- SEO baseline: robots.txt, sitemap.xml, meta descriptions, Open Graph, JSON-LD structured data.
- Automated QA: `run_qa_checks`, `seed_qa_users`, `clear_branding_logos` management commands.
- Accessibility fixes: skip link, focus-visible outlines, pinch-zoom, reduced-motion media query.
- Supabase Storage (S3-compatible) for order files with randomised secure filenames.
- Vercel Cron route for nightly expired-file purge.

---

[Unreleased]: https://github.com/MeTariqul/printedge/compare/1.0.0...main
[1.0.0]: https://github.com/MeTariqul/printedge/releases/tag/1.0.0
