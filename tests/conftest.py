"""
conftest.py — Fixtures compartidos para todos los tests de Deudix.

Crea una base de datos SQLite en memoria para cada test,
sin tocar la DB real de producción.
"""
import sys
import os
import sqlite3
import pytest

# Agregar el directorio raíz del proyecto al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Fixture: base de datos en memoria ────────────────────────────────────────

@pytest.fixture
def db_conn():
    """
    Conexión SQLite en memoria con todas las tablas de Deudix.
    Se crea y destruye para cada test — completamente aislada.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE clientes (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre          TEXT    NOT NULL,
            email           TEXT    UNIQUE,
            email_empresa   TEXT,
            precio_consulta REAL    DEFAULT 0.35,
            activo          INTEGER DEFAULT 1,
            fecha_alta      TEXT    DEFAULT (datetime('now','localtime')),
            notas           TEXT,
            razon_social    TEXT,
            cuit_empresa    TEXT,
            domicilio       TEXT,
            ciudad          TEXT,
            provincia       TEXT,
            telefono        TEXT,
            web             TEXT,
            logo_bytes      BLOB
        );

        CREATE TABLE usuarios (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre          TEXT    NOT NULL,
            email           TEXT    UNIQUE NOT NULL,
            password_hash   TEXT    NOT NULL,
            cliente_id      INTEGER REFERENCES clientes(id),
            rol             TEXT    DEFAULT 'user',
            activo          INTEGER DEFAULT 1,
            fecha_alta      TEXT    DEFAULT (datetime('now','localtime')),
            ultimo_acceso   TEXT
        );

        CREATE TABLE aceptaciones_tyc (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id  INTEGER NOT NULL,
            fecha_hora  TEXT,
            ip_hash     TEXT,
            user_agent  TEXT,
            tyc_version TEXT NOT NULL,
            tyc_hash    TEXT NOT NULL
        );

        CREATE TABLE saldos (
            cliente_id  INTEGER PRIMARY KEY,
            saldo_usd   REAL    DEFAULT 0.0,
            actualizado TEXT
        );

        CREATE TABLE movimientos_saldo (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id      INTEGER NOT NULL,
            usuario_id      INTEGER,
            tipo            TEXT    NOT NULL,
            monto_usd       REAL    NOT NULL,
            consultas_equiv INTEGER DEFAULT 0,
            referencia_ext  TEXT,
            modo_pago       TEXT    DEFAULT 'MOCK',
            estado          TEXT    DEFAULT 'pendiente',
            descripcion     TEXT,
            fecha_hora      TEXT    DEFAULT (datetime('now','localtime')),
            fecha_acreditado TEXT
        );

        CREATE TABLE eventos_individuales (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id  INTEGER,
            cliente_id  INTEGER,
            fecha_hora  TEXT,
            resultado_cat TEXT,
            costo       REAL    DEFAULT 0.0,
            precio_unitario REAL DEFAULT 0.0
        );

        CREATE TABLE eventos_masivos (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id      INTEGER,
            cliente_id      INTEGER,
            fecha_hora      TEXT,
            total_casos     INTEGER DEFAULT 0,
            pasan           INTEGER DEFAULT 0,
            no_pasan        INTEGER DEFAULT 0,
            errores         INTEGER DEFAULT 0,
            sin_deuda       INTEGER DEFAULT 0,
            costo_total     REAL    DEFAULT 0.0,
            precio_unitario REAL    DEFAULT 0.0,
            umbral_usado    REAL    DEFAULT 0.0
        );

        CREATE TABLE vigilados (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id      INTEGER NOT NULL,
            usuario_id      INTEGER,
            cuit            TEXT    NOT NULL,
            alias           TEXT,
            activo          INTEGER DEFAULT 1,
            fecha_alta      TEXT,
            ultima_consulta TEXT,
            UNIQUE(cliente_id, cuit)
        );

        CREATE TABLE historial_vigilados (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            vigilado_id     INTEGER NOT NULL,
            cliente_id      INTEGER NOT NULL,
            periodo_bcra    TEXT,
            fecha_consulta  TEXT,
            monto_sit1      REAL    DEFAULT 0.0,
            monto_riesgo    REAL    DEFAULT 0.0,
            cant_entidades  INTEGER DEFAULT 0,
            situacion_peor  INTEGER DEFAULT 0,
            sin_deuda       INTEGER DEFAULT 0,
            variacion       TEXT    DEFAULT 'NUEVO',
            delta_sit1      REAL    DEFAULT 0.0,
            delta_riesgo    REAL    DEFAULT 0.0,
            costo           REAL    DEFAULT 0.0,
            error           TEXT
        );

        -- Datos base para los tests
        INSERT INTO clientes (id, nombre, email, precio_consulta,
                              cuit_empresa, domicilio, ciudad, provincia,
                              telefono, email_empresa)
        VALUES (1, 'Empresa Test', 'test@test.com', 0.35,
                '30-12345678-9', 'Av. Test 123', 'Buenos Aires', 'CABA',
                '(011) 1234-5678', 'contacto@test.com');

        INSERT INTO usuarios (id, nombre, email, password_hash, cliente_id, rol)
        VALUES (1, 'Usuario Test', 'user@test.com', 'hash_ficticio', 1, 'user');

        INSERT INTO usuarios (id, nombre, email, password_hash, cliente_id, rol)
        VALUES (2, 'Admin Test', 'admin@test.com', 'hash_ficticio', 1, 'admin');
    """)
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def cliente_id():
    return 1


@pytest.fixture
def usuario_id():
    return 1


# ── Respuestas BCRA de ejemplo ────────────────────────────────────────────────

@pytest.fixture
def respuesta_bcra_con_deuda():
    """Respuesta típica de la API BCRA para un deudor con deuda."""
    return {
        "results": {
            "identificacion": {"denominacion": "GARCIA JUAN CARLOS"},
            "periodos": [{
                "periodo": "202605",
                "entidades": [
                    {"entidad": "Banco Nacion", "situacion": 1,
                     "monto": 150.0, "diasAtrasoPago": 0},
                    {"entidad": "Banco Provincia", "situacion": 3,
                     "monto": 50.0,  "diasAtrasoPago": 90},
                ]
            }]
        }
    }


@pytest.fixture
def respuesta_bcra_sin_deuda():
    """Respuesta BCRA para alguien sin deuda registrada."""
    return {
        "results": {
            "identificacion": {"denominacion": "EMPRESA LIMPIA SA"},
            "periodos": []
        }
    }


@pytest.fixture
def respuesta_bcra_todo_riesgo():
    """Respuesta BCRA con toda la deuda en situación de riesgo."""
    return {
        "results": {
            "periodos": [{
                "periodo": "202605",
                "entidades": [
                    {"entidad": "Banco X", "situacion": 4,
                     "monto": 200.0, "diasAtrasoPago": 180},
                    {"entidad": "Banco Y", "situacion": 5,
                     "monto": 100.0, "diasAtrasoPago": 365},
                ]
            }]
        }
    }
