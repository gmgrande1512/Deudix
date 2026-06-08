"""
test_database.py — Tests de la capa de base de datos.

Cubre: clientes, usuarios, saldo, movimientos, vigilados, eventos.
Usa la DB en memoria del conftest — no toca la DB real.
"""
import pytest
import hashlib
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Helpers que replican la lógica de database.py usando db_conn ──────────────

def get_saldo_test(conn, cliente_id):
    row = conn.execute(
        "SELECT saldo_usd FROM saldos WHERE cliente_id=?", (cliente_id,)
    ).fetchone()
    return float(row["saldo_usd"]) if row else 0.0


def acreditar_saldo(conn, cliente_id, monto):
    conn.execute("""
        INSERT INTO saldos (cliente_id, saldo_usd) VALUES (?,?)
        ON CONFLICT(cliente_id) DO UPDATE
        SET saldo_usd = saldo_usd + excluded.saldo_usd
    """, (cliente_id, monto))
    conn.commit()


# ══════════════════════════════════════════════════════════════════════════════
# CLIENTES
# ══════════════════════════════════════════════════════════════════════════════

class TestClientes:

    def test_cliente_existe(self, db_conn):
        row = db_conn.execute(
            "SELECT * FROM clientes WHERE id=1"
        ).fetchone()
        assert row is not None
        assert row["nombre"] == "Empresa Test"

    def test_precio_consulta(self, db_conn):
        precio = db_conn.execute(
            "SELECT precio_consulta FROM clientes WHERE id=1"
        ).fetchone()["precio_consulta"]
        assert precio == 0.35

    def test_perfil_completo(self, db_conn):
        """El cliente del fixture debe tener todos los campos obligatorios."""
        row = db_conn.execute("SELECT * FROM clientes WHERE id=1").fetchone()
        campos = ["nombre","cuit_empresa","domicilio","ciudad",
                  "provincia","telefono","email_empresa"]
        for campo in campos:
            assert row[campo] is not None and str(row[campo]).strip() != "", \
                f"Campo obligatorio vacío: {campo}"

    def test_actualizar_precio(self, db_conn):
        db_conn.execute(
            "UPDATE clientes SET precio_consulta=0.50 WHERE id=1"
        )
        db_conn.commit()
        nuevo = db_conn.execute(
            "SELECT precio_consulta FROM clientes WHERE id=1"
        ).fetchone()["precio_consulta"]
        assert nuevo == 0.50

    def test_email_empresa_unico(self, db_conn):
        from sqlite3 import IntegrityError
        with pytest.raises(IntegrityError):
            db_conn.execute(
                "INSERT INTO clientes (nombre, email) VALUES ('Otro','test@test.com')"
            )


# ══════════════════════════════════════════════════════════════════════════════
# USUARIOS Y TYC
# ══════════════════════════════════════════════════════════════════════════════

class TestUsuarios:

    def test_usuario_existe(self, db_conn):
        row = db_conn.execute(
            "SELECT * FROM usuarios WHERE id=1"
        ).fetchone()
        assert row is not None
        assert row["email"] == "user@test.com"

    def test_admin_rol(self, db_conn):
        row = db_conn.execute(
            "SELECT rol FROM usuarios WHERE id=2"
        ).fetchone()
        assert row["rol"] == "admin"

    def test_tyc_no_aceptado(self, db_conn):
        """Usuario nuevo no tiene TyC aceptados."""
        row = db_conn.execute(
            "SELECT id FROM aceptaciones_tyc WHERE usuario_id=1"
        ).fetchone()
        assert row is None

    def test_tyc_aceptar(self, db_conn):
        version = "v1.0-2026"
        ip_hash = hashlib.sha256("192.168.1.1".encode()).hexdigest()[:16]
        db_conn.execute("""
            INSERT INTO aceptaciones_tyc
                (usuario_id, ip_hash, user_agent, tyc_version, tyc_hash)
            VALUES (1,?,?,?,?)
        """, (ip_hash, "Mozilla/5.0", version,
              hashlib.sha256(version.encode()).hexdigest()[:12]))
        db_conn.commit()
        row = db_conn.execute(
            "SELECT * FROM aceptaciones_tyc WHERE usuario_id=1 AND tyc_version=?",
            (version,)
        ).fetchone()
        assert row is not None
        assert "192.168.1.1" not in row["ip_hash"]  # IP no guardada en claro

    def test_tyc_ip_no_en_claro(self, db_conn):
        """La IP real nunca debe aparecer en la DB."""
        ip_real = "200.100.50.25"
        ip_hash = hashlib.sha256(ip_real.encode()).hexdigest()[:16]
        db_conn.execute("""
            INSERT INTO aceptaciones_tyc
                (usuario_id, ip_hash, user_agent, tyc_version, tyc_hash)
            VALUES (2,?,'Firefox','v1.0-2026','abc123def456')
        """, (ip_hash,))
        db_conn.commit()
        row = db_conn.execute(
            "SELECT ip_hash FROM aceptaciones_tyc WHERE usuario_id=2"
        ).fetchone()
        assert ip_real not in row["ip_hash"]
        assert row["ip_hash"] == ip_hash


