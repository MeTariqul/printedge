# Print-Edge SEO Score

> Search-engine optimization baseline and improvements.  
> Last updated: 2026-06-24

---

**Overall: 72/100 -> ~85/100 after fixes**

| Check | Before | After |
|-------|--------|-------|
| Unique `<title>` per page | Partial (`{% block title %}`) | Pass |
| Meta description | Fail | Pass (base + index) |
| Single H1 per page | Partial | Improved (404) |
| robots.txt | Fail | Pass (`/robots.txt`) |
| XML sitemap | Fail | Pass (`/sitemap.xml`) |
| Canonical URL | Fail | Pass (base template) |
| Open Graph tags | Fail | Pass (base template) |
| Twitter Card | Fail | Pass (`summary`) |
| Structured data | Fail | Pass (LocalBusiness on home) |
| 404 returns 404 | Pass | Pass |
| HTTPS | Deploy-dependent | Vercel SSL |
| Mobile-friendly | Pass | Pass (responsive) |
| Image alt text | Partial | Review marketing images |
| favicon | Fail | Pass |

## Public URLs in sitemap

- `/`, `/services/`, `/pricing/`, `/upload/`, `/contact/`

## Next steps

- Add per-page `meta_description` blocks on services, pricing, contact.
- Submit sitemap in Google Search Console after deploy.
- Add `og:image` pointing to logo asset.
