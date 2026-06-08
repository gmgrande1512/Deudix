"""
database.py — Gestión de base de datos SQLite para Deudix

Principio de privacidad (Ley 25.326 Argentina):
  Deudix no almacena datos de las personas consultadas.
  Solo se registran métricas operacionales propias del servicio.

Tablas:
  clientes              — empresas cliente con perfil completo y logo
  usuarios              — operadores de cada empresa
  aceptaciones_tyc      — registro de aceptación de TyC
  eventos_masivos       — una fila por corrida batch (totales, sin CUITs)
  eventos_individuales  — una fila por consulta puntual (sin CUIT)
"""
import sqlite3
import os
import hashlib
from datetime import datetime
from config import PRECIO_DEFAULT_USD

# En Streamlit Cloud /mount/src es read-only — usar /tmp que persiste en la sesion
# En local usar la carpeta del proyecto
_es_cloud = os.path.exists("/mount/src")
DB_PATH = "/tmp/deudix.db" if _es_cloud else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "deudix.db"
)

TYC_VERSION = "v1.0-2026"
TYC_HASH    = hashlib.sha256(TYC_VERSION.encode()).hexdigest()[:12]

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()

    # ── clientes ──────────────────────────────────────────────────────────────
    # email         = email administrativo / de contacto interno Deudix
    # email_empresa = email público de la empresa (va en reportes y PDF)
    # logo_bytes    = imagen PNG/JPG guardada como BLOB
    c.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre          TEXT    NOT NULL,
            email           TEXT    UNIQUE,
            email_empresa   TEXT,
            precio_consulta REAL    DEFAULT 0.0,
            activo          INTEGER DEFAULT 1,
            fecha_alta      TEXT    DEFAULT (datetime('now','localtime')),
            notas           TEXT,
            -- perfil empresa
            razon_social    TEXT,
            cuit_empresa    TEXT,
            domicilio       TEXT,
            ciudad          TEXT,
            provincia       TEXT,
            telefono        TEXT,
            web             TEXT,
            logo_bytes      BLOB
        )
    """)

    # Migraciones: agregar columnas nuevas si la tabla ya existía
    columnas_nuevas = [
        ("email_empresa", "TEXT"),
        ("razon_social",  "TEXT"),
        ("cuit_empresa",  "TEXT"),
        ("domicilio",     "TEXT"),
        ("ciudad",        "TEXT"),
        ("provincia",     "TEXT"),
        ("telefono",      "TEXT"),
        ("web",           "TEXT"),
        ("logo_bytes",    "BLOB"),
    ]
    cols_existentes = {row[1] for row in c.execute("PRAGMA table_info(clientes)").fetchall()}
    for col, tipo in columnas_nuevas:
        if col not in cols_existentes:
            c.execute(f"ALTER TABLE clientes ADD COLUMN {col} {tipo}")

    # ── usuarios ──────────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre          TEXT    NOT NULL,
            email           TEXT    UNIQUE NOT NULL,
            password_hash   TEXT    NOT NULL,
            cliente_id      INTEGER REFERENCES clientes(id),
            rol             TEXT    DEFAULT 'user',
            activo          INTEGER DEFAULT 1,
            aprobado        INTEGER DEFAULT 0,
            fecha_alta      TEXT    DEFAULT (datetime('now','localtime')),
            ultimo_acceso   TEXT
        )
    """)

    # Migración: aprobado
    _cols_u = {r[1] for r in c.execute("PRAGMA table_info(usuarios)").fetchall()}
    if "aprobado" not in _cols_u:
        c.execute("ALTER TABLE usuarios ADD COLUMN aprobado INTEGER DEFAULT 0")
        c.execute("UPDATE usuarios SET aprobado=1 WHERE rol='admin'")

    # ── aceptaciones_tyc ─────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS aceptaciones_tyc (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id      INTEGER NOT NULL REFERENCES usuarios(id),
            fecha_hora      TEXT    DEFAULT (datetime('now','localtime')),
            ip_hash         TEXT,
            user_agent      TEXT,
            tyc_version     TEXT    NOT NULL,
            tyc_hash        TEXT    NOT NULL
        )
    """)

    # ── eventos_masivos ───────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS eventos_masivos (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id      INTEGER REFERENCES usuarios(id),
            cliente_id      INTEGER REFERENCES clientes(id),
            fecha_hora      TEXT    DEFAULT (datetime('now','localtime')),
            total_casos     INTEGER DEFAULT 0,
            pasan           INTEGER DEFAULT 0,
            no_pasan        INTEGER DEFAULT 0,
            errores         INTEGER DEFAULT 0,
            sin_deuda       INTEGER DEFAULT 0,
            costo_total     REAL    DEFAULT 0.0,
            precio_unitario REAL    DEFAULT 0.0,
            umbral_usado    REAL    DEFAULT 0.0
        )
    """)

    # ── eventos_individuales ──────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS eventos_individuales (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id      INTEGER REFERENCES usuarios(id),
            cliente_id      INTEGER REFERENCES clientes(id),
            fecha_hora      TEXT    DEFAULT (datetime('now','localtime')),
            resultado_cat   TEXT,
            costo           REAL    DEFAULT 0.0,
            precio_unitario REAL    DEFAULT 0.0
        )
    """)

    # ── saldos ───────────────────────────────────────────────────────────────
    # Un registro por cliente. saldo_usd es el saldo disponible actual.
    c.execute("""
        CREATE TABLE IF NOT EXISTS saldos (
            cliente_id      INTEGER PRIMARY KEY REFERENCES clientes(id),
            saldo_usd       REAL    DEFAULT 0.0,
            actualizado     TEXT    DEFAULT (datetime('now','localtime'))
        )
    """)

    # ── movimientos_saldo ─────────────────────────────────────────────────────
    # Historial completo de recargas y consumos.
    # tipo: 'recarga' | 'consumo' | 'ajuste_admin' | 'reembolso'
    # estado: 'pendiente' | 'acreditado' | 'rechazado' | 'cancelado'
    c.execute("""
        CREATE TABLE IF NOT EXISTS movimientos_saldo (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id      INTEGER NOT NULL REFERENCES clientes(id),
            usuario_id      INTEGER REFERENCES usuarios(id),
            tipo            TEXT    NOT NULL,
            monto_usd       REAL    NOT NULL,
            consultas_equiv INTEGER DEFAULT 0,
            referencia_ext  TEXT,
            modo_pago       TEXT    DEFAULT 'MOCK',
            estado          TEXT    DEFAULT 'pendiente',
            descripcion     TEXT,
            fecha_hora      TEXT    DEFAULT (datetime('now','localtime')),
            fecha_acreditado TEXT
        )
    """)


    # ── vigilados ─────────────────────────────────────────────────────────────
    # CUITs/CUILs que el cliente quiere monitorear mes a mes.
    c.execute("""
        CREATE TABLE IF NOT EXISTS vigilados (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id       INTEGER NOT NULL REFERENCES clientes(id),
            usuario_id       INTEGER REFERENCES usuarios(id),
            cuit             TEXT    NOT NULL,
            alias            TEXT,
            activo           INTEGER DEFAULT 1,
            fecha_alta       TEXT    DEFAULT (datetime('now','localtime')),
            ultima_consulta  TEXT,
            umbral_pct       REAL    DEFAULT 40.0,
            UNIQUE(cliente_id, cuit)
        )
    """)

    # Migración: agregar umbral_pct si ya existía la tabla sin ese campo
    _cols_v = {r[1] for r in c.execute("PRAGMA table_info(vigilados)").fetchall()}
    if "umbral_pct" not in _cols_v:
        c.execute("ALTER TABLE vigilados ADD COLUMN umbral_pct REAL DEFAULT 40.0")

    # ── historial_vigilados ───────────────────────────────────────────────────
    # Un registro por (vigilado, periodo). Guarda la foto del mes y la variación.
    # variacion: 'NUEVO' | 'SIN_CAMBIO' | 'SUBE' | 'BAJA' | 'DESAPARECE' | 'ERROR'
    c.execute("""
        CREATE TABLE IF NOT EXISTS historial_vigilados (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            vigilado_id      INTEGER NOT NULL REFERENCES vigilados(id),
            cliente_id       INTEGER NOT NULL,
            periodo_bcra     TEXT,
            fecha_consulta   TEXT    DEFAULT (datetime('now','localtime')),
            monto_sit1       REAL    DEFAULT 0.0,
            monto_riesgo     REAL    DEFAULT 0.0,
            cant_entidades   INTEGER DEFAULT 0,
            situacion_peor   INTEGER DEFAULT 0,
            sin_deuda        INTEGER DEFAULT 0,
            variacion        TEXT    DEFAULT 'NUEVO',
            delta_sit1       REAL    DEFAULT 0.0,
            delta_riesgo     REAL    DEFAULT 0.0,
            costo            REAL    DEFAULT 0.0,
            error            TEXT
        )
    """)

    # ── reportes_seguimiento ─────────────────────────────────────────────────
    # Guarda el PDF generado en cada ejecución mensual del seguimiento.
    c.execute("""
        CREATE TABLE IF NOT EXISTS reportes_seguimiento (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id  INTEGER NOT NULL REFERENCES clientes(id),
            usuario_id  INTEGER REFERENCES usuarios(id),
            periodo     TEXT    NOT NULL,
            fecha_gen   TEXT    DEFAULT (datetime('now','localtime')),
            total_cuits INTEGER DEFAULT 0,
            suben       INTEGER DEFAULT 0,
            bajan       INTEGER DEFAULT 0,
            sin_cambio  INTEGER DEFAULT 0,
            errores     INTEGER DEFAULT 0,
            pdf_bytes   BLOB
        )
    """)

    # ── log de migraciones ────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS _migracion_log (
            id    INTEGER PRIMARY KEY AUTOINCREMENT,
            accion TEXT,
            fecha  TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    if c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='consultas'").fetchone():
        c.execute("DROP TABLE consultas")
        c.execute("INSERT INTO _migracion_log (accion) VALUES ('tabla consultas eliminada — migración privacidad')")

    # ── Admin por defecto ─────────────────────────────────────────────────────
    c.execute("SELECT COUNT(*) FROM clientes WHERE id=1")
    if c.fetchone()[0] == 0:
        c.execute("""
            INSERT INTO clientes (id, nombre, email, precio_consulta, notas)
            VALUES (1, 'Administración Deudix', 'admin@deudix.com', 0.0, 'Cliente interno')
        """)
    c.execute("SELECT COUNT(*) FROM usuarios WHERE email='admin@deudix.com'")
    if c.fetchone()[0] == 0:
        import bcrypt
        pw_hash = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode()
        c.execute("""
            INSERT INTO usuarios (nombre, email, password_hash, cliente_id, rol, aprobado)
            VALUES ('Administrador', 'admin@deudix.com', ?, 1, 'admin', 1)
        """, (pw_hash,))

    conn.commit()
    conn.close()

# ── Usuarios ──────────────────────────────────────────────────────────────────

def get_usuario(email: str, solo_aprobados: bool = True):
    conn = get_conn()
    filtro = "AND activo=1 AND aprobado=1" if solo_aprobados else "AND activo=1"
    u = conn.execute(f"SELECT * FROM usuarios WHERE email=? {filtro}", (email,)).fetchone()
    conn.close()
    return dict(u) if u else None


def get_usuario_cualquier_estado(email: str):
    conn = get_conn()
    u = conn.execute("SELECT * FROM usuarios WHERE email=?", (email,)).fetchone()
    conn.close()
    return dict(u) if u else None

def actualizar_ultimo_acceso(usuario_id: int):
    conn = get_conn()
    conn.execute("UPDATE usuarios SET ultimo_acceso=datetime('now','localtime') WHERE id=?", (usuario_id,))
    conn.commit()
    conn.close()

def crear_usuario(nombre, email, password, cliente_id, rol="user"):
    import bcrypt
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    conn = get_conn()
    try:
        conn.execute("""
            INSERT INTO usuarios (nombre, email, password_hash, cliente_id, rol)
            VALUES (?, ?, ?, ?, ?)
        """, (nombre, email, pw_hash, cliente_id, rol))
        conn.commit()
        return True, "Usuario creado correctamente"
    except sqlite3.IntegrityError:
        return False, "El email ya existe"
    finally:
        conn.close()

def listar_usuarios():
    conn = get_conn()
    rows = conn.execute("""
        SELECT u.*, c.nombre as cliente_nombre
        FROM usuarios u
        LEFT JOIN clientes c ON u.cliente_id = c.id
        ORDER BY u.fecha_alta DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ── Clientes ──────────────────────────────────────────────────────────────────

