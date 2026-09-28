param(
    [int]$Port = 8060,
    [string]$DataDir = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $DataDir) {
    $DataDir = Join-Path $repoRoot "runtime/manual-demo-2026-09-28"
}
$demoRoot = [System.IO.Path]::GetFullPath($DataDir)
New-Item -ItemType Directory -Path $demoRoot -Force | Out-Null
if (-not (Test-Path (Join-Path $repoRoot "frontend/dist/index.html"))) {
    throw "Frontend absent. Run: npm --prefix frontend run build"
}

$pythonExe = Join-Path $repoRoot ".venv/Scripts/python.exe"
if (-not (Test-Path $pythonExe)) { $pythonExe = "python" }
$env:CASE_DB_PATH = Join-Path $demoRoot "cases.sqlite"
$env:CHECKPOINT_DB_PATH = Join-Path $demoRoot "checkpoints.sqlite"
$env:UPLOAD_DIR = Join-Path $demoRoot "uploads"
$env:EVENT_LOG_PATH = Join-Path $demoRoot "events.jsonl"
$env:PORTFOLIO_STATE_PATH = Join-Path $demoRoot "portfolio.json"
$env:LLM_PROVIDER = "manual"
$env:JEV_ENABLED = "false"
$env:LANGSMITH_TRACING = "false"
$env:OPENAI_API_KEY = ""
$env:TYPESAFE_API_KEY = ""
$env:LANGSMITH_API_KEY = ""
$env:QDRANT_URL = ""
$env:QDRANT_API_KEY = ""

Set-Location $repoRoot
Write-Host "Demo locale synthetique : http://127.0.0.1:$Port"
Write-Host "Donnees de cette session : $demoRoot"
Write-Host "Ctrl+C arrete le serveur ; les donnees restent disponibles pour reprendre la demonstration."
& $pythonExe -m uvicorn boussla.web.app:app --host 127.0.0.1 --port $Port
exit $LASTEXITCODE
