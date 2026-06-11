"""
bcra.py — Lógica de consulta a la API BCRA y procesamiento de respuestas.

Mejoras:
  - Sesión nueva por cada consulta (evita sesiones stale en Streamlit Cloud)
  - Intenta con verify=True primero, fallback a verify=False
  - Mejor logging del error real para diagnóstico
"""
import requests
import urllib3
import time
import os

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL    = "https://api.bcra.gob.ar/centraldedeudores/v1.0/Deudas"
SITS_RIESGO = [2, 3, 4, 5]

# En Streamlit Cloud puede haber restricciones de red distintas
_ES_CLOUD = os.path.exists("/mount/src")

# ── Headers que simulan un navegador real ─────────────────────────────────────

_HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection":      "keep-alive",
    "Referer":         "https://www.bcra.gob.ar/BCRAyVos/Registro_sistemaFinanciero.asp",
    "Origin":          "https://www.bcra.gob.ar",
    "Sec-Fetch-Dest":  "empty",
    "Sec-Fetch-Mode":  "cors",
    "Sec-Fetch-Site":  "same-origin",
}


def _nueva_sesion(verify: bool = True) -> requests.Session:
    """Crea una sesión fresca. En Cloud probamos con y sin SSL verify."""
    s = requests.Session()
    s.verify = verify
    s.headers.update(_HEADERS)
    # Warm-up: visitar la página pública para obtener cookies
    try:
        s.get(
            "https://www.bcra.gob.ar/BCRAyVos/Registro_sistemaFinanciero.asp",
            timeout=10,
            verify=verify,
        )
    except Exception:
        pass
    return s


def consultar_bcra(cuit, intentos=4) -> dict:
    """
    Consulta la API BCRA para un CUIT dado.
    Retorna {"ok": True, "data": ...} o {"ok": False, "error": "..."}.
    """
    cuit_limpio = str(cuit).replace("-", "").replace(" ", "").replace(".", "").strip()
    url = f"{BASE_URL}/{cuit_limpio}"

    ultimo_error = ""

    for intento in range(1, intentos + 1):
        # Alternar: intento 1 y 3 con verify=True, 2 y 4 con verify=False
        verificar_ssl = (intento % 2 == 1)

        try:
            sesion = _nueva_sesion(verify=verificar_ssl)
            resp = sesion.get(url, timeout=25)

            if resp.status_code == 200:
                try:
                    data = resp.json()
                    return {"ok": True, "data": data}
                except Exception:
                    return {"ok": True, "data": None}

            elif resp.status_code == 404:
                return {"ok": True, "data": None}

            elif resp.status_code == 429:
                ultimo_error = f"HTTP 429 (rate limit) intento {intento}"
                time.sleep(5 * intento)
                continue

            elif resp.status_code == 403:
                ultimo_error = f"HTTP 403 (bloqueado) intento {intento}"
                time.sleep(3 * intento)
                continue

            elif resp.status_code >= 500:
                ultimo_error = f"HTTP {resp.status_code} (error servidor) intento {intento}"
                time.sleep(3 * intento)
                continue

            else:
                ultimo_error = f"HTTP {resp.status_code} intento {intento}"
                if intento < intentos:
                    time.sleep(2 * intento)
                    continue
                return {"ok": False, "error": ultimo_error}

        except requests.exceptions.SSLError as e:
            ultimo_error = f"SSL error intento {intento} (verify={verificar_ssl})"
            if intento < intentos:
                time.sleep(2)
                continue
        except requests.exceptions.ConnectionError as e:
            ultimo_error = f"Conexión rechazada intento {intento}"
            if intento < intentos:
                time.sleep(3 * intento)
                continue
        except requests.exceptions.Timeout:
            ultimo_error = f"Timeout intento {intento}"
            if intento < intentos:
                time.sleep(2)
                continue
        except Exception as e:
            ultimo_error = f"{type(e).__name__}: {str(e)[:80]} intento {intento}"
            if intento < intentos:
                time.sleep(3 * intento)
                continue

    return {"ok": False, "error": ultimo_error or "Falló después de todos los intentos"}


# ── Procesamiento de respuestas ───────────────────────────────────────────────

