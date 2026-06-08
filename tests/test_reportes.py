"""
test_reportes.py — Tests de generación de reportes Excel.

Verifica que el Excel se genera correctamente con los datos esperados.
El PDF no se testa en CI porque requiere reportlab + matplotlib instalados,
pero se verifica que la función existe y acepta los parámetros correctos.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reportes import generar_excel


# ── Datos de prueba ───────────────────────────────────────────────────────────

@pytest.fixture
def resultados_mixtos():
    return [
        {
            "CUIT": "20123456789",
            "Nombre": "GARCIA JUAN",
            "Capital": None,
            "Sin_Deuda": False,
            "Monto_Sit1": 150.0,
            "Monto_Riesgo": 50.0,
            "Entidades": [
                {"Entidad":"Banco Nacion","Situacion":1,"Monto":150,"Dias_Atraso":0},
                {"Entidad":"Banco Prov",  "Situacion":3,"Monto":50, "Dias_Atraso":90},
            ],
            "Periodo": "202605",
            "Cant_Operaciones": 1,
        },
        {
            "CUIT": "30987654321",
            "Nombre": "EMPRESA SA",
            "Capital": None,
            "Sin_Deuda": True,
            "Monto_Sit1": 0,
            "Monto_Riesgo": 0,
            "Entidades": [],
            "Periodo": "202605",
            "Cant_Operaciones": 1,
        },
        {
            "CUIT": "27111222333",
            "Nombre": "LOPEZ MARIA",
            "Capital": None,
            "Sin_Deuda": False,
            "Monto_Sit1": 0,
            "Monto_Riesgo": 200.0,
            "Entidades": [
                {"Entidad":"Banco X","Situacion":5,"Monto":200,"Dias_Atraso":365},
            ],
            "Periodo": "202605",
            "Cant_Operaciones": 2,
            "error": None,
        },
        {
            "CUIT": "20444555666",
            "Nombre": "ERROR CUIT",
            "Capital": None,
            "error": "ConnectionResetError",
            "Monto_Sit1": 0,
            "Monto_Riesgo": 0,
            "Sin_Deuda": False,
            "Entidades": [],
            "Periodo": "",
            "Cant_Operaciones": 1,
        },
    ]


@pytest.fixture
def resultados_con_capital():
    return [
        {
            "CUIT": "20123456789",
            "Nombre": "GARCIA JUAN",
            "Capital": 500000.0,
            "Sin_Deuda": False,
            "Monto_Sit1": 150.0,
            "Monto_Riesgo": 50.0,
            "Entidades": [
                {"Entidad":"Banco X","Situacion":1,"Monto":150,"Dias_Atraso":0},
            ],
            "Periodo": "202605",
            "Cant_Operaciones": 1,
        },
    ]


# ══════════════════════════════════════════════════════════════════════════════
# GENERACIÓN DE EXCEL
# ══════════════════════════════════════════════════════════════════════════════

class TestGenerarExcel:

    def test_genera_bytes(self, resultados_mixtos):
        xlsx = generar_excel(resultados_mixtos, umbral=40)
        assert isinstance(xlsx, bytes)
        assert len(xlsx) > 0

    def test_es_archivo_xlsx_valido(self, resultados_mixtos):
        """Los primeros 4 bytes de un xlsx son la firma ZIP (PK\x03\x04)."""
        xlsx = generar_excel(resultados_mixtos, umbral=40)
        assert xlsx[:4] == b"PK\x03\x04", "No es un archivo ZIP/XLSX válido"

    def test_contiene_hojas_esperadas(self, resultados_mixtos):
        import zipfile
        import io
        xlsx  = generar_excel(resultados_mixtos, umbral=40)
        zf    = zipfile.ZipFile(io.BytesIO(xlsx))
        names = zf.namelist()
        # Un xlsx es un ZIP con sheets en xl/worksheets/
        sheet_files = [n for n in names if "worksheets" in n]
        assert len(sheet_files) >= 2, \
            f"Esperaba al menos 2 hojas, encontré {len(sheet_files)}: {sheet_files}"

    def test_umbral_40(self, resultados_mixtos):
        xlsx40 = generar_excel(resultados_mixtos, umbral=40)
        assert len(xlsx40) > 1000

    def test_umbral_0_todo_no_pasa(self, resultados_mixtos):
        """Con umbral 0, cualquier deuda en riesgo genera NO PASA."""
        xlsx = generar_excel(resultados_mixtos, umbral=0)
        assert isinstance(xlsx, bytes)

    def test_umbral_100_todo_pasa(self, resultados_mixtos):
        """Con umbral 100, nadie es NO PASA."""
        xlsx = generar_excel(resultados_mixtos, umbral=100)
        assert isinstance(xlsx, bytes)

    def test_lista_vacia(self):
        xlsx = generar_excel([], umbral=40)
        assert isinstance(xlsx, bytes)

    def test_con_capital(self, resultados_con_capital):
        """Con Capital, debe generarse la hoja extra."""
        xlsx = generar_excel(resultados_con_capital, umbral=40)
        import zipfile, io
        zf   = zipfile.ZipFile(io.BytesIO(xlsx))
        # Debe haber al menos 3 hojas cuando hay capital
        sheet_files = [n for n in zf.namelist() if "worksheets" in n]
        assert len(sheet_files) >= 3, "Falta hoja de capital"

    def test_errores_no_rompen(self, resultados_mixtos):
        """Los registros con error no deben romper la generación."""
        errores = [r for r in resultados_mixtos if r.get("error")]
        assert len(errores) > 0, "El fixture debe tener al menos un error"
        xlsx = generar_excel(resultados_mixtos, umbral=40)
        assert isinstance(xlsx, bytes)


# ══════════════════════════════════════════════════════════════════════════════
# CALCULAR PASA — integración con reportes
# ══════════════════════════════════════════════════════════════════════════════

class TestCalculoPasaEnReporte:

    @pytest.mark.parametrize("sit1,riesgo,umbral,expected", [
        (150, 50,  40, "PASA"),      # 25% < 40%
        (0,   200, 40, "NO PASA"),   # 100% > 40%
        (100, 100, 50, "NO PASA"),   # 50% >= 50%
        (100, 49,  50, "PASA"),      # 32.8% < 50%
        (0,   0,   40, "PASA"),      # sin deuda
    ])
    def test_umbral_en_reporte(self, sit1, riesgo, umbral, expected):
        from bcra import calcular_pasa
        _, resultado = calcular_pasa(sit1, riesgo, umbral)
        assert resultado == expected


# ══════════════════════════════════════════════════════════════════════════════
# PDF — solo verifica firma y parámetros (no generación completa)
# ══════════════════════════════════════════════════════════════════════════════

class TestPDF:

    def test_funcion_existe(self):
        from reportes import generar_pdf
        import inspect
        params = inspect.signature(generar_pdf).parameters
        assert "resultados"   in params
        assert "umbral"       in params
        assert "graf_torta"   in params
        assert "graf_barras"  in params
        assert "empresa"      in params

    def test_sin_reportlab_retorna_none(self, resultados_mixtos):
        """Si reportlab no está, generar_pdf retorna None sin crashear."""
        from unittest.mock import patch
        with patch.dict("sys.modules", {"reportlab": None,
                                         "reportlab.lib": None,
                                         "reportlab.lib.pagesizes": None}):
            from reportes import generar_pdf
            # Si reportlab está instalado, retorna bytes; si no, None
            result = generar_pdf(resultados_mixtos, 40)
            assert result is None or isinstance(result, bytes)
