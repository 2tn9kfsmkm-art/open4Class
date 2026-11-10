# Build ClassManager with Nuitka (standalone).
# Usage:  .\build.ps1            -> version from latest git tag
#         .\build.ps1 0.40.0     -> explicit version

param([string]$Version = "")

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

if (-not $Version) {
    try {
        $tag = (git describe --tags --abbrev=0) 2>$null
        if ($tag) { $Version = $tag.TrimStart('v') }
    } catch { }
}
if (-not $Version) { $Version = "0.0.0" }
Write-Host "[build] version: $Version"

if (Test-Path build) { Remove-Item build -Recurse -Force }

$nuitkaArgs = @(
    "-m", "nuitka", "main.py",
    "--standalone",
    "--enable-plugin=pyside6",
    "--mingw64",              # 不用默认的 zig：它在 Windows 上编译本工程会崩
    "--windows-console-mode=disable",
    "--windows-icon-from-ico=resources\icon.ico",
    "--company-name=Shixi High School",
    "--product-name=ClassManager",
    "--file-description=ClassManager",
    "--file-version=$Version",
    "--product-version=$Version",
    "--include-data-dir=stylesheet=stylesheet",
    "--include-data-dir=resources=resources",
    "--include-data-dir=messages\templates=messages\templates",
    "--include-data-files=messages\message.html=messages\message.html",
    "--output-dir=build",
    "--assume-yes-for-downloads",
    "--nofollow-import-to=pytest",
    "--remove-output"
)

Write-Host "[build] compiling (first run downloads MinGW, be patient)..."
& python @nuitkaArgs
if ($LASTEXITCODE -ne 0) { Write-Host "[build] FAILED"; exit 1 }

$distDir = Join-Path $PSScriptRoot "build\main.dist"
$exe = Join-Path $distDir "ClassManager.exe"
if ((Test-Path (Join-Path $distDir "main.exe")) -and -not (Test-Path $exe)) {
    Rename-Item (Join-Path $distDir "main.exe") "ClassManager.exe"
}

Write-Host "[build] done: $exe"