def extraer_nombre_api(data) -> str:
    """Busca la denominación en todos los campos posibles de la respuesta BCRA."""
    try:
        if not data:
            return ""
        results = data.get("results", {})
        if not isinstance(results, dict):
            return ""
        ident = results.get("identificacion", {})
        if isinstance(ident, dict):
            n = ident.get("denominacion", "")
            if n:
                return str(n).strip()
        n = results.get("denominacion", "")
        if n:
            return str(n).strip()
        periodos = results.get("periodos", [])
        if isinstance(periodos, list) and periodos:
            p = periodos[0]
            if isinstance(p, dict):
                n = p.get("denominacion", "")
                if n:
                    return str(n).strip()
                entidades = p.get("entidades", [])
                if isinstance(entidades, list) and entidades:
                    n = entidades[0].get("denominacion", "") if isinstance(entidades[0], dict) else ""
                    if n:
                        return str(n).strip()
        return ""
    except Exception:
        return ""

def procesar_respuesta(data, cuit, nombre="", capital=None) -> dict:
    """Convierte la respuesta cruda de la API en un dict normalizado."""
    if not nombre:
        nombre = extraer_nombre_api(data)
    base = {
        "CUIT":        cuit,
        "Nombre":      nombre,
        "Capital":     capital,
        "Sin_Deuda":   True,
        "Monto_Sit1":  0,
        "Monto_Riesgo":0,
        "Entidades":   [],
        "Periodo":     "",
    }
    if data is None:
        return base
    results_raw = data.get("results", {})
    if not isinstance(results_raw, dict):
        return base
    periodos = results_raw.get("periodos", [])
    if not periodos:
        return base
    periodo    = periodos[0]
    periodo_id = str(periodo.get("periodo", ""))
    entidades  = periodo.get("entidades", [])
    sit1 = riesgo = 0.0
    detalle = []
    for ent in entidades:
        sit   = int(ent.get("situacion", 0) or 0)
        monto = float(ent.get("monto", 0) or 0)
        detalle.append({
            "Entidad":    ent.get("entidad", ""),
            "Situacion":  sit,
            "Monto":      monto,
            "Dias_Atraso":ent.get("diasAtrasoPago", 0),
        })
        if sit == 1:
            sit1 += monto
        elif sit in SITS_RIESGO:
            riesgo += monto
    return {
        **base,
        "Sin_Deuda":    False,
        "Monto_Sit1":   sit1,
        "Monto_Riesgo": riesgo,
        "Entidades":    detalle,
        "Periodo":      periodo_id,
    }

# ── Helpers de cálculo ────────────────────────────────────────────────────────

def calcular_pasa(sit1: float, riesgo: float, umbral: float) -> tuple[float, str]:
    """Retorna (ratio_porcentaje, 'PASA'|'NO PASA')."""
    total = sit1 + riesgo
    if total == 0:
        return 0.0, "PASA"
    ratio = riesgo / total * 100
    return round(ratio, 2), "NO PASA" if ratio >= umbral else "PASA"

def detalle_str(entidades: list) -> str:
    return " | ".join(
        f"{e['Entidad']} (Sit: {e['Situacion']} ${e['Monto']:.0f})"
        for e in entidades
    )

def periodo_a_texto(periodo_str: str) -> str:
    """Convierte '202604' → 'Abril 2026'."""
    meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
             "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
    try:
        p    = str(periodo_str).strip()
        anio = int(p[:4])
        mes  = int(p[4:6])
        return f"{meses[mes-1]} {anio}"
    except Exception:
        return str(periodo_str)

def normalizar_columnas(df):
    """Normaliza nombres de columnas del Excel de entrada."""
    df.columns = [c.strip().upper() for c in df.columns]
    cuit_col    = next((c for c in df.columns if c in
                        ["CUIT","CUIL","CUIT/CUIL","NRO_CUIT","NRO_CUIL"]), None)
    nombre_col  = next((c for c in df.columns if c in
                        ["NOMBRE","APELL Y NOMBRE","APELLIDO Y NOMBRE","DENOMINACION","RAZON SOCIAL"]), None)
    capital_col = next((c for c in df.columns if c in
                        ["TOTAL","CAPITAL","CAPITAL VENDIDO","MONTO","CREDITO","IMPORTE"]), None)
    return df, cuit_col, nombre_col, capital_col
