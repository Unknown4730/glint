<#
.SYNOPSIS
    Installs everything GLINT needs on a Windows 10/11 machine.

.DESCRIPTION
    The script performs, in order:

      1. Checks that a supported Python (3.11 - 3.13) is installed.
      2. Checks that Node.js (>= 20.19) and npm are installed.
      3. Creates a Python virtual environment in .venv
      4. Installs backend\requirements.txt into that environment.
      5. Verifies that the local OCR engine really initializes and recognizes a
         probe image (the PP-OCRv6 models ship inside the rapidocr wheel, so no
         model download and no internet connection is needed afterwards).
      6. Installs the frontend dependencies with npm.
      7. Creates .env from .env.example when it does not exist yet.

    It exits with a non-zero code as soon as a required step fails, and prints
    what to do next.

.PARAMETER SkipFrontend
    Only install the Python side.

.PARAMETER SkipOcrCheck
    Do not run the OCR verification step (useful on a machine without the
    models, for example in CI).

.PARAMETER PythonCommand
    Use a specific Python interpreter, e.g. -PythonCommand "C:\Python311\python.exe"

.EXAMPLE
    .\install.ps1

.EXAMPLE
    .\install.ps1 -SkipFrontend -PythonCommand "py"
#>
[CmdletBinding()]
param(
    [switch]$SkipFrontend,
    [switch]$SkipOcrCheck,
    [string]$PythonCommand
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'scripts\glint-env.ps1')

$Root = $script:GlintRoot
$BackendDir = Join-Path $Root 'backend'
$FrontendDir = Join-Path $Root 'frontend'
$VenvDir = Join-Path $Root '.venv'
$Requirements = Join-Path $BackendDir 'requirements.txt'

Write-Host ''
Write-Host '  GLINT - local OCR & document digitization' -ForegroundColor White
Write-Host '  See beyond the page.' -ForegroundColor DarkGray
Write-Host ('  Installing into: ' + $Root) -ForegroundColor DarkGray

# ---------------------------------------------------------------------------
# 1. Python
# ---------------------------------------------------------------------------
Write-Step 'Checking Python'

function Find-Python {
    $attempts = New-Object System.Collections.ArrayList
    if ($PythonCommand) {
        [void]$attempts.Add(@{ Exe = $PythonCommand; Args = @() })
    }
    [void]$attempts.Add(@{ Exe = 'py'; Args = @('-3.11') })
    [void]$attempts.Add(@{ Exe = 'py'; Args = @('-3') })
    [void]$attempts.Add(@{ Exe = 'python'; Args = @() })
    [void]$attempts.Add(@{ Exe = 'python3'; Args = @() })

    $probe = "import sys; print('%d.%d.%d' % sys.version_info[:3]); print(sys.executable)"

    foreach ($attempt in $attempts) {
        $command = Get-Command $attempt.Exe -ErrorAction SilentlyContinue
        if (-not $command) { continue }
        try {
            $argList = $attempt.Args
            $output = & $attempt.Exe @argList -c $probe 2>$null
            if ($LASTEXITCODE -ne 0 -or -not $output) { continue }
            $lines = @($output)
            if ($lines.Count -lt 2) { continue }
            return [pscustomobject]@{
                Exe       = $attempt.Exe
                Args      = $attempt.Args
                Version   = $lines[0].Trim()
                Path      = $lines[1].Trim()
            }
        }
        catch { continue }
    }
    return $null
}

$python = Find-Python
if (-not $python) {
    Fail ('No usable Python interpreter was found. Install Python 3.11 from ' +
          'https://www.python.org/downloads/windows/ and tick "Add python.exe to PATH", ' +
          'then run install.ps1 again.')
}

$parts = $python.Version.Split('.')
$major = [int]$parts[0]
$minor = [int]$parts[1]

if ($major -ne 3 -or $minor -lt 11) {
    Fail ("Python $($python.Version) was found at $($python.Path), but Glint needs " +
          'Python 3.11 or newer (its pinned dependencies require it).')
}
if ($minor -gt 13) {
    Write-Note ("Python $($python.Version) is newer than the versions Glint was verified " +
                'with (3.11 - 3.13). Installation may fail if a wheel is missing.')
}
Write-Ok ("Python $($python.Version)  ->  $($python.Path)")

# ---------------------------------------------------------------------------
# 2. Node.js / npm
# ---------------------------------------------------------------------------
if (-not $SkipFrontend) {
    Write-Step 'Checking Node.js and npm'

    $nodeCommand = Get-Command node -ErrorAction SilentlyContinue
    if (-not $nodeCommand) {
        Fail ('Node.js was not found. Install the LTS build from https://nodejs.org/ ' +
              '(Glint needs Node 20.19 or newer) and run install.ps1 again.')
    }
    $nodeVersionRaw = (& node -v 2>$null)
    if ($LASTEXITCODE -ne 0 -or -not $nodeVersionRaw) {
        Fail 'Node.js did not report a version. Reinstall it from https://nodejs.org/.'
    }
    $nodeVersion = $nodeVersionRaw.TrimStart('v')
    $nodeParts = $nodeVersion.Split('.')
    $nodeMajor = [int]$nodeParts[0]
    $nodeMinor = [int]$nodeParts[1]
    if ($nodeMajor -lt 20 -or ($nodeMajor -eq 20 -and $nodeMinor -lt 19)) {
        Fail ("Node.js $nodeVersion is too old. Vite needs Node 20.19+ or 22.12+.")
    }
    Write-Ok "Node.js $nodeVersion"

    $npmCommand = Get-Command npm -ErrorAction SilentlyContinue
    if (-not $npmCommand) { Fail 'npm was not found. It is installed together with Node.js.' }
    $npmVersion = (& npm -v 2>$null)
    Write-Ok "npm $npmVersion"
}

