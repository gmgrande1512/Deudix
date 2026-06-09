"""
database.py — Gestión de base de datos SQLite para Deudix

Principio de privacidad (Ley 25.326 Argentina):
  Deudix no almacena datos de las personas consultadas.
  Solo se registran métricas operacionales propias del servicio.
"""
import sqlite3
import os
import hashlib
from datetime import datetime
from config import PRECIO_DEFAULT_USD

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

    _cols_u = {r[1] for r in c.execute("PRAGMA table_info(usuarios)").fetchall()}
    if "aprobado" not in _cols_u:
        c.execute("ALTER TABLE usuarios ADD COLUMN aprobado INTEGER DEFAULT 0")
        c.execute("UPDATE usuarios SET aprobado=1 WHERE rol='admin'")

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

    c.execute("""
        CREATE TABLE IF NOT EXISTS saldos (
            cliente_id      INTEGER PRIMARY KEY REFERENCES clientes(id),
            saldo_usd       REAL    DEFAULT 0.0,
            actualizado     TEXT    DEFAULT (datetime('now','localtime'))
        )
    """)

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

    _cols_v = {r[1] for r in c.execute("PRAGMA table_info(vigilados)").fetchall()}
    if "umbral_pct" not in _cols_v:
        c.execute("ALTER TABLE vigilados ADD COLUMN umbral_pct REAL DEFAULT 40.0")

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
    rows = conn.execute("""
        SELECT id, nombre, email, email_empresa, precio_consulta, activo,
               fecha_alta, notas, razon_social, cuit_empresa,
               domicilio, ciudad, provincia, telefono, web
        FROM clientes ORDER BY nombre
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_cliente(cliente_id: int) -> dict:
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
    BUG 5 FIX: email tiene restricción UNIQUE. Si se intenta actualizar con un email
    ya usado por otro cliente, SQLite lanza IntegrityError.
    Solución: excluir 'email' de la actualización por perfil (el email administrativo
    no debería cambiarse por este formulario — es el campo UNIQUE de login del cliente).
    Solo se actualiza si el valor cambió o es distinto del actual.
    """
    campos_permitidos = {
        "nombre", "email_empresa", "precio_consulta", "notas",
        "razon_social", "cuit_empresa", "domicilio", "ciudad",
        "provincia", "telefono", "web",
        # "email" excluido: campo UNIQUE, se maneja por separado si hace falta
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
    try:
        conn.execute(f"UPDATE clientes SET {', '.join(sets)} WHERE id=?", vals)
        conn.commit()
    except sqlite3.IntegrityError as e:
        conn.rollback()
        raise sqlite3.IntegrityError(f"Error al guardar datos: {e}") from e
    finally:
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
    """BUG FIX: parámetros correctos para queries con y sin cliente_id."""
    conn = get_conn()
    rango = f"-{dias} days"
    if cliente_id:
        rows = conn.execute("""
            SELECT dia, SUM(n) AS n FROM (
                SELECT date(fecha_hora) AS dia, COUNT(*) AS n
                FROM eventos_individuales
                WHERE fecha_hora >= date('now', ?) AND cliente_id=?
                GROUP BY dia
                UNION ALL
                SELECT date(fecha_hora) AS dia, SUM(total_casos) AS n
                FROM eventos_masivos
                WHERE fecha_hora >= date('now', ?) AND cliente_id=?
                GROUP BY dia
            ) GROUP BY dia ORDER BY dia
        """, (rango, cliente_id, rango, cliente_id)).fetchall()
    else:
        rows = conn.execute("""
            SELECT dia, SUM(n) AS n FROM (
                SELECT date(fecha_hora) AS dia, COUNT(*) AS n
                FROM eventos_individuales
                WHERE fecha_hora >= date('now', ?)
                GROUP BY dia
                UNION ALL
                SELECT date(fecha_hora) AS dia, SUM(total_casos) AS n
                FROM eventos_masivos
                WHERE fecha_hora >= date('now', ?)
                GROUP BY dia
            ) GROUP BY dia ORDER BY dia
        """, (rango, rango)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_top_clientes(periodo: str, limite=8) -> list:
    conn = get_conn()
    rows = conn.execute("""
        SELECT cl.nombre AS cliente,
               COALESCE(SUM(e.total_casos),0) + COUNT(DISTINCT ei.id) AS total,
               COALESCE(SUM(e.costo_total),0) + COALESCE(SUM(ei.costo),0) AS costo
        FROM clientes cl
        LEFT JOIN eventos_masivos     e  ON e.cliente_id=cl.id  AND strftime('%Y-%m',e.fecha_hora)=?
        LEFT JOIN eventos_individuales ei ON ei.cliente_id=cl.id AND strftime('%Y-%m',ei.fecha_hora)=?
        GROUP BY cl.id
        HAVING total > 0
        ORDER BY total DESC
        LIMIT ?
    """, (periodo, periodo, limite)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ── Saldos ────────────────────────────────────────────────────────────────────

def get_resumen_saldo(cliente_id: int) -> dict:
    conn = get_conn()
    row  = conn.execute(
        "SELECT saldo_usd, actualizado FROM saldos WHERE cliente_id=?",
        (cliente_id,)
    ).fetchone()
    precio = conn.execute(
        "SELECT precio_consulta FROM clientes WHERE id=?", (cliente_id,)
    ).fetchone()
    conn.close()
    saldo      = float(row["saldo_usd"]) if row else 0.0
    precio_u   = float(precio["precio_consulta"]) if precio else 0.0
    consultas  = int(saldo / precio_u) if precio_u > 0 else 0
    return {
        "saldo_usd":       saldo,
        "precio_consulta": precio_u,
        "consultas_equiv": consultas,
        "actualizado":     row["actualizado"] if row else "",
    }

def consumir_saldo(cliente_id: int, usuario_id: int,
                   cant_consultas: int, descripcion: str = ""):
    conn = get_conn()
    precio = conn.execute(
        "SELECT precio_consulta FROM clientes WHERE id=?", (cliente_id,)
    ).fetchone()
    precio_u = float(precio["precio_consulta"]) if precio else 0.0
    monto    = cant_consultas * precio_u
    if monto <= 0:
        conn.close()
        return
    conn.execute("""
        INSERT INTO saldos (cliente_id, saldo_usd) VALUES (?, 0.0)
        ON CONFLICT(cliente_id) DO UPDATE
        SET saldo_usd  = MAX(0, saldo_usd - ?),
            actualizado = datetime('now','localtime')
    """, (cliente_id, monto))
    conn.execute("""
        INSERT INTO movimientos_saldo
            (cliente_id, usuario_id, tipo, monto_usd, consultas_equiv,
             modo_pago, estado, descripcion, fecha_acreditado)
        VALUES (?,?,'consumo',?,?,'SISTEMA','acreditado',?,datetime('now','localtime'))
    """, (cliente_id, usuario_id, monto, cant_consultas, descripcion))
    conn.commit()
    conn.close()

def registrar_recarga_pendiente(cliente_id: int, usuario_id: int,
                                 monto_usd: float, referencia_ext: str,
                                 modo_pago: str = "MOCK") -> int:
    conn  = get_conn()
    precio = conn.execute(
        "SELECT precio_consulta FROM clientes WHERE id=?", (cliente_id,)
    ).fetchone()
    precio_u   = float(precio["precio_consulta"]) if precio else 0.0
    consultas  = int(monto_usd / precio_u) if precio_u > 0 else 0
    cur = conn.execute("""
        INSERT INTO movimientos_saldo
            (cliente_id, usuario_id, tipo, monto_usd, consultas_equiv,
             referencia_ext, modo_pago, estado, descripcion)
        VALUES (?,?,'recarga',?,?,?,'MOCK','pendiente','Recarga pendiente de confirmación')
    """, (cliente_id, usuario_id, monto_usd, consultas, referencia_ext))
    mov_id = cur.lastrowid
    conn.commit()
    conn.close()
    return mov_id

def confirmar_recarga(mov_id: int) -> bool:
    conn = get_conn()
    mov  = conn.execute(
        "SELECT * FROM movimientos_saldo WHERE id=? AND estado='pendiente'",
        (mov_id,)
    ).fetchone()
    if not mov:
        conn.close()
        return False
    conn.execute("""
        UPDATE movimientos_saldo
        SET estado='acreditado', fecha_acreditado=datetime('now','localtime')
        WHERE id=?
    """, (mov_id,))
    conn.execute("""
        INSERT INTO saldos (cliente_id, saldo_usd) VALUES (?, ?)
        ON CONFLICT(cliente_id) DO UPDATE
        SET saldo_usd  = saldo_usd + excluded.saldo_usd,
            actualizado = datetime('now','localtime')
    """, (mov["cliente_id"], mov["monto_usd"]))
    conn.commit()
    conn.close()
    return True

def rechazar_recarga(mov_id: int) -> bool:
    conn = get_conn()
    conn.execute(
        "UPDATE movimientos_saldo SET estado='rechazado' WHERE id=? AND estado='pendiente'",
        (mov_id,)
    )
    conn.commit()
    conn.close()
    return True

def get_movimientos(cliente_id: int, limite=50) -> list:
    conn = get_conn()
    rows = conn.execute("""
        SELECT m.*, u.nombre AS usuario_nombre
        FROM movimientos_saldo m
        LEFT JOIN usuarios u ON m.usuario_id = u.id
        WHERE m.cliente_id=?
        ORDER BY m.fecha_hora DESC LIMIT ?
    """, (cliente_id, limite)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def ajuste_admin_saldo(cliente_id: int, admin_id: int,
                        monto_usd: float, descripcion: str):
    conn = get_conn()
    conn.execute("""
        INSERT INTO saldos (cliente_id, saldo_usd) VALUES (?, ?)
        ON CONFLICT(cliente_id) DO UPDATE
        SET saldo_usd  = MAX(0, saldo_usd + ?),
            actualizado = datetime('now','localtime')
    """, (cliente_id, max(0, monto_usd), monto_usd))
    conn.execute("""
        INSERT INTO movimientos_saldo
            (cliente_id, usuario_id, tipo, monto_usd,
             modo_pago, estado, descripcion, fecha_acreditado)
        VALUES (?,?,'ajuste_admin',?,
                'ADMIN','acreditado',?,datetime('now','localtime'))
    """, (cliente_id, admin_id, monto_usd, descripcion))
    conn.commit()
    conn.close()

def get_mov_pendiente_por_ref(referencia_ext: str) -> dict | None:
    conn = get_conn()
    row  = conn.execute(
        "SELECT * FROM movimientos_saldo WHERE referencia_ext=? AND estado='pendiente' LIMIT 1",
        (referencia_ext,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None

# ── Vigilados / Seguimiento ───────────────────────────────────────────────────

def agregar_vigilado(cliente_id: int, usuario_id: int,
                     cuit: str, alias: str = "") -> tuple[bool, str]:
    cuit_limpio = cuit.replace("-","").replace(".","").strip()
    conn = get_conn()
    try:
        conn.execute("""
            INSERT INTO vigilados (cliente_id, usuario_id, cuit, alias)
            VALUES (?, ?, ?, ?)
        """, (cliente_id, usuario_id, cuit_limpio, alias or cuit_limpio))
        conn.commit()
        return True, "Agregado al seguimiento"
    except sqlite3.IntegrityError:
        return False, "Este CUIT ya está en seguimiento"
    finally:
        conn.close()

def listar_vigilados(cliente_id: int) -> list:
    conn = get_conn()
    rows = conn.execute("""
        SELECT v.*, 
               (SELECT variacion FROM historial_vigilados
                WHERE vigilado_id=v.id ORDER BY id DESC LIMIT 1) AS ultima_variacion,
               (SELECT monto_sit1 + monto_riesgo FROM historial_vigilados
                WHERE vigilado_id=v.id ORDER BY id DESC LIMIT 1) AS ultimo_total
        FROM vigilados v
        WHERE v.cliente_id=? AND v.activo=1
        ORDER BY v.alias
    """, (cliente_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def eliminar_vigilado(vigilado_id: int, cliente_id: int) -> bool:
    conn = get_conn()
    conn.execute(
        "UPDATE vigilados SET activo=0 WHERE id=? AND cliente_id=?",
        (vigilado_id, cliente_id)
    )
    conn.commit()
    conn.close()
    return True

def get_historial_vigilado(vigilado_id: int, limite=12) -> list:
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM historial_vigilados
        WHERE vigilado_id=?
        ORDER BY id DESC LIMIT ?
    """, (vigilado_id, limite)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def registrar_resultado_vigilado(vigilado_id: int, cliente_id: int,
                                  periodo: str, sit1: float, riesgo: float,
                                  n_ent: int, sit_peor: int,
                                  sin_d: bool, costo: float = 0.0,
                                  error: str = "") -> str:
    if error:
        conn = get_conn()
        conn.execute("""
            INSERT INTO historial_vigilados
                (vigilado_id, cliente_id, periodo_bcra, sin_deuda, variacion, error)
            VALUES (?,?,?,?,?,?)
        """, (vigilado_id, cliente_id, periodo, sin_d, "ERROR", error))
        conn.execute(
            "UPDATE vigilados SET ultima_consulta=datetime('now','localtime') WHERE id=?",
            (vigilado_id,)
        )
        conn.commit()
        conn.close()
        return "ERROR"

    conn = get_conn()
    prev = conn.execute("""
        SELECT * FROM historial_vigilados
        WHERE vigilado_id=? ORDER BY id DESC LIMIT 1
    """, (vigilado_id,)).fetchone()

    if prev is None:
        variacion = "NUEVO"
        d_sit1 = d_riesgo = 0.0
    elif sin_d and prev["sin_deuda"]:
        variacion = "SIN_CAMBIO"
        d_sit1 = d_riesgo = 0.0
    elif sin_d and not prev["sin_deuda"]:
        variacion = "BAJA"
        d_sit1   = -float(prev["monto_sit1"])
        d_riesgo = -float(prev["monto_riesgo"])
    elif not sin_d and prev["sin_deuda"]:
        variacion = "SUBE"
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

    conn.execute("""
        UPDATE vigilados SET ultima_consulta=datetime('now','localtime')
        WHERE id=?
    """, (vigilado_id,))

    conn.commit()
    conn.close()
    return variacion

def get_resumen_seguimiento(cliente_id: int) -> dict:
    conn = get_conn()
    total = conn.execute(
        "SELECT COUNT(*) FROM vigilados WHERE cliente_id=? AND activo=1",
        (cliente_id,)
    ).fetchone()[0]

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
    import bcrypt
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    conn = get_conn()
    try:
        cur = conn.execute("""
            INSERT INTO clientes (nombre, email, cuit_empresa, precio_consulta, notas)
            VALUES (?,?,?,0.35,'Registro web — pendiente de aprobación')
        """, (nombre_empresa, email, cuit_empresa))
        cliente_id = cur.lastrowid

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
    conn = get_conn()
    u = conn.execute(
        "SELECT * FROM usuarios WHERE id=?", (usuario_id,)
    ).fetchone()
    if not u:
        conn.close()
        return False

    conn.execute("UPDATE usuarios SET aprobado=1 WHERE id=?", (usuario_id,))

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
