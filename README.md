# WorldLink Business Manager V1.1

A compact Django business operations system for WorldLink Security Systems.

## V1.1 additions

- Cleaner single-color navy interface with improved mobile layout and scrollbars.
- Centered branded login page.
- Company logo upload from System > Admin Panel > Company Settings.
- User profile images and full names.
- Top-right greeting menu with profile, settings and sign out.
- Dropdown chevron rotates up/down with menu state.
- Pure JavaScript dashboard charts (no CDN dependency).
- Separate create/edit pages instead of placing CRUD forms beside list tables.
- Edit/delete actions for customers, products, saved services and projects.
- Admin edit/delete for expenses.
- Admin create/edit/delete/deactivate user controls.
- Separate stock purchase entry page.
- Separate money account create/edit pages.
- Audit entries for important edits/deletes.

## Existing V1 database upgrade

Keep your existing `db.sqlite3`, `venv`, and uploaded `media` folder.
Replace the project code with the V1.1 files, activate your existing virtual environment, then run:

```powershell
python manage.py makemigrations accounts business
python manage.py migrate
python manage.py check
python manage.py runserver
```

If PowerShell blocks venv activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

## Fresh Windows setup

From the extracted project directory:

```powershell
.\setup_windows.bat
```

The setup script reuses `venv` if it already exists.

## Starter accounts on a fresh database

- Admin: `admin` / `admin123`
- Cashier: `cashier` / `cashier123`

Change starter passwords before real use.

## Branding

Go to **Admin Panel > Company Settings** to upload the company logo. It is used by the sidebar and login screen.

Go to **My Profile** or **Admin Panel > Users > Edit** to upload user profile images and set full names.

## Production media

Django serves uploaded media automatically only while `DEBUG=True`. On a VPS with Nginx, configure `/media/` to serve the project's `media` directory.
