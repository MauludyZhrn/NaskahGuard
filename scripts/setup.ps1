$ErrorActionPreference = "Stop"
Write-Host "Menyiapkan NaskahGuard di Windows..."

if (-not (Test-Path "backend\.venv")) {
    python -m venv backend\.venv
}

backend\.venv\Scripts\python.exe -m pip install --upgrade pip
backend\.venv\Scripts\pip.exe install -r backend\requirements.txt -r backend\requirements-dev.txt

if (-not (Test-Path "backend\.env")) {
    Copy-Item "backend\.env.example" "backend\.env"
}

Push-Location backend
.\.venv\Scripts\alembic.exe upgrade head
Pop-Location

Push-Location frontend
npm install
Pop-Location

Write-Host "Setup selesai. Jalankan .\scripts\dev.ps1 untuk memulai aplikasi."
