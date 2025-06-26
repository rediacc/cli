@echo off
REM Simple CMD wrapper for Rediacc CLI PowerShell script
REM This allows users to run commands from CMD without typing PowerShell

powershell -ExecutionPolicy Bypass -File "%~dp0rediacc.ps1" %*