<#
.SYNOPSIS
    Runs the GLINT frontend in the current terminal (terminal 2 of 2).

.DESCRIPTION
    Starts the Vite development server on http://localhost:5173. The dev server
    proxies every /api request to the FastAPI backend, so the browser never has
    to deal with CORS and no backend URL is hardcoded in the React code.

.PARAMETER Production
    Build the frontend (npm run build) and serve the optimized bundle with
    "npm run preview" instead of the development server.

.EXAMPLE
    .\run-frontend.ps1
#>
[CmdletBinding()]
param(
    [switch]$Production
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'scripts\glint-env.ps1')

$Root = $script:GlintRoot
Read-DotEnv (Join-Path $Root '.env')

$FrontendDir = Join-Path $Root 'frontend'
if (-not (Test-Path -LiteralPath (Join-Path $FrontendDir 'node_modules'))) {
    Fail ('frontend\node_modules is missing. Run .\install.ps1 first (or "npm install" ' +
          "inside $FrontendDir).")
}

$npmCommand = Get-Command npm -ErrorAction SilentlyContinue
if (-not $npmCommand) {
    Fail 'npm was not found. Install Node.js 20.19+ from https://nodejs.org/ and try again.'
}

$frontendHost = Get-EnvValue 'GLINT_FRONTEND_HOST' '127.0.0.1'
$frontendPort = Get-EnvValue 'GLINT_FRONTEND_PORT' '5173'
$backendUrl = Get-EnvValue 'GLINT_BACKEND_URL' 'http://127.0.0.1:8000'

# vite.config.ts reads these from the process environment.
Set-Item -Path 'Env:GLINT_FRONTEND_HOST' -Value $frontendHost
Set-Item -Path 'Env:GLINT_FRONTEND_PORT' -Value $frontendPort
Set-Item -Path 'Env:GLINT_BACKEND_URL' -Value $backendUrl
Set-Item -Path 'Env:GLINT_FRONTEND_ALLOWED_HOSTS' -Value (Get-EnvValue 'GLINT_FRONTEND_ALLOWED_HOSTS' '')

Set-Location $FrontendDir

if ($Production) {
    Write-Step "Building and previewing the frontend on http://localhost:${frontendPort}"
    Write-Info 'Backend proxy target: ' + $backendUrl
    & npm run build
    if ($LASTEXITCODE -ne 0) { Fail 'The production build failed - see the errors above.' }
    & npm run preview
    exit $LASTEXITCODE
}

Write-Step "Starting the GLINT frontend on http://localhost:${frontendPort}"
Write-Info 'Backend proxy target : ' + $backendUrl
Write-Info 'Press Ctrl+C to stop.'

if (Test-PortInUse -Port ([int]$frontendPort)) {
    Write-Note ("Port $frontendPort is already in use. Vite will pick the next free port; " +
                'watch the output for the real URL.')
}

& npm run dev
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    Write-Note "The frontend stopped with exit code $exitCode."
}
exit $exitCode
