"""
bcra.py — Consulta a la API BCRA con múltiples estrategias de conexión.

El WAF del BCRA bloquea la huella TLS de Python en algunos entornos,
y el curl del sistema falla en otros (ej. Streamlit Cloud, error 000).
Por eso intentamos varios métodos en orden hasta que uno funcione:
  1. curl del sistema (funciona en Windows local, pasa el WAF)
  2. urllib nativo de Python (funciona en Streamlit Cloud)
  3. requests (último recurso)
"""
import subprocess
import json
import time
import shutil
import ssl
import urllib.request
import urllib.error

BASE_URL    = "https://api.bcra.gob.ar/centraldedeudores/v1.0/Deudas"
SITS_RIESGO = [2, 3, 4, 5]

_CURL = shutil.which("curl")

_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/126.0.0.0 Safari/537.36",
}


def _interpretar_codigo(code: int, body: str) -> dict:
    """Convierte un código HTTP + body en el dict de resultado estándar."""
    if code == 200:
        try:
            return {"ok": True, "data": json.loads(body)}
        except json.JSONDecodeError:
            return {"ok": True, "data": None}
    elif code == 404:
        return {"ok": True, "data": None}
    elif code == 503:
        return {"ok": False, "error": "BCRA en mantenimiento (503). Intentá en unos minutos."}
    elif code == 429:
        return {"ok": False, "error": "Rate limit BCRA (429)", "retry": True}
    else:
        return {"ok": False, "error": f"HTTP {code}"}


def _via_curl(url: str, timeout: int = 20) -> dict:
    """Método 1: curl del sistema."""
    if not _CURL:
        return {"ok": False, "error": "curl no disponible"}
    try:
        result = subprocess.run(
            [
                _CURL, "-s", "-S",
                "--max-time", str(timeout),
                "--connect-timeout", "10",
                "-H", f"Accept: {_HEADERS['Accept']}",
                "-H", f"User-Agent: {_HEADERS['User-Agent']}",
                "-w", "\n%{http_code}",
                url,
            ],
            capture_output=True, text=True, timeout=timeout + 5,
        )
        output = result.stdout.strip()
        if not output:
            return {"ok": False, "error": f"curl vacío: {result.stderr.strip()[:80]}"}
        lines = output.rsplit("\n", 1)
        body  = lines[0].strip()
        code  = int(lines[1]) if len(lines) > 1 and lines[1].strip().isdigit() else 0
        if code == 0:
            return {"ok": False, "error": f"curl sin conexión (000): {body[:60]}"}
        return _interpretar_codigo(code, body)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "curl timeout"}
    except Exception as e:
        return {"ok": False, "error": f"curl: {type(e).__name__}"}


def _via_urllib(url: str, timeout: int = 20) -> dict:
    """Método 2: urllib nativo de Python (funciona en Streamlit Cloud)."""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            code = resp.getcode()
            body = resp.read().decode("utf-8", errors="replace")
            return _interpretar_codigo(code, body)
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return _interpretar_codigo(e.code, body)
    except Exception as e:
        return {"ok": False, "error": f"urllib: {type(e).__name__}: {str(e)[:60]}"}


def _via_requests(url: str, timeout: int = 20) -> dict:
    """Método 3: requests (último recurso)."""
    try:
        import requests
        import urllib3
        urllib3.disable_warnings()
        resp = requests.get(url, headers=_HEADERS, timeout=timeout, verify=False)
        return _interpretar_codigo(resp.status_code, resp.text)
    except Exception as e:
        return {"ok": False, "error": f"requests: {type(e).__name__}: {str(e)[:60]}"}


def _consulta(url: str, timeout: int = 20) -> dict:
    """Intenta los 3 métodos en orden hasta que uno conecte."""
    errores = []
    for metodo in (_via_curl, _via_urllib, _via_requests):
        res = metodo(url, timeout)
        # Si conectó (ok) o el BCRA respondió algo concreto (mantenimiento, rate limit), devolver
        if res.get("ok") or "mantenimiento" in res.get("error", "").lower() or res.get("retry"):
            return res
        errores.append(res.get("error", "?"))
    # Ningún método funcionó
    return {"ok": False, "error": " | ".join(errores[:3])}


