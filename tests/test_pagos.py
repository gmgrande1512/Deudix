"""
test_pagos.py — Tests del sistema de pagos en modo MOCK.

Verifica el flujo completo: crear preferencia → registrar → confirmar/rechazar.
No llama a Mercado Pago real.
"""
import pytest
import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestPagosMock:

    def test_crear_preferencia_mock(self):
        """En modo MOCK, crear_preferencia siempre retorna ok=True."""
        with patch("pagos.PAYMENT_MODE", "MOCK"):
            from pagos import crear_preferencia
            result = crear_preferencia(1, 25.0, "Test")
        assert result.ok          == True
        assert result.monto_usd   == 25.0
        assert result.modo        == "MOCK"
        assert result.preferencia_id.startswith("MOCK-")
        assert "mock_pago=" in result.link_pago

    def test_preferencia_id_unico(self):
        """Cada preferencia genera un ID distinto."""
        with patch("pagos.PAYMENT_MODE", "MOCK"):
            from pagos import crear_preferencia
            r1 = crear_preferencia(1, 10.0, "Test 1")
            r2 = crear_preferencia(1, 10.0, "Test 2")
        assert r1.preferencia_id != r2.preferencia_id

    def test_verificar_pago_mock_aprobado(self):
        """En modo MOCK, verificar_pago siempre retorna acreditado."""
        with patch("pagos.PAYMENT_MODE", "MOCK"):
            from pagos import verificar_pago
            status = verificar_pago("MOCK-TEST-001")
        assert status.estado == "acreditado"

    def test_montos_distintos(self):
        """Los paquetes de recarga tienen montos correctos."""
        with patch("pagos.PAYMENT_MODE", "MOCK"):
            from pagos import crear_preferencia
            for monto in [10.0, 25.0, 50.0, 100.0, 250.0]:
                r = crear_preferencia(1, monto, f"Paquete {monto}")
                assert r.monto_usd == monto

    def test_mp_sin_token_retorna_error(self):
        """Sin token configurado o sin libreria, MP retorna error claro."""
        with patch("pagos.PAYMENT_MODE", "PRODUCCION"), \
             patch("pagos.MP_ACCESS_TOKEN", "TEST-xxxx-xxxx"):
            from pagos import crear_preferencia
            result = crear_preferencia(1, 25.0, "Test")
        assert result.ok == False
        # El error puede ser por token invalido O por libreria no instalada
        assert ("Access Token" in result.error or
                "mercadopago" in result.error.lower()), \
            f"Error inesperado: {result.error}" 

    def test_mp_sin_libreria_retorna_error(self):
        """Si mercadopago no está instalado, retorna error descriptivo."""
        with patch("pagos.PAYMENT_MODE", "SANDBOX"), \
             patch("pagos.MP_ACCESS_TOKEN", "APP_USR-real-token"), \
             patch.dict("sys.modules", {"mercadopago": None}):
            from pagos import crear_preferencia
            result = crear_preferencia(1, 25.0, "Test")
        assert result.ok == False


class TestFlujoCompletoMock:
    """
    Simula el flujo completo: generar link → registrar → confirmar → saldo acreditado.
    """

    def test_flujo_recarga_completo(self, db_conn, cliente_id, usuario_id):
        with patch("pagos.PAYMENT_MODE", "MOCK"):
            from pagos import crear_preferencia
            result = crear_preferencia(cliente_id, 50.0, "Recarga test")

        assert result.ok
        pref_id = result.preferencia_id

        # Registrar como pendiente
        db_conn.execute("""
            INSERT INTO movimientos_saldo
                (cliente_id, usuario_id, tipo, monto_usd, consultas_equiv,
                 referencia_ext, modo_pago, estado, descripcion)
            VALUES (?,?,'recarga',50.0,142,?,?,'pendiente','Recarga 50 USD')
        """, (cliente_id, usuario_id, pref_id, result.modo))
        db_conn.commit()

        # Verificar que está pendiente
        mov = db_conn.execute(
            "SELECT * FROM movimientos_saldo WHERE referencia_ext=?",
            (pref_id,)
        ).fetchone()
        assert mov["estado"] == "pendiente"
        assert mov["monto_usd"] == 50.0

        # Confirmar (simula webhook o botón manual)
        db_conn.execute("""
            UPDATE movimientos_saldo
            SET estado='acreditado', fecha_acreditado=datetime('now','localtime')
            WHERE referencia_ext=? AND estado='pendiente'
        """, (pref_id,))
        db_conn.execute("""
            INSERT INTO saldos (cliente_id, saldo_usd) VALUES (?,50.0)
            ON CONFLICT(cliente_id) DO UPDATE SET saldo_usd=saldo_usd+50.0
        """, (cliente_id,))
        db_conn.commit()

        # Verificar saldo acreditado
        saldo = db_conn.execute(
            "SELECT saldo_usd FROM saldos WHERE cliente_id=?", (cliente_id,)
        ).fetchone()["saldo_usd"]
        assert saldo == 50.0

        estado_final = db_conn.execute(
            "SELECT estado FROM movimientos_saldo WHERE referencia_ext=?",
            (pref_id,)
        ).fetchone()["estado"]
        assert estado_final == "acreditado"

    def test_flujo_recarga_rechazada_no_acredita(self, db_conn, cliente_id, usuario_id):
        with patch("pagos.PAYMENT_MODE", "MOCK"):
            from pagos import crear_preferencia
            result = crear_preferencia(cliente_id, 30.0, "Recarga rechazada")

        db_conn.execute("""
            INSERT INTO movimientos_saldo
                (cliente_id, usuario_id, tipo, monto_usd,
                 referencia_ext, modo_pago, estado)
            VALUES (?,?,'recarga',30.0,?,?,'pendiente')
        """, (cliente_id, usuario_id, result.preferencia_id, result.modo))
        db_conn.commit()

        row_antes = db_conn.execute(
            "SELECT COALESCE(saldo_usd,0) FROM saldos WHERE cliente_id=?",
            (cliente_id,)
        ).fetchone()
        saldo_antes_val = row_antes[0] if row_antes else 0.0

        # Rechazar (sin acreditar saldo)
        db_conn.execute("""
            UPDATE movimientos_saldo SET estado='rechazado'
            WHERE referencia_ext=?
        """, (result.preferencia_id,))
        db_conn.commit()

        row_despues = db_conn.execute(
            "SELECT COALESCE(saldo_usd,0) FROM saldos WHERE cliente_id=?",
            (cliente_id,)
        ).fetchone()
        saldo_despues = row_despues[0] if row_despues else 0.0

        assert saldo_despues == saldo_antes_val  # sin cambio
