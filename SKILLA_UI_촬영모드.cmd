@echo off
cd /d "%~dp0"
start "" ".venv\Scripts\pythonw.exe" "tools\run_skilla_ui_preview.py" showcase
