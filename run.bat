@echo off
echo ===================================================
echo        Expense Tracker - Development Launcher
echo ===================================================
echo.

:: Step 1: Check and activate the virtual environment
if exist "env\Scripts\activate.bat" (
    echo [1/3] Activating virtual environment...
    call env\Scripts\activate.bat
) else (
    echo [ERROR] Virtual environment 'env' was not found!
    echo Please ensure you are running this file from the project root.
    echo.
    pause
    exit /b 1
)

echo.
:: Step 2: Check database migration status
echo [2/3] Checking database migration status...
python manage.py showmigrations
if errorlevel 1 (
    echo.
    echo [NOTE] If you saw a connection error above:
    echo Please ensure PostgreSQL service is started and accepting connections.
    echo.
)

echo.
:: Step 3: Start the Django development server
echo [3/3] Starting Django server at http://127.0.0.1:8000/ ...
echo Press Ctrl+C in this window anytime to stop the server.
echo ===================================================
echo.
python manage.py runserver

pause