# ---------------------------------------------------------------------------
# 3. Virtual environment
# ---------------------------------------------------------------------------
Write-Step 'Creating the Python virtual environment'
$venvPython = Get-VenvPython -Root $Root
if ($venvPython) {
    Write-Ok '.venv already exists, reusing it'
}
else {
    $pyArgs = $python.Args
    & $python.Exe @pyArgs -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) { Fail "Creating the virtual environment failed in $VenvDir." }
    $venvPython = Get-VenvPython -Root $Root
    if (-not $venvPython) { Fail "The virtual environment was created but python.exe is missing in $VenvDir." }
    Write-Ok ".venv created at $VenvDir"
}

# ---------------------------------------------------------------------------
# 4. Backend dependencies
# ---------------------------------------------------------------------------
Write-Step 'Installing the backend dependencies (this downloads ~250 MB once)'
if (-not (Test-Path -LiteralPath $Requirements)) {
    Fail "requirements.txt was not found at $Requirements."
}

& $venvPython -m pip install --upgrade pip --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { Write-Note 'Upgrading pip failed; continuing with the bundled pip.' }

& $venvPython -m pip install -r $Requirements --disable-pip-version-check
if ($LASTEXITCODE -ne 0) {
    Fail ('Installing backend\requirements.txt failed. Read the pip error above - ' +
          'the usual causes are no internet connection, a proxy, or a Python version ' +
          'that has no wheel for onnxruntime / pymupdf / pandas.')
}
Write-Ok 'Backend dependencies installed'

# ---------------------------------------------------------------------------
# 5. OCR verification (the models ship inside the rapidocr wheel)
# ---------------------------------------------------------------------------
if ($SkipOcrCheck) {
    Write-Step 'Skipping the OCR verification (-SkipOcrCheck)'
}
else {
    Write-Step 'Verifying the local OCR engine'
    $verifyScript = Join-Path (Join-Path $BackendDir 'scripts') 'verify_ocr.py'
    Push-Location $BackendDir
    try {
        & $venvPython $verifyScript
        $verifyExit = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
    if ($verifyExit -ne 0) {
        Fail ('The OCR engine could not be verified. Glint would start but every upload ' +
              'would be rejected, so the installation is not complete. Try: ' +
              "$venvPython -m pip install --force-reinstall rapidocr==3.10.0 onnxruntime==1.23.2")
    }
    Write-Ok 'Local OCR verified (CPU, ONNX Runtime, bundled PP-OCRv6 models)'
}

# ---------------------------------------------------------------------------
# 6. Frontend dependencies
# ---------------------------------------------------------------------------
if ($SkipFrontend) {
    Write-Step 'Skipping the frontend (-SkipFrontend)'
}
else {
    Write-Step 'Installing the frontend dependencies'
    if (-not (Test-Path -LiteralPath (Join-Path $FrontendDir 'package.json'))) {
        Fail "frontend\package.json was not found in $FrontendDir."
    }
    Push-Location $FrontendDir
    try {
        $lockFile = Join-Path $FrontendDir 'package-lock.json'
        if (Test-Path -LiteralPath $lockFile) {
            & npm ci --no-audit --no-fund
        }
        else {
            & npm install --no-audit --no-fund
        }
        $npmExit = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
    if ($npmExit -ne 0) {
        Fail 'npm install failed. Check your internet connection or proxy settings (npm config get proxy).'
    }
    Write-Ok 'Frontend dependencies installed'
}

# ---------------------------------------------------------------------------
# 7. Environment file and data directory
# ---------------------------------------------------------------------------
Write-Step 'Preparing configuration and folders'
$envExample = Join-Path $Root '.env.example'
$envFile = Join-Path $Root '.env'
if ((Test-Path -LiteralPath $envExample) -and -not (Test-Path -LiteralPath $envFile)) {
    Copy-Item -LiteralPath $envExample -Destination $envFile
    Write-Ok '.env created from .env.example (all defaults, safe to edit)'
}
elseif (Test-Path -LiteralPath $envFile) {
    Write-Ok '.env already exists, leaving it untouched'
}

$dataDir = Join-Path $BackendDir 'data'
if (-not (Test-Path -LiteralPath $dataDir)) {
    New-Item -ItemType Directory -Path $dataDir | Out-Null
}
Write-Ok "SQLite data folder ready: backend\data"

# ---------------------------------------------------------------------------
Write-Host ''
Write-Host '  Installation finished.' -ForegroundColor Green
Write-Host ''
Write-Host '  Start Glint with:' -ForegroundColor White
Write-Host '      .\start.ps1' -ForegroundColor Yellow
Write-Host ''
Write-Host '  Then open:  http://localhost:5173' -ForegroundColor White
Write-Host '  API docs :  http://127.0.0.1:8000/api/docs' -ForegroundColor DarkGray
Write-Host ''
exit 0
