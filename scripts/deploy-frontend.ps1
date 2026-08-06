# ============================================
# Cloud Run Deploy Script for Next.js Frontend
# ============================================

$ErrorActionPreference = "Stop"

# Auto-add Google Cloud SDK path if gcloud is not in PATH
if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    $gcloudPaths = @(
        "C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin",
        "C:\Program Files\Google\Cloud SDK\google-cloud-sdk\bin",
        "$env:LOCALAPPDATA\Google\Cloud SDK\google-cloud-sdk\bin"
    )
    foreach ($p in $gcloudPaths) {
        if (Test-Path $p) {
            $env:PATH = "$p;$env:PATH"
            break
        }
    }
}

Write-Host "[INFO] Deploying Frontend (Next.js) to Cloud Run (service: my-frontend-service)..." -ForegroundColor Green

# Set working directory to frontend directory
Push-Location frontend

try {
    gcloud run deploy my-frontend-service `
      --source . `
      --region asia-southeast1 `
      --allow-unauthenticated `
      --set-env-vars "NEXT_PUBLIC_API_BASE_URL=https://my-app-service-78389130178.asia-southeast1.run.app"

    if ($LASTEXITCODE -eq 0) {
        Write-Host "[SUCCESS] Frontend deployed successfully to Cloud Run!" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] Frontend deployment failed!" -ForegroundColor Red
    }
} finally {
    Pop-Location
}
