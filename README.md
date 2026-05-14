# Print-Edge (PrintEase) - Enterprise Printing Business App

A comprehensive, production-ready Django web application built for a university-based print shop at Gono Bishwabidyalay.

## Features

### 🌟 Customer Portal
*   **Instant Live Quotes**: Upload a document and immediately see the cost based on configuration.
*   **File Support**: Upload PDF, DOC, DOCX, PPT, PPTX up to 50MB.
*   **Order Tracking**: Visual status pipeline (Pending → Printing → Quality Check → Ready → Delivered).
*   **Mobile-Ready UI**: Fully responsive with high-contrast Dark Mode.

### 💼 Walk-in / Offline Order System (Admin)
*   **Quick Walk-in Orders**: Handle physical customers effortlessly.
*   **No File Required Mode**: Manual page entry for hard-copy jobs.
*   **One-click Presets**: "Thesis Print", "Assignment", "Poster".
*   **Direct Receipt Printing**: Support for 80mm thermal receipts.

### 🛡️ Enterprise Security
*   Supabase PostgreSQL Row Level Security (RLS).
*   Django CSRF, XSS, and SQL Injection protections enabled.
*   Strict RBAC (Role-Based Access Control) for Super Admin, Manager, and Operators.
*   Automated inactivity session timeouts.

### 📊 Advanced Dashboard & CRM
*   **Real-time Activity Feed**: Watch orders flow in as they are placed.
*   **KPI Tracking**: Daily revenue, order volume, and active users.
*   **Inventory Tracking**: Toner, paper reams, and binding coils tracking.
*   **Dynamic Pricing Engine**: Automated bulk discounts and promo code applications.

## Technology Stack
*   **Backend Framework**: Django 5.x
*   **Database**: Supabase (PostgreSQL)
*   **Frontend**: Custom HTML/CSS with Glassmorphism, Bootstrap 5, Chart.js
*   **Storage**: Supabase Storage

## Installation

1. **Clone Repository**
```bash
git clone https://github.com/MeTariqul/printedge.git
cd printedge
```

2. **Setup Virtual Environment**
```bash
python -m venv venv
venv\Scripts\activate
```

3. **Install Dependencies**
```bash
pip install -r requirements.txt
```

4. **Environment Variables**
Create a `.env` file in the root directory:
```env
SECRET_KEY=your-django-secret
DEBUG=True
SUPABASE_URL=your-supabase-url
SUPABASE_KEY=your-supabase-service-key
```

5. **Run the Application**
```bash
python manage.py runserver
```

## System Architecture
*   `core/`: Core business logic, models, and user views.
*   `printease/`: Django project settings and root routing.
*   `templates/`: Master layout files containing the UI system.
*   `static/css/`: Advanced CSS variables and dynamic dark-mode configuration.

*Developed for Gono Bishwabidyalay.*