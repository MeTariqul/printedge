# Print-Edge

> **Enterprise Printing Business App** · Django · Supabase · Dark Mode  
> Last updated: 2026-06-24 · [CHANGELOG](./CHANGELOG.md) · [Deploy Guide](./DEPLOY.md)

---

## Table of Contents

1. [Overview](#overview)  
2. [Features](#features)  
   2.1 [Customer Portal](#customer-portal)  
   2.2 [Walk-in Orders](#walk-in-orders)  
   2.3 [Enterprise Security](#enterprise-security)  
   2.4 [Dashboard & CRM](#dashboard--crm)  
3. [Technology Stack](#technology-stack)  
4. [Local Installation](#local-installation)  
5. [Environment Variables](#environment-variables)  
6. [Quality Checks](#quality-checks)  
7. [Deployment](#deployment)  
8. [Contributing](#contributing)  
9. [QA & Reports](#qa--reports)  

---

## Overview

Print-Edge is a production-ready Django web application for a campus print shop.
Delivery convenience point: **Gono Bishwabidyalay** (not affiliated with the university).

---

## Features

### Customer Portal
- **Instant Live Quotes** — upload a document and immediately see the cost.
- **File Support** — PDF, DOC, DOCX, PPT, PPTX up to 50 MB.
- **Order Tracking** — Pending → Printing → Quality Check → Ready → Delivered.
- **Mobile-Ready UI** — responsive high-contrast Dark Mode.

### Walk-in Orders
- **Quick Walk-in Orders** — handle physical customers effortlessly.
- **No File Required Mode** — manual page entry for hard-copy jobs.
- **One-click Presets** — "Thesis Print", "Assignment", "Poster".
- **80 mm Thermal Receipts** — direct ESC/POS receipt printing.

### Enterprise Security
- Supabase PostgreSQL **Row Level Security (RLS)**.
- Django CSRF, XSS, and SQL Injection protections enabled.
- **Auth Rate Limiting** — 5 failures / 5 minutes per IP.
- **Magic-byte Upload Validation** — prevents extension-only bypass.
- Strict **RBAC**: Super Admin, Manager, Operator.
- Automated inactivity session timeouts.

### Dashboard & CRM
- **Real-time Activity Feed**.
- **KPI Tracking** — daily revenue, order volume, active users.
- **Inventory Tracking** — toner, paper, binding coils.
- **Dynamic Pricing Engine** — bulk discounts + promo codes.
- **System Status Page** — live checks for 6 services.

---

## Technology Stack

| Layer | Technology |
|---|---|
| Backend framework | Django 5.x |
| Database | Supabase (PostgreSQL) |
| Frontend | HTML + Tailwind + Bootstrap 5 + Chart.js |
| Storage | Supabase Storage (S3-compatible) |
| PDF generation | ReportLab |
| Scheduled jobs | Vercel Cron |
| Static files | WhiteNoise |
| Auth | Django Auth + custom EmailBackend |

---

## Local Installation



Browser: **http://127.0.0.1:8000/**

---

## Environment Variables

Create a  file in the project root using  as a template:

| Variable | Purpose | Required |
|---|---|---|
| SECRET_KEY | Django signing key | Yes |
| DEBUG | True for dev; False in production | Yes |
| DATABASE_URL | Supabase Postgres pooler URL | Yes |
| ALLOWED_HOSTS | Comma-separated allowed hosts | Yes |
| AWS_ACCESS_KEY_ID | Supabase service role key | Yes |
| AWS_SECRET_ACCESS_KEY | Same service role key | Yes |
| AWS_S3_ENDPOINT_URL | S3-compatible endpoint | Yes |
| AWS_S3_REGION_NAME | auto | Yes |
| SUPABASE_STORAGE_BUCKET | order-files | Yes |
| DEFAULT_FROM_EMAIL | Outbound sender address | Yes |
| EMAIL_HOST | SMTP host | optional |
| EMAIL_HOST_USER | SMTP username | optional |
| EMAIL_HOST_PASSWORD | SMTP app password | optional |
| CRON_SECRET | Bearer token for purge-file cron | Yes |
| ADMIN_EMAILS | Comma-separated super-admin addresses | Yes |

---

## Quality Checks



---

## Deployment

Read the full guide in **[DEPLOY.md](./DEPLOY.md)**.

### Pre-deploy checklist



> **Security reminder:** never commit , , or any real credentials to version control.

---

## Contributing

- **Hygiene first** — remove scratch/debug scripts and local backups before committing. Follow the rules in [AGENTS.md](./AGENTS.md).
- **Commit messages** — use [Conventional Commits](https://www.conventionalcommits.org/): , , , , .
- **Push policy** — push only when explicitly asked; never push secrets or .
- **Before push** — run the quality checks listed in [AGENTS.md](./AGENTS.md).

---

## QA & Reports

All reports are in [](./qa_reports/).

| File | Description |
|------|-------------|
| [BUG_REPORT.md](./qa_reports/BUG_REPORT.md) | Bugs sorted by severity |
| [FIX_REPORT.md](./qa_reports/FIX_REPORT.md) | Fix summaries with files changed |
| [ACCESSIBILITY_REPORT.md](./qa_reports/ACCESSIBILITY_REPORT.md) | WCAG 2.1 AA audit |
| [SECURITY_REPORT.md](./qa_reports/SECURITY_REPORT.md) | OWASP Top 10 review |
| [PERFORMANCE_REPORT.md](./qa_reports/PERFORMANCE_REPORT.md) | Lighthouse targets and bottlenecks |
| [SEO_REPORT.md](./qa_reports/SEO_REPORT.md) | SEO score and improvements |
| [COMPATIBILITY_REPORT.md](./qa_reports/COMPATIBILITY_REPORT.md) | Browser + device matrix |
| [AUDIT_2026-05-24.md](./qa_reports/AUDIT_2026-05-24.md) | Brand + functional + security audit |
| [FINAL_VERDICT.md](./qa_reports/FINAL_VERDICT.md) | Production-readiness verdict |

---

*Delivery convenience point: Gono Bishwabidyalay (not affiliated).*
