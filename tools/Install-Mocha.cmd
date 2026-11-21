@echo off
setlocal
cd /d "%~dp0"
if exist "%~dp0runtime\python.exe" (
  set "PYTHON=%~dp0runtime\python.exe"
) else (
  where py >nul 2>&1
  if errorlevel 1 goto missing
  set "PYTHON=py"
)
if exist "%~dp0platform-tools\fastboot.exe" set "PATH=%~dp0platform-tools;%PATH%"
where fastboot >nul 2>&1
if errorlevel 1 goto missing
where ssh >nul 2>&1
if errorlevel 1 goto missing
where ssh-keygen >nul 2>&1
if errorlevel 1 goto missing
echo Mocha installer - clears APP, UDA and cache. Back up personal files first.
echo The GPT/LNX backup cannot restore personal files. Press Ctrl+C now to cancel.
echo Only the validated 16 GB Mocha is supported. Enter factory Fastboot first.
"%PYTHON%" flash-distribution.py "..\image" --install --erase APP_UDA --allow-candidate
if errorlevel 1 (
  echo Installation stopped. Keep USB connected and read the error above.
  pause
  exit /b 1
)
echo Default username and password: mocha. Change the password after login.
pause
exit /b 0
:missing
echo Missing Python 3.11+, fastboot, ssh, or ssh-keygen. Install prerequisites and retry.
pause
exit /b 1
