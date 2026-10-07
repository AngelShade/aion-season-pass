@echo off
setlocal
echo Aion 4.8 Aetherfall Season Pass client patch
echo Use only after the server operator has enabled the pass and supplied its HTTPS address.
echo Close Aion before continuing.
set /p "CLIENT=Full path to your Aion 4.8 NA client folder: "
set /p "SERVER=Public HTTPS origin from your server operator: "
set /p "STAGED=New staging folder (must not already exist): "
if "%CLIENT%"=="" goto failed
if "%SERVER%"=="" goto failed
if "%STAGED%"=="" goto failed
where python >nul 2>nul
if errorlevel 1 (
  echo Python 3.10 or newer is required.
  goto failed
)
python -c "import PIL" >nul 2>nul
if errorlevel 1 (
  echo Pillow is required. Install it with: python -m pip install Pillow
  goto failed
)
where java >nul 2>nul
if errorlevel 1 (
  echo Java is required to rebuild the local addon signatures.
  goto failed
)
python "%~dp0client-mods\season-pass\prepare.py" --client "%CLIENT%" --output "%STAGED%" --server-url "%SERVER%"
if errorlevel 1 goto failed
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0client-mods\season-pass\install.ps1" -PreparedPath "%STAGED%"
if errorlevel 1 goto failed
echo.
echo Season Pass client patch installed. Keep the printed backup path for restore.
pause
exit /b 0
:failed
echo.
echo Installation stopped. Check the error above; preserve any backup path printed by the installer.
pause
exit /b 1
