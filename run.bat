@echo off
TITLE SENA - AI Knowledge Search Hub
color 0b

echo ==================================================================
echo    S E N A  --  AI Knowledge Search Hub (Local & 100%% Offline)
echo ==================================================================
echo.

:: Check if python is in PATH
where python >nul 2>nul
if %errorlevel% neq 0 (
    color 0c
    echo [ERROR] Python tidak ditemukan di sistem Windows Anda.
    echo Silakan install Python 3.10 atau lebih baru dari https://python.org
    echo Pastikan mencentang opsi "Add Python to PATH" saat instalasi.
    echo.
    pause
    exit /b 1
)

:: Run launcher
python run.py

if %errorlevel% neq 0 (
    echo.
    echo Terjadi kendala saat menjalankan SENA.
    pause
)
