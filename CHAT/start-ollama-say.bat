@echo off
cd /d "%~dp0"
python serve_ollama_say.py
if errorlevel 1 pause
