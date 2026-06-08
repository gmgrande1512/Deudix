"""
test_bcra.py — Tests de la lógica de procesamiento de respuestas BCRA.

NO llama a la API real — usa respuestas simuladas del conftest.
Cubre: extracción de nombre, cálculo de montos, calcular_pasa, normalizar_columnas.
"""
import pytest
import sys
import os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bcra import (
    procesar_respuesta, calcular_pasa, extraer_nombre_api,
    periodo_a_texto, normalizar_columnas, detalle_str,
)


# ══════════════════════════════════════════════════════════════════════════════
# EXTRACCIÓN DE NOMBRE
# ══════════════════════════════════════════════════════════════════════════════

class TestExtraerNombre:

    def test_nombre_en_identificacion(self, respuesta_bcra_con_deuda):
        nombre = extraer_nombre_api(respuesta_bcra_con_deuda)
        assert nombre == "GARCIA JUAN CARLOS"

    def test_none_retorna_vacio(self):
        assert extraer_nombre_api(None) == ""

    def test_sin_nombre_retorna_vacio(self):
        assert extraer_nombre_api({"results": {}}) == ""

    def test_nombre_en_periodos(self):
        data = {"results": {"periodos": [{"denominacion": "EMPRESA X SA"}]}}
        nombre = extraer_nombre_api(data)
        assert nombre == "EMPRESA X SA"


# ══════════════════════════════════════════════════════════════════════════════
# PROCESAR RESPUESTA
# ══════════════════════════════════════════════════════════════════════════════

class TestProcesarRespuesta:

    def test_con_deuda(self, respuesta_bcra_con_deuda):
        r = procesar_respuesta(respuesta_bcra_con_deuda, "20123456789")
        assert r["CUIT"]          == "20123456789"
        assert r["Sin_Deuda"]     == False
        assert r["Monto_Sit1"]    == 150.0   # entidad en sit 1
        assert r["Monto_Riesgo"]  == 50.0    # entidad en sit 3
        assert len(r["Entidades"]) == 2
        assert r["Periodo"]       == "202605"
        assert r["Nombre"]        == "GARCIA JUAN CARLOS"

    def test_sin_deuda(self, respuesta_bcra_sin_deuda):
        r = procesar_respuesta(respuesta_bcra_sin_deuda, "20999888777")
        assert r["Sin_Deuda"]    == True
        assert r["Monto_Sit1"]   == 0
        assert r["Monto_Riesgo"] == 0
        assert r["Entidades"]    == []

    def test_todo_riesgo(self, respuesta_bcra_todo_riesgo):
        r = procesar_respuesta(respuesta_bcra_todo_riesgo, "30111222333")
        assert r["Monto_Sit1"]   == 0
        assert r["Monto_Riesgo"] == 300.0  # 200 + 100
        assert r["Sin_Deuda"]    == False

    def test_none_retorna_sin_deuda(self):
        r = procesar_respuesta(None, "20000000000")
        assert r["Sin_Deuda"] == True

    def test_nombre_override(self, respuesta_bcra_con_deuda):
        """Si se pasa nombre, tiene prioridad sobre el de la API."""
        r = procesar_respuesta(respuesta_bcra_con_deuda, "20123456789",
                               nombre="NOMBRE OVERRIDE")
        assert r["Nombre"] == "NOMBRE OVERRIDE"

    def test_capital_se_guarda(self, respuesta_bcra_con_deuda):
        r = procesar_respuesta(respuesta_bcra_con_deuda, "20123456789",
                               capital=500000.0)
        assert r["Capital"] == 500000.0

    def test_situaciones_clasificadas(self, respuesta_bcra_con_deuda):
        """Sit 1 va a Monto_Sit1, sit 2-5 van a Monto_Riesgo."""
        r = procesar_respuesta(respuesta_bcra_con_deuda, "20123456789")
        sit1_ents   = [e for e in r["Entidades"] if e["Situacion"] == 1]
        riesgo_ents = [e for e in r["Entidades"] if e["Situacion"] in [2,3,4,5]]
        total_sit1   = sum(e["Monto"] for e in sit1_ents)
        total_riesgo = sum(e["Monto"] for e in riesgo_ents)
        assert total_sit1   == r["Monto_Sit1"]
        assert total_riesgo == r["Monto_Riesgo"]


# ══════════════════════════════════════════════════════════════════════════════
# CALCULAR PASA / NO PASA
# ══════════════════════════════════════════════════════════════════════════════

