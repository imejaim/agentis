@echo off
chcp 65001 >nul
setlocal

set "SCRIPT_DIR=%~dp0"
set "PYTHON_CMD=python"
set "NEED_PAUSE=0"

python --version >nul 2>nul
if errorlevel 1 (
  py -3 --version >nul 2>nul
  if errorlevel 1 (
    echo [Agentis] Python 3 was not found.
    echo Install Python 3 and run this file again.
    pause
    exit /b 1
  )
  set "PYTHON_CMD=py -3"
)

if "%~1"=="" (
  set "NEED_PAUSE=1"
  echo.
  echo Agentis installer
  echo Enter the absolute path of the work folder to install into.
  echo Example: C:\work\project-a
  echo.
  set /p "TARGET_DIR=> "
  if "%TARGET_DIR%"=="" (
    echo Target path is empty. Installation cancelled.
    pause
    exit /b 2
  )
  %PYTHON_CMD% "%SCRIPT_DIR%install.py" --target "%TARGET_DIR%"
) else (
  %PYTHON_CMD% "%SCRIPT_DIR%install.py" %*
)

set "EXIT_CODE=%ERRORLEVEL%"
echo.
if "%EXIT_CODE%"=="0" (
  echo Agentis installer finished.
) else (
  echo Agentis installer failed. Exit code: %EXIT_CODE%
)
if "%NEED_PAUSE%"=="1" pause
exit /b %EXIT_CODE%