def listar_clientes():
    conn = get_conn()
    # No retornamos logo_bytes en el listado (pesado) — solo en get_cliente
    rows = conn.execute("""
        SELECT id, nombre, email, email_empresa, precio_consulta, activo,
               fecha_alta, notas, razon_social, cuit_empresa,
               domicilio, ciudad, provincia, telefono, web
        FROM clientes ORDER BY nombre
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_cliente(cliente_id: int) -> dict:
    """Devuelve el cliente completo incluyendo logo_bytes."""
    conn = get_conn()
    row = conn.execute("SELECT * FROM clientes WHERE id=?", (cliente_id,)).fetchone()
    conn.close()
    return dict(row) if row else {}

def crear_cliente(nombre, email, precio_consulta, notas="",
                  email_empresa="", razon_social="", cuit_empresa="",
                  domicilio="", ciudad="", provincia="", telefono="", web=""):
    conn = get_conn()
    try:
        conn.execute("""
            INSERT INTO clientes
                (nombre, email, email_empresa, precio_consulta, notas,
                 razon_social, cuit_empresa, domicilio, ciudad, provincia, telefono, web)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (nombre, email, email_empresa, precio_consulta, notas,
              razon_social, cuit_empresa, domicilio, ciudad, provincia, telefono, web))
        conn.commit()
        return True, "Cliente creado correctamente"
    except sqlite3.IntegrityError:
        return False, "El email ya existe"
    finally:
        conn.close()

