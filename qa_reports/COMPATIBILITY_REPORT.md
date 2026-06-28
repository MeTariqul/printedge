# Print-Edge Compatibility Report

> Browser, device, and network coverage matrix.  
> Last updated: 2026-06-24

---

## Test matrix (code + template audit)

| Area | Coverage | Result |
|------|----------|--------|
| Chrome / Edge (Chromium) | Primary target | Expected pass |
| Firefox | Tailwind CDN + Alpine | Expected pass |
| Safari | iOS viewport-fit | Expected pass (verify safe-area) |
| Responsive breakpoints | Tailwind `sm/md/lg` | Pass (fluid layouts) |
| Dark theme | Fixed dark | Consistent |
| PWA manifest | `/manifest.json` | Pass |
| Service worker | None | Offline not supported (by design) |
| i18n | English only | N/A |
| Timezone | Asia/Dhaka | Configured in settings |
| Currency | ৳ BDT | Used in templates |

## Breakpoints to verify manually

- 2560×1440, 1920×1080, 1440×900, 1366×768
- 1024×768, 768×1024, 834×1112
- 430×932, 375×812, 360×640

**Focus pages:** `/`, `/user/orders/new/`, `/admin/orders/`, `/admin/orders/walkin/`

## Network

| Condition | Expected |
|-----------|----------|
| Fast WiFi | Good |
| Slow 3G | Slow FCP (Tailwind CDN) |
| Offline | No PWA cache — error pages |

## OS tested

- Windows 10/11 (QA environment)

## Device features

- Touch: Mobile bottom nav + 56px FAB targets
- Keyboard: Skip link + focus rings added
- 200% zoom: Enabled after viewport fix
