<#
.SYNOPSIS
    Shared helpers for the GLINT PowerShell scripts.

.DESCRIPTION
    Dot-source this file from install.ps1, start.ps1, run-backend.ps1 and
    run-frontend.ps1:

        . (Join-Path $PSScriptRoot 'scripts\glint-env.ps1')

    Written for Windows PowerShell 5.1 and PowerShell 7+, so it avoids
    newer-only syntax (no ?? operator, no ternary operator).
#>

Set-StrictMode -Version Latest

# Resolve the project root from the location of THIS file (scripts\ -> root).
$script:GlintRoot = Split-Path -Parent $PSScriptRoot
if (-not $script:GlintRoot) { $script:GlintRoot = (Get-Location).Path }

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Ok {
    param([string]$Message)
    Write-Host "    [ok] $Message" -ForegroundColor Green
}

function Write-Info {
    param([string]$Message)
    Write-Host "    $Message" -ForegroundColor Gray
}

function Write-Note {
    param([string]$Message)
    Write-Host "    [!] $Message" -ForegroundColor Yellow
}

function Fail {
    param([string]$Message, [int]$Code = 1)
    Write-Host ""
    Write-Host "ERROR: $Message" -ForegroundColor Red
    Write-Host ""
    exit $Code
}

function Read-DotEnv {
    <#
    .SYNOPSIS
        Loads KEY=VALUE pairs from a .env file into the process environment.
        Values that are already set in the shell win, so you can always
        override a setting for a single run.
    #>
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) { return }

    foreach ($rawLine in Get-Content -LiteralPath $Path) {
        $line = $rawLine.Trim()
        if ($line.Length -eq 0) { continue }
        if ($line.StartsWith('#')) { continue }

        $separator = $line.IndexOf('=')
        if ($separator -lt 1) { continue }

        $key = $line.Substring(0, $separator).Trim()
        $value = $line.Substring($separator + 1).Trim()

        # Strip one layer of surrounding quotes, and an inline comment.
        if ($value.Length -ge 2) {
            if (($value.StartsWith('"') -and $value.EndsWith('"')) -or
                ($value.StartsWith("'") -and $value.EndsWith("'"))) {
                $value = $value.Substring(1, $value.Length - 2)
            }
        }

        if (-not (Test-Path -LiteralPath "Env:\$key")) {
            Set-Item -LiteralPath "Env:\$key" -Value $value
        }
    }
}

function Get-EnvValue {
    param([string]$Name, [string]$Default)
    $value = [Environment]::GetEnvironmentVariable($Name)
    if ($null -eq $value -or $value.Trim().Length -eq 0) { return $Default }
    return $value.Trim()
}

function Test-PortInUse {
    param([int]$Port)
    try {
        $listener = [System.Net.Sockets.TcpClient]::new()
        $listener.Connect('127.0.0.1', $Port)
        $listener.Close()
        return $true
    }
    catch {
        return $false
    }
}

function Wait-ForUrl {
    <#
    .SYNOPSIS
        Polls a URL until it answers or the timeout expires.
        Returns $true when the URL responded.
    #>
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 90,
        [int]$IntervalMs = 750
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) { return $true }
        }
        catch {
            # Not up yet - keep waiting.
        }
        Start-Sleep -Milliseconds $IntervalMs
    }
    return $false
}

function Get-VenvPython {
    param([string]$Root)
    $candidate = Join-Path (Join-Path $Root '.venv') 'Scripts\python.exe'
    if (Test-Path -LiteralPath $candidate) { return $candidate }
    # Fallback for people who run these scripts on Linux/macOS via pwsh.
    $unixCandidate = Join-Path (Join-Path $Root '.venv') 'bin/python'
    if (Test-Path -LiteralPath $unixCandidate) { return $unixCandidate }
    return $null
}
