@echo off
chcp 65001 > nul
setlocal

:: ── clco-tools Global Installer ─────────────────────────────────────────────
:: Reads .env.clco in the repo root and installs:
::   clco-notify  →  ~/.claude/hooks/clco_notify.py  +  ~/.claude/.env.clconotify
::   clco-wiki    →  ~/.claude/commands/              +  ~/.env.clcowiki
:: ─────────────────────────────────────────────────────────────────────────────

cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] python not found in PATH
    pause
    exit /b 1
)

python dev\install_global.py %*

echo.
pause
