<#
.SYNOPSIS
    Runs the GLINT FastAPI backend in the current terminal (terminal 1 of 2).

.DESCRIPTION
    Starts uvicorn with a single worker on http://127.0.0.1:8000 using the
    Python interpreter from .venv. The first start takes a few seconds longer
    because the local OCR engine loads its bundled models and runs a warm-up
    pass; after that every request reuses the same engine.

    Settings are read from the .env file in the project root, and any value you
    set in the shell before running this script wins over .env.

.PARAMETER Reload
    Restart the server automatically when a backend file changes (development).

.EXAMPLE
    .\run-backend.ps1
#>
[CmdletBinding()]
param(
    [switch]$Reload
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'scripts\glint-env.ps1')

$Root = $script:GlintRoot
Read-DotEnv (Join-Path $Root '.env')

$venvPython = Get-VenvPython -Root $Root
if (-not $venvPython) {
    Fail ('No virtual environment found. Run .\install.ps1 first - it creates .venv ' +
          'and installs the backend dependencies.')
}

$backendHost = Get-EnvValue 'GLINT_BACKEND_HOST' '127.0.0.1'
$backendPort = Get-EnvValue 'GLINT_BACKEND_PORT' '8000'

Write-Step "Starting the GLINT backend on http://${backendHost}:${backendPort}"
Write-Info "Interpreter : $venvPython"
Write-Info "API docs    : http://${backendHost}:${backendPort}/api/docs"
Write-Info 'Workers     : 1 (sequential OCR is intentional on a low-spec PC)'
Write-Info 'Press Ctrl+C to stop.'

if (Test-PortInUse -Port ([int]$backendPort)) {
    Write-Note ("Port $backendPort is already in use. If Glint is already running you can " +
                'just open the frontend; otherwise stop the other program first.')
}

Set-Location (Join-Path $Root 'backend')

$uvicornArgs = @(
    '-m', 'uvicorn',
    'app.main:app',
    '--host', $backendHost,
    '--port', $backendPort,
    '--workers', '1'
)
if ($Reload) { $uvicornArgs += '--reload' }

& $venvPython @uvicornArgs
$exitCode = $LASTEXITCODE

if ($exitCode -ne 0) {
    Write-Host ''
    Write-Note "The backend stopped with exit code $exitCode. The error message above explains why."
}
exit $exitCode
