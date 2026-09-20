#Requires -Version 5.1
<#
.SYNOPSIS
  One command: check Docker + USB, then start LeRobot.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File docker/setup.ps1
#>
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$PyScript = Join-Path $RepoRoot "src\lerobot\scripts\lerobot_setup_container.py"

function Test-RealPython([string]$Exe, [string[]]$PrefixArgs) {
    try {
        $ErrorActionPreference = "Continue"
        & $Exe @PrefixArgs -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" 2>$null | Out-Null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Find-Python {
    $candidates = @(
        @{ Exe = "python"; Args = @() },
        @{ Exe = "python3"; Args = @() },
        @{ Exe = "py"; Args = @("-3") }
    )
    foreach ($item in $candidates) {
        $cmd = Get-Command $item.Exe -ErrorAction SilentlyContinue
        if (-not $cmd) { continue }
        if ($cmd.Source -match "WindowsApps\\python.exe$") { continue }
        if (Test-RealPython $cmd.Source $item.Args) {
            return @{ Exe = $cmd.Source; Args = $item.Args }
        }
    }
    return $null
}

Write-Host "LeRobot setup (Windows)"
Write-Host "This script finds Python, then checks Docker and your robot USB cables."
Write-Host ""

$python = Find-Python
if (-not $python) {
    Write-Host @"
Python is not installed (or not on PATH).

Do this:
  1. Open https://www.python.org/downloads/windows/
  2. Install Python 3.12 or newer
  3. CHECK the box: "Add python.exe to PATH"
  4. Close this terminal, open a new one, and run:

     powershell -ExecutionPolicy Bypass -File docker\setup.ps1
"@
    exit 1
}

if (-not (Test-Path $PyScript)) {
    Write-Host "Could not find $PyScript"
    Write-Host "Run this from the lerobot repo (the folder that contains src\ and docker\)."
    exit 1
}

$argList = @($python.Args) + @($PyScript) + $args
Write-Host ("Running: {0} {1}" -f $python.Exe, ($argList -join " "))
Write-Host ""
& $python.Exe @argList
exit $LASTEXITCODE
