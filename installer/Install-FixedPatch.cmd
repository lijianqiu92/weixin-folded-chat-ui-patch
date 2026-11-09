@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Manage-FixedPatch.ps1" -Mode Install
