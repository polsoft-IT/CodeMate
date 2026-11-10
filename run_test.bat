@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo ========================================
echo  CodeMate - uruchamianie testow
echo ========================================
echo.

rem Prefer a stable Python 3.14 runtime; Python 3.15 currently has an
rem incompatible AnyIO/pytest plugin combination in this environment.
set "PYTHON="
for %%V in (3.14 3.13 3.12 3.11) do (
    if not defined PYTHON for /f "delims=" %%P in ('py -%%V -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON=%%P"
)
if not defined PYTHON (
    where python >nul 2>nul
    if not errorlevel 1 set "PYTHON=python"
)
if not defined PYTHON (
    echo [BLAD] Nie znaleziono Pythona 3.11-3.14.
    echo Zainstaluj Python 3.14 i uruchom ponownie ten plik.
    set "TEST_EXIT_CODE=9009"
    goto :finish
)

echo Interpreter: %PYTHON%
"%PYTHON%" -c "import sys; print('Wersja:', sys.version.split()[0])"
"%PYTHON%" -m pytest -q
set "TEST_EXIT_CODE=%errorlevel%"

:finish
echo.
if "%TEST_EXIT_CODE%"=="0" (
    echo Testy zakonczone powodzeniem.
) else (
    echo Testy nie powiodly sie. Kod wyjscia: %TEST_EXIT_CODE%
)
echo.
pause
exit /b %TEST_EXIT_CODE%
