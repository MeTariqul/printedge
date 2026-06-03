# Print-Edge Accessibility Report

**Target:** WCAG 2.1 AA  
**Method:** Code audit + planned Lighthouse (run locally after `python manage.py runserver`)

## Score estimate

| Page | Before | After (estimated) |
|------|--------|-------------------|
| Home `/` | ~75 | ~88 |
| New order | ~70 | ~85 |
| Admin dashboard | ~72 | ~82 |

*Run Lighthouse Accessibility in Chrome DevTools for official scores.*

## Fixes applied

| Criterion | Issue | Fix |
|-----------|-------|-----|
| 1.4.4 Resize text | `user-scalable=no` | Removed from viewport meta |
| 2.4.1 Bypass blocks | No skip link | Added skip link to main |
| 2.4.7 Focus visible | Weak focus | `:focus-visible` outline styles |
| 2.3.3 Animation | No reduced motion | `@media (prefers-reduced-motion)` |
| 1.3.1 Info & relationships | Unlabeled admin inputs | `sr-only` labels on ban/password |
| 2.4.6 Headings | 404 decorative h1 | Semantic "Page not found" h1 |
| 4.1.2 Name, role | Messenger/WhatsApp | Already had `aria-label` |

## Remaining gaps

- Chart.js / ApexCharts: ensure data tables or ARIA alternatives for screen readers.
- Color contrast audit on `text-neutral-500` on black - verify 4.5:1 ratio.
- Add `lang` attributes if Bengali content added later.

## Compliance level

**Conditional AA** - blockers addressed; manual screen reader pass recommended before launch.
