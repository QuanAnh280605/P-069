# ============================================
# Cloud Run Deploy Script using .env.production
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

if (-not (Test-Path ".env.production")) {
    Write-Host "[ERROR] .env.production file not found! Copy from .env.production.example first." -ForegroundColor Red
    exit 1
}

Write-Host "[INFO] Reading configuration from .env.production..." -ForegroundColor Cyan

# Read non-empty, non-comment lines and join with semicolon delimiter for gcloud
$lines = Get-Content .env.production | Where-Object { $_ -and -not $_.Trim().StartsWith("#") }
$envVars = $lines -join ";"

Write-Host "[INFO] Deploying to Cloud Run (service: my-app-service)..." -ForegroundColor Green

# Use ^;^ custom delimiter so values with commas (like CORS_ORIGINS) are parsed correctly
gcloud run deploy my-app-service `
  --source . `
  --region asia-southeast1 `
  --allow-unauthenticated `
  --set-env-vars "^;^$envVars"

if ($LASTEXITCODE -eq 0) {
    Write-Host "[SUCCESS] Deployment completed successfully!" -ForegroundColor Green
} else {
    Write-Host "[ERROR] Deployment failed!" -ForegroundColor Red
}
