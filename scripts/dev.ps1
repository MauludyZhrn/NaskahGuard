$ErrorActionPreference = "Stop"

# Stop any stale server currently occupying port 8000 or 5173 so latest API routes are always active
foreach ($port in @(8000, 5173)) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    foreach ($c in $conns) {
        if ($c.OwningProcess -and $c.OwningProcess -gt 4) {
            Write-Host "Menghentikan proses lama pada port $port (PID $($c.OwningProcess))..."
            Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
        }
    }
}

Write-Host "Menjalankan Backend (127.0.0.1:8000, auto-reload) dan Frontend (127.0.0.1:5173)..."

$backendJob = Start-Process -FilePath "backend\.venv\Scripts\python.exe" `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000", "--reload", "--reload-dir", "app" `
    -WorkingDirectory "backend" -PassThru

$frontendJob = Start-Process -FilePath "npm.cmd" `
    -ArgumentList "run", "dev" `
    -WorkingDirectory "frontend" -PassThru

Write-Host "Backend PID: $($backendJob.Id) | Frontend PID: $($frontendJob.Id)"
Write-Host "Buka browser ke http://127.0.0.1:5173 . Tekan Enter untuk menghentikan kedua server."
Read-Host | Out-Null

Stop-Process -Id $backendJob.Id -ErrorAction SilentlyContinue
Stop-Process -Id $frontendJob.Id -ErrorAction SilentlyContinue
