# Print-Edge Security Report

## OWASP Top 10 Summary

| Risk | Status | Notes |
|------|--------|-------|
| Broken Access Control | **Mitigated** | Order detail/download scoped to owner or admin; admin routes use decorators |
| Cryptographic Failures | **Partial** | Django password hashing; `password_plain` field remains a risk |
| Injection | **Low risk** | Django ORM; search uses parameterized queries |
| Insecure Design | **Improved** | Rate limiting on auth added |
| Security Misconfiguration | **Improved** | ALLOWED_HOSTS tightened; headers middleware; DEBUG must be False in prod |
| Vulnerable Components | **Not run** | Run `pip-audit -r requirements.txt` locally |
| Auth Failures | **Improved** | Rate limit + Django validators |
| Logging | **OK** | AuditLog on login; no passwords in logs |
| SSRF | **N/A** | No user-controlled URL fetch |

## Headers (after fix)

| Header | Status |
|--------|--------|
| X-Content-Type-Options | Present (`nosniff`) |
| X-Frame-Options | Present (`DENY`) |
| X-XSS-Protection | Present |
| Referrer-Policy | Present |
| Permissions-Policy | Present |
| Strict-Transport-Security | Production only (`DEBUG=False`) |
| Content-Security-Policy | **Not set** — conflicts with Tailwind CDN + inline scripts |

## Cookie security

| Flag | Session | CSRF |
|------|---------|------|
| HttpOnly | Yes | Yes |
| Secure | When `DEBUG=False` | When `DEBUG=False` |
| SameSite | Lax | Lax |

## CSRF

- Middleware enabled on all POST forms.
- Cron endpoint uses secret token (not CSRF) — correct for machine callers.

## CORS

- Same-origin app; no wildcard CORS configured.

## Remaining recommendations

1. Set `CRON_SECRET` in production; never commit to git.
2. Use strong `SECRET_KEY` and `DEBUG=False` on Vercel.
3. Set `ALLOWED_HOSTS` to your Vercel domain(s).
4. Consider removing `password_plain` or encrypting at rest.
5. Add Redis cache on Vercel for distributed rate limiting.
6. Run `pip-audit` before each release.
