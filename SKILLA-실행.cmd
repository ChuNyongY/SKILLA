@echo off
cd /d "%~dp0"
start "" "%~dp0.venv\Scripts\pythonw.exe" -m javis_core.cli run-product-host-credential "%~dp0." "%~dp0config\product_host.json"