def consultar_bcra(cuit, intentos=3) -> dict:
    cuit_limpio = str(cuit).replace("-", "").replace(" ", "").replace(".", "").strip()
    url = f"{BASE_URL}/{cuit_limpio}"
    ultimo_error = ""
    for intento in range(1, intentos + 1):
        resultado = _consulta(url)
        if resultado.get("ok"):
            return resultado
        ultimo_error = resultado.get("error", "desconocido")
        if "mantenimiento" in ultimo_error.lower():
            return resultado
        if resultado.get("retry"):
            time.sleep(5 * intento)
        elif intento < intentos:
            time.sleep(2 * intento)
    return {"ok": False, "error": ultimo_error}


def consultar_bcra_historico(cuit, intentos=3) -> dict:
    cuit_limpio = str(cuit).replace("-", "").replace(" ", "").replace(".", "").strip()
    url = f"{BASE_URL}/Historicas/{cuit_limpio}"
    ultimo_error = ""
    for intento in range(1, intentos + 1):
        resultado = _consulta(url)
        if resultado.get("ok"):
            return resultado
        ultimo_error = resultado.get("error", "desconocido")
        if "mantenimiento" in ultimo_error.lower():
            return resultado
        if resultado.get("retry"):
            time.sleep(5 * intento)
        elif intento < intentos:
            time.sleep(2 * intento)
    return {"ok": False, "error": ultimo_error}


# ── Procesamiento de respuestas ───────────────────────────────────────────────

def extraer_nombre_api(data) -> str:
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
    if not nombre:
        nombre = extraer_nombre_api(data)
    base = {
        "CUIT": cuit, "Nombre": nombre, "Capital": capital,
        "Sin_Deuda": True, "Monto_Sit1": 0, "Monto_Riesgo": 0,
        "Entidades": [], "Periodo": "",
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
        "Sin_Deuda": False, "Monto_Sit1": sit1, "Monto_Riesgo": riesgo,
        "Entidades": detalle, "Periodo": periodo_id,
    }

def procesar_respuesta_historica(data, cuit) -> dict:
    nombre = extraer_nombre_api(data) if data else ""
    base = {"CUIT": cuit, "Nombre": nombre, "periodos": []}
    if data is None:
        return base
    results_raw = data.get("results", {})
    if not isinstance(results_raw, dict):
        return base
    periodos_raw = results_raw.get("periodos", [])
    if not periodos_raw:
        return base
    periodos = []
    for p in periodos_raw:
        periodo_id = str(p.get("periodo", ""))
        entidades  = p.get("entidades", [])
        sit_peor   = 0
        total_monto = 0.0
        detalle     = []
        for ent in entidades:
            sit   = int(ent.get("situacion", 0) or 0)
            monto = float(ent.get("monto", 0) or 0)
            detalle.append({
                "Entidad":   ent.get("entidad", ""),
                "Situacion": sit,
                "Monto":     monto,
            })
            if sit > sit_peor:
                sit_peor = sit
            total_monto += monto
        periodos.append({
            "periodo":        periodo_id,
            "periodo_texto":  periodo_a_texto(periodo_id),
            "sit_peor":       sit_peor,
            "total_monto":    total_monto,
            "cant_entidades": len(entidades),
            "entidades":      detalle,
        })
    periodos.sort(key=lambda x: x["periodo"])
    return {**base, "Nombre": nombre, "periodos": periodos}

# ── Helpers de cálculo ────────────────────────────────────────────────────────

def calcular_pasa(sit1: float, riesgo: float, umbral: float) -> tuple[float, str]:
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
    meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
             "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
    try:
        p = str(periodo_str).strip()
        anio = int(p[:4]); mes = int(p[4:6])
        return f"{meses[mes-1]} {anio}"
    except Exception:
        return str(periodo_str)

def normalizar_columnas(df):
    df.columns = [c.strip().upper() for c in df.columns]
    cuit_col    = next((c for c in df.columns if c in
                        ["CUIT","CUIL","CUIT/CUIL","NRO_CUIT","NRO_CUIL"]), None)
    nombre_col  = next((c for c in df.columns if c in
                        ["NOMBRE","APELL Y NOMBRE","APELLIDO Y NOMBRE","DENOMINACION","RAZON SOCIAL"]), None)
    capital_col = next((c for c in df.columns if c in
                        ["TOTAL","CAPITAL","CAPITAL VENDIDO","MONTO","CREDITO","IMPORTE"]), None)
    return df, cuit_col, nombre_col, capital_col
