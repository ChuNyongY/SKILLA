@echo off
cd /d "%~dp0"
set "PYTHONPATH=%~dp0src"
start "" "%~dp0.venv\Scripts\pythonw.exe" -m skilla_core.cli run-product-host-credential "%~dp0." "%~dp0config\product_host.json"
