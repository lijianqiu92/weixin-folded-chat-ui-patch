@echo off
setlocal
cd /d "%~dp0"
echo Weixin UI patch - Restore
echo.
if not exist "%~dp0Manage-FixedPatch.ps1" (
  echo ERROR: Manage-FixedPatch.ps1 is missing. Keep all patch files together.
  pause
  exit /b 1
)
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -File "%~dp0Manage-FixedPatch.ps1" -Mode Restore %*
set "PATCH_EXIT_CODE=%errorlevel%"
echo.
echo Installer exited with code %PATCH_EXIT_CODE%.
echo If an error appeared, copy it before closing this window.
pause
exit /b %PATCH_EXIT_CODE%
