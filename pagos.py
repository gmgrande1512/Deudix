"""
pagos.py — Capa de abstracción del sistema de pagos Deudix.

Expone una interfaz única independientemente del backend:
  crear_preferencia(cliente_id, monto_usd, descripcion) -> PreferenciaResult
  verificar_pago(referencia_externa) -> PagoStatus

Internamente enruta a:
  _pago_mock()        — simulación instantánea
  _pago_mp_sandbox()  — Mercado Pago test
  _pago_mp_prod()     — Mercado Pago producción
"""
from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from config import PAYMENT_MODE, MP_ACCESS_TOKEN, MP_BACK_URL_OK, MP_BACK_URL_FAIL, MONEDA


@dataclass
class PreferenciaResult:
    ok:           bool
    preferencia_id: str       = ""
    link_pago:    str         = ""   # URL que el usuario abre para pagar
    monto_usd:    float       = 0.0
    modo:         str         = ""
    error:        str         = ""
    metadata:     dict        = field(default_factory=dict)


@dataclass
class PagoStatus:
    referencia_id: str
    estado:        str    = "pendiente"   # pendiente | acreditado | rechazado | error
    monto_usd:     float  = 0.0
    fecha:         str    = ""
    detalle:       str    = ""


# ── MOCK ──────────────────────────────────────────────────────────────────────

def _mock_crear(cliente_id: int, monto_usd: float, descripcion: str) -> PreferenciaResult:
    """
    Modo MOCK: genera un ID falso y un link que apunta a la página de Estado de
    cuenta con ?mock_pago=<id>. La confirmación es manual desde el botón
    'Simular pago aprobado' en la UI.
    """
    pref_id  = f"MOCK-{uuid.uuid4().hex[:12].upper()}"
    link     = f"?mock_pago={pref_id}&monto={monto_usd}"
    return PreferenciaResult(
        ok=True,
        preferencia_id=pref_id,
        link_pago=link,
        monto_usd=monto_usd,
        modo="MOCK",
        metadata={"cliente_id": cliente_id, "descripcion": descripcion},
    )


def _mock_verificar(referencia_id: str) -> PagoStatus:
    """En MOCK todo pago se considera aprobado al verificar."""
    return PagoStatus(
        referencia_id=referencia_id,
        estado="acreditado",
        monto_usd=0.0,     # el monto real viene de la DB
        fecha=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        detalle="Pago simulado aprobado",
    )


# ── MERCADO PAGO ──────────────────────────────────────────────────────────────

def _mp_crear(cliente_id: int, monto_usd: float, descripcion: str,
              sandbox: bool) -> PreferenciaResult:
    """
    Crea una preferencia de pago en Mercado Pago.
    Requiere: pip install mercadopago
    """
    try:
        import mercadopago
    except ImportError:
        return PreferenciaResult(
            ok=False,
            error="Librería mercadopago no instalada. Ejecutá: pip install mercadopago",
        )

    token = MP_ACCESS_TOKEN
    if not token or token.startswith("TEST-xxxx"):
        return PreferenciaResult(
            ok=False,
            error="Access Token de Mercado Pago no configurado. Ver config.py",
        )

    sdk  = mercadopago.SDK(token)
    pref = {
        "items": [{
            "title":       descripcion,
            "quantity":    1,
            "unit_price":  float(monto_usd),
            "currency_id": MONEDA,
        }],
        "back_urls": {
            "success": MP_BACK_URL_OK,
            "failure": MP_BACK_URL_FAIL,
            "pending": MP_BACK_URL_OK,
        },
        "auto_return":   "approved",
        "external_reference": f"DEUDIX-{cliente_id}-{uuid.uuid4().hex[:8]}",
        "statement_descriptor": "DEUDIX CONSULTAS",
    }

    resp = sdk.preference().create(pref)

    if resp["status"] not in (200, 201):
        return PreferenciaResult(
            ok=False,
            error=f"Error MP {resp['status']}: {resp.get('response', {}).get('message', '')}",
        )

    data     = resp["response"]
    link_key = "sandbox_init_point" if sandbox else "init_point"

    return PreferenciaResult(
        ok=True,
        preferencia_id=data["id"],
        link_pago=data.get(link_key, data.get("init_point", "")),
        monto_usd=monto_usd,
        modo="SANDBOX" if sandbox else "PRODUCCION",
        metadata={"external_reference": pref["external_reference"]},
    )


def _mp_verificar(referencia_id: str) -> PagoStatus:
    """Consulta el estado de un pago por su preference_id o payment_id."""
    try:
        import mercadopago
    except ImportError:
        return PagoStatus(referencia_id=referencia_id, estado="error",
                          detalle="Librería mercadopago no instalada")

    sdk  = mercadopago.SDK(MP_ACCESS_TOKEN)
    resp = sdk.payment().search({"external_reference": referencia_id})

    if resp["status"] != 200:
        return PagoStatus(referencia_id=referencia_id, estado="error",
                          detalle=f"Error MP {resp['status']}")

    results = resp["response"].get("results", [])
    if not results:
        return PagoStatus(referencia_id=referencia_id, estado="pendiente",
                          detalle="Sin pagos registrados para esta referencia")

    pago   = results[0]
    estado = {
        "approved": "acreditado",
        "rejected": "rechazado",
        "pending":  "pendiente",
        "in_process": "pendiente",
    }.get(pago.get("status", ""), "pendiente")

    return PagoStatus(
        referencia_id=referencia_id,
        estado=estado,
        monto_usd=float(pago.get("transaction_amount", 0)),
        fecha=pago.get("date_approved", ""),
        detalle=pago.get("status_detail", ""),
    )


# ── Interfaz pública ──────────────────────────────────────────────────────────

def crear_preferencia(cliente_id: int, monto_usd: float,
                      descripcion: str = "Recarga Deudix") -> PreferenciaResult:
    """Punto de entrada unificado — enruta según PAYMENT_MODE."""
    if PAYMENT_MODE == "MOCK":
        return _mock_crear(cliente_id, monto_usd, descripcion)
    elif PAYMENT_MODE == "SANDBOX":
        return _mp_crear(cliente_id, monto_usd, descripcion, sandbox=True)
    else:
        return _mp_crear(cliente_id, monto_usd, descripcion, sandbox=False)


def verificar_pago(referencia_id: str) -> PagoStatus:
    """Consulta el estado de un pago."""
    if PAYMENT_MODE == "MOCK":
        return _mock_verificar(referencia_id)
    else:
        return _mp_verificar(referencia_id)
