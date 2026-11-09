@echo off
cd /d "%~dp0"
python "%~dp0runtime_patch.py" disable
pause
