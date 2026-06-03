# PrintEdge - Agent Commands

## Quality Checks
- **Python syntax**: `python -m py_compile core\invoice_pdf.py core\storage.py core\views.py core\models.py core\walkin_helpers.py core\notifications.py`
- **Template verification**: `python -c "import django; django.setup(); from django.template.loader import get_template; get_template('admin/walkin_order.html')"`
- **Lint for undefined names**: `python -m flake8 core/ --select=F821`
- **Type check**: `mypy core\notifications.py --ignore-missing-imports`
- **Run tests**: `python manage.py test core.tests.test_notifications`