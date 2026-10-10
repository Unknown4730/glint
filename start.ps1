<#
.SYNOPSIS
    Starts GLINT: the FastAPI backend and the Vite frontend.

.DESCRIPTION
    start.ps1 opens the backend and the frontend in two separate PowerShell
    windows, waits until both really answer, and then prints the URLs.

    It is careful not to start duplicates: if the backend already answers on
    /api/health, or the frontend already answers on its port, the existing
    process is reused instead of starting a second one.

    If you prefer to see the logs yourself, run the two scripts manually in two
    terminals:

        Terminal 1:  .\run-backend.ps1
        Terminal 2:  .\run-frontend.ps1

.PARAMETER BackendOnly
    Start only the API server.

.PARAMETER FrontendOnly
    Start only the Vite dev server (the backend must already be running).

.PARAMETER NoBrowser
    Do not open the browser automatically.

.PARAMETER BackendTimeout
    Seconds to wait for the backend to become healthy (default 180 - the first
    start loads the OCR models).

.EXAMPLE
    .\start.ps1

.EXAMPLE
    .\start.ps1 -BackendOnly -NoBrowser
#>
[CmdletBinding()]
param(
    [switch]$BackendOnly,
    [switch]$FrontendOnly,
    [switch]$NoBrowser,
    [int]$BackendTimeout = 180,
    [int]$FrontendTimeout = 60
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'scripts\glint-env.ps1')

$Root = $script:GlintRoot
Read-DotEnv (Join-Path $Root '.env')

$backendHost = Get-EnvValue 'GLINT_BACKEND_HOST' '127.0.0.1'
$backendPort = Get-EnvValue 'GLINT_BACKEND_PORT' '8000'
$frontendPort = Get-EnvValue 'GLINT_FRONTEND_PORT' '5173'

$healthUrl = "http://${backendHost}:${backendPort}/api/health"
$frontendUrl = "http://localhost:${frontendPort}"

Write-Host ''
Write-Host '  GLINT' -ForegroundColor White
Write-Host '  See beyond the page.' -ForegroundColor DarkGray

$backendRunning = $false
$frontendRunning = $false

# ---------------------------------------------------------------------------
# Backend
# ---------------------------------------------------------------------------
if (-not $FrontendOnly) {
    Write-Step 'Backend (FastAPI + local OCR)'

    if (-not (Get-VenvPython -Root $Root)) {
        Fail 'No virtual environment found. Run .\install.ps1 first.'
    }

    if (Wait-ForUrl -Url $healthUrl -TimeoutSeconds 3) {
        Write-Ok "Already running at $healthUrl - reusing it"
        $backendRunning = $true
    }
    elseif (Test-PortInUse -Port ([int]$backendPort)) {
        Fail ("Port $backendPort is used by another program that does not answer " +
              "$healthUrl. Stop that program, or set GLINT_BACKEND_PORT in .env to a " +
              'different port and run install-free: .\start.ps1 again.')
    }
    else {
        $backendScript = Join-Path $Root 'run-backend.ps1'
        $arguments = "-NoExit -ExecutionPolicy Bypass -File `"$backendScript`""
        Start-Process -FilePath 'powershell.exe' -ArgumentList $arguments -WorkingDirectory $Root | Out-Null
        Write-Info 'Started in a new window; loading the OCR models takes a few seconds...'

        if (Wait-ForUrl -Url $healthUrl -TimeoutSeconds $BackendTimeout) {
            $backendRunning = $true
            Write-Ok "Healthy at $healthUrl"
            try {
                $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 10
                if ($health.ocr.ready) {
                    Write-Ok ("OCR ready: " + $health.ocr.model)
                }
                else {
                    Write-Note ("The backend is up but OCR is NOT ready: " + $health.ocr.error)
                    Write-Note 'Uploads will be rejected until this is fixed (see README > Troubleshooting).'
                }
            }
            catch {
                Write-Note 'The health endpoint answered but could not be parsed.'
            }
        }
        else {
            Write-Note ("The backend did not become healthy within $BackendTimeout seconds.")
            Write-Note 'Look at the "GLINT backend" window for the actual error message.'
        }
    }
}

# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------
if (-not $BackendOnly) {
    Write-Step 'Frontend (React + Vite)'

    if (-not (Test-Path -LiteralPath (Join-Path (Join-Path $Root 'frontend') 'node_modules'))) {
        Fail 'frontend\node_modules is missing. Run .\install.ps1 first.'
    }

    if (Wait-ForUrl -Url $frontendUrl -TimeoutSeconds 3) {
        Write-Ok "Already running at $frontendUrl - reusing it"
        $frontendRunning = $true
    }
    else {
        if (Test-PortInUse -Port ([int]$frontendPort)) {
            Write-Note ("Port $frontendPort is busy, so Vite will choose the next free port.")
        }
        $frontendScript = Join-Path $Root 'run-frontend.ps1'
        $arguments = "-NoExit -ExecutionPolicy Bypass -File `"$frontendScript`""
        Start-Process -FilePath 'powershell.exe' -ArgumentList $arguments -WorkingDirectory $Root | Out-Null
        Write-Info 'Started in a new window...'

        if (Wait-ForUrl -Url $frontendUrl -TimeoutSeconds $FrontendTimeout) {
            $frontendRunning = $true
            Write-Ok "Serving at $frontendUrl"
        }
        else {
            Write-Note ("The frontend did not answer on $frontendUrl within $FrontendTimeout seconds.")
            Write-Note 'Check the "GLINT frontend" window - Vite may have picked another port.'
        }
    }
}

# ---------------------------------------------------------------------------
Write-Host ''
Write-Host '  ----------------------------------------------------------------' -ForegroundColor DarkGray
if ($frontendRunning -and -not $BackendOnly) {
    Write-Host "  Glint UI   : $frontendUrl" -ForegroundColor Green
}
if ($backendRunning -and -not $FrontendOnly) {
    Write-Host "  Backend API: http://${backendHost}:${backendPort}" -ForegroundColor Green
    Write-Host "  API docs   : http://${backendHost}:${backendPort}/api/docs" -ForegroundColor DarkGray
}
Write-Host '  ----------------------------------------------------------------' -ForegroundColor DarkGray

if (-not $backendRunning -and -not $frontendRunning) {
    Write-Host ''
    Fail 'Nothing could be started. Read the messages above (and the two new terminal windows).'
}

if ($frontendRunning -and -not $NoBrowser -and -not $BackendOnly) {
    Write-Host ''
    Write-Info 'Opening your browser...'
    Start-Process $frontendUrl
}

Write-Host ''
Write-Info 'Stop Glint by closing the two terminal windows (or Ctrl+C inside them).'
Write-Host ''
exit 0
