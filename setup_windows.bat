@echo off
setlocal

if not exist venv\Scripts\python.exe (
    echo Creating project virtual environment...
    py -m venv venv
)

call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py makemigrations accounts business
python manage.py migrate
python manage.py seed_demo

echo.
echo Setup complete. Starting WorldLink Business Manager V1.1...
python manage.py runserver
