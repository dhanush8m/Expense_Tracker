Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "       Expense Tracker - Development Launcher      " -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Activate Virtual Environment
if (Test-Path "env\Scripts\Activate.ps1") {
    Write-Host "[1/3] Activating virtual environment..." -ForegroundColor Yellow
    & ".\env\Scripts\Activate.ps1"
} else {
    Write-Host "[ERROR] Virtual environment 'env' not found!" -ForegroundColor Red
    Write-Host "Make sure you are running this from the project root directory."
    Exit 1
}

Write-Host ""
# Step 2: Check Migration Status
Write-Host "[2/3] Checking database migration status..." -ForegroundColor Yellow
python manage.py showmigrations
if ($LASTEXITCODE -ne 0) {
    Write-Host "`n[NOTE] If a database connection error was reported above:" -ForegroundColor DarkYellow
    Write-Host "Please ensure your PostgreSQL service is started on port 5432.`n" -ForegroundColor DarkYellow
}

Write-Host ""
# Step 3: Run Server
Write-Host "[3/3] Starting Django server at http://127.0.0.1:8000/ ..." -ForegroundColor Green
Write-Host "Press Ctrl+C to stop the server.`n"
python manage.py runserver
