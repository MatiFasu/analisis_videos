@echo off
chcp 65001 >nul
title Generador de Apuntes de YouTube con Gemini

python "%~dp0generar_apunte.py" %*

echo.
pause