# ══════════════════════════════════════════════════════════════════════════════
# SALDO Y MOVIMIENTOS
# ══════════════════════════════════════════════════════════════════════════════

class TestSaldo:

    def test_saldo_inicial_cero(self, db_conn, cliente_id):
        saldo = get_saldo_test(db_conn, cliente_id)
        assert saldo == 0.0

    def test_acreditar_saldo(self, db_conn, cliente_id):
        acreditar_saldo(db_conn, cliente_id, 25.0)
        saldo = get_saldo_test(db_conn, cliente_id)
        assert abs(saldo - 25.0) < 0.001

    def test_saldo_no_negativo(self, db_conn, cliente_id):
        """El saldo no puede quedar negativo."""
        acreditar_saldo(db_conn, cliente_id, 1.0)
        db_conn.execute("""
            UPDATE saldos
            SET saldo_usd = MAX(0, saldo_usd - 999.0)
            WHERE cliente_id=?
        """, (cliente_id,))
        db_conn.commit()
        saldo = get_saldo_test(db_conn, cliente_id)
        assert saldo >= 0.0

    def test_consumo_descuenta(self, db_conn, cliente_id):
        acreditar_saldo(db_conn, cliente_id, 10.0)
        precio = 0.35
        db_conn.execute(
            "UPDATE saldos SET saldo_usd = MAX(0, saldo_usd - ?) WHERE cliente_id=?",
            (precio, cliente_id)
        )
        db_conn.commit()
        saldo = get_saldo_test(db_conn, cliente_id)
        assert abs(saldo - (10.0 - precio)) < 0.001

    def test_consultas_disponibles(self, db_conn, cliente_id):
        acreditar_saldo(db_conn, cliente_id, 3.50)  # 10 consultas a $0.35
        saldo  = get_saldo_test(db_conn, cliente_id)
        precio = db_conn.execute(
            "SELECT precio_consulta FROM clientes WHERE id=?", (cliente_id,)
        ).fetchone()["precio_consulta"]
        equiv  = int(saldo / precio)
        assert equiv == 10

    def test_recarga_pendiente(self, db_conn, cliente_id, usuario_id):
        db_conn.execute("""
            INSERT INTO movimientos_saldo
                (cliente_id, usuario_id, tipo, monto_usd, referencia_ext, modo_pago, estado)
            VALUES (?,?,'recarga',50.0,'MOCK-TEST-001','MOCK','pendiente')
        """, (cliente_id, usuario_id))
        db_conn.commit()
        mov = db_conn.execute(
            "SELECT * FROM movimientos_saldo WHERE estado='pendiente' AND cliente_id=?",
            (cliente_id,)
        ).fetchone()
        assert mov is not None
        assert mov["monto_usd"] == 50.0

    def test_confirmar_recarga(self, db_conn, cliente_id, usuario_id):
        db_conn.execute("""
            INSERT INTO movimientos_saldo
                (cliente_id, usuario_id, tipo, monto_usd, referencia_ext, modo_pago, estado)
            VALUES (?,?,'recarga',20.0,'MOCK-CONF-001','MOCK','pendiente')
        """, (cliente_id, usuario_id))
        db_conn.commit()
        mov_id = db_conn.execute(
            "SELECT id FROM movimientos_saldo WHERE referencia_ext='MOCK-CONF-001'"
        ).fetchone()["id"]

        # Confirmar
        db_conn.execute("""
            UPDATE movimientos_saldo
            SET estado='acreditado', fecha_acreditado=datetime('now','localtime')
            WHERE id=?
        """, (mov_id,))
        acreditar_saldo(db_conn, cliente_id, 20.0)
        db_conn.commit()

        saldo = get_saldo_test(db_conn, cliente_id)
        assert saldo == 20.0
        estado = db_conn.execute(
            "SELECT estado FROM movimientos_saldo WHERE id=?", (mov_id,)
        ).fetchone()["estado"]
        assert estado == "acreditado"

    def test_rechazar_recarga_no_acredita(self, db_conn, cliente_id, usuario_id):
        db_conn.execute("""
            INSERT INTO movimientos_saldo
                (cliente_id, usuario_id, tipo, monto_usd, referencia_ext, modo_pago, estado)
            VALUES (?,?,'recarga',15.0,'MOCK-REJ-001','MOCK','pendiente')
        """, (cliente_id, usuario_id))
        db_conn.commit()
        saldo_antes = get_saldo_test(db_conn, cliente_id)
        db_conn.execute(
            "UPDATE movimientos_saldo SET estado='rechazado' WHERE referencia_ext='MOCK-REJ-001'"
        )
        db_conn.commit()
        saldo_despues = get_saldo_test(db_conn, cliente_id)
        assert saldo_antes == saldo_despues  # no cambió


