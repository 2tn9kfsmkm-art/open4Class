@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

rem ============================================================
rem  打包脚本：Nuitka 编译 → 生成 dist\ClassManager\ 独立目录
rem  用法：
rem      build.bat                 （版本号取自最近的 git tag）
rem      build.bat 0.40.0          （手动指定版本）
rem ============================================================

cd /d "%~dp0"

set "APPVERSION=%~1"
if "%APPVERSION%"=="" (
    for /f "delims=" %%v in ('git describe --tags --abbrev=0 2^>nul') do set "TAG=%%v"
    if defined TAG (
        set "APPVERSION=!TAG:v=!"
    ) else (
        set "APPVERSION=0.0.0"
    )
)
echo [build] 版本号: %APPVERSION%

echo [build] 清理旧输出...
if exist build rmdir /s /q build

echo [build] Nuitka 编译中（首次会下载 MinGW，比较慢）...
python -m nuitka main.py ^
  --standalone ^
  --enable-plugin=pyside6 ^
  --windows-disable-console ^
  --windows-icon-from-ico=resources\icon.ico ^
  --company-name="市西中学" ^
  --product-name="班级管理系统" ^
  --file-description="班级管理系统" ^
  --copyright="市西中学" ^
  --file-version=%APPVERSION% ^
  --product-version=%APPVERSION% ^
  --include-data-dir=stylesheet=stylesheet ^
  --include-data-dir=resources=resources ^
  --include-data-dir=messages=messages ^
  --output-dir=build ^
  --output-filename=ClassManager.exe ^
  --assume-yes-for-downloads ^
  --nofollow-import-to=pytest ^
  --noinclude-data-files=*.csv ^
  --remove-output

if errorlevel 1 (
    echo [build] 编译失败
    exit /b 1
)

echo [build] 完成： build\main.dist\ClassManager.exe
echo [build] 提示：把这个目录整个复制走即可免安装运行
