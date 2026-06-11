"""
app.py — Deudix · Router principal
Cada sección es una función independiente.
El menú lateral es la navegación permanente.
"""
import streamlit as st
import pandas as pd
import io
import time
from datetime import datetime

from auth     import require_login, logout
from database import (registrar_evento_individual, registrar_evento_masivo,
                      get_cliente, get_resumen_mes, get_eventos_periodo,
                      get_actividad_diaria, get_precio_cliente,
                      get_resumen_saldo, registrar_recarga_pendiente,
                      confirmar_recarga, rechazar_recarga,
                      get_movimientos, ajuste_admin_saldo,
                      get_mov_pendiente_por_ref)
from bcra     import (consultar_bcra, consultar_bcra_historico,
                      procesar_respuesta, procesar_respuesta_historica,
                      calcular_pasa, periodo_a_texto, normalizar_columnas)
from reportes import generar_excel, generar_pdf
from admin    import render_admin
from setup    import render_setup
from seguimiento import render_seguimiento

# ── Config ────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Deudix",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

usuario_actual = require_login()

# ══════════════════════════════════════════════════════════════════════════════
# ESTILOS GLOBALES
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,700&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    background-color: #f5f5f7 !important;
    color: #1d1d1f;
}
.stApp { background-color: #f5f5f7 !important; }

/* ── Sidebar — fondo blanco, igual que el back office ────────────────────── */
section[data-testid="stSidebar"] {
    background: #ffffff !important;
    border-right: 0.5px solid #d2d2d7 !important;
}
section[data-testid="stSidebar"] * { color: #1d1d1f !important; }
section[data-testid="stSidebar"] .stRadio label {
    font-size: 14px !important;
    font-weight: 400 !important;
}
[data-testid="collapsedControl"] { display: none !important; }
button[data-testid="baseButton-headerNoPadding"] { display: none !important; }

/* ── Cards (st.container border=True) ────────────────────────────────────── */
div[data-testid="stVerticalBlockBorderWrapper"] {
    background: #ffffff !important;
    border-radius: 16px !important;
    border: 0.5px solid #e5e5ea !important;
    padding: 24px 28px !important;
    box-shadow: none !important;
}

/* ── Tipografía de página ─────────────────────────────────────────────────── */
.page-title { font-size:28px; font-weight:700; color:#1d1d1f; letter-spacing:-0.03em; margin:0 0 2px 0; padding-top:4px; }
.page-sub   { font-size:15px; color:#86868b; margin:0 0 24px 0; font-weight:300; }
.sec-label  { font-size:11px; font-weight:600; letter-spacing:0.08em; text-transform:uppercase; color:#86868b; margin-bottom:12px; }
.divider    { border:none; border-top:0.5px solid #e5e5ea; margin:20px 0; }

/* ── Inputs ──────────────────────────────────────────────────────────────── */
div[data-testid="stTextInput"] input,
div[data-testid="stNumberInput"] input {
    background: #f5f5f7 !important;
    border: 0.5px solid #e5e5ea !important;
    border-radius: 10px !important;
    color: #1d1d1f !important;
    font-size: 15px !important;
    padding: 10px 14px !important;
    transition: border-color 0.15s, box-shadow 0.15s !important;
}
div[data-testid="stTextInput"] input:focus,
div[data-testid="stNumberInput"] input:focus {
    background: #ffffff !important;
    border-color: #0066cc !important;
    box-shadow: 0 0 0 3px rgba(0,102,204,0.12) !important;
    outline: none !important;
}
div[data-testid="stTextInput"] label,
div[data-testid="stNumberInput"] label,
div[data-testid="stSelectbox"] label,
div[data-testid="stFileUploader"] label,
div[data-testid="stCheckbox"] label p {
    color: #1d1d1f !important; font-size: 13px !important; font-weight: 500 !important;
}
div[data-baseweb="select"] > div {
    background: #f5f5f7 !important; border: 0.5px solid #e5e5ea !important;
    border-radius: 10px !important; color: #1d1d1f !important;
}
div[data-baseweb="select"] * { color: #1d1d1f !important; }
div[data-testid="stFileUploader"] {
    background: #f5f5f7 !important; border: 0.5px solid #e5e5ea !important; border-radius: 12px !important;
}
div[data-testid="stFileUploaderDropzone"] * { color: #86868b !important; }

/* ── Botones ─────────────────────────────────────────────────────────────── */
div[data-testid="stButton"] button[kind="primary"] {
    background: #0066cc !important; color: #ffffff !important; font-weight: 600 !important;
    font-size: 15px !important; border: none !important; border-radius: 980px !important;
    padding: 10px 24px !important; transition: background 0.2s !important;
}
div[data-testid="stButton"] button[kind="primary"]:hover { background: #0055aa !important; }
div[data-testid="stButton"] button[kind="secondary"] {
    background: transparent !important; color: #0066cc !important; font-weight: 500 !important;
    border: 0.5px solid #0066cc !important; border-radius: 980px !important; padding: 10px 22px !important;
}
div[data-testid="stDownloadButton"] button {
    background: #0066cc !important; color: #ffffff !important; font-weight: 500 !important;
    border: none !important; border-radius: 8px !important; font-size: 13px !important;
    padding: 8px 16px !important;
}

/* ── Progress, DataFrames, Metrics, Alerts ────────────────────────────────── */
.stProgress > div > div { background: #0066cc !important; border-radius: 4px !important; }
.stProgress > div       { background: #e8e8ed !important; border-radius: 4px !important; }
div[data-testid="stDataFrame"] { border-radius: 12px !important; overflow: hidden !important; }
div[data-testid="stMetric"] { background: #f5f5f7; border-radius: 12px; padding: 16px !important; border: 0.5px solid #e5e5ea; }
div[data-testid="stMetric"] label { color: #86868b !important; font-size: 12px !important; }
div[data-testid="stMetric"] div[data-testid="stMetricValue"] { color: #1d1d1f !important; font-weight: 600 !important; }
div[data-testid="stSuccess"] { border-radius: 10px !important; border: none !important; background: #f0faf0 !important; }
div[data-testid="stError"]   { border-radius: 10px !important; border: none !important; background: #fff0f0 !important; }
div[data-testid="stWarning"] { border-radius: 10px !important; border: none !important; background: #fffbf0 !important; }
div[data-testid="stInfo"]    { border-radius: 10px !important; border: none !important; background: #f0f6ff !important; }

/* ── KPIs ────────────────────────────────────────────────────────────────── */
.kpi  { background:#f5f5f7; border-radius:14px; padding:20px; text-align:center; }
.kpi .n { font-size:2rem; font-weight:700; letter-spacing:-0.04em; line-height:1; color:#1d1d1f; }
.kpi .l { font-size:10px; font-weight:600; color:#86868b; text-transform:uppercase; letter-spacing:0.06em; margin-top:5px; }

/* ── Badges ──────────────────────────────────────────────────────────────── */
.b-pasa   { display:inline-block; background:#f0faf0; color:#1a7a1a; font-size:14px; font-weight:600; padding:6px 16px; border-radius:20px; }
.b-nopasa { display:inline-block; background:#fff0f0; color:#cc0000; font-size:14px; font-weight:600; padding:6px 16px; border-radius:20px; }
.b-sd     { display:inline-block; background:#f0f6ff; color:#0066cc; font-size:14px; font-weight:600; padding:6px 16px; border-radius:20px; }

/* ── Log ─────────────────────────────────────────────────────────────────── */
.log  { background:#1d1d1f; border-radius:12px; padding:14px 18px; font-family:'JetBrains Mono',monospace; font-size:12px; line-height:1.7; height:240px; overflow-y:auto; }
.logh { color:#555; font-size:10px; letter-spacing:0.1em; text-transform:uppercase; margin-bottom:8px; padding-bottom:6px; border-bottom:0.5px solid #2d2d2f; }

/* ── Próximamente ────────────────────────────────────────────────────────── */
.pronto { text-align:center; padding:80px 40px; color:#86868b; }
.pronto .ico { font-size:48px; margin-bottom:16px; }
.pronto h3   { font-size:20px; font-weight:600; color:#1d1d1f; margin:0 0 8px 0; }
.pronto p    { font-size:14px; margin:0; }

/* ── Download button pequeño en cabecera ─────────────────────────────────── */
div[data-testid="stDownloadButton"] button {
    font-size: 11px !important;
    padding: 5px 10px !important;
    border-radius: 6px !important;
    font-weight: 500 !important;
    line-height: 1.3 !important;
    white-space: normal !important;
    text-align: center !important;
    min-height: unset !important;
}

/* ── Footer ──────────────────────────────────────────────────────────────── */
.footer { text-align:center; margin-top:48px; padding:20px 40px; border-top:0.5px solid #e5e5ea; }
.footer .nombre { color:#1d1d1f; font-size:11px; font-weight:600; margin:0 0 4px 0; }
.footer .aviso  { color:#86868b; font-size:10px; margin:0; line-height:1.6; max-width:720px; display:inline-block; }

#MainMenu {visibility:hidden;} footer {visibility:hidden;}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR — MENÚ PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════
es_admin   = usuario_actual.get("email","").lower() == "admin@deudix.com"
cliente    = get_cliente(usuario_actual.get("cliente_id", 0))
logo_bytes = cliente.get("logo_bytes") if cliente else None

with st.sidebar:

    # Logo + nombre empresa
    # Validar que logo_bytes sea una imagen real antes de mostrar
    logo_valido = False
    if logo_bytes and len(logo_bytes) > 16:
        try:
            from PIL import Image
            import io as _io
            Image.open(_io.BytesIO(logo_bytes)).verify()
            logo_valido = True
        except Exception:
            logo_valido = False

    if logo_valido:
        st.image(logo_bytes, width=120)
        st.markdown("<br>", unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">
            <div style="width:36px;height:36px;background:#0066cc;border-radius:10px;
                        display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0;">🏦</div>
            <span style="font-size:18px;font-weight:700;letter-spacing:-0.02em;">Deudix</span>
        </div>
        """, unsafe_allow_html=True)

    nombre_emp = (cliente.get("nombre","") if cliente else "") or "Deudix"
    st.markdown(f'<p style="font-size:11px;color:#86868b;margin:0 0 20px 0;">{nombre_emp}</p>',
                unsafe_allow_html=True)

    # ── Sección: Consultas ─────────────────────────────────────────────────────
    st.markdown('<p style="font-size:10px;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;color:#86868b;margin:0 0 4px 0;">Consultas</p>', unsafe_allow_html=True)

    MENU_ITEMS = [
        ("Consulta individual",  "individual"),
        ("Consulta histórica",   "historica"),
        ("Carga masiva",         "masiva"),
    ]
    MENU_ITEMS_EXTRA = [
        ("Historial",            "historial"),
        ("Seguimiento mensual",  "seguimiento"),
        ("Estado de cuenta ·",   "cuenta"),   # próximamente — deshabilitado
    ]
    MENU_ADMIN = [
        ("Mi empresa",           "setup"),
        ("Back Office",          "backoffice"),
    ]
    MENU_ADMIN_SOLO = [
        ("Mi empresa",           "setup"),
    ]

    todos_items = MENU_ITEMS + MENU_ITEMS_EXTRA
    if es_admin:
        todos_items += MENU_ADMIN
    else:
        todos_items += MENU_ADMIN_SOLO

    labels  = [item[0] for item in todos_items]
    valores = [item[1] for item in todos_items]

    # Separador visual antes de "Más" y "Admin"
    opciones_radio = (
        MENU_ITEMS +
        [("─────────────────", "sep1")] +
        MENU_ITEMS_EXTRA +
        [("─────────────────", "sep2")] +
        (MENU_ADMIN if es_admin else MENU_ADMIN_SOLO)
    )
    labels_radio  = [o[0] for o in opciones_radio]
    valores_radio = [o[1] for o in opciones_radio]

    seleccion = st.radio(
        "",
        labels_radio,
        label_visibility="collapsed",
        key="nav_radio",
    )
    pagina = seleccion  # puede ser sep1/sep2 — los handlers los ignoran

    # ── Usuario ────────────────────────────────────────────────────────────────
    st.markdown('<hr style="border:none;border-top:0.5px solid #d2d2d7;margin:20px 0 12px 0;">', unsafe_allow_html=True)
    st.markdown(f'<p style="font-size:13px;font-weight:500;margin:0;">{usuario_actual.get("nombre","")}</p>', unsafe_allow_html=True)
    st.markdown(f'<p style="font-size:11px;color:#86868b;margin:2px 0 12px 0;">{usuario_actual.get("email","")}</p>', unsafe_allow_html=True)
    if st.button("Cerrar sesión", use_container_width=True, key="btn_logout"):
        logout()

# ══════════════════════════════════════════════════════════════════════════════
# FOOTER — reutilizable
# ══════════════════════════════════════════════════════════════════════════════
FOOTER_HTML = """
<div class="footer">
  <p class="nombre">Deudix · BCRA Central de Deudores · Uso interno · Datos confidenciales</p>
  <p class="aviso"><strong>Aviso:</strong> La información mostrada se obtiene de la API pública del BCRA.
  Este sitio es independiente del BCRA y no almacena datos personales.
  Nuestro sistema agrega valor mediante procesamiento, visualización y reportes, pero no modifica la información.
  El BCRA no avala ni certifica este servicio.</p>
</div>
"""

# ══════════════════════════════════════════════════════════════════════════════
# PÁGINAS
# ══════════════════════════════════════════════════════════════════════════════

def _perfil_completo(cliente: dict) -> bool:
    """Devuelve True si los campos obligatorios del perfil están completos."""
    obligatorios = ["nombre","cuit_empresa","domicilio","ciudad","provincia","telefono","email_empresa"]
    return all(bool(((cliente or {}).get(f) or "").strip()) for f in obligatorios)

def pagina_individual():
    cliente_actual = get_cliente(usuario_actual.get("cliente_id", 0))
    if not _perfil_completo(cliente_actual):
        st.markdown('<p class="page-title">Consulta individual</p>', unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown('''<p style="font-size:16px;font-weight:600;color:#cc0000;margin:0 0 8px 0;">
                Datos de empresa incompletos</p>''', unsafe_allow_html=True)
            from setup import CAMPOS_OBLIGATORIOS
            faltantes = [CAMPOS_OBLIGATORIOS[f] for f in CAMPOS_OBLIGATORIOS
                         if not ((cliente_actual or {}).get(f) or "").strip()]
            st.markdown(f'Completá los siguientes campos antes de realizar consultas: **{", ".join(faltantes)}**')
            if st.button("Completar datos de empresa →", type="primary", key="btn_goto_setup_ind"):
                st.session_state["_ir_a_setup"] = True
                st.rerun()
        return

    st.markdown('<p class="page-title">Consulta individual</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-sub">Consultá la situación crediticia de un CUIT en el BCRA</p>', unsafe_allow_html=True)

    col_form, col_gap, col_result = st.columns([4, 1, 7])

    with col_form:
        with st.container(border=True):
            st.markdown('<p class="sec-label">Datos de consulta</p>', unsafe_allow_html=True)

            cuit_input = st.text_input("CUIT / CUIL",
                                       placeholder="20-12345678-9",
                                       max_chars=13,
                                       key="cuit_ind_v2")
            umbral_ind = st.number_input("Umbral de riesgo (%)",
                                         min_value=1, max_value=100, value=40,
                                         key="umbral_ind_v2",
                                         help="% máximo de deuda en situación negativa para aprobar")
            st.markdown("<br>", unsafe_allow_html=True)
            btn_consultar = st.button("Consultar BCRA", use_container_width=True,
                                      type="primary", key="btn_consultar_v2")

            st.markdown('<hr class="divider">', unsafe_allow_html=True)
            st.markdown('<p class="sec-label">Mapa y Street View</p>', unsafe_allow_html=True)
            direccion_input = st.text_input("Domicilio",
                                            placeholder="Av. Corrientes 1234, Buenos Aires",
                                            key="dir_mapa_v2")
            if direccion_input.strip():
                dir_enc   = direccion_input.strip().replace(" ", "+").replace(",", "%2C")
                gmaps_url = f"https://www.google.com/maps/search/{dir_enc}"
                st.markdown(
                    f'<div style="border-radius:12px;overflow:hidden;'
                    f'border:0.5px solid #e5e5ea;margin-top:8px;">'
                    f'<iframe width="100%" height="260" frameborder="0" '
                    f'style="border:0;display:block;" loading="lazy" allowfullscreen '
                    f'referrerpolicy="no-referrer-when-downgrade" '
                    f'src="https://maps.google.com/maps?q={dir_enc}&output=embed&z=16">'
                    f'</iframe></div>'
                    f'<p style="font-size:11px;color:#86868b;margin:6px 0 0 0;text-align:center;">'
                    f'Clic en 🟡 para Street View &nbsp;&middot;&nbsp; '
                    f'<a href="{gmaps_url}" target="_blank" '
                    f'style="color:#0066cc;text-decoration:none;">Abrir en Google Maps</a></p>',
                    unsafe_allow_html=True,
                )

    with col_result:
        if btn_consultar:
            if not cuit_input.strip():
                st.warning("Ingresá un CUIT válido")
            else:
                with st.spinner("Consultando BCRA…"):
                    resp = consultar_bcra(cuit_input)

                if not resp["ok"]:
                    _err_detalle = resp.get("error", "desconocido")
                    st.markdown(
                        '<div style="background:#fff8f0;border:1.5px solid #cc6600;border-radius:10px;padding:20px 24px;margin:8px 0;">'
                        '<p style="font-size:16px;font-weight:700;color:#cc6600;margin:0 0 6px 0;">⚠️ El BCRA no está disponible en este momento</p>'
                        '<p style="font-size:14px;color:#1d1d1f;margin:0 0 8px 0;">No pudimos conectarnos con la Central de Deudores del Banco Central.</p>'
                        '<p style="font-size:13px;color:#86868b;margin:0;">Esto suele ser temporal. Esperá unos segundos y volvé a intentar. '
                        'Si el problema persiste, el servicio del BCRA puede estar en mantenimiento.</p>'
                        f'<p style="font-size:11px;color:#aeaeb2;margin:8px 0 0 0;font-family:monospace;">Detalle: {_err_detalle}</p>'
                        '</div>',
                        unsafe_allow_html=True,
                    )
                    if st.button("Reintentar", type="primary", key="btn_retry_bcra"):
                        st.rerun()
                else:
                    r           = procesar_respuesta(resp.get("data"), cuit_input)
                    ratio, res  = calcular_pasa(r["Monto_Sit1"], r["Monto_Riesgo"], umbral_ind)
                    nombre_bcra = r.get("Nombre", "")
                    periodo_txt = periodo_a_texto(r.get("Periodo","")) if r.get("Periodo") else ""

                    # ── Resultado principal ────────────────────────────────────
                    with st.container(border=True):
                        # Nombre y CUIT
                        if nombre_bcra:
                            st.markdown(f'<p style="font-size:22px;font-weight:700;color:#1d1d1f;letter-spacing:-0.02em;margin:0 0 2px 0;">{nombre_bcra}</p>', unsafe_allow_html=True)
                        st.markdown(
                            f'<p style="font-size:13px;color:#86868b;margin:0 0 16px 0;">'
                            f'CUIT {cuit_input}'
                            + (f'&nbsp;·&nbsp;{periodo_txt}' if periodo_txt else '')
                            + '</p>',
                            unsafe_allow_html=True,
                        )

                        # Badge de resultado
                        if r.get("Sin_Deuda"):
                            st.markdown('<span class="b-sd">✓ Sin deuda registrada</span>', unsafe_allow_html=True)
                        elif res == "PASA":
                            st.markdown(f'<span class="b-pasa">✓ Pasa · {ratio}% en riesgo</span>', unsafe_allow_html=True)
                        else:
                            st.markdown(f'<span class="b-nopasa">✗ No pasa · {ratio}% en riesgo</span>', unsafe_allow_html=True)

                        # Métricas
                        if not r.get("Sin_Deuda"):
                            st.markdown("<br>", unsafe_allow_html=True)
                            m1, m2, m3 = st.columns(3)
                            total = r["Monto_Sit1"] + r["Monto_Riesgo"]
                            m1.metric("Deuda normal",    f"${r['Monto_Sit1']:,.0f}")
                            m2.metric("Deuda en riesgo", f"${r['Monto_Riesgo']:,.0f}")
                            m3.metric("Total deuda",     f"${total:,.0f}")

                        # Detalle por entidad
                        if r.get("Entidades"):
                            st.markdown('<hr class="divider">', unsafe_allow_html=True)
                            st.markdown('<p class="sec-label">Detalle por entidad financiera</p>', unsafe_allow_html=True)
                            df_ent = pd.DataFrame(r["Entidades"])
                            df_ent.columns = ["Entidad", "Sit.", "Monto $", "Días atraso"]
                            # Color de situación
                            def color_sit(val):
                                colores = {1:"#f0faf0", 2:"#fff8f0", 3:"#fff3e0", 4:"#fff0f0", 5:"#fce4e4"}
                                return f"background-color:{colores.get(val,'')}"
                            st.dataframe(df_ent, use_container_width=True, hide_index=True)

                            st.markdown("<br>", unsafe_allow_html=True)
                            buf = io.BytesIO()
                            df_ent.to_excel(buf, index=False)
                            fname = f"bcra_{cuit_input}_{datetime.now().strftime('%Y%m%d')}"
                            st.download_button(
                                "⬇ Descargar detalle Excel",
                                data=buf.getvalue(),
                                file_name=f"{fname}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True,
                            )

                    # ── Vigilancia mensual ────────────────────────────────────
                    st.markdown('<hr class="divider">', unsafe_allow_html=True)
                    from database import agregar_vigilado, listar_vigilados
                    _ya_vigilado = any(
                        v["cuit"] == cuit_input.replace("-","").replace(".","").strip()
                        for v in listar_vigilados(usuario_actual["cliente_id"])
                    )
                    if _ya_vigilado:
                        st.markdown(
                            '<div style="background:#e8f4ff;border:1.5px solid #0066cc;'
                            'border-radius:10px;padding:14px 18px;margin:4px 0;">'
                            '<p style="font-size:16px;font-weight:700;color:#0066cc;margin:0;">'
                            '👁 En seguimiento mensual</p>'
                            '<p style="font-size:13px;color:#0066cc;margin:4px 0 0 0;font-weight:400;">'
                            'Este CUIT está siendo monitoreado. Recibirás alertas si su situación cambia.</p>'
                            '</div>',
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            '<div style="background:#f5f5f7;border:1.5px solid #d2d2d7;'
                            'border-radius:10px;padding:14px 18px;margin:4px 0;">'
                            '<p style="font-size:15px;font-weight:600;color:#1d1d1f;margin:0 0 6px 0;">'
                            '📋 Seguimiento mensual</p>'
                            '<p style="font-size:13px;color:#86868b;margin:0;">'
                            'Activá el seguimiento para recibir alertas si la situación crediticia cambia mes a mes.</p>'
                            '</div>',
                            unsafe_allow_html=True,
                        )
                        # Botón en lugar de checkbox para evitar rerun antes de mostrar confirmación
                        if st.button("👁 Agregar al seguimiento mensual",
                                     key=f"btn_vigilar_{cuit_input}",
                                     use_container_width=True):
                            _alias = nombre_bcra or cuit_input
                            _ok, _msg = agregar_vigilado(
                                usuario_actual["cliente_id"],
                                usuario_actual["id"],
                                cuit_input, _alias,
                            )
                            if _ok:
                                st.session_state[f"vigilado_ok_{cuit_input}"] = True
                                st.rerun()
                            else:
                                st.error(f"No se pudo agregar: {_msg}")
                        # Confirmación persistente
                        if st.session_state.get(f"vigilado_ok_{cuit_input}"):
                            st.markdown(
                                '<div style="background:#f0faf0;border:1.5px solid #1a7a1a;'
                                'border-radius:10px;padding:16px 20px;margin:8px 0;text-align:center;">'
                                '<p style="font-size:18px;font-weight:700;color:#1a7a1a;margin:0 0 4px 0;">'
                                '✅ CUIT agregado al seguimiento mensual</p>'
                                '<p style="font-size:13px;color:#1a7a1a;margin:0;">'
                                'Vas a recibir alertas si su situación crediticia cambia.</p>'
                                '</div>',
                                unsafe_allow_html=True,
                            )



                    # Mapa si hay dirección
                    if direccion_input.strip():
                        dir_enc = direccion_input.strip().replace(" ", "+").replace(",", "%2C")
                        st.markdown(
                            f'<div style="border-radius:12px;overflow:hidden;border:0.5px solid #e5e5ea;margin-top:16px;">'
                            f'<iframe width="100%" height="280" frameborder="0" style="border:0;display:block;" '
                            f'loading="lazy" allowfullscreen referrerpolicy="no-referrer-when-downgrade" '
                            f'src="https://maps.google.com/maps?q={dir_enc}&output=embed&z=17"></iframe></div>'
                            f'<p style="font-size:11px;color:#86868b;margin-top:6px;text-align:center;">Clic en 🟡 para Street View</p>',
                            unsafe_allow_html=True,
                        )

                    # Registrar en DB
                    registrar_evento_individual(
                        usuario_id=usuario_actual["id"],
                        cliente_id=usuario_actual["cliente_id"],
                        resultado_cat="SIN DEUDA" if r.get("Sin_Deuda") else res,
                    )
        else:
            # Estado vacío — instrucciones
            st.markdown("""
            <div style="text-align:center;padding:60px 20px;color:#86868b;">
                <div style="font-size:48px;margin-bottom:16px;">🔍</div>
                <p style="font-size:16px;font-weight:500;color:#1d1d1f;margin:0 0 8px 0;">Ingresá un CUIT para consultar</p>
                <p style="font-size:14px;margin:0;">El resultado aparecerá aquí en segundos</p>
            </div>
            """, unsafe_allow_html=True)

    st.markdown(FOOTER_HTML, unsafe_allow_html=True)


def pagina_masiva():
    cliente_actual = get_cliente(usuario_actual.get("cliente_id", 0))
    if not _perfil_completo(cliente_actual):
        st.markdown('<p class="page-title">Carga masiva</p>', unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown('''<p style="font-size:16px;font-weight:600;color:#cc0000;margin:0 0 8px 0;">
                Datos de empresa incompletos</p>''', unsafe_allow_html=True)
            from setup import CAMPOS_OBLIGATORIOS
            faltantes = [CAMPOS_OBLIGATORIOS[f] for f in CAMPOS_OBLIGATORIOS
                         if not ((cliente_actual or {}).get(f) or "").strip()]
            st.markdown(f'Completá los siguientes campos antes de procesar consultas: **{", ".join(faltantes)}**')
            if st.button("Completar datos de empresa →", type="primary", key="btn_goto_setup_mas"):
                st.session_state["_ir_a_setup"] = True
                st.rerun()
        return

    st.markdown('<p class="page-title">Carga masiva</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-sub">Procesá un archivo Excel con múltiples CUITs en un solo paso</p>', unsafe_allow_html=True)

    if "procesando" not in st.session_state:
        st.session_state["procesando"] = False

    # ── Subida de archivo ──────────────────────────────────────────────────────
    import os as _os
    _plantilla_path = _os.path.join(_os.path.dirname(__file__), "plantilla_carga_masiva.xlsx")
    _tooltip_formato = (
        "Columnas reconocidas en el Excel:\n"
        "\u2022 CUIT / CUIL / NRO_CUIT (obligatoria)\n"
        "\u2022 NOMBRE / DENOMINACION (opcional)\n"
        "\u2022 CAPITAL / TOTAL / MONTO (opcional)\n"
        "Los CUITs duplicados se agrupan. Columnas extra se ignoran."
    )
    with st.container(border=True):
        _col_tit, _col_btn = st.columns([5, 3])
        with _col_tit:
            st.markdown('<p class="sec-label" style="margin-bottom:4px;">Archivo de entrada</p>',
                        unsafe_allow_html=True)
        with _col_btn:
            if _os.path.exists(_plantilla_path):
                with open(_plantilla_path, "rb") as _pf:
                    st.download_button(
                        "Template de formato de entrada",
                        data=_pf.read(),
                        file_name="plantilla_carga_masiva.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        help=_tooltip_formato,
                        use_container_width=True,
                        key="btn_dl_plantilla",
                    )
        archivo = st.file_uploader("Seleccioná el archivo Excel", type=["xlsx","xls"])

    if not archivo:
        st.markdown(FOOTER_HTML, unsafe_allow_html=True)
        return

    try:
        df_raw = pd.read_excel(archivo)
    except Exception as e:
        st.error(f"No se pudo leer el archivo: {e}")
        return

    df_input, cuit_col, nombre_col, capital_col = normalizar_columnas(df_raw)

    if not cuit_col:
        st.error(f"No se encontró columna CUIT/CUIL. Columnas disponibles: {df_raw.columns.tolist()}")
        return

    conteo_ops  = df_input.groupby(cuit_col).size().reset_index(name="Cant_Operaciones")
    agg = {}
    if nombre_col:  agg[nombre_col]  = "first"
    if capital_col: agg[capital_col] = "sum"
    df_agrupado = (df_input.groupby(cuit_col, as_index=False).agg(agg)
                   if agg else df_input[[cuit_col]].drop_duplicates())
    df_agrupado = df_agrupado.merge(conteo_ops, on=cuit_col, how="left")

    total_filas = len(df_input)
    total_cuits = len(df_agrupado)
    duplicados  = int((conteo_ops["Cant_Operaciones"] > 1).sum())

    # ── Resumen del archivo + parámetros ──────────────────────────────────────
    col_info, col_params = st.columns([5, 7])

    with col_info:
        with st.container(border=True):
            st.markdown('<p class="sec-label">Archivo cargado</p>', unsafe_allow_html=True)
            i1, i2, i3 = st.columns(3)
            i1.metric("Filas", total_filas)
            i2.metric("CUITs únicos", total_cuits)
            i3.metric("Duplicados", duplicados)
            st.caption(f"CUIT: {cuit_col} · Nombre: {nombre_col or '—'} · Capital: {capital_col or '—'}")

    with col_params:
        with st.container(border=True):
            st.markdown('<p class="sec-label">Parámetros de procesamiento</p>', unsafe_allow_html=True)
            r1, r2 = st.columns([1, 3])
            with r1:
                umbral = st.number_input(
                    "% Pasa / No Pasa",
                    min_value=1, max_value=100, value=40, key="umbral_mas",
                    help="Porcentaje máximo de deuda en situación negativa para aprobar un CUIT",
                )
            with r2:
                nombre_sugerido = f"reporte_bcra_{datetime.now().strftime('%Y%m%d_%H%M')}"
                nombre_archivo  = st.text_input(
                    "Nombre del reporte",
                    value=nombre_sugerido, key="nombre_mas",
                )
            st.markdown('<hr style="border:none;border-top:0.5px solid #f0f0f0;margin:10px 0 8px 0;">', unsafe_allow_html=True)
            r3, r4, r5 = st.columns([2, 2, 2])
            with r3:
                st.markdown('<p style="font-size:12px;font-weight:500;color:#1d1d1f;margin:0 0 4px 0;">Formatos de salida</p>', unsafe_allow_html=True)
                gen_excel_chk = st.checkbox("Excel", value=True, key="chk_excel")
                gen_pdf_chk   = st.checkbox("PDF",   value=True, key="chk_pdf")
            with r4:
                st.markdown('<p style="font-size:12px;font-weight:500;color:#1d1d1f;margin:0 0 4px 0;">Opciones</p>', unsafe_allow_html=True)
                incluir_capital = st.checkbox(
                    "Incluir Capital Origen",
                    value=bool(capital_col), disabled=not bool(capital_col), key="chk_cap",
                    help="Incluye la columna de capital del archivo en el cálculo del umbral",
                )
            with r5:
                delay_label = st.selectbox(
                    "Velocidad de consulta",
                    ["0.5s — Rápido", "1.3s — Normal", "2.0s — Seguro"],
                    index=2, key="delay_mas",
                )
                delay_seg = {"0.5s — Rápido": 0.5, "1.3s — Normal": 1.3, "2.0s — Seguro": 2.0}[delay_label]


    # ── Worker de fondo ────────────────────────────────────────────────────────
    # El procesamiento corre en un thread separado.
    # La UI solo lee session_state, asi el usuario puede navegar sin interrumpir.

    def _worker(filas, cuit_col, nombre_col, capital_col, incluir_capital,
                delay_seg, umbral, nombre_archivo, gen_excel, gen_pdf,
                usuario_id, cliente_id):
        resultados = []
        log_msgs   = []
        total      = len(filas)

        for idx_r, row in enumerate(filas):
            if st.session_state.get("cancelar"):
                hora_c = datetime.now().strftime("%H:%M:%S")
                log_msgs.append(
                    f'<span style="color:#ff9500">[{hora_c}] '
                    f'cancelado en {idx_r+1}/{total}</span>'
                )
                break

            cuit     = str(row[cuit_col]).replace(".0", "").strip()
            nombre   = str(row[nombre_col]).strip() if nombre_col else ""
            cap_val  = row.get(capital_col)
            capital  = (float(cap_val)
                        if (capital_col and incluir_capital
                            and cap_val is not None
                            and str(cap_val) not in ("nan", ""))
                        else None)
            cant_ops = int(row.get("Cant_Operaciones", 1))

            resp = consultar_bcra(cuit)
            hora = datetime.now().strftime("%H:%M:%S")

            if resp["ok"]:
                r = procesar_respuesta(resp.get("data"), cuit, nombre, capital)
                r["Cant_Operaciones"] = cant_ops
                resultados.append(r)
                estado_log = "sin deuda" if r.get("Sin_Deuda") else "con deuda"
                log_msgs.append(
                    f'<span style="color:#aaffaa">[{hora}] {cuit} '
                    f'· {estado_log} '
                    f'· {len(r.get("Entidades", []))} entidades</span>'
                )
            else:
                resultados.append({
                    "CUIT": cuit, "Nombre": nombre, "Capital": capital,
                    "error": resp["error"], "Cant_Operaciones": cant_ops,
                    "Monto_Sit1": 0, "Monto_Riesgo": 0,
                    "Sin_Deuda": False, "Entidades": [], "Periodo": "",
                })
                log_msgs.append(
                    f'<span style="color:#ff6b6b">[{hora}] '
                    f'error · {cuit} · {resp["error"][:50]}</span>'
                )

            st.session_state["_worker_progreso"] = {
                "procesados": idx_r + 1,
                "total":      total,
                "log_msgs":   list(log_msgs[-50:]),
            }
            time.sleep(delay_seg)

        # Reintentar errores
        if not st.session_state.get("cancelar"):
            errores_idx = [i for i, r in enumerate(resultados) if r.get("error")]
            if errores_idx:
                time.sleep(3)
                for i in errores_idx:
                    r     = resultados[i]
                    resp2 = consultar_bcra(r["CUIT"])
                    if resp2["ok"]:
                        nuevo = procesar_respuesta(
                            resp2.get("data"), r["CUIT"],
                            r.get("Nombre", ""), r.get("Capital")
                        )
                        nuevo["Cant_Operaciones"] = r.get("Cant_Operaciones", 1)
                        resultados[i] = nuevo
                    time.sleep(2)

        # Registrar en DB
        try:
            registrar_evento_masivo(
                usuario_id=usuario_id,
                cliente_id=cliente_id,
                resultados=resultados,
                umbral=umbral,
            )
        except Exception:
            pass

        # Escribir resultado final en session_state
        st.session_state.update({
            "procesando":       False,
            "resultados":       resultados,
            "umbral_mas_res":   umbral,
            "log_msgs":         log_msgs,
            "nombre_archivo":   nombre_archivo,
            "gen_excel":        gen_excel,
            "gen_pdf":          gen_pdf,
            "_worker_progreso": None,
        })

    # ── Botones de control ─────────────────────────────────────────────────────
    procesando_ahora = st.session_state.get("procesando", False)
    bc1, bc2, bc3 = st.columns([3, 1, 8])
    with bc1:
        btn_proc = st.button(
            "Iniciar procesamiento", use_container_width=True,
            type="primary", key="btn_proc_v2",
            disabled=procesando_ahora,
        )
    with bc2:
        btn_cancel = st.button("Cancelar", key="btn_cancel_v2", use_container_width=True, type="secondary")

    if btn_cancel:
        st.session_state["cancelar"]   = True
        st.session_state["procesando"] = False
        st.rerun()

    if btn_proc:
        st.session_state["cancelar"]         = False
        st.session_state["procesando"]       = True
        st.session_state["_worker_progreso"] = {
            "procesados": 0, "total": total_cuits, "log_msgs": []
        }
        for k in ("resultados", "log_msgs"):
            st.session_state.pop(k, None)

        import threading
        _t = threading.Thread(
            target=_worker,
            args=(
                df_agrupado.to_dict("records"),
                cuit_col, nombre_col, capital_col,
                incluir_capital, delay_seg, umbral, nombre_archivo,
                gen_excel_chk, gen_pdf_chk,
                usuario_actual["id"], usuario_actual["cliente_id"],
            ),
            daemon=True,
        )
        _t.start()
        st.rerun()

    # ── Panel de progreso en vivo ──────────────────────────────────────────────
    progreso = st.session_state.get("_worker_progreso")
    if procesando_ahora and progreso:
        procesados = progreso.get("procesados", 0)
        total_w    = progreso.get("total", total_cuits)
        pct        = int(procesados / total_w * 100) if total_w else 0
        log_live   = progreso.get("log_msgs", [])

        st.markdown(
            f'<p style="text-align:center;color:#86868b;font-size:13px;margin:8px 0;">'
            f'Procesando {procesados} de {total_w} &nbsp;·&nbsp; {pct}%</p>',
            unsafe_allow_html=True,
        )
        st.progress(pct / 100)
        if log_live:
            st.markdown(
                f'<div class="log"><div class="logh">procesando en segundo plano '
                f'— {procesados}/{total_w}</div>'
                f'{"<br>".join(log_live[-20:])}</div>',
                unsafe_allow_html=True,
            )
        # Auto-refresh mientras corre
        time.sleep(1.5)
        st.rerun()

    # Log final (cuando ya termino)
    if "log_msgs" in st.session_state and not procesando_ahora:
        msgs = st.session_state["log_msgs"]
        st.markdown(
            f'<div class="log"><div class="logh">log &nbsp;·&nbsp; {len(msgs)} eventos</div>'
            f'{"<br>".join(msgs)}</div>',
            unsafe_allow_html=True,
        )


    # ── Resultados ─────────────────────────────────────────────────────────────
    if "resultados" in st.session_state:
        resultados    = st.session_state["resultados"]
        umbral_actual = st.session_state.get("umbral_mas_res", 40)

        pasan     = sum(1 for r in resultados if not r.get("error") and not r.get("Sin_Deuda")
                        and calcular_pasa(r["Monto_Sit1"],r["Monto_Riesgo"],umbral_actual)[1]=="PASA")
        no_pasan  = sum(1 for r in resultados if not r.get("error")
                        and calcular_pasa(r["Monto_Sit1"],r["Monto_Riesgo"],umbral_actual)[1]=="NO PASA")
        sin_deuda = sum(1 for r in resultados if not r.get("error") and r.get("Sin_Deuda"))
        errores   = sum(1 for r in resultados if r.get("error"))

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<p class="sec-label">Resultados del procesamiento</p>', unsafe_allow_html=True)

        k1,k2,k3,k4,k5 = st.columns(5)
        for col,num,lbl,color in [
            (k1,len(resultados),"Total",    "#1d1d1f"),
            (k2,pasan,          "Pasan",    "#1a7a1a"),
            (k3,no_pasan,       "No pasan", "#cc0000"),
            (k4,sin_deuda,      "Sin deuda","#0066cc"),
            (k5,errores,        "Errores",  "#86868b"),
        ]:
            col.markdown(f'<div class="kpi"><div class="n" style="color:{color}">{num}</div><div class="l">{lbl}</div></div>',
                         unsafe_allow_html=True)

        # Gráficos
        st.markdown("<br>", unsafe_allow_html=True)
        labels_t=[]; valores_t=[]; colores_t=[]
        for lbl,val,col in [("Pasa",pasan,"#1a7a1a"),("No pasa",no_pasan,"#cc0000"),
                             ("Sin deuda",sin_deuda,"#0066cc"),("Errores",errores,"#86868b")]:
            if val > 0:
                labels_t.append(lbl); valores_t.append(val); colores_t.append(col)

        sit_cnt = {1:0,2:0,3:0,4:0,5:0}
        for r in resultados:
            for ent in r.get("Entidades",[]):
                s = int(ent.get("Situacion",0))
                if s in sit_cnt: sit_cnt[s] += 1

        gc1, gc2 = st.columns(2)
        with gc1:
            st.markdown('<p class="sec-label">Distribución</p>', unsafe_allow_html=True)
            if valores_t:
                try:
                    import plotly.graph_objects as go
                    fig = go.Figure(go.Pie(labels=labels_t,values=valores_t,marker_colors=colores_t,
                                          hole=0.45,textinfo="label+percent",textfont_size=12,
                                          hovertemplate="<b>%{label}</b><br>%{value} CUITs · %{percent}<extra></extra>"))
                    fig.update_layout(margin=dict(t=8,b=8,l=8,r=8),height=240,showlegend=False,
                                      paper_bgcolor="rgba(0,0,0,0)",font_family="DM Sans")
                    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})
                except ImportError:
                    st.bar_chart(pd.DataFrame({"R":labels_t,"N":valores_t}).set_index("R"),height=220)

        with gc2:
            st.markdown('<p class="sec-label">Entidades por situación BCRA</p>', unsafe_allow_html=True)
            if sum(sit_cnt.values()) > 0:
                try:
                    import plotly.graph_objects as go
                    fig2 = go.Figure(go.Bar(
                        x=["Sit.1","Sit.2","Sit.3","Sit.4","Sit.5"],
                        y=[sit_cnt[s] for s in range(1,6)],
                        marker_color=["#1a7a1a","#e68a00","#cc5500","#cc0000","#7a0000"],
                        text=[sit_cnt[s] for s in range(1,6)],textposition="outside",textfont_size=12,
                        hovertemplate="<b>%{x}</b><br>%{y} entidades<extra></extra>",
                    ))
                    fig2.update_layout(margin=dict(t=8,b=8,l=8,r=8),height=240,showlegend=False,
                                       paper_bgcolor="rgba(0,0,0,0)",font_family="DM Sans",
                                       yaxis=dict(showgrid=True,gridcolor="#f0f0f0",zeroline=False),
                                       xaxis=dict(showgrid=False))
                    st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar":False})
                except ImportError:
                    st.bar_chart(pd.DataFrame({"S":[f"Sit.{s}" for s in range(1,6)],
                                               "N":[sit_cnt[s] for s in range(1,6)]}).set_index("S"),height=220)

        st.session_state["graf_torta"]  = {"labels":labels_t,"valores":valores_t,"colores":colores_t}
        st.session_state["graf_barras"] = {s:sit_cnt[s] for s in range(1,6)}

        # ── Vigilancia desde resultado masivo ────────────────────────────────
        st.markdown("<br>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown('<p class="sec-label">Seguimiento mensual</p>', unsafe_allow_html=True)
            st.markdown(
                '<p style="font-size:13px;color:#86868b;margin:0 0 12px 0;">'
                '¿Querés recibir alertas si la situación crediticia cambia mes a mes?</p>',
                unsafe_allow_html=True,
            )

            modo_vig = st.radio(
                "¿Cuáles querés vigilar?",
                ["No vigilar ninguno",
                 "Vigilar todos",
                 "Solo los No pasan",
                 "Seleccionar uno a uno"],
                horizontal=True,
                key="radio_vigilar_masivo",
            )

            if modo_vig != "No vigilar ninguno":
                from database import agregar_vigilado, listar_vigilados
                _vigilados_actuales = {
                    v["cuit"] for v in listar_vigilados(usuario_actual["cliente_id"])
                }

                if modo_vig == "Seleccionar uno a uno":
                    st.markdown("<br>", unsafe_allow_html=True)
                    _sel_cuits = []
                    # Mostrar en columnas de 3
                    _validos = [r for r in resultados if not r.get("error")]
                    _cols_vig = st.columns(3)
                    for _i, _r in enumerate(_validos):
                        _cuit_v = _r["CUIT"].replace("-","").replace(".","").strip()
                        _nombre_v = (_r.get("Nombre") or _cuit_v)[:30]
                        _ya = _cuit_v in _vigilados_actuales
                        with _cols_vig[_i % 3]:
                            _label = f"{'✓ ' if _ya else ''}{_nombre_v}"
                            if st.checkbox(_label, value=_ya, key=f"vig_m_{_cuit_v}",
                                           disabled=_ya):
                                if not _ya:
                                    _sel_cuits.append(_r)

                    if st.button("Agregar seleccionados al seguimiento",
                                 type="primary", key="btn_vig_sel",
                                 disabled=not _sel_cuits):
                        _ok_n = _err_n = 0
                        for _r in _sel_cuits:
                            _ok, _ = agregar_vigilado(
                                usuario_actual["cliente_id"], usuario_actual["id"],
                                _r["CUIT"], _r.get("Nombre","") or _r["CUIT"],
                            )
                            if _ok: _ok_n += 1
                            else:   _err_n += 1
                        st.success(f"✅ {_ok_n} CUITs agregados al seguimiento")
                        if _err_n:
                            st.warning(f"{_err_n} ya existían o tuvieron error")

                else:
                    # Todos o Solo No pasan
                    if modo_vig == "Vigilar todos":
                        _a_vigilar = [r for r in resultados if not r.get("error")]
                    else:  # Solo los No pasan
                        _a_vigilar = [
                            r for r in resultados
                            if not r.get("error") and
                            calcular_pasa(r["Monto_Sit1"], r["Monto_Riesgo"], umbral_actual)[1] == "NO PASA"
                        ]

                    _nuevos = [
                        r for r in _a_vigilar
                        if r["CUIT"].replace("-","").replace(".","").strip()
                        not in _vigilados_actuales
                    ]
                    _ya_estan = len(_a_vigilar) - len(_nuevos)

                    st.markdown(
                        f'<p style="font-size:13px;color:#1d1d1f;margin:8px 0;">'
                        f'{len(_a_vigilar)} CUITs seleccionados · '
                        f'<span style="color:#0066cc;">{_ya_estan} ya en seguimiento</span> · '
                        f'<span style="color:#1a7a1a;">{len(_nuevos)} nuevos</span></p>',
                        unsafe_allow_html=True,
                    )

                    if _nuevos:
                        if st.button(
                            f"Agregar {len(_nuevos)} CUITs al seguimiento",
                            type="primary", key="btn_vig_masivo",
                        ):
                            _ok_n = _err_n = 0
                            for _r in _nuevos:
                                _ok, _ = agregar_vigilado(
                                    usuario_actual["cliente_id"], usuario_actual["id"],
                                    _r["CUIT"], _r.get("Nombre","") or _r["CUIT"],
                                )
                                if _ok: _ok_n += 1
                                else:   _err_n += 1
                            st.success(f"✅ {_ok_n} CUITs agregados al seguimiento mensual")
                            st.rerun()
                    else:
                        st.info("Todos los CUITs seleccionados ya están en seguimiento.")

        # Descarga
        st.markdown("<br>", unsafe_allow_html=True)
        nombre_final = st.session_state.get("nombre_archivo", f"reporte_{datetime.now().strftime('%Y%m%d_%H%M')}")
        if st.button("Generar reportes", use_container_width=False, type="primary", key="btn_gen_rep"):
            if st.session_state.get("gen_excel",True):
                excel_bytes = generar_excel(resultados, umbral_actual)
                st.download_button("⬇ Descargar Excel", data=excel_bytes,
                                   file_name=f"{nombre_final}.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                   use_container_width=True)
            if st.session_state.get("gen_pdf",True):
                empresa_pdf = get_cliente(usuario_actual.get("cliente_id",0))
                pdf_bytes   = generar_pdf(resultados, umbral_actual,
                                          graf_torta  = st.session_state.get("graf_torta"),
                                          graf_barras = st.session_state.get("graf_barras"),
                                          empresa     = empresa_pdf)
                if pdf_bytes:
                    st.download_button("⬇ Descargar PDF", data=pdf_bytes,
                                       file_name=f"{nombre_final}.pdf",
                                       mime="application/pdf",
                                       use_container_width=True)
                else:
                    st.warning("Para PDF: pip install reportlab matplotlib")

    st.markdown(FOOTER_HTML, unsafe_allow_html=True)


def pagina_pronto(titulo, icono, descripcion):
    st.markdown(f'<p class="page-title">{titulo}</p>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="pronto">
        <div class="ico">{icono}</div>
        <h3>Próximamente</h3>
        <p>{descripcion}</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(FOOTER_HTML, unsafe_allow_html=True)



def pagina_historial():
    st.markdown('<p class="page-title">Historial de consultas</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-sub">Actividad y detalle de consultas realizadas por tu empresa</p>', unsafe_allow_html=True)

    cliente_id = usuario_actual.get("cliente_id")
    now = datetime.now()

    with st.container(border=True):
        st.markdown('<p class="sec-label">Período</p>', unsafe_allow_html=True)
        f1, f2 = st.columns(2)
        with f1:
            anio_sel = st.selectbox("Año", list(range(now.year, now.year - 3, -1)), key="hist_anio")
        with f2:
            meses   = {"Enero":1,"Febrero":2,"Marzo":3,"Abril":4,"Mayo":5,"Junio":6,
                       "Julio":7,"Agosto":8,"Septiembre":9,"Octubre":10,"Noviembre":11,"Diciembre":12}
            mes_n   = st.selectbox("Mes", list(meses.keys()), index=now.month - 1, key="hist_mes")
            mes_sel = meses[mes_n]

    res = get_resumen_mes(cliente_id=cliente_id, anio=anio_sel, mes=mes_sel)
    st.markdown(
        f'<p style="font-size:11px;font-weight:600;letter-spacing:0.08em;'
        f'text-transform:uppercase;color:#86868b;margin:16px 0 12px 0;">'
        f'{mes_n} {anio_sel}</p>',
        unsafe_allow_html=True,
    )

    k1, k2, k3, k4 = st.columns(4)
    for col, val, lbl, color in [
        (k1, res["total_consultas"],        "Total casos",  "#1d1d1f"),
        (k2, f"${res['total_costo']:,.2f}", "Facturado",    "#0066cc"),
        (k3, res["mas_corridas"],           "Batch",        "#1d1d1f"),
        (k4, res["ind_total"],              "Individuales", "#1d1d1f"),
    ]:
        col.markdown(
            f'<div class="kpi"><div class="n" style="color:{color}">{val}</div>'
            f'<div class="l">{lbl}</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)
    col_ind, col_mas = st.columns(2)
    with col_ind:
        with st.container(border=True):
            st.markdown('<p class="sec-label">Individuales</p>', unsafe_allow_html=True)
            for lbl, val, color in [
                ("Pasan",     res["ind_pasan"],    "#1a7a1a"),
                ("No pasan",  res["ind_no_pasan"], "#cc0000"),
                ("Sin deuda", res["ind_sin_deuda"],"#0066cc"),
                ("Errores",   res["ind_errores"],  "#86868b"),
            ]:
                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;padding:6px 0;'
                    f'border-bottom:0.5px solid #f5f5f7;">'
                    f'<span style="font-size:13px;color:#1d1d1f;">{lbl}</span>'
                    f'<span style="font-size:13px;font-weight:600;color:{color};">{val}</span></div>',
                    unsafe_allow_html=True,
                )
    with col_mas:
        with st.container(border=True):
            st.markdown('<p class="sec-label">Batch</p>', unsafe_allow_html=True)
            for lbl, val, color in [
                ("Corridas",  res["mas_corridas"],  "#1d1d1f"),
                ("Casos",     res["mas_casos"],     "#1d1d1f"),
                ("Pasan",     res["mas_pasan"],     "#1a7a1a"),
                ("No pasan",  res["mas_no_pasan"],  "#cc0000"),
                ("Sin deuda", res["mas_sin_deuda"], "#0066cc"),
                ("Errores",   res["mas_errores"],   "#86868b"),
            ]:
                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;padding:6px 0;'
                    f'border-bottom:0.5px solid #f5f5f7;">'
                    f'<span style="font-size:13px;color:#1d1d1f;">{lbl}</span>'
                    f'<span style="font-size:13px;font-weight:600;color:{color};">{val}</span></div>',
                    unsafe_allow_html=True,
                )

    st.markdown("<br>", unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown('<p class="sec-label">Actividad — últimos 30 días</p>', unsafe_allow_html=True)
        act = get_actividad_diaria(30, cliente_id=cliente_id)
        if act:
            df_act = pd.DataFrame(act)
            df_act.columns = ["Día", "Consultas"]
            st.bar_chart(df_act.set_index("Día"), height=180)
        else:
            st.markdown(
                '<p style="color:#86868b;font-size:13px;text-align:center;padding:20px 0;">'
                'Sin actividad en los últimos 30 días</p>',
                unsafe_allow_html=True,
            )

    eventos = get_eventos_periodo(cliente_id=cliente_id, anio=anio_sel, mes=mes_sel)
    with st.container(border=True):
        n_mas = len(eventos["masivos"])
        st.markdown(
            f'<p class="sec-label">Corridas batch — {mes_n} {anio_sel} ({n_mas})</p>',
            unsafe_allow_html=True,
        )
        if eventos["masivos"]:
            df_m = pd.DataFrame(eventos["masivos"])[
                ["fecha_hora","usuario","total_casos","pasan","no_pasan","sin_deuda","errores","costo_total","umbral_usado"]
            ]
            df_m.columns = ["Fecha","Usuario","Casos","Pasan","No pasan","Sin deuda","Errores","Costo $","Umbral %"]
            df_m["Costo $"] = df_m["Costo $"].apply(lambda x: f"${x:,.2f}")
            st.dataframe(df_m, use_container_width=True, hide_index=True, height=220)
        else:
            st.markdown('<p style="color:#86868b;font-size:13px;">Sin corridas batch en este período.</p>', unsafe_allow_html=True)

    with st.container(border=True):
        n_ind = len(eventos["individuales"])
        st.markdown(
            f'<p class="sec-label">Consultas individuales — {mes_n} {anio_sel} ({n_ind})</p>',
            unsafe_allow_html=True,
        )
        if eventos["individuales"]:
            df_i = pd.DataFrame(eventos["individuales"])[["fecha_hora","usuario","resultado_cat","costo"]]
            df_i.columns = ["Fecha","Usuario","Resultado","Costo $"]
            df_i["Costo $"] = df_i["Costo $"].apply(lambda x: f"${x:,.2f}")
            st.dataframe(df_i, use_container_width=True, hide_index=True, height=220)
        else:
            st.markdown('<p style="color:#86868b;font-size:13px;">Sin consultas individuales en este período.</p>', unsafe_allow_html=True)

    st.markdown(FOOTER_HTML, unsafe_allow_html=True)



def pagina_estado_cuenta():
    from config   import PAQUETES, PAYMENT_MODE
    from pagos    import crear_preferencia, verificar_pago
    from database import (get_resumen_saldo, registrar_recarga_pendiente,
                           confirmar_recarga, rechazar_recarga,
                           get_movimientos, ajuste_admin_saldo,
                           get_mov_pendiente_por_ref)

    st.markdown('<p class="page-title">Estado de cuenta</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-sub">Saldo disponible, precio por consulta y movimientos</p>',
                unsafe_allow_html=True)

    cliente_id = usuario_actual.get("cliente_id")
    es_admin_g = usuario_actual.get("rol") == "admin"
    resumen    = get_resumen_saldo(cliente_id)

    # ── Verificar pago pendiente en modo MOCK (query param) ───────────────────
    # En producción esto lo hace el webhook de MP. En MOCK lo hacemos manual.
    params = st.query_params
    if "mock_pago" in params:
        ref_mock = params["mock_pago"]
        mov = get_mov_pendiente_por_ref(ref_mock)
        if mov:
            st.session_state["_mock_pago_pendiente"] = mov["id"]

    # ── Panel de saldo actual ─────────────────────────────────────────────────
    with st.container(border=True):
        st.markdown('<p class="sec-label">Saldo disponible</p>', unsafe_allow_html=True)
        s1, s2, s3, s4 = st.columns(4)

        saldo      = resumen["saldo_usd"]
        equiv      = resumen["consultas_disp"]
        precio     = resumen["precio_usd"]
        color_saldo = "#1a7a1a" if saldo > 0 else "#cc0000"

        s1.markdown(
            f'<div class="kpi"><div class="n" style="color:{color_saldo};">'
            f'USD&nbsp;{saldo:,.2f}</div><div class="l">Saldo disponible</div></div>',
            unsafe_allow_html=True,
        )
        s2.markdown(
            f'<div class="kpi"><div class="n" style="color:{color_saldo};">'
            f'{equiv:,}</div><div class="l">Consultas disponibles</div></div>',
            unsafe_allow_html=True,
        )
        s3.markdown(
            f'<div class="kpi"><div class="n">USD&nbsp;{precio:.4f}</div>'
            f'<div class="l">Precio por consulta</div></div>',
            unsafe_allow_html=True,
        )
        s4.markdown(
            f'<div class="kpi"><div class="n">USD&nbsp;{resumen["tot_consumido"]:,.2f}</div>'
            f'<div class="l">Consumido histórico</div></div>',
            unsafe_allow_html=True,
        )

        if saldo <= precio * 5:
            st.warning(
                f"Saldo bajo: te quedan {equiv} consulta{'s' if equiv != 1 else ''}. "
                f"Recargá para seguir operando."
            )

    # ── Recarga pendiente de confirmación (MOCK) ──────────────────────────────
    mov_id_pendiente = st.session_state.get("_mock_pago_pendiente")
    if mov_id_pendiente and PAYMENT_MODE == "MOCK":
        with st.container(border=True):
            st.markdown('<p class="sec-label">Pago en proceso</p>', unsafe_allow_html=True)
            st.info(
                "Hay una recarga pendiente de confirmación. "
                "En modo MOCK podés aprobarla o rechazarla manualmente."
            )
            col_ok, col_no, _ = st.columns([2, 2, 6])
            with col_ok:
                if st.button("Confirmar pago recibido", type="primary",
                             key="btn_confirmar_mock"):
                    if confirmar_recarga(mov_id_pendiente):
                        st.session_state.pop("_mock_pago_pendiente", None)
                        st.success("Saldo acreditado correctamente")
                        st.rerun()
                    else:
                        st.error("No se pudo confirmar el pago")
            with col_no:
                if st.button("Rechazar", key="btn_rechazar_mock"):
                    rechazar_recarga(mov_id_pendiente)
                    st.session_state.pop("_mock_pago_pendiente", None)
                    st.rerun()

    # ── Recargar saldo ────────────────────────────────────────────────────────
    with st.container(border=True):
        st.markdown('<p class="sec-label">Recargar saldo</p>', unsafe_allow_html=True)

        modo_label = {"MOCK": "Modo simulación", "SANDBOX": "Mercado Pago test",
                      "PRODUCCION": "Mercado Pago"}.get(PAYMENT_MODE, PAYMENT_MODE)
        st.markdown(
            f'<p style="font-size:12px;color:#86868b;margin:0 0 16px 0;">'
            f'Plataforma de pago: <strong style="color:#1d1d1f;">{modo_label}</strong>'
            + (" — los pagos son simulados, sin cobro real" if PAYMENT_MODE == "MOCK" else "")
            + "</p>",
            unsafe_allow_html=True,
        )

        tab_paquetes, tab_libre = st.tabs(["Paquetes", "Monto libre"])

        with tab_paquetes:
            st.markdown("<br>", unsafe_allow_html=True)
            cols = st.columns(len(PAQUETES))
            monto_paquete = None
            for i, (col, (label, usd, desc)) in enumerate(zip(cols, PAQUETES)):
                equiv_p = int(usd / precio) if precio > 0 else 0
                col.markdown(
                    f'<div style="background:#f5f5f7;border-radius:12px;padding:16px 12px;'
                    f'text-align:center;border:0.5px solid #e5e5ea;">'
                    f'<div style="font-size:13px;font-weight:600;color:#1d1d1f;">{label}</div>'
                    f'<div style="font-size:1.6rem;font-weight:700;color:#0066cc;'
                    f'letter-spacing:-0.03em;margin:6px 0;">USD&nbsp;{usd:.0f}</div>'
                    f'<div style="font-size:11px;color:#86868b;">~{equiv_p} consultas</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if col.button("Seleccionar", key=f"pkg_{i}", use_container_width=True):
                    st.session_state["_monto_recarga"] = usd

            monto_sel = st.session_state.get("_monto_recarga")
            if monto_sel:
                st.markdown(
                    f'<p style="font-size:13px;color:#1d1d1f;margin:12px 0 4px 0;">'
                    f'Monto seleccionado: <strong>USD {monto_sel:.2f}</strong> '
                    f'(~{int(monto_sel/precio) if precio > 0 else 0} consultas)</p>',
                    unsafe_allow_html=True,
                )
                if st.button("Generar link de pago", type="primary",
                             key="btn_pagar_paquete"):
                    _procesar_pago(cliente_id, monto_sel,
                                   f"Recarga Deudix {monto_sel:.0f} USD",
                                   crear_preferencia, registrar_recarga_pendiente)

        with tab_libre:
            st.markdown("<br>", unsafe_allow_html=True)
            c_amt, c_btn = st.columns([2, 1])
            with c_amt:
                monto_libre = st.number_input(
                    "Monto en USD", min_value=1.0, max_value=10000.0,
                    value=50.0, step=5.0, key="monto_libre_input",
                )
                equiv_libre = int(monto_libre / precio) if precio > 0 else 0
                st.caption(f"Equivale a aproximadamente {equiv_libre} consultas")
            with c_btn:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Generar link de pago", type="primary",
                             key="btn_pagar_libre"):
                    _procesar_pago(cliente_id, monto_libre,
                                   f"Recarga Deudix {monto_libre:.0f} USD",
                                   crear_preferencia, registrar_recarga_pendiente)

    # ── Link de pago generado ─────────────────────────────────────────────────
    link_info = st.session_state.get("_link_pago_info")
    if link_info:
        with st.container(border=True):
            st.markdown('<p class="sec-label">Link de pago generado</p>',
                        unsafe_allow_html=True)
            if PAYMENT_MODE == "MOCK":
                st.success(
                    f"Pago simulado generado por USD {link_info['monto']:.2f}. "
                    f"En modo MOCK hacé clic en 'Confirmar' para acreditar el saldo."
                )
                if st.button("Simular pago aprobado", type="primary",
                             key="btn_simular_ok"):
                    if confirmar_recarga(link_info["mov_id"]):
                        st.session_state.pop("_link_pago_info", None)
                        st.session_state.pop("_monto_recarga", None)
                        st.success("Saldo acreditado. Recargando...")
                        st.rerun()
            else:
                st.info(
                    "Tu link de pago está listo. Abrilo para completar la transacción. "
                    "El saldo se acreditará automáticamente al confirmar el pago."
                )
                link = link_info.get("link", "")
                st.markdown(
                    f'<a href="{link}" target="_blank" style="display:inline-block;'
                    f'background:#0066cc;color:#fff;padding:10px 24px;border-radius:8px;'
                    f'text-decoration:none;font-weight:600;font-size:14px;">'
                    f'Ir a pagar USD {link_info["monto"]:.2f}</a>',
                    unsafe_allow_html=True,
                )
                st.caption(f"Referencia: {link_info.get('ref', '')}")

    # ── Facturación del mes ───────────────────────────────────────────────────
    with st.container(border=True):
        st.markdown('<p class="sec-label">Facturación este mes</p>', unsafe_allow_html=True)
        now = datetime.now()
        res = get_resumen_mes(cliente_id=cliente_id, anio=now.year, mes=now.month)
        f1, f2, f3 = st.columns(3)
        f1.metric("Consultas del mes", res["total_consultas"])
        f2.metric("Facturado",         f"USD {res['total_costo']:,.2f}")
        f3.metric("Batch realizados",  res["mas_corridas"])

    # ── Historial de movimientos ──────────────────────────────────────────────
    with st.container(border=True):
        st.markdown('<p class="sec-label">Movimientos de saldo</p>', unsafe_allow_html=True)
        movs = get_movimientos(cliente_id, limite=50)
        if movs:
            tipo_icon  = {"recarga":"↑","consumo":"↓","ajuste_admin":"≈","reembolso":"↩"}
            tipo_color = {"recarga":"#1a7a1a","consumo":"#cc0000",
                          "ajuste_admin":"#0066cc","reembolso":"#e68a00"}
            estado_badge = {
                "acreditado": '<span style="background:#f0faf0;color:#1a7a1a;'
                              'padding:2px 8px;border-radius:4px;font-size:11px;">acreditado</span>',
                "pendiente":  '<span style="background:#fffbf0;color:#cc6600;'
                              'padding:2px 8px;border-radius:4px;font-size:11px;">pendiente</span>',
                "rechazado":  '<span style="background:#fff0f0;color:#cc0000;'
                              'padding:2px 8px;border-radius:4px;font-size:11px;">rechazado</span>',
            }
            for m in movs[:20]:
                t     = m.get("tipo","")
                ico   = tipo_icon.get(t, "·")
                col   = tipo_color.get(t, "#86868b")
                signo = "+" if t in ("recarga","ajuste_admin","reembolso") else "-"
                badge = estado_badge.get(m.get("estado",""), "")
                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;'
                    f'align-items:center;padding:8px 0;border-bottom:0.5px solid #f5f5f7;">'
                    f'<div>'
                    f'<span style="font-size:13px;color:#1d1d1f;">'
                    f'{m.get("descripcion","—")}</span><br>'
                    f'<span style="font-size:11px;color:#86868b;">'
                    f'{m.get("fecha_hora","")[:16]}'
                    f'{" · " + m["usuario_nombre"] if m.get("usuario_nombre") else ""}'
                    f'</span></div>'
                    f'<div style="text-align:right;">'
                    f'<span style="font-size:14px;font-weight:600;color:{col};">'
                    f'{signo} USD {abs(m.get("monto_usd",0)):.2f}</span><br>'
                    f'{badge}</div></div>',
                    unsafe_allow_html=True,
                )
            if len(movs) > 20:
                st.caption(f"Mostrando 20 de {len(movs)} movimientos")
        else:
            st.markdown(
                '<p style="color:#86868b;font-size:13px;">Sin movimientos registrados.</p>',
                unsafe_allow_html=True,
            )

    # ── Ajuste manual de saldo (solo admin global) ────────────────────────────
    if es_admin_g:
        with st.container(border=True):
            st.markdown('<p class="sec-label">Ajuste de saldo (admin)</p>',
                        unsafe_allow_html=True)
            st.caption("Para acreditar o debitar saldo manualmente a este cliente.")
            aj1, aj2, aj3 = st.columns([1, 2, 1])
            with aj1:
                monto_aj = st.number_input(
                    "Monto USD (negativo para debitar)",
                    min_value=-10000.0, max_value=10000.0,
                    value=0.0, step=1.0, key="aj_monto",
                )
            with aj2:
                desc_aj = st.text_input("Motivo del ajuste", key="aj_desc")
            with aj3:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Aplicar ajuste", key="btn_ajuste",
                             disabled=(monto_aj == 0 or not desc_aj.strip())):
                    ajuste_admin_saldo(
                        cliente_id, usuario_actual["id"],
                        monto_aj, desc_aj.strip()
                    )
                    st.success(
                        f"Ajuste aplicado: {'+'if monto_aj>=0 else ''}USD {monto_aj:.2f}"
                    )
                    st.rerun()

    st.markdown(FOOTER_HTML, unsafe_allow_html=True)


def _procesar_pago(cliente_id, monto_usd, descripcion,
                   crear_preferencia_fn, registrar_fn):
    """Helper: crea preferencia de pago y la guarda en session_state."""
    result = crear_preferencia_fn(cliente_id, monto_usd, descripcion)
    if not result.ok:
        st.error(f"Error al generar el link de pago: {result.error}")
        return
    mov_id = registrar_fn(
        cliente_id=cliente_id,
        usuario_id=st.session_state.get("usuario", {}).get("id", 0),
        monto_usd=monto_usd,
        referencia_ext=result.preferencia_id,
        modo_pago=result.modo,
    )
    st.session_state["_link_pago_info"] = {
        "mov_id": mov_id,
        "link":   result.link_pago,
        "monto":  monto_usd,
        "ref":    result.preferencia_id,
    }
    if result.modo == "MOCK":
        st.session_state["_mock_pago_pendiente"] = mov_id
    st.rerun()



def pagina_historica():
    """Consulta histórica individual — últimos 24 meses de un CUIT."""
    cliente_actual = get_cliente(usuario_actual.get("cliente_id", 0))
    if not _perfil_completo(cliente_actual):
        st.markdown('<p class="page-title">Consulta histórica</p>', unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown('''<p style="font-size:16px;font-weight:600;color:#cc0000;margin:0 0 8px 0;">
                Datos de empresa incompletos</p>''', unsafe_allow_html=True)
            from setup import CAMPOS_OBLIGATORIOS
            faltantes = [CAMPOS_OBLIGATORIOS[f] for f in CAMPOS_OBLIGATORIOS
                         if not ((cliente_actual or {}).get(f) or "").strip()]
            st.markdown(f'Completá los siguientes campos antes de realizar consultas: **{", ".join(faltantes)}**')
            if st.button("Completar datos de empresa →", type="primary", key="btn_goto_setup_hist"):
                st.session_state["_ir_a_setup"] = True
                st.rerun()
        return

    st.markdown('<p class="page-title">Consulta histórica</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-sub">Evolución crediticia de un CUIT en los últimos 24 meses</p>', unsafe_allow_html=True)

    col_form, col_gap, col_result = st.columns([4, 1, 7])

    with col_form:
        with st.container(border=True):
            st.markdown('<p class="sec-label">Datos de consulta</p>', unsafe_allow_html=True)
            cuit_input = st.text_input("CUIT / CUIL",
                                       placeholder="20-12345678-9",
                                       max_chars=13,
                                       key="cuit_hist_v1")
            st.markdown("<br>", unsafe_allow_html=True)
            btn_consultar = st.button("Consultar historial BCRA", use_container_width=True,
                                      type="primary", key="btn_consultar_hist_v1")

            st.markdown('<hr class="divider">', unsafe_allow_html=True)
            st.markdown('<p class="sec-label">Mapa y Street View</p>', unsafe_allow_html=True)
            direccion_input = st.text_input("Domicilio",
                                            placeholder="Av. Corrientes 1234, Buenos Aires",
                                            key="dir_mapa_hist_v1")
            if direccion_input.strip():
                dir_enc   = direccion_input.strip().replace(" ", "+").replace(",", "%2C")
                gmaps_url = f"https://www.google.com/maps/search/{dir_enc}"
                st.markdown(
                    f'<div style="border-radius:12px;overflow:hidden;'
                    f'border:0.5px solid #e5e5ea;margin-top:8px;">'
                    f'<iframe width="100%" height="260" frameborder="0" '
                    f'style="border:0;display:block;" loading="lazy" allowfullscreen '
                    f'referrerpolicy="no-referrer-when-downgrade" '
                    f'src="https://maps.google.com/maps?q={dir_enc}&output=embed&z=16">'
                    f'</iframe></div>'
                    f'<p style="font-size:11px;color:#86868b;margin:6px 0 0 0;text-align:center;">'
                    f'<a href="{gmaps_url}" target="_blank" '
                    f'style="color:#0066cc;text-decoration:none;">Abrir en Google Maps</a></p>',
                    unsafe_allow_html=True,
                )

    with col_result:
        if btn_consultar:
            if not cuit_input.strip():
                st.warning("Ingresá un CUIT válido")
            else:
                with st.spinner("Consultando historial BCRA…"):
                    resp = consultar_bcra_historico(cuit_input)

                if not resp["ok"]:
                    _err_detalle = resp.get("error", "desconocido")
                    st.markdown(
                        '<div style="background:#fff8f0;border:1.5px solid #cc6600;border-radius:10px;padding:20px 24px;margin:8px 0;">'
                        '<p style="font-size:16px;font-weight:700;color:#cc6600;margin:0 0 6px 0;">⚠️ El BCRA no está disponible en este momento</p>'
                        '<p style="font-size:14px;color:#1d1d1f;margin:0 0 8px 0;">No pudimos conectarnos con la Central de Deudores.</p>'
                        f'<p style="font-size:11px;color:#aeaeb2;margin:8px 0 0 0;font-family:monospace;">Detalle: {_err_detalle}</p>'
                        '</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    r = procesar_respuesta_historica(resp.get("data"), cuit_input)
                    nombre_bcra = r.get("Nombre", "")
                    periodos    = r.get("periodos", [])

                    # ── Header ──────────────────────────────────────────────
                    with st.container(border=True):
                        if nombre_bcra:
                            st.markdown(
                                f'<p style="font-size:22px;font-weight:700;color:#1d1d1f;'
                                f'letter-spacing:-0.02em;margin:0 0 2px 0;">{nombre_bcra}</p>',
                                unsafe_allow_html=True,
                            )
                        st.markdown(
                            f'<p style="font-size:13px;color:#86868b;margin:0 0 16px 0;">'
                            f'CUIT {cuit_input} · Últimos {len(periodos)} meses</p>',
                            unsafe_allow_html=True,
                        )

                        if not periodos:
                            st.markdown('<span class="b-sd">✓ Sin registros históricos</span>',
                                        unsafe_allow_html=True)
                        else:
                            # ── Gráfico de evolución ────────────────────────
                            st.markdown('<p class="sec-label">Evolución de situación crediticia</p>',
                                        unsafe_allow_html=True)

                            try:
                                import plotly.graph_objects as go

                                x_periodos   = [p["periodo_texto"] for p in periodos]
                                y_sit_peor   = [p["sit_peor"] for p in periodos]
                                y_monto      = [p["total_monto"] for p in periodos]

                                # Color por situación
                                sit_colors = {
                                    0: "#c7c7cc", 1: "#1a7a1a", 2: "#e68a00",
                                    3: "#cc5500", 4: "#cc0000", 5: "#7a0000",
                                }
                                bar_colors = [sit_colors.get(s, "#86868b") for s in y_sit_peor]

                                fig = go.Figure()
                                fig.add_trace(go.Bar(
                                    x=x_periodos,
                                    y=y_sit_peor,
                                    marker_color=bar_colors,
                                    text=[f"Sit. {s}" for s in y_sit_peor],
                                    textposition="outside",
                                    textfont_size=11,
                                    hovertemplate=(
                                        "<b>%{x}</b><br>"
                                        "Peor situación: %{y}<br>"
                                        "<extra></extra>"
                                    ),
                                ))

                                # Línea de referencia en Sit. 1 (zona segura)
                                fig.add_hline(
                                    y=1.5, line_dash="dot", line_color="#1a7a1a",
                                    opacity=0.4,
                                    annotation_text="Zona segura (Sit. 1)",
                                    annotation_position="top left",
                                    annotation_font_size=10,
                                    annotation_font_color="#1a7a1a",
                                )

                                fig.update_layout(
                                    margin=dict(t=16, b=8, l=8, r=8),
                                    height=280,
                                    showlegend=False,
                                    paper_bgcolor="rgba(0,0,0,0)",
                                    plot_bgcolor="rgba(0,0,0,0)",
                                    font_family="DM Sans",
                                    yaxis=dict(
                                        title="Situación",
                                        range=[0, 5.8],
                                        dtick=1,
                                        showgrid=True,
                                        gridcolor="#f0f0f0",
                                        zeroline=False,
                                    ),
                                    xaxis=dict(
                                        title="Período",
                                        showgrid=False,
                                        tickangle=-45,
                                    ),
                                )
                                st.plotly_chart(fig, use_container_width=True,
                                                config={"displayModeBar": False})

                            except ImportError:
                                st.bar_chart(
                                    pd.DataFrame({
                                        "Período": [p["periodo_texto"] for p in periodos],
                                        "Sit. peor": [p["sit_peor"] for p in periodos],
                                    }).set_index("Período"),
                                    height=250,
                                )

                            # ── KPIs resumen ────────────────────────────────
                            st.markdown("<br>", unsafe_allow_html=True)
                            peor_global     = max(p["sit_peor"] for p in periodos) if periodos else 0
                            meses_fuera_s1  = sum(1 for p in periodos if p["sit_peor"] > 1)
                            monto_max       = max(p["total_monto"] for p in periodos) if periodos else 0

                            k1, k2, k3, k4 = st.columns(4)
                            for col, val, lbl, color in [
                                (k1, len(periodos),      "Meses",         "#1d1d1f"),
                                (k2, f"Sit. {peor_global}", "Peor situación", "#cc0000" if peor_global > 1 else "#1a7a1a"),
                                (k3, meses_fuera_s1,     "Meses fuera Sit.1", "#cc0000" if meses_fuera_s1 > 0 else "#1a7a1a"),
                                (k4, f"${monto_max:,.0f}","Deuda máxima",  "#1d1d1f"),
                            ]:
                                col.markdown(
                                    f'<div class="kpi"><div class="n" style="color:{color}">{val}</div>'
                                    f'<div class="l">{lbl}</div></div>',
                                    unsafe_allow_html=True,
                                )

                            # ── Tabla detalle por período ────────────────────
                            st.markdown("<br>", unsafe_allow_html=True)
                            st.markdown('<p class="sec-label">Detalle por período</p>',
                                        unsafe_allow_html=True)

                            filas_tabla = []
                            for p in reversed(periodos):  # más reciente primero
                                for ent in p["entidades"]:
                                    filas_tabla.append({
                                        "Período":  p["periodo_texto"],
                                        "Entidad":  ent["Entidad"],
                                        "Sit.":     ent["Situacion"],
                                        "Monto $":  ent["Monto"],
                                    })
                            if filas_tabla:
                                df_hist = pd.DataFrame(filas_tabla)
                                st.dataframe(df_hist, use_container_width=True,
                                             hide_index=True, height=320)

                                # Descargar Excel
                                buf = io.BytesIO()
                                df_hist.to_excel(buf, index=False)
                                fname = f"historico_{cuit_input}_{datetime.now().strftime('%Y%m%d')}"
                                st.download_button(
                                    "⬇ Descargar detalle Excel",
                                    data=buf.getvalue(),
                                    file_name=f"{fname}.xlsx",
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                    use_container_width=True,
                                )

                    # ── Registrar y cobrar la consulta ─────────────────────
                    registrar_evento_individual(
                        usuario_id=usuario_actual["id"],
                        cliente_id=usuario_actual["cliente_id"],
                        resultado_cat="HISTORICA",
                    )

        else:
            st.markdown("""
            <div style="text-align:center;padding:60px 20px;color:#86868b;">
                <div style="font-size:48px;margin-bottom:16px;">📊</div>
                <p style="font-size:16px;font-weight:500;color:#1d1d1f;margin:0 0 8px 0;">Ingresá un CUIT para ver su historial</p>
                <p style="font-size:14px;margin:0;">Vas a ver la evolución crediticia de los últimos 24 meses</p>
            </div>
            """, unsafe_allow_html=True)

    st.markdown(FOOTER_HTML, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# ROUTER
# ══════════════════════════════════════════════════════════════════════════════

_router = {
    "Consulta individual": pagina_individual,
    "Consulta histórica":  pagina_historica,
    "Carga masiva":        pagina_masiva,
    "Historial": pagina_historial,
    "Seguimiento mensual": lambda: render_seguimiento(usuario_actual),
    "Estado de cuenta ·": lambda: pagina_pronto(
        "Estado de cuenta",
        "💳",
        "Esta sección estará disponible próximamente. "
        "Podrás ver tu saldo, recargar y ver el historial de facturación."
    ),
    "Mi empresa":  lambda: render_setup(usuario_actual),
    "Back Office": lambda: render_admin(usuario_actual) if es_admin else pagina_individual(),
}

# Redirección a Mi empresa
if st.session_state.pop("_ir_a_setup", False):
    render_setup(usuario_actual)
    st.stop()

fn = _router.get(pagina)
if fn:
    fn()
else:
    pagina_individual()
