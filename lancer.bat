@echo off
cd /d "%~dp0"
python collect.py
python send.py
