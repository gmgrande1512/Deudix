@echo off
echo.
echo ============================================
echo   SISTEMA CONSULTA BCRA - Iniciando...
echo ============================================
echo.
echo Instalando/verificando librerias...
pip install streamlit pandas openpyxl requests reportlab --quiet
echo.
echo Abriendo sistema en el navegador...
echo (Para cerrar, presiona Ctrl+C en esta ventana)
echo.
streamlit run app.py --server.port 8501 --server.headless false
pause
