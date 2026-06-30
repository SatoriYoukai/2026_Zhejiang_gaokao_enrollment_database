@echo off
setlocal
chcp 65001 >nul

set "EXE="
for %%F in ("%~dp0*.exe") do set "EXE=%%~fF"

if not defined EXE (
  echo ERROR: estimator exe was not found in this folder.
  pause
  exit /b 1
)

"%EXE%" %*
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" echo ERROR: estimator exited with code %EXIT_CODE%.
pause
exit /b %EXIT_CODE%
