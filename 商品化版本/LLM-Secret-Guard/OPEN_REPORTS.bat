@echo off
cd /d "%~dp0"
if not exist reports mkdir reports
start "" "%CD%\reports"
