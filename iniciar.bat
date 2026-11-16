@echo off
chcp 65001 >nul
title Generador de Apuntes de YouTube con Gemini
set PYTHONIOENCODING=utf-8

python "%~dp0generar_apunte.py" %*

echo.
pause
