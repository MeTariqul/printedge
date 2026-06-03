# Print-Edge Performance Report

**Note:** Lighthouse not executed in QA sandbox (Python unavailable). Metrics below are code-based estimates.

## Expected bottlenecks

| Issue | Impact | Recommendation |
|-------|--------|----------------|
| Tailwind CDN script | Render-blocking | Build Tailwind locally; purge unused CSS |
| Google Fonts | Extra RTT | `font-display: swap` already on link; subset fonts |
| Alpine.js defer | Low | OK |
| Chart.js (admin only) | Medium on dashboard | Load only on dashboard route |
| No image dimensions | CLS risk | Add `width`/`height` on hero images |
| WhiteNoise (now enabled) | Positive | Run `collectstatic` on deploy |

## Target metrics (Slow 3G) — to verify locally

| Metric | Target | Expected current |
|--------|--------|------------------|
| FCP | < 2s | ~2.5–4s (CDN Tailwind) |
| LCP | < 3s | ~3–5s |
| TTI | < 4s | ~4–6s |
| CLS | < 0.1 | ~0.05–0.15 |
| TBT | < 300ms | ~200–500ms |

## Optimizations applied

- Enabled WhiteNoise for static file compression/serving.

## Recommended follow-up

1. Self-host Tailwind CSS (remove cdn.tailwindcss.com).
2. Lazy-load below-fold images (`loading="lazy"`).
3. Preconnect only to fonts CDN (already present).
4. Bundle size audit not applicable (no npm frontend).

## How to measure

```bash
python manage.py runserver
# Chrome DevTools → Lighthouse → Performance + Slow 3G
```
