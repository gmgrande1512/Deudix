"""
config.py — Configuración central de Deudix

PAYMENT_MODE controla el sistema de pagos:
  MOCK       — simula pagos al instante, sin red. Para desarrollo local.
  SANDBOX    — Mercado Pago test, tarjetas ficticias, sin cobro real.
  PRODUCCION — Mercado Pago real. Requiere ACCESS_TOKEN válido.

Para pasar a SANDBOX o PRODUCCION:
  1. Obtener Access Token en https://www.mercadopago.com.ar/developers/panel
  2. Completar MP_ACCESS_TOKEN abajo o en variable de entorno DEUDIX_MP_TOKEN
  3. Cambiar PAYMENT_MODE
"""
import os

# ── Modo de pagos ─────────────────────────────────────────────────────────────
PAYMENT_MODE = "MOCK"          # "MOCK" | "SANDBOX" | "PRODUCCION"

# ── Mercado Pago ──────────────────────────────────────────────────────────────
MP_ACCESS_TOKEN  = os.getenv("DEUDIX_MP_TOKEN", "TEST-xxxx-xxxx")   # reemplazar en producción
MP_WEBHOOK_PATH  = "/mp_webhook"   # path del endpoint webhook (cuando se publique)
MP_BACK_URL_OK   = "https://deudix.com/pago_ok"
MP_BACK_URL_FAIL = "https://deudix.com/pago_error"

# ── Negocio ───────────────────────────────────────────────────────────────────
PRECIO_DEFAULT_USD = 0.35          # precio por consulta si el cliente no tiene uno configurado
MONEDA             = "USD"

# ── Paquetes de recarga sugeridos ─────────────────────────────────────────────
# (label, usd, descripcion)
PAQUETES = [
    ("Starter",     10.0,  "~28 consultas"),
    ("Básico",      25.0,  "~71 consultas"),
    ("Profesional", 50.0,  "~142 consultas"),
    ("Empresarial", 100.0, "~285 consultas"),
    ("Premium",     250.0, "~714 consultas"),
]
