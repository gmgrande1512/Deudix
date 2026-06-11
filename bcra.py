"""
bcra.py — Consulta a la API BCRA usando curl del sistema.

El WAF del BCRA bloquea las librerías Python (requests, curl_cffi) por
huella TLS. El curl del sistema operativo sí pasa, así que lo usamos
via subprocess. Disponible en Windows 10+, Linux y Streamlit Cloud.
"""
import subprocess
import json
import time
import shutil

BASE_URL    = "https://api.bcra.gob.ar/centraldedeudores/v1.0/Deudas"
SITS_RIESGO = [2, 3, 4, 5]

# Verificar que curl exista
_CURL = shutil.which("curl")

def _consulta_curl(url: str, timeout: int = 20) -> dict:
    """Llama a curl del sistema y parsea la respuesta JSON."""
    if not _CURL:
        return {"ok": False, "error": "curl no encontrado en el sistema"}

    try:
        result = subprocess.run(
            [
                _CURL,
                "-s",                    # silencioso
                "-S",                    # mostrar errores
                "--max-time", str(timeout),
                "--connect-timeout", "10",
                "-H", "Accept: application/json",
                "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/126.0.0.0 Safari/537.36",
                "-w", "\n%{http_code}",  # agregar código HTTP al final
                url,
            ],
            capture_output=True,
            text=True,
            timeout=timeout + 5,
        )

        output = result.stdout.strip()
        if not output:
            stderr = result.stderr.strip()
            return {"ok": False, "error": f"curl sin respuesta: {stderr[:100]}"}

        # Separar body del código HTTP (último línea)
        lines = output.rsplit("\n", 1)
        body  = lines[0].strip()
        code  = int(lines[1]) if len(lines) > 1 and lines[1].strip().isdigit() else 0

        if code == 200:
            try:
                data = json.loads(body)
                return {"ok": True, "data": data}
            except json.JSONDecodeError:
                return {"ok": True, "data": None}
        elif code == 404:
            return {"ok": True, "data": None}
        elif code == 503:
            return {"ok": False, "error": "BCRA en mantenimiento (503). Intentá en unos minutos."}
        elif code == 429:
            return {"ok": False, "error": "Rate limit BCRA (429)", "retry": True}
        elif code == 0:
            return {"ok": False, "error": f"curl error: {body[:100]}"}
        else:
            return {"ok": False, "error": f"HTTP {code}"}

    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Timeout — el BCRA no respondió"}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:80]}"}


def consultar_bcra(cuit, intentos=3) -> dict:
    """
    Consulta la API BCRA para un CUIT dado.
    Retorna {"ok": True, "data": ...} o {"ok": False, "error": "..."}.
    """
    cuit_limpio = str(cuit).replace("-", "").replace(" ", "").replace(".", "").strip()
    url = f"{BASE_URL}/{cuit_limpio}"

    ultimo_error = ""

    for intento in range(1, intentos + 1):
        resultado = _consulta_curl(url)

        if resultado.get("ok"):
            return resultado

        ultimo_error = resultado.get("error", "desconocido")

        if "mantenimiento" in ultimo_error.lower():
            return resultado  # No reintentar si está en mantenimiento

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
