@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

rem ============================================================
rem  打包脚本：Nuitka 编译 → build\main.dist\ClassManager.exe
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
rem 注意：只打进 message.html 与 templates；messages\images 里的班级照片
rem 属于隐私数据，绝不能进分发包
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
  --include-data-dir=messages\templates=messages\templates ^
  --include-data-files=messages\message.html=messages\message.html ^
  --output-dir=build ^
  --assume-yes-for-downloads ^
  --nofollow-import-to=pytest ^
  --remove-output

if errorlevel 1 (
    echo [build] 编译失败
    exit /b 1
)

rem Nuitka 生成的 exe 名跟随入口脚本（main.exe），统一改成 ClassManager.exe
if exist "build\main.dist\main.exe" if not exist "build\main.dist\ClassManager.exe" (
    ren "build\main.dist\main.exe" "ClassManager.exe"
)

echo [build] 完成： build\main.dist\ClassManager.exe
echo [build] 提示：把这个目录整个复制走即可免安装运行
