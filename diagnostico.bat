@echo off
echo.
echo ==========================================
echo   DIAGNOSTICO PYTHON - DEUDIX
echo ==========================================
echo.

echo --- Version de Python ---
python --version
echo.

echo --- Donde esta Python ---
where python
echo.

echo --- Modulos instalados (pytest) ---
python -c "import pytest; print('pytest OK version:', pytest.__version__)"
echo.

echo --- Intentando instalar pytest ---
python -m pip install pytest --quiet
echo.

echo --- Verificando de nuevo ---
python -c "import pytest; print('pytest OK:', pytest.__version__)"
echo.

pause
