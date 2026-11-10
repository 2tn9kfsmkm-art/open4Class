# Build ClassManager with Nuitka (standalone).
# Usage:  .\build.ps1            -> version from latest git tag
#         .\build.ps1 0.40.0     -> explicit version

param([string]$Version = "", [string]$Compiler = "auto")

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

$pyMinor = (& python -c "import sys; print(sys.version_info.minor)").Trim()
Write-Host "[build] python 3.$pyMinor"
if ($pyMinor -ge 13 -and $Compiler -eq "mingw") {
    Write-Host "[build] Python 3.$pyMinor 不支持 MinGW，忽略该选项"
}

if (Test-Path build) { Remove-Item build -Recurse -Force }

$nuitkaArgs = @(
    "-m", "nuitka", "main.py",
    "--standalone",
    "--enable-plugin=pyside6",
    # 编译器：zig 在本机编译本工程会崩；Python 3.13 又不支持 mingw64，故默认 msvc
    "--msvc=latest"
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

Write-Host "[build] compiling with MSVC (需要 VS 2022 Build Tools)..."
& python @nuitkaArgs
if ($LASTEXITCODE -ne 0) { Write-Host "[build] FAILED"; exit 1 }

$distDir = Join-Path $PSScriptRoot "build\main.dist"
$exe = Join-Path $distDir "ClassManager.exe"
if ((Test-Path (Join-Path $distDir "main.exe")) -and -not (Test-Path $exe)) {
    Rename-Item (Join-Path $distDir "main.exe") "ClassManager.exe"
}

Write-Host "[build] done: $exe"