def actualizar_perfil_cliente(cliente_id: int, datos: dict):
    """
    Actualiza campos de perfil de empresa.
    datos: dict con cualquier subconjunto de campos editables.
    logo_bytes se maneja por separado con actualizar_logo_cliente().
    """
    campos_permitidos = {
        "nombre", "email", "email_empresa", "precio_consulta", "notas",
        "razon_social", "cuit_empresa", "domicilio", "ciudad",
        "provincia", "telefono", "web",
    }
    sets  = []
    vals  = []
    for k, v in datos.items():
        if k in campos_permitidos:
            sets.append(f"{k}=?")
            vals.append(v)
    if not sets:
        return
    vals.append(cliente_id)
    conn = get_conn()
    conn.execute(f"UPDATE clientes SET {', '.join(sets)} WHERE id=?", vals)
    conn.commit()
    conn.close()

def actualizar_logo_cliente(cliente_id: int, logo_bytes: bytes):
    conn = get_conn()
    conn.execute("UPDATE clientes SET logo_bytes=? WHERE id=?", (logo_bytes, cliente_id))
    conn.commit()
    conn.close()

def actualizar_precio_cliente(cliente_id, precio):
    conn = get_conn()
    conn.execute("UPDATE clientes SET precio_consulta=? WHERE id=?", (precio, cliente_id))
    conn.commit()
    conn.close()

def get_precio_cliente(cliente_id) -> float:
    conn = get_conn()
    row = conn.execute("SELECT precio_consulta FROM clientes WHERE id=?", (cliente_id,)).fetchone()
    conn.close()
    return float(row["precio_consulta"]) if row else 0.0

# ── Términos y condiciones ────────────────────────────────────────────────────

def usuario_acepto_tyc(usuario_id: int) -> bool:
    conn = get_conn()
    row = conn.execute("""
        SELECT id FROM aceptaciones_tyc
        WHERE usuario_id=? AND tyc_version=? LIMIT 1
    """, (usuario_id, TYC_VERSION)).fetchone()
    conn.close()
    return row is not None

def registrar_aceptacion_tyc(usuario_id: int, ip_raw: str = "", user_agent: str = ""):
    ip_hash = hashlib.sha256(ip_raw.encode()).hexdigest()[:16] if ip_raw else "desconocida"
    conn = get_conn()
    conn.execute("""
        INSERT INTO aceptaciones_tyc
            (usuario_id, ip_hash, user_agent, tyc_version, tyc_hash)
        VALUES (?, ?, ?, ?, ?)
    """, (usuario_id, ip_hash, user_agent[:300], TYC_VERSION, TYC_HASH))
    conn.commit()
    conn.close()

