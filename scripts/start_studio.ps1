$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$studioRuntime = Join-Path $projectRoot ".studio-runtime"

if (-not (Get-Command langgraph -ErrorAction SilentlyContinue)) {
    throw "langgraph CLI is not installed. Install langgraph-cli[inmem] in a dedicated Studio environment first."
}

if (-not (Test-Path (Join-Path $studioRuntime "starlette"))) {
    throw "The isolated Studio runtime is missing. Install Starlette 1.6.0 into .studio-runtime first."
}

$env:PYTHONUTF8 = "1"
$env:PYTHONPATH = $studioRuntime

Push-Location $projectRoot
try {
    & langgraph dev --port 2024 --allow-blocking
}
finally {
    Pop-Location
}
