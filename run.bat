@echo off
rem Uruchamianie Bazy Skryptow
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" baza_skryptow.py
) else (
    start "" pythonw baza_skryptow.py
)