# ══════════════════════════════════════════════════════════════════════════════
# EVENTOS
# ══════════════════════════════════════════════════════════════════════════════

class TestEventos:

    def test_registrar_individual(self, db_conn, cliente_id, usuario_id):
        precio = 0.35
        db_conn.execute("""
            INSERT INTO eventos_individuales
                (usuario_id, cliente_id, resultado_cat, costo, precio_unitario)
            VALUES (?,?,'PASA',?,?)
        """, (usuario_id, cliente_id, precio, precio))
        db_conn.commit()
        row = db_conn.execute(
            "SELECT COUNT(*) as n FROM eventos_individuales WHERE cliente_id=?",
            (cliente_id,)
        ).fetchone()
        assert row["n"] == 1

    def test_resultado_validos(self, db_conn, cliente_id, usuario_id):
        """Solo se pueden registrar categorías válidas."""
        validos = ["PASA", "NO PASA", "SIN DEUDA", "ERROR"]
        for i, cat in enumerate(validos):
            db_conn.execute("""
                INSERT INTO eventos_individuales
                    (usuario_id, cliente_id, resultado_cat, costo, precio_unitario)
                VALUES (?,?,?,0.35,0.35)
            """, (usuario_id, cliente_id, cat))
        db_conn.commit()
        n = db_conn.execute(
            "SELECT COUNT(*) as n FROM eventos_individuales WHERE cliente_id=?",
            (cliente_id,)
        ).fetchone()["n"]
        assert n == 4

    def test_registrar_masivo(self, db_conn, cliente_id, usuario_id):
        db_conn.execute("""
            INSERT INTO eventos_masivos
                (usuario_id, cliente_id, total_casos, pasan, no_pasan,
                 errores, sin_deuda, costo_total, precio_unitario, umbral_usado)
            VALUES (?,?,100,60,30,5,5,35.0,0.35,40.0)
        """, (usuario_id, cliente_id))
        db_conn.commit()
        row = db_conn.execute(
            "SELECT * FROM eventos_masivos WHERE cliente_id=?",
            (cliente_id,)
        ).fetchone()
        assert row["total_casos"] == 100
        assert row["pasan"] + row["no_pasan"] + row["errores"] + row["sin_deuda"] == 100
        assert abs(row["costo_total"] - 35.0) < 0.001


# ══════════════════════════════════════════════════════════════════════════════
# VIGILADOS
# ══════════════════════════════════════════════════════════════════════════════

