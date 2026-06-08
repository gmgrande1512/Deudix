@echo off
echo.
echo ==========================================
echo   DEUDIX - Suite de tests de regresion
echo ==========================================
echo.

cd /d %~dp0\..

echo Instalando pytest...
python -m pip install pytest pytest-cov --quiet

echo.
echo Corriendo tests...
echo.

python -m pytest tests/ -v --tb=short --no-header

echo.
echo ==========================================
echo   Fin de la suite
echo ==========================================
echo.
pause