class TestCalcularPasa:

    @pytest.mark.parametrize("sit1,riesgo,umbral,expected_resultado", [
        (100, 0,   40, "PASA"),        # sin riesgo siempre pasa
        (0,   0,   40, "PASA"),        # sin deuda pasa
        (100, 50,  40, "NO PASA"),     # 50/150 = 33% < 40% → PASA? No: 33 < 40 → PASA
        (100, 50,  30, "NO PASA"),     # 33% > 30% → NO PASA
        (100, 50,  34, "PASA"),        # 33% < 34% → PASA
        (0,   100, 40, "NO PASA"),     # 100% en riesgo → NO PASA
        (200, 100, 40, "BAJA"),        # 33% < 40% → PASA (override siguiente)
    ])
    def test_umbral_variado(self, sit1, riesgo, umbral, expected_resultado):
        """Verifica que el cálculo del umbral sea correcto para distintos casos."""
        ratio, resultado = calcular_pasa(sit1, riesgo, umbral)
        total = sit1 + riesgo
        if total == 0:
            assert resultado == "PASA"
        else:
            ratio_real = riesgo / total * 100
            expected   = "NO PASA" if ratio_real >= umbral else "PASA"
            assert resultado == expected, \
                f"sit1={sit1} riesgo={riesgo} umbral={umbral}: {ratio_real:.1f}% → {resultado} ≠ {expected}"

    def test_ratio_correcto(self):
        ratio, _ = calcular_pasa(100, 50, 40)
        assert abs(ratio - 33.33) < 0.1

    def test_sin_deuda_ratio_cero(self):
        ratio, resultado = calcular_pasa(0, 0, 40)
        assert ratio == 0.0
        assert resultado == "PASA"

    def test_todo_riesgo_ratio_100(self):
        ratio, resultado = calcular_pasa(0, 200, 40)
        assert ratio == 100.0
        assert resultado == "NO PASA"


# ══════════════════════════════════════════════════════════════════════════════
# PERIODO A TEXTO
# ══════════════════════════════════════════════════════════════════════════════

class TestPeriodoATexto:

    @pytest.mark.parametrize("periodo,expected", [
        ("202601", "Enero 2026"),
        ("202606", "Junio 2026"),
        ("202512", "Diciembre 2025"),
        ("",       ""),
        ("XXXX",   "XXXX"),
    ])
    def test_conversion(self, periodo, expected):
        resultado = periodo_a_texto(periodo)
        assert resultado == expected


# ══════════════════════════════════════════════════════════════════════════════
# NORMALIZAR COLUMNAS EXCEL
# ══════════════════════════════════════════════════════════════════════════════

class TestNormalizarColumnas:

    def _df(self, cols):
        return pd.DataFrame({c: [] for c in cols})

    def test_detecta_cuit(self):
        df, cuit, nombre, capital = normalizar_columnas(self._df(["CUIT","NOMBRE"]))
        assert cuit   == "CUIT"
        assert nombre == "NOMBRE"

    def test_detecta_cuil(self):
        df, cuit, _, _ = normalizar_columnas(self._df(["CUIL"]))
        assert cuit == "CUIL"

    def test_detecta_capital(self):
        df, _, _, cap = normalizar_columnas(self._df(["CUIT","CAPITAL"]))
        assert cap == "CAPITAL"

    def test_detecta_total_como_capital(self):
        df, _, _, cap = normalizar_columnas(self._df(["CUIT","TOTAL"]))
        assert cap == "TOTAL"

    def test_sin_cuit_retorna_none(self):
        df, cuit, _, _ = normalizar_columnas(self._df(["NOMBRE","MONTO"]))
        assert cuit is None

    def test_mayusculas(self):
        """Las columnas en minúscula deben normalizarse."""
        df_raw = pd.DataFrame({"cuit": [], "nombre": []})
        df, cuit, nombre, _ = normalizar_columnas(df_raw)
        assert cuit   == "CUIT"
        assert nombre == "NOMBRE"


# ══════════════════════════════════════════════════════════════════════════════
# DETALLE STR
# ══════════════════════════════════════════════════════════════════════════════

class TestDetalleStr:

    def test_una_entidad(self):
        ents = [{"Entidad":"Banco Nacion","Situacion":1,"Monto":100}]
        s = detalle_str(ents)
        assert "Banco Nacion" in s
        assert "Sit: 1" in s

    def test_vacio(self):
        assert detalle_str([]) == ""