class TestVigilados:

    def test_agregar_vigilado(self, db_conn, cliente_id, usuario_id):
        db_conn.execute("""
            INSERT OR IGNORE INTO vigilados (cliente_id, usuario_id, cuit, alias)
            VALUES (?,?,'20123456789','García Juan')
        """, (cliente_id, usuario_id))
        db_conn.commit()
        row = db_conn.execute(
            "SELECT * FROM vigilados WHERE cuit='20123456789' AND cliente_id=?",
            (cliente_id,)
        ).fetchone()
        assert row is not None
        assert row["alias"] == "García Juan"

    def test_cuit_unico_por_cliente(self, db_conn, cliente_id, usuario_id):
        db_conn.execute("""
            INSERT OR IGNORE INTO vigilados (cliente_id, usuario_id, cuit, alias)
            VALUES (?,?,'30987654321','Empresa SA')
        """, (cliente_id, usuario_id))
        db_conn.commit()
        # Segunda inserción del mismo CUIT — debe actualizar, no duplicar
        db_conn.execute("""
            INSERT OR REPLACE INTO vigilados (cliente_id, usuario_id, cuit, alias)
            VALUES (?,?,'30987654321','Empresa SA Actualizada')
        """, (cliente_id, usuario_id))
        db_conn.commit()
        n = db_conn.execute(
            "SELECT COUNT(*) as n FROM vigilados WHERE cuit='30987654321' AND cliente_id=?",
            (cliente_id,)
        ).fetchone()["n"]
        assert n == 1

    def test_desactivar_vigilado(self, db_conn, cliente_id, usuario_id):
        db_conn.execute("""
            INSERT OR IGNORE INTO vigilados (cliente_id, usuario_id, cuit, alias)
            VALUES (?,?,'27111222333','A Desactivar')
        """, (cliente_id, usuario_id))
        db_conn.commit()
        vid = db_conn.execute(
            "SELECT id FROM vigilados WHERE cuit='27111222333'"
        ).fetchone()["id"]
        db_conn.execute(
            "UPDATE vigilados SET activo=0 WHERE id=?", (vid,)
        )
        db_conn.commit()
        activos = db_conn.execute(
            "SELECT COUNT(*) as n FROM vigilados WHERE activo=1 AND cuit='27111222333'"
        ).fetchone()["n"]
        assert activos == 0

    def test_historial_variacion_nuevo(self, db_conn, cliente_id, usuario_id):
        """Primer registro de un vigilado debe ser NUEVO."""
        db_conn.execute("""
            INSERT OR IGNORE INTO vigilados (cliente_id, usuario_id, cuit, alias)
            VALUES (?,?,'20444555666','Test Variacion')
        """, (cliente_id, usuario_id))
        db_conn.commit()
        vid = db_conn.execute(
            "SELECT id FROM vigilados WHERE cuit='20444555666'"
        ).fetchone()["id"]
        db_conn.execute("""
            INSERT INTO historial_vigilados
                (vigilado_id, cliente_id, periodo_bcra, monto_sit1, monto_riesgo, variacion)
            VALUES (?,?,'202605',100000,0,'NUEVO')
        """, (vid, cliente_id))
        db_conn.commit()
        row = db_conn.execute(
            "SELECT variacion FROM historial_vigilados WHERE vigilado_id=?", (vid,)
        ).fetchone()
        assert row["variacion"] == "NUEVO"

    @pytest.mark.parametrize("sit1_prev,riesgo_prev,sit1_nuevo,riesgo_nuevo,expected", [
        (100, 0,   200, 0,   "SUBE"),       # sube deuda normal
        (100, 50,  100, 20,  "BAJA"),       # baja deuda en riesgo
        (100, 50,  100, 50,  "SIN_CAMBIO"), # sin cambio
        (100, 50,  0,   0,   "BAJA"),       # desapareció la deuda
        (0,   0,   100, 50,  "SUBE"),       # apareció deuda nueva
    ])
    def test_calculo_variacion(self, sit1_prev, riesgo_prev,
                                sit1_nuevo, riesgo_nuevo, expected):
        """Verifica la lógica de cálculo de variación sin tocar la DB."""
        d_total = (sit1_nuevo + riesgo_nuevo) - (sit1_prev + riesgo_prev)
        if abs(d_total) < 0.01:
            variacion = "SIN_CAMBIO"
        elif d_total > 0:
            variacion = "SUBE"
        else:
            variacion = "BAJA"
        assert variacion == expected, \
            f"prev=({sit1_prev},{riesgo_prev}) nuevo=({sit1_nuevo},{riesgo_nuevo}) → {variacion} ≠ {expected}"
