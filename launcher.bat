@echo off
title APKs Guard Pro 289 - Antivirus Launcher
color 0b
cls
echo =====================================================================
echo               APKs GUARD PRO 289 - ANDROID ANTIVIRUS                 
echo          Advanced Android Malware Cleaner ^& Security Engine          
echo =====================================================================
echo.
echo [*] Checking Python environment...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Python is not found in PATH!
    echo [!] Please make sure Python 3.10+ is installed.
    pause
    exit /b
)

echo [*] Starting APKs Guard Pro 289...
start "" python "%~dp0app.py"
exit
