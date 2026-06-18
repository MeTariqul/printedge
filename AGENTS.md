# PrintEdge - Agent Commands

## Quality Checks
- **Python syntax**: `python -m py_compile core\invoice_pdf.py core\storage.py core\views.py core\models.py core\walkin_helpers.py core\notifications.py`
- **Template verification**: `python -c "import django; django.setup(); from django.template.loader import get_template; get_template('admin/walkin_order.html')"`
- **Lint for undefined names**: `python -m flake8 core/ --select=F821`
- **Type check**: `mypy core\notifications.py --ignore-missing-imports`
- **Run tests**: `python manage.py test core.tests.test_notifications`

## Hygiene
- Never commit scratch / debug scripts (`check_*.py`, `fix_*.py`, `verify_*.py`, `test_api.py`, `test_detail.py`) or local backups (`backup.json`, `printedge_backup.json`, `model_*.txt`). They are gitignored — remove them before committing.
- Commit messages use Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`).
- Push only when explicitly asked; never push secrets or `.env`.