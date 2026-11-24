$ErrorActionPreference = "Stop"
Write-Host "Menjalankan Backend (127.0.0.1:8000) dan Frontend (127.0.0.1:5173)..."

$backendJob = Start-Process -FilePath "backend\.venv\Scripts\python.exe" `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000" `
    -WorkingDirectory "backend" -PassThru

$frontendJob = Start-Process -FilePath "npm.cmd" `
    -ArgumentList "run", "dev" `
    -WorkingDirectory "frontend" -PassThru

Write-Host "Backend PID: $($backendJob.Id) | Frontend PID: $($frontendJob.Id)"
Write-Host "Buka browser ke http://127.0.0.1:5173 . Tekan Enter untuk menghentikan kedua server."
Read-Host | Out-Null

Stop-Process -Id $backendJob.Id -ErrorAction SilentlyContinue
Stop-Process -Id $frontendJob.Id -ErrorAction SilentlyContinue
