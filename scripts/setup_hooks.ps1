# Install git pre-push hook for AI log submission (Windows PowerShell).
# Run once after cloning: powershell -ExecutionPolicy Bypass -File scripts\setup_hooks.ps1

$ErrorActionPreference = 'Stop'

$HookFile = '.git/hooks/pre-push'

# Git on Windows runs hooks via Git Bash, so the hook body must be bash and LF line endings.
$HookBody = "#!/usr/bin/env bash`n# Pre-push: sweep recent Antigravity / Gemini prompts, then submit AI logs.`nbash scripts/_pyrun.sh scripts/log_antigravity.py --auto || true`nbash scripts/_pyrun.sh scripts/submit_log.py || true`nexit 0`n"

$Utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText((Resolve-Path $HookFile -ErrorAction SilentlyContinue), $HookBody, $Utf8NoBom)

Write-Host "[ai-log] Git pre-push hook installed."

if (-not (Test-Path .ai-log)) { New-Item -ItemType Directory -Path .ai-log | Out-Null }
if (-not (Test-Path .ai-log/.gitkeep)) { New-Item -ItemType File -Path .ai-log/.gitkeep | Out-Null }

Write-Host "[ai-log] Setup complete. Configure AI_LOG_SERVER in your .env file."

