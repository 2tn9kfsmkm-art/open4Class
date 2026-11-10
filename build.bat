@echo off
rem Wrapper: all real work is in build.ps1 (ASCII only, CRLF line endings)
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build.ps1" %*