def listar_aceptaciones_tyc():
    conn = get_conn()
    rows = conn.execute("""
        SELECT u.id AS usuario_id, u.nombre AS usuario, u.email,
               cl.nombre AS cliente, u.fecha_alta,
               a.fecha_hora AS fecha_aceptacion, a.ip_hash,
               a.user_agent, a.tyc_version, a.tyc_hash,
               CASE WHEN a.id IS NOT NULL THEN 1 ELSE 0 END AS acepto
        FROM usuarios u
        LEFT JOIN clientes cl ON u.cliente_id = cl.id
        LEFT JOIN aceptaciones_tyc a
               ON u.id = a.usuario_id AND a.tyc_version = ?
        ORDER BY u.fecha_alta DESC
    """, (TYC_VERSION,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ── Registro de eventos ───────────────────────────────────────────────────────

def registrar_evento_individual(usuario_id, cliente_id, resultado_cat):
    precio = get_precio_cliente(cliente_id)
    conn   = get_conn()
    conn.execute("""
        INSERT INTO eventos_individuales
            (usuario_id, cliente_id, resultado_cat, costo, precio_unitario)
        VALUES (?, ?, ?, ?, ?)
    """, (usuario_id, cliente_id, resultado_cat, precio, precio))
    conn.commit()
    conn.close()
    # Descontar del saldo (sin bloquear si no hay saldo — se registra igual)
    consumir_saldo(cliente_id, usuario_id, 1, "Consulta individual")

def registrar_evento_masivo(usuario_id, cliente_id, resultados: list, umbral: float):
    precio_unit = get_precio_cliente(cliente_id)
    pasan = no_pasan = sin_deuda = errores = 0
    for r in resultados:
        if r.get("error"):
            errores += 1; continue
        if r.get("Sin_Deuda"):
            sin_deuda += 1; continue
        total = r.get("Monto_Sit1", 0) + r.get("Monto_Riesgo", 0)
        if total == 0:
            pasan += 1
        elif r.get("Monto_Riesgo", 0) / total * 100 >= umbral:
            no_pasan += 1
        else:
            pasan += 1
    casos_validos = pasan + no_pasan + sin_deuda
    costo_total   = casos_validos * precio_unit
    conn = get_conn()
    conn.execute("""
        INSERT INTO eventos_masivos
            (usuario_id, cliente_id, total_casos, pasan, no_pasan,
             errores, sin_deuda, costo_total, precio_unitario, umbral_usado)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (usuario_id, cliente_id, len(resultados), pasan, no_pasan,
          errores, sin_deuda, costo_total, precio_unit, umbral))
    conn.commit()
    conn.close()
    # Descontar del saldo por los casos válidos procesados
    if casos_validos > 0:
        consumir_saldo(cliente_id, usuario_id, casos_validos,
                       f"Carga masiva — {casos_validos} casos")
    return costo_total

# ── Consultas para reportes ───────────────────────────────────────────────────

def get_resumen_mes(cliente_id=None, anio=None, mes=None) -> dict:
    now     = datetime.now()
    anio    = anio or now.year
    mes     = mes  or now.month
    periodo = f"{anio}-{mes:02d}"
    conn    = get_conn()
    filtro  = "AND cliente_id=?" if cliente_id else ""
    params  = (periodo, cliente_id) if cliente_id else (periodo,)

    ind = conn.execute(f"""
        SELECT COUNT(*) AS total, COALESCE(SUM(costo),0) AS costo,
               COUNT(CASE WHEN resultado_cat='PASA'      THEN 1 END) AS pasan,
               COUNT(CASE WHEN resultado_cat='NO PASA'   THEN 1 END) AS no_pasan,
               COUNT(CASE WHEN resultado_cat='SIN DEUDA' THEN 1 END) AS sin_deuda,
               COUNT(CASE WHEN resultado_cat='ERROR'     THEN 1 END) AS errores
        FROM eventos_individuales
        WHERE strftime('%Y-%m', fecha_hora)=? {filtro}
    """, params).fetchone()

    mas = conn.execute(f"""
        SELECT COUNT(*) AS corridas, COALESCE(SUM(total_casos),0) AS total_casos,
               COALESCE(SUM(pasan),0) AS pasan,   COALESCE(SUM(no_pasan),0) AS no_pasan,
               COALESCE(SUM(sin_deuda),0) AS sin_deuda, COALESCE(SUM(errores),0) AS errores,
               COALESCE(SUM(costo_total),0) AS costo
        FROM eventos_masivos
        WHERE strftime('%Y-%m', fecha_hora)=? {filtro}
    """, params).fetchone()

    conn.close()
    return {
        "ind_total":     ind["total"]     if ind else 0,
        "ind_costo":     ind["costo"]     if ind else 0.0,
        "ind_pasan":     ind["pasan"]     if ind else 0,
        "ind_no_pasan":  ind["no_pasan"]  if ind else 0,
        "ind_sin_deuda": ind["sin_deuda"] if ind else 0,
        "ind_errores":   ind["errores"]   if ind else 0,
        "mas_corridas":  mas["corridas"]    if mas else 0,
        "mas_casos":     mas["total_casos"] if mas else 0,
        "mas_pasan":     mas["pasan"]       if mas else 0,
        "mas_no_pasan":  mas["no_pasan"]    if mas else 0,
        "mas_sin_deuda": mas["sin_deuda"]   if mas else 0,
        "mas_errores":   mas["errores"]     if mas else 0,
        "mas_costo":     mas["costo"]       if mas else 0.0,
        "total_consultas": (ind["total"] if ind else 0) + (mas["total_casos"] if mas else 0),
        "total_costo":     (ind["costo"] if ind else 0.0) + (mas["costo"] if mas else 0.0),
    }

def get_eventos_periodo(cliente_id=None, anio=None, mes=None) -> dict:
    now     = datetime.now()
    anio    = anio or now.year
    mes     = mes  or now.month
    periodo = f"{anio}-{mes:02d}"
    conn    = get_conn()
    filtro  = "AND e.cliente_id=?" if cliente_id else ""
    params  = (periodo, cliente_id) if cliente_id else (periodo,)

    ind_rows = conn.execute(f"""
        SELECT e.fecha_hora, cl.nombre AS cliente, u.nombre AS usuario,
               e.resultado_cat, e.costo, e.precio_unitario
        FROM eventos_individuales e
        LEFT JOIN clientes cl ON e.cliente_id = cl.id
        LEFT JOIN usuarios  u  ON e.usuario_id  = u.id
        WHERE strftime('%Y-%m', e.fecha_hora)=? {filtro}
        ORDER BY e.fecha_hora DESC
    """, params).fetchall()

    mas_rows = conn.execute(f"""
        SELECT e.fecha_hora, cl.nombre AS cliente, u.nombre AS usuario,
               e.total_casos, e.pasan, e.no_pasan, e.sin_deuda, e.errores,
               e.costo_total, e.precio_unitario, e.umbral_usado
        FROM eventos_masivos e
        LEFT JOIN clientes cl ON e.cliente_id = cl.id
        LEFT JOIN usuarios  u  ON e.usuario_id  = u.id
        WHERE strftime('%Y-%m', e.fecha_hora)=? {filtro}
        ORDER BY e.fecha_hora DESC
    """, params).fetchall()

    conn.close()
    return {
        "individuales": [dict(r) for r in ind_rows],
        "masivos":      [dict(r) for r in mas_rows],
    }

def get_actividad_diaria(dias=7, cliente_id=None) -> list:
    conn    = get_conn()
    filtro  = "AND cliente_id=?" if cliente_id else ""
    params  = (f"-{dias} days", cliente_id, f"-{dias} days", cliente_id) if cliente_id else (f"-{dias} days", f"-{dias} days")
    rows = conn.execute(f"""
        SELECT dia, SUM(n) AS n FROM (
            SELECT date(fecha_hora) AS dia, COUNT(*) AS n
            FROM eventos_individuales
            WHERE fecha_hora >= date('now', ?) {filtro}
            GROUP BY dia
            UNION ALL
            SELECT date(fecha_hora) AS dia, SUM(total_casos) AS n
            FROM eventos_masivos
            WHERE fecha_hora >= date('now', ?) {filtro}
            GROUP BY dia
        ) GROUP BY dia ORDER BY dia
    """, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_top_clientes(periodo: str, limite=8) -> list:
    conn = get_conn()
    rows = conn.execute("""
        SELECT cliente, SUM(consultas) AS consultas, SUM(costo) AS costo FROM (
            SELECT cl.nombre AS cliente, COUNT(*) AS consultas, COALESCE(SUM(e.costo),0) AS costo
            FROM eventos_individuales e JOIN clientes cl ON e.cliente_id=cl.id
            WHERE strftime('%Y-%m', e.fecha_hora)=? GROUP BY e.cliente_id
            UNION ALL
            SELECT cl.nombre AS cliente, SUM(e.total_casos) AS consultas, COALESCE(SUM(e.costo_total),0) AS costo
            FROM eventos_masivos e JOIN clientes cl ON e.cliente_id=cl.id
            WHERE strftime('%Y-%m', e.fecha_hora)=? GROUP BY e.cliente_id
        ) GROUP BY cliente ORDER BY consultas DESC LIMIT ?
    """, (periodo, periodo, limite)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ══════════════════════════════════════════════════════════════════════════════
# SALDO Y MOVIMIENTOS
# ══════════════════════════════════════════════════════════════════════════════

def get_saldo(cliente_id: int) -> float:
    """Devuelve el saldo disponible en USD. Crea registro si no existe."""
    conn = get_conn()
    row = conn.execute(
        "SELECT saldo_usd FROM saldos WHERE cliente_id=?", (cliente_id,)
    ).fetchone()
    if not row:
        conn.execute(
            "INSERT OR IGNORE INTO saldos (cliente_id, saldo_usd) VALUES (?,0.0)",
            (cliente_id,)
        )
        conn.commit()
        conn.close()
        return 0.0
    conn.close()
    return float(row["saldo_usd"])


def get_consultas_disponibles(cliente_id: int) -> int:
    """Cuantas consultas puede hacer el cliente con su saldo actual."""
    saldo  = get_saldo(cliente_id)
    precio = get_precio_cliente(cliente_id) or PRECIO_DEFAULT_USD
    if precio <= 0:
        return 0
    return int(saldo / precio)


def tiene_saldo(cliente_id: int, cantidad: int = 1) -> bool:
    """True si el cliente tiene saldo para 'cantidad' consultas."""
    return get_consultas_disponibles(cliente_id) >= cantidad


def _actualizar_saldo(conn, cliente_id: int, delta_usd: float):
    """Suma o resta delta_usd al saldo. delta negativo = consumo."""
    conn.execute(
        "INSERT INTO saldos (cliente_id, saldo_usd, actualizado) VALUES (?,?,datetime('now','localtime'))"
        " ON CONFLICT(cliente_id) DO UPDATE SET"
        "   saldo_usd   = MAX(0, saldo_usd + excluded.saldo_usd),"
        "   actualizado = excluded.actualizado",
        (cliente_id, delta_usd)
    )


def registrar_recarga_pendiente(cliente_id: int, usuario_id: int,
                                 monto_usd: float, referencia_ext: str,
                                 modo_pago: str = "MOCK") -> int:
    """
    Registra una recarga en estado 'pendiente'.
    Retorna el id del movimiento para luego confirmar o rechazar.
    """
    precio   = get_precio_cliente(cliente_id) or PRECIO_DEFAULT_USD
    equiv    = int(monto_usd / precio) if precio > 0 else 0
    conn     = get_conn()
    cur      = conn.execute("""
        INSERT INTO movimientos_saldo
            (cliente_id, usuario_id, tipo, monto_usd, consultas_equiv,
             referencia_ext, modo_pago, estado, descripcion)
        VALUES (?,?,'recarga',?,?,?,?,'pendiente',?)
    """, (cliente_id, usuario_id, monto_usd, equiv,
          referencia_ext, modo_pago,
          f"Recarga {modo_pago} — {monto_usd:.2f} USD"))
    mov_id = cur.lastrowid
    conn.commit()
    conn.close()
    return mov_id


def confirmar_recarga(mov_id: int) -> bool:
    """
    Acredita una recarga pendiente: actualiza saldo y marca como acreditado.
    Retorna True si se procesó, False si ya estaba procesada o no existe.
    """
    conn = get_conn()
    mov  = conn.execute(
        "SELECT * FROM movimientos_saldo WHERE id=? AND estado='pendiente'",
        (mov_id,)
    ).fetchone()
    if not mov:
        conn.close()
        return False
    _actualizar_saldo(conn, mov["cliente_id"], mov["monto_usd"])
    conn.execute("""
        UPDATE movimientos_saldo
        SET estado='acreditado', fecha_acreditado=datetime('now','localtime')
        WHERE id=?
    """, (mov_id,))
    conn.commit()
    conn.close()
    return True


def rechazar_recarga(mov_id: int) -> bool:
    """Marca una recarga como rechazada sin modificar el saldo."""
    conn = get_conn()
    ok   = conn.execute(
        "UPDATE movimientos_saldo SET estado='rechazado' WHERE id=? AND estado='pendiente'",
        (mov_id,)
    ).rowcount > 0
    conn.commit()
    conn.close()
    return ok


def consumir_saldo(cliente_id: int, usuario_id: int,
                   cantidad: int, descripcion: str = "") -> bool:
    """
    Descuenta saldo por 'cantidad' consultas.
    Retorna True si había saldo, False si no alcanzaba.
    Operacion atomica con bloqueo de fila.
    """
    precio = get_precio_cliente(cliente_id) or PRECIO_DEFAULT_USD
    monto  = cantidad * precio
    conn   = get_conn()
    saldo_row = conn.execute(
        "SELECT saldo_usd FROM saldos WHERE cliente_id=?", (cliente_id,)
    ).fetchone()
    saldo_actual = float(saldo_row["saldo_usd"]) if saldo_row else 0.0
    if saldo_actual < monto - 0.0001:   # tolerancia de floating point
        conn.close()
        return False
    _actualizar_saldo(conn, cliente_id, -monto)
    conn.execute("""
        INSERT INTO movimientos_saldo
            (cliente_id, usuario_id, tipo, monto_usd, consultas_equiv,
             referencia_ext, modo_pago, estado, descripcion)
        VALUES (?,?,'consumo',?,?,NULL,'SISTEMA','acreditado',?)
    """, (cliente_id, usuario_id, monto, cantidad, descripcion or f"{cantidad} consulta(s)"))
    conn.commit()
    conn.close()
    return True


def ajuste_admin_saldo(cliente_id: int, admin_id: int,
                        monto_usd: float, descripcion: str) -> bool:
    """Ajuste manual del saldo por el administrador (positivo o negativo)."""
    conn = get_conn()
    _actualizar_saldo(conn, cliente_id, monto_usd)
    tipo = "ajuste_admin"
    conn.execute("""
        INSERT INTO movimientos_saldo
            (cliente_id, usuario_id, tipo, monto_usd, consultas_equiv,
             referencia_ext, modo_pago, estado, descripcion, fecha_acreditado)
        VALUES (?,?,?,?,0,NULL,'ADMIN','acreditado',?,datetime('now','localtime'))
    """, (cliente_id, admin_id, tipo, monto_usd, descripcion))
    conn.commit()
    conn.close()
    return True


def get_movimientos(cliente_id: int, limite: int = 100) -> list:
    """Historial de movimientos de saldo para un cliente."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT m.*, u.nombre as usuario_nombre
        FROM movimientos_saldo m
        LEFT JOIN usuarios u ON m.usuario_id = u.id
        WHERE m.cliente_id=?
        ORDER BY m.fecha_hora DESC
        LIMIT ?
    """, (cliente_id, limite)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_mov_pendiente_por_ref(referencia_ext: str) -> dict | None:
    """Busca un movimiento pendiente por su referencia externa (ID de MP)."""
    conn = get_conn()
    row  = conn.execute(
        "SELECT * FROM movimientos_saldo WHERE referencia_ext=? AND estado='pendiente' LIMIT 1",
        (referencia_ext,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_resumen_saldo(cliente_id: int) -> dict:
    """Todo lo que necesita la pantalla de Estado de cuenta."""
    saldo  = get_saldo(cliente_id)
    precio = get_precio_cliente(cliente_id) or PRECIO_DEFAULT_USD
    equiv  = int(saldo / precio) if precio > 0 else 0
    conn   = get_conn()
    # Total recargado histórico
    tot_recargado = conn.execute(
        "SELECT COALESCE(SUM(monto_usd),0) FROM movimientos_saldo "
        "WHERE cliente_id=? AND tipo='recarga' AND estado='acreditado'",
        (cliente_id,)
    ).fetchone()[0]
    # Total consumido histórico
    tot_consumido = conn.execute(
        "SELECT COALESCE(SUM(monto_usd),0) FROM movimientos_saldo "
        "WHERE cliente_id=? AND tipo='consumo' AND estado='acreditado'",
        (cliente_id,)
    ).fetchone()[0]
    # Recarga pendiente (si hay)
    pendiente = conn.execute(
        "SELECT id, monto_usd, referencia_ext, modo_pago, fecha_hora "
        "FROM movimientos_saldo "
        "WHERE cliente_id=? AND tipo='recarga' AND estado='pendiente' "
        "ORDER BY fecha_hora DESC LIMIT 1",
        (cliente_id,)
    ).fetchone()
    conn.close()
    return {
        "saldo_usd":       saldo,
        "consultas_disp":  equiv,
        "precio_usd":      precio,
        "tot_recargado":   float(tot_recargado),
        "tot_consumido":   float(tot_consumido),
        "pendiente":       dict(pendiente) if pendiente else None,
    }


# ══════════════════════════════════════════════════════════════════════════════
# VIGILADOS — SEGUIMIENTO MENSUAL
# ══════════════════════════════════════════════════════════════════════════════

def agregar_vigilado(cliente_id: int, usuario_id: int,
                     cuit: str, alias: str = "") -> tuple[bool, str]:
    """Alta de un CUIT a vigilar. Reactivar si ya existía."""
    cuit = cuit.replace("-","").replace(".","").replace(" ","").strip()
    conn = get_conn()
    try:
        conn.execute("""
            INSERT INTO vigilados (cliente_id, usuario_id, cuit, alias)
            VALUES (?,?,?,?)
            ON CONFLICT(cliente_id, cuit) DO UPDATE
            SET activo=1, alias=excluded.alias, usuario_id=excluded.usuario_id
        """, (cliente_id, usuario_id, cuit, alias or cuit))
        conn.commit()
        return True, "CUIT agregado al seguimiento"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def agregar_vigilados_masivo(cliente_id: int, usuario_id: int,
                              lista: list[dict]) -> tuple[int, int]:
    """
    Alta masiva desde lista de dicts con claves 'cuit' y opcionalmente 'alias'.
    Retorna (ok, errores).
    """
    ok = err = 0
    for item in lista:
        cuit  = str(item.get("cuit","")).replace("-","").replace(".","").strip()
        alias = str(item.get("alias","") or item.get("nombre","") or cuit).strip()
        if not cuit:
            err += 1; continue
        r, _ = agregar_vigilado(cliente_id, usuario_id, cuit, alias)
        if r: ok += 1
        else: err += 1
    return ok, err


def listar_vigilados(cliente_id: int, solo_activos: bool = True) -> list:
    conn  = get_conn()
    where = "WHERE v.cliente_id=?" + (" AND v.activo=1" if solo_activos else "")
    rows  = conn.execute(f"""
        SELECT v.*,
               h.periodo_bcra     AS ultimo_periodo,
               h.monto_sit1       AS ultimo_sit1,
               h.monto_riesgo     AS ultimo_riesgo,
               h.variacion        AS ultima_variacion,
               h.fecha_consulta   AS ultima_fecha
        FROM vigilados v
        LEFT JOIN historial_vigilados h
               ON h.vigilado_id = v.id
              AND h.id = (SELECT MAX(id) FROM historial_vigilados
                          WHERE vigilado_id = v.id)
        {where}
        ORDER BY v.alias, v.cuit
    """, (cliente_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def actualizar_umbral_vigilado(vigilado_id: int, cliente_id: int, umbral: float) -> bool:
    """Actualiza el umbral pasa/no pasa de un CUIT vigilado."""
    conn = get_conn()
    ok   = conn.execute(
        "UPDATE vigilados SET umbral_pct=? WHERE id=? AND cliente_id=?",
        (umbral, vigilado_id, cliente_id)
    ).rowcount > 0
    conn.commit()
    conn.close()
    return ok


def desactivar_vigilado(vigilado_id: int, cliente_id: int) -> bool:
    conn = get_conn()
    ok   = conn.execute(
        "UPDATE vigilados SET activo=0 WHERE id=? AND cliente_id=?",
        (vigilado_id, cliente_id)
    ).rowcount > 0
    conn.commit()
    conn.close()
    return ok


def get_historial_vigilado(vigilado_id: int, limite: int = 24) -> list:
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM historial_vigilados
        WHERE vigilado_id=?
        ORDER BY fecha_consulta DESC
        LIMIT ?
    """, (vigilado_id, limite)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def registrar_resultado_seguimiento(vigilado_id: int, cliente_id: int,
                                     usuario_id: int, resultado: dict,
                                     costo: float) -> str:
    """
    Guarda el resultado del mes para un vigilado y calcula la variación
    comparando con el registro anterior.
    Retorna el código de variación.
    """
    conn = get_conn()

    # Último registro del mismo vigilado
    prev = conn.execute("""
        SELECT monto_sit1, monto_riesgo, sin_deuda
        FROM historial_vigilados
        WHERE vigilado_id=?
        ORDER BY fecha_consulta DESC LIMIT 1
    """, (vigilado_id,)).fetchone()

    if resultado.get("error"):
        variacion = "ERROR"
        conn.execute("""
            INSERT INTO historial_vigilados
                (vigilado_id, cliente_id, variacion, costo, error)
            VALUES (?,?,'ERROR',?,?)
        """, (vigilado_id, cliente_id, costo, resultado["error"][:200]))
        conn.commit()
        conn.close()
        return variacion

    sit1    = resultado.get("Monto_Sit1", 0)
    riesgo  = resultado.get("Monto_Riesgo", 0)
    n_ent   = len(resultado.get("Entidades", []))
    sin_d   = 1 if resultado.get("Sin_Deuda") else 0
    periodo = resultado.get("Periodo", "")
    sit_peor = max((e.get("Situacion", 0) for e in resultado.get("Entidades", [])), default=0)

    if prev is None:
        variacion = "NUEVO"
        d_sit1 = d_riesgo = 0.0
    elif sin_d and prev["sin_deuda"]:
        variacion = "SIN_CAMBIO"
        d_sit1 = d_riesgo = 0.0
    elif sin_d and not prev["sin_deuda"]:
        variacion = "BAJA"   # tenía deuda, ahora no
        d_sit1   = -float(prev["monto_sit1"])
        d_riesgo = -float(prev["monto_riesgo"])
    elif not sin_d and prev["sin_deuda"]:
        variacion = "SUBE"   # no tenía deuda, ahora sí
        d_sit1   = sit1
        d_riesgo = riesgo
    else:
        d_sit1   = sit1   - float(prev["monto_sit1"])
        d_riesgo = riesgo - float(prev["monto_riesgo"])
        total_delta = abs(d_sit1) + abs(d_riesgo)
        if total_delta < 0.01:
            variacion = "SIN_CAMBIO"
        elif (d_sit1 + d_riesgo) > 0:
            variacion = "SUBE"
        else:
            variacion = "BAJA"

    conn.execute("""
        INSERT INTO historial_vigilados
            (vigilado_id, cliente_id, periodo_bcra, monto_sit1, monto_riesgo,
             cant_entidades, situacion_peor, sin_deuda, variacion,
             delta_sit1, delta_riesgo, costo)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, (vigilado_id, cliente_id, periodo, sit1, riesgo,
          n_ent, sit_peor, sin_d, variacion, d_sit1, d_riesgo, costo))

    # Actualizar ultima_consulta en vigilados
    conn.execute("""
        UPDATE vigilados SET ultima_consulta=datetime('now','localtime')
        WHERE id=?
    """, (vigilado_id,))

    conn.commit()
    conn.close()
    return variacion


def get_resumen_seguimiento(cliente_id: int) -> dict:
    """Resumen para el dashboard de seguimiento."""
    conn = get_conn()
    total = conn.execute(
        "SELECT COUNT(*) FROM vigilados WHERE cliente_id=? AND activo=1",
        (cliente_id,)
    ).fetchone()[0]

    # Variaciones del último procesamiento
    stats = conn.execute("""
        SELECT variacion, COUNT(*) as n
        FROM historial_vigilados h
        INNER JOIN vigilados v ON h.vigilado_id=v.id
        WHERE v.cliente_id=? AND v.activo=1
          AND h.id = (SELECT MAX(id) FROM historial_vigilados
                      WHERE vigilado_id=v.id)
        GROUP BY variacion
    """, (cliente_id,)).fetchall()
    conn.close()

    res = {"total": total, "SUBE":0,"BAJA":0,"SIN_CAMBIO":0,"NUEVO":0,"ERROR":0}
    for row in stats:
        res[row["variacion"]] = row["n"]
    return res


def guardar_reporte_seguimiento(cliente_id: int, usuario_id: int,
                                 periodo: str, stats: dict,
                                 pdf_bytes: bytes) -> int:
    """Persiste el PDF mensual del seguimiento. Retorna el id del registro."""
    conn = get_conn()
    cur  = conn.execute("""
        INSERT INTO reportes_seguimiento
            (cliente_id, usuario_id, periodo, total_cuits,
             suben, bajan, sin_cambio, errores, pdf_bytes)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (cliente_id, usuario_id, periodo,
          stats.get("total",0), stats.get("SUBE",0), stats.get("BAJA",0),
          stats.get("SIN_CAMBIO",0), stats.get("ERROR",0), pdf_bytes))
    rid = cur.lastrowid
    conn.commit()
    conn.close()
    return rid


def listar_reportes_seguimiento(cliente_id: int) -> list:
    """Lista los PDFs mensuales guardados (sin el BLOB para no cargar todo)."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT id, periodo, fecha_gen, total_cuits,
               suben, bajan, sin_cambio, errores
        FROM reportes_seguimiento
        WHERE cliente_id=?
        ORDER BY fecha_gen DESC
    """, (cliente_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_pdf_seguimiento(reporte_id: int, cliente_id: int) -> bytes | None:
    """Recupera el PDF de un reporte guardado."""
    conn = get_conn()
    row  = conn.execute(
        "SELECT pdf_bytes FROM reportes_seguimiento WHERE id=? AND cliente_id=?",
        (reporte_id, cliente_id)
    ).fetchone()
    conn.close()
    return bytes(row["pdf_bytes"]) if row and row["pdf_bytes"] else None


def registrar_empresa_usuario(nombre_empresa: str, cuit_empresa: str,
                               nombre_usuario: str, email: str,
                               password: str) -> tuple[bool, str]:
    """
    Crea un cliente nuevo + su usuario en estado pendiente de aprobación.
    Al aprobarse recibe 100 consultas de crédito de prueba.
    """
    import bcrypt
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    conn = get_conn()
    try:
        # Crear cliente
        cur = conn.execute("""
            INSERT INTO clientes (nombre, email, cuit_empresa, precio_consulta, notas)
            VALUES (?,?,?,0.35,'Registro web — pendiente de aprobación')
        """, (nombre_empresa, email, cuit_empresa))
        cliente_id = cur.lastrowid

        # Crear usuario pendiente (aprobado=0)
        conn.execute("""
            INSERT INTO usuarios
                (nombre, email, password_hash, cliente_id, rol, activo, aprobado)
            VALUES (?,?,?,?,'user',1,0)
        """, (nombre_usuario, email.strip().lower(), pw_hash, cliente_id))
        conn.commit()
        return True, "Registro exitoso. Tu cuenta será revisada y activada pronto."
    except Exception as e:
        conn.rollback()
        if "UNIQUE" in str(e):
            return False, "El email ya está registrado."
        return False, f"Error al registrar: {e}"
    finally:
        conn.close()


def aprobar_usuario(usuario_id: int, admin_id: int,
                    credito_consultas: int = 100) -> bool:
    """
    Aprueba un usuario y le acredita el crédito inicial de prueba.
    """
    conn = get_conn()
    u = conn.execute(
        "SELECT * FROM usuarios WHERE id=?", (usuario_id,)
    ).fetchone()
    if not u:
        conn.close()
        return False

    conn.execute(
        "UPDATE usuarios SET aprobado=1 WHERE id=?", (usuario_id,)
    )

    # Acreditar crédito inicial de prueba
    precio = conn.execute(
        "SELECT precio_consulta FROM clientes WHERE id=?",
        (u["cliente_id"],)
    ).fetchone()
    precio_unit = float(precio["precio_consulta"]) if precio else 0.35
    monto_usd   = credito_consultas * precio_unit

    conn.execute("""
        INSERT INTO saldos (cliente_id, saldo_usd) VALUES (?,?)
        ON CONFLICT(cliente_id) DO UPDATE
        SET saldo_usd = saldo_usd + excluded.saldo_usd
    """, (u["cliente_id"], monto_usd))

    conn.execute("""
        INSERT INTO movimientos_saldo
            (cliente_id, usuario_id, tipo, monto_usd, consultas_equiv,
             modo_pago, estado, descripcion, fecha_acreditado)
        VALUES (?,?,  'recarga',?,?,  'ADMIN','acreditado',
                'Crédito de prueba — 100 consultas iniciales',
                datetime('now','localtime'))
    """, (u["cliente_id"], admin_id, monto_usd, credito_consultas))

    conn.commit()
    conn.close()
    return True


def listar_usuarios_pendientes() -> list:
    conn = get_conn()
    rows = conn.execute("""
        SELECT u.*, c.nombre as cliente_nombre, c.cuit_empresa
        FROM usuarios u
        LEFT JOIN clientes c ON u.cliente_id = c.id
        WHERE u.aprobado=0 AND u.activo=1
        ORDER BY u.fecha_alta DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]
