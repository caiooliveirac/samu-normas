#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."

echo "### Snapshot rápido — SAMU"
echo
echo "Pwd: $(pwd)"
echo
echo "#### Versões"
source .venv/bin/activate >/dev/null 2>&1 || true
python - <<'PY' || true
import os, django, sys
try:
  import pkg_resources as pr
  v = lambda p: pr.get_distribution(p).version
  import django
  print("Python:", sys.version.split()[0])
  print("Django:", django.get_version())
  for p in ["gunicorn","django-extensions","python-dotenv"]:
    try: print(f"{p}:", v(p))
    except: pass
except Exception as e:
  print("Versões: (venv não ativo?)", e)
PY
echo
echo "#### URLs (samu_q/urls.py)"
grep -n 'urlpatterns' -n samu_q/urls.py; sed -n '1,200p' samu_q/urls.py | sed -n '/urlpatterns = \[/,/\]/p'
echo
echo "#### URLs (questions/urls.py)"
sed -n '1,200p' questions/urls.py
echo
echo "#### STATIC settings"
python - <<'PY' || true
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','samu_q.settings')
django.setup()
from django.conf import settings
print("STATIC_URL:", settings.STATIC_URL)
print("STATIC_ROOT:", settings.STATIC_ROOT)
print("STATICFILES_DIRS:", settings.STATICFILES_DIRS)
PY
echo
echo "#### Models (counts)"
python manage.py shell -c "from questions.models import Question, Rule; print('Questions:', Question.objects.count()); print('Rules:', Rule.objects.count())" || true
