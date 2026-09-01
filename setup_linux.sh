#!/usr/bin/env bash
set -e

if [ ! -x "venv/bin/python" ]; then
  echo "Creating project virtual environment..."
  python3 -m venv venv
fi

source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py makemigrations accounts business
python manage.py migrate
python manage.py seed_demo
python manage.py runserver 0.0.0.0:8000
