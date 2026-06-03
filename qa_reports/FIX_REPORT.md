# Print-Edge Fix Report

| ID | Severity | Summary | Files changed | Retest |
|----|----------|---------|---------------|--------|
| PE-001 | High | Restrict ALLOWED_HOSTS | `print_edge/settings.py`, `.env.example` | Pending |
| PE-002 | High | Auth rate limiting | `core/ratelimit.py`, `core/views.py`, `settings.py` | Pending |
| PE-003 | High | Magic-byte upload validation | `core/utils.py` | Pending |
| PE-005 | Medium | Remove DEBUG prints | `core/views.py` | Yes |
| PE-006 | High | Require upload file | `core/utils.py`, `core/views.py`, `new_order.html` | Pending |
| PE-007 | Medium | Prevent double submit | `templates/user/new_order.html` | Pending |
| PE-008 | Medium | Allow pinch-zoom | `base.html`, `admin_base.html` | Yes |
| PE-009 | Medium | Skip to main content link | `base.html`, `admin_base.html` | Yes |
| PE-010 | Medium | Focus-visible outlines | `base.html`, `admin_base.html` | Yes |
| PE-011 | Medium | prefers-reduced-motion | `base.html`, `admin_base.html` | Yes |
| PE-012 | Medium | Label ban/password fields | `admin/users.html` | Yes |
| PE-013 | Medium | Fix template block nesting | `user/new_order.html` | Yes |
| PE-014 | Medium | robots.txt + sitemap | `core/views.py`, `core/urls.py` | Pending |
| PE-015 | Medium | SEO meta tags | `base.html`, `index.html` | Pending |
| PE-016 | Low | Favicon link | `base.html` | Yes |
| PE-017 | Medium | Enable WhiteNoise | `settings.py` | Pending |
| PE-018 | Medium | Download forbidden UX | `admin_ops_views.py` | Pending |
| PE-020 | Medium | Structured data | `index.html` | Pending |
| PE-021 | Low | 404 heading semantics | `404.html` | Yes |

## New tooling

| Artifact | Purpose |
|----------|---------|
| `core/management/commands/seed_qa_users.py` | QA accounts per role |
| `core/management/commands/run_qa_checks.py` | Automated smoke tests |
| `core/middleware.py` → `SecurityHeadersMiddleware` | X-Frame-Options, Referrer-Policy, etc. |

## Before / after highlights

**Upload security:** Extension-only → extension + magic-byte verification.  
**Auth:** Unlimited attempts → 5 failures / 5 minutes per IP (cache-based).  
**Hosts:** `*` → configurable allowlist.  
**Accessibility:** Blocked zoom → standard viewport; added skip link, focus rings, reduced motion.  
**SEO:** No robots/sitemap/meta → full baseline SEO on public pages.
