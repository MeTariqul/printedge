#!/bin/bash
set -e
python3 -m pip install -r requirements.txt --break-system-packages
if [ -f ./tailwindcss ]; then
  ./tailwindcss -i ./static/src/input.css -o ./static/css/main.css --minify
elif command -v npm >/dev/null 2>&1; then
  npm install && npm run build:css
fi
python3 manage.py migrate --noinput
python3 manage.py collectstatic --noinput
