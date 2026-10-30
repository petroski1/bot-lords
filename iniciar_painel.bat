@echo off
cd /d "%~dp0"
pip install opencv-python numpy flask >nul 2>&1
python painel.py
pause
