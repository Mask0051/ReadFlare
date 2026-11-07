@echo off
REM Double-click to start the CodeREAD monitor, API and dashboard.
cd /d "%~dp0"

REM Prefer the "py" launcher; fall back to "python". An if/else (not && ... ||)
REM so start.py never runs twice when it exits with an error.
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 start.py %*
) else (
    python start.py %*
)
pause