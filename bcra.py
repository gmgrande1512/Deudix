"""
bcra.py — Lógica de consulta a la API BCRA y procesamiento de respuestas.
Extraído de app.py para mantenerlo enfocado en UI.
"""
import requests
import urllib3
import time

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL   = "https://api.bcra.gob.ar/centraldedeudores/v1.0/Deudas"
SITS_RIESGO = [2, 3, 4, 5]

# ── Sesión HTTP ───────────────────────────────────────────────────────────────

_sesion_bcra = None

def get_sesion() -> requests.Session:
    global _sesion_bcra
    s = requests.Session()
    s.verify = False
    s.headers.update({
        "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept":          "application/json, text/plain, */*",
        "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection":      "keep-alive",
        "Referer":         "https://www.bcra.gob.ar/BCRAyVos/Registro_sistemaFinanciero.asp",
        "Origin":          "https://www.bcra.gob.ar",
        "Sec-Fetch-Dest":  "empty",
        "Sec-Fetch-Mode":  "cors",
        "Sec-Fetch-Site":  "same-origin",
    })
    try:
        s.get("https://www.bcra.gob.ar/BCRAyVos/Registro_sistemaFinanciero.asp",
              timeout=10, verify=False)
    except Exception:
        pass
    _sesion_bcra = s
    return _sesion_bcra

def consultar_bcra(cuit, intentos=4) -> dict:
    """
    Consulta la API BCRA para un CUIT dado.
    Retorna {"ok": True, "data": ...} o {"ok": False, "error": "..."}.
    """
    global _sesion_bcra
    cuit_limpio = str(cuit).replace("-", "").replace(" ", "").strip()
    url = f"{BASE_URL}/{cuit_limpio}"
    if _sesion_bcra is None:
        get_sesion()
    for intento in range(1, intentos + 1):
        try:
            resp = _sesion_bcra.get(url, timeout=20)
            if resp.status_code == 200:
                return {"ok": True, "data": resp.json()}
            elif resp.status_code == 404:
                return {"ok": True, "data": None}
            elif resp.status_code == 429:
                time.sleep(5 * intento)
                continue
            else:
                return {"ok": False, "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            if intento < intentos:
                time.sleep(3 * intento)
                get_sesion()
                continue
            return {"ok": False, "error": str(e)}
    return {"ok": False, "error": "Falló después de 4 intentos"}

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
