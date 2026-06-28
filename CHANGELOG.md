# Print-Edge Changelog

> All notable changes to this project are documented here.  
> Format: [Conventional Commits](https://www.conventionalcommits.org/).  
> Last updated: 2026-06-28

---

## [Unreleased]

### Added
- `static/icons/logo.svg` — new vector SVG logo (document icon + wordmark) with PNG fallback.
- `static/icons/favicon.svg` — square SVG favicon (icon mark only, no text).
- Mobile bottom navigation bar wired into `base.html` for all pages.
- Premium admin dashboard redesign with `.dash-card`, `.dash-kpi-card` component system.
- Graphical effects on admin dashboard: ambient blurred background blobs, card shimmer sweep, gradient top border on hover, glass reflection on KPI icons, staggered card entrance animation.
- `.gitignore` patterns for scratch scripts (`regen*.py`, `.chunk*.done`, `nul`, `write_probe.txt`).

### Changed
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
- `templates/admin_base.html` — fixed Django template `{% with %}` syntax error (removed `==` expressions from `{% with %}` tags).
- Navbar backgrounds changed from translucent glassmorphism (`bg-white/75 backdrop-blur-xl`) to solid `bg-white` for full opacity on all platforms.
- Redundant "PrintEdge" text span from admin sidebar header (logo SVG already contains the wordmark).
- Temporary scratch files (`.chunk1.done`, `.chunk2.done`, `nul`, `regen_md.py`, `write_probe.txt`).

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
