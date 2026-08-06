# ============================================
# Run Alembic Migration against Production Database (Supabase)
# ============================================

$ErrorActionPreference = "Stop"

if (-not (Test-Path ".env.production")) {
    Write-Host "[ERROR] File .env.production not found!" -ForegroundColor Red
    exit 1
}

# Find DATABASE_URL in .env.production
$dbUrlLine = Get-Content .env.production | Where-Object { $_ -match "^DATABASE_URL=" }

if (-not $dbUrlLine) {
    Write-Host "[ERROR] DATABASE_URL not found in .env.production!" -ForegroundColor Red
    exit 1
}

$prodDbUrl = $dbUrlLine.Split("=", 2)[1].Trim()

Write-Host "[INFO] Running 'alembic upgrade head' on Production DB..." -ForegroundColor Cyan

# Override DATABASE_URL temporarily for alembic
$oldDbUrl = $env:DATABASE_URL
$env:DATABASE_URL = $prodDbUrl

try {
    alembic upgrade head
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[SUCCESS] Migration completed on Production DB!" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] Migration failed! Check DATABASE_URL password in .env.production" -ForegroundColor Red
        exit 1
    }
} finally {
    # Restore original environment variable
    if ($oldDbUrl) {
        $env:DATABASE_URL = $oldDbUrl
    } else {
        Remove-Item Env:\DATABASE_URL -ErrorAction SilentlyContinue
    }
}
