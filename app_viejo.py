import streamlit as st
import pandas as pd
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import io
import zipfile
from datetime import datetime
import time

# ── Configuración de página ──────────────────────────────────────────────────
st.set_page_config(
    page_title="Consulta BCRA",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ── Estilos ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');

html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif;
    background-color: #0f1117;
    color: #e8e8e8;
}

h1, h2, h3 { font-family: 'IBM Plex Mono', monospace; }

.header-box {
    background: linear-gradient(135deg, #1a1f2e 0%, #0f1117 100%);
    border: 1px solid #2a9d8f;
    border-radius: 8px;
    padding: 24px 32px;
    margin-bottom: 32px;
}

.header-box h1 {
    color: #2a9d8f;
    font-size: 1.8rem;
    margin: 0;
    letter-spacing: -0.5px;
}

.header-box p {
    color: #8a8a9a;
    margin: 6px 0 0 0;
    font-size: 0.9rem;
}

.panel {
    background: #1a1f2e;
    border: 1px solid #2a2f3e;
    border-radius: 8px;
    padding: 24px;
    height: 100%;
}

.panel-title {
    font-family: 'IBM Plex Mono', monospace;
    color: #2a9d8f;
    font-size: 0.85rem;
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-bottom: 20px;
    padding-bottom: 12px;
    border-bottom: 1px solid #2a2f3e;
}

.resultado-ok {
    background: #0d2b1f;
    border: 1px solid #2a9d8f;
    border-radius: 6px;
    padding: 12px 16px;
    color: #2a9d8f;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.85rem;
    margin: 8px 0;
}

.resultado-mal {
    background: #2b0d0d;
    border: 1px solid #e63946;
    border-radius: 6px;
    padding: 12px 16px;
    color: #e63946;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.85rem;
    margin: 8px 0;
}

.resultado-warn {
    background: #2b200d;
    border: 1px solid #e9c46a;
    border-radius: 6px;
    padding: 12px 16px;
    color: #e9c46a;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.85rem;
    margin: 8px 0;
}

.stat-box {
    background: #0f1117;
    border: 1px solid #2a2f3e;
    border-radius: 6px;
    padding: 16px;
    text-align: center;
}

.stat-number {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 1.8rem;
    font-weight: 600;
    color: #2a9d8f;
}

.stat-label {
    font-size: 0.75rem;
    color: #8a8a9a;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-top: 4px;
}

div[data-testid="stButton"] button {
    background: #2a9d8f !important;
    color: #0f1117 !important;
    border: none !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-weight: 600 !important;
    letter-spacing: 1px !important;
    border-radius: 4px !important;
    padding: 8px 20px !important;
}

div[data-testid="stButton"] button:hover {
    background: #21867a !important;
}

.stProgress > div > div {
    background-color: #2a9d8f !important;
}

.divider {
    border: none;
    border-top: 1px solid #2a2f3e;
    margin: 24px 0;
}

/* Ocultar menú hamburguesa */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ── Constantes ───────────────────────────────────────────────────────────────
BASE_URL = "https://api.bcra.gob.ar/centraldedeudores/v1.0/Deudas"
SITUACIONES_RIESGO = [2, 3, 4, 5]
SITUACION_NORMAL = 1

# ── Funciones BCRA ───────────────────────────────────────────────────────────
def consultar_bcra(cuit: str) -> dict:
    """Consulta la API del BCRA para un CUIT dado."""
    cuit_limpio = str(cuit).replace("-", "").replace(" ", "").strip()
    url = f"{BASE_URL}/{cuit_limpio}"
    try:
        resp = requests.get(url, timeout=15, verify=False)
        if resp.status_code == 200:
            return {"ok": True, "data": resp.json()}
        elif resp.status_code == 404:
            return {"ok": True, "data": None, "sin_deuda": True}
        else:
            return {"ok": False, "error": f"HTTP {resp.status_code}"}
    except requests.exceptions.Timeout:
        return {"ok": False, "error": "Timeout - API no responde"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def procesar_respuesta_bcra(data: dict, cuit: str, nombre: str = "", total_credito: float = None) -> dict:
    """Procesa la respuesta del BCRA y calcula situaciones."""
    if data is None:
        return {
            "CUIT": cuit, "Nombre": nombre,
            "Sin_Deuda": True,
            "Monto_Sit1": 0, "Monto_Riesgo": 0,
            "Ratio_Riesgo": 0.0, "Resultado_BCRA": "SIN DEUDA",
            "Total_Credito": total_credito,
            "Resultado_Con_Credito": "N/A",
            "Entidades": []
        }

    periodos = data.get("results", {}).get("periodos", [])
    if not periodos:
        return {
            "CUIT": cuit, "Nombre": nombre,
            "Sin_Deuda": True,
            "Monto_Sit1": 0, "Monto_Riesgo": 0,
            "Ratio_Riesgo": 0.0, "Resultado_BCRA": "SIN DEUDA",
            "Total_Credito": total_credito,
            "Resultado_Con_Credito": "N/A",
            "Entidades": []
        }

    # Tomar el período más reciente
    periodo = periodos[0]
    entidades = periodo.get("entidades", [])

    monto_sit1 = 0.0
    monto_riesgo = 0.0
    detalle_entidades = []

    for ent in entidades:
        sit = ent.get("situacion", 0)
        monto = float(ent.get("monto", 0) or 0)
        nombre_ent = ent.get("entidad", "Sin nombre")

        detalle_entidades.append({
            "Entidad": nombre_ent,
            "Situacion": sit,
            "Monto": monto,
            "Dias_Atraso": ent.get("diasAtrasoPago", 0),
        })

        if sit == SITUACION_NORMAL:
            monto_sit1 += monto
        elif sit in SITUACIONES_RIESGO:
            monto_riesgo += monto

    return {
        "CUIT": cuit,
        "Nombre": nombre,
        "Sin_Deuda": False,
        "Monto_Sit1": monto_sit1,
        "Monto_Riesgo": monto_riesgo,
        "Ratio_Riesgo": 0.0,
        "Resultado_BCRA": "",
        "Total_Credito": total_credito,
        "Resultado_Con_Credito": "N/A",
        "Entidades": detalle_entidades
    }


def calcular_pasa(monto_sit1: float, monto_riesgo: float, umbral: float) -> tuple:
    """Calcula si pasa o no pasa según el umbral."""
    total = monto_sit1 + monto_riesgo
    if total == 0:
        return 0.0, "PASA"
    ratio = monto_riesgo / total * 100
    resultado = "NO PASA" if ratio >= umbral else "PASA"
    return ratio, resultado


def calcular_pasa_con_credito(monto_sit1: float, monto_riesgo: float, credito: float, umbral: float) -> tuple:
    """Calcula pasa/no pasa sumando el crédito propio a situación 1."""
    monto_sit1_total = monto_sit1 + credito
    total = monto_sit1_total + monto_riesgo
    if total == 0:
        return 0.0, "PASA"
    ratio = monto_riesgo / total * 100
    resultado = "NO PASA" if ratio >= umbral else "PASA"
    return ratio, resultado


# ── Generación de reportes ───────────────────────────────────────────────────
def generar_excel(resultados: list, umbral: float) -> bytes:
    """Genera el archivo Excel con 3 hojas."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:

        # Hoja 1: Detalle por entidad
        rows_detalle = []
        for r in resultados:
            if r.get("error"):
                rows_detalle.append({
                    "CUIT": r["CUIT"], "Nombre": r.get("Nombre", ""),
                    "Entidad": "ERROR", "Situacion": "", "Monto": "",
                    "Dias_Atraso": r["error"]
                })
                continue
            for ent in r.get("Entidades", []):
                rows_detalle.append({
                    "CUIT": r["CUIT"], "Nombre": r.get("Nombre", ""),
                    "Entidad": ent["Entidad"],
                    "Situacion": ent["Situacion"],
                    "Monto": ent["Monto"],
                    "Dias_Atraso": ent["Dias_Atraso"]
                })
            if not r.get("Entidades"):
                rows_detalle.append({
                    "CUIT": r["CUIT"], "Nombre": r.get("Nombre", ""),
                    "Entidad": "SIN DEUDA REGISTRADA",
                    "Situacion": "", "Monto": 0, "Dias_Atraso": 0
                })

        df1 = pd.DataFrame(rows_detalle)
        df1.to_excel(writer, sheet_name="Detalle Entidades", index=False)

        # Hoja 2: Consolidado BCRA
        rows_consol = []
        for r in resultados:
            if r.get("error"):
                rows_consol.append({
                    "CUIT": r["CUIT"], "Nombre": r.get("Nombre", ""),
                    "Monto_Sit1": "", "Monto_Riesgo": "",
                    "Ratio_%": "", "Umbral_%": umbral,
                    "Resultado": "ERROR - " + r["error"]
                })
                continue
            ratio, resultado = calcular_pasa(r["Monto_Sit1"], r["Monto_Riesgo"], umbral)
            rows_consol.append({
                "CUIT": r["CUIT"], "Nombre": r.get("Nombre", ""),
                "Monto_Sit1": r["Monto_Sit1"],
                "Monto_Riesgo": r["Monto_Riesgo"],
                "Ratio_%": round(ratio, 2),
                "Umbral_%": umbral,
                "Resultado": resultado
            })
        df2 = pd.DataFrame(rows_consol)
        df2.to_excel(writer, sheet_name="Consolidado BCRA", index=False)

        # Hoja 3: Con crédito propio
        rows_cred = []
        for r in resultados:
            if r.get("error") or r.get("Total_Credito") is None:
                continue
            ratio_cc, resultado_cc = calcular_pasa_con_credito(
                r["Monto_Sit1"], r["Monto_Riesgo"], r["Total_Credito"], umbral
            )
            rows_cred.append({
                "CUIT": r["CUIT"], "Nombre": r.get("Nombre", ""),
                "Monto_Sit1_BCRA": r["Monto_Sit1"],
                "Credito_Propio": r["Total_Credito"],
                "Monto_Sit1_Total": r["Monto_Sit1"] + r["Total_Credito"],
                "Monto_Riesgo": r["Monto_Riesgo"],
                "Ratio_%_Con_Credito": round(ratio_cc, 2),
                "Umbral_%": umbral,
                "Resultado_Con_Credito": resultado_cc
            })
        if rows_cred:
            df3 = pd.DataFrame(rows_cred)
            df3.to_excel(writer, sheet_name="Con Credito Propio", index=False)

    return output.getvalue()


def generar_pdf_simple(resultados: list, umbral: float) -> bytes:
    """Genera un PDF simple con resumen de resultados."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.enums import TA_CENTER

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                                rightMargin=2*cm, leftMargin=2*cm,
                                topMargin=2*cm, bottomMargin=2*cm)

        styles = getSampleStyleSheet()
        story = []

        # Título
        title_style = ParagraphStyle('Title', parent=styles['Title'],
                                     fontSize=16, textColor=colors.HexColor('#2a9d8f'),
                                     spaceAfter=6)
        story.append(Paragraph("Reporte Consolidado BCRA", title_style))
        story.append(Paragraph(f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')} | Umbral: {umbral}%",
                               styles['Normal']))
        story.append(Spacer(1, 0.5*cm))

        # Tabla resumen
        data = [["CUIT", "Nombre", "Monto Sit.1", "Monto Riesgo", "Ratio %", "Resultado"]]
        for r in resultados:
            if r.get("error"):
                data.append([r["CUIT"], r.get("Nombre",""), "ERROR", "", "", r["error"]])
                continue
            ratio, resultado = calcular_pasa(r["Monto_Sit1"], r["Monto_Riesgo"], umbral)
            data.append([
                str(r["CUIT"]),
                str(r.get("Nombre", ""))[:30],
                f"${r['Monto_Sit1']:,.0f}",
                f"${r['Monto_Riesgo']:,.0f}",
                f"{ratio:.1f}%",
                resultado
            ])

        table = Table(data, colWidths=[3*cm, 4.5*cm, 3*cm, 3*cm, 2*cm, 2.5*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2a9d8f')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f5f5f5')]),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cccccc')),
            ('ALIGN', (2,1), (-1,-1), 'RIGHT'),
        ]))

        # Color rojo para NO PASA
        for i, r in enumerate(resultados, 1):
            if not r.get("error"):
                _, resultado = calcular_pasa(r["Monto_Sit1"], r["Monto_Riesgo"], umbral)
                if resultado == "NO PASA":
                    table.setStyle(TableStyle([
                        ('TEXTCOLOR', (5,i), (5,i), colors.HexColor('#e63946')),
                        ('FONTNAME', (5,i), (5,i), 'Helvetica-Bold'),
                    ]))

        story.append(table)
        doc.build(story)
        return buffer.getvalue()

    except ImportError:
        # Si no tiene reportlab, devuelve un PDF mínimo con mensaje
        return b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 595 842]/Parent 2 0 R/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj 4 0 obj<</Length 44>>stream\nBT /F1 12 Tf 100 700 Td (Instale reportlab: pip install reportlab) Tj ET\nendstream\nendobj 5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\nxref\n0 6\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\n0000000274 00000 n\n0000000370 00000 n\ntrailer<</Size 6/Root 1 0 R>>\nstartxref\n441\n%%EOF"


# ── INTERFAZ PRINCIPAL ───────────────────────────────────────────────────────

st.markdown("""
<div class="header-box">
    <h1>🏦 Sistema de Consulta BCRA</h1>
    <p>Central de Deudores del Sistema Financiero — Consulta individual y masiva</p>
</div>
""", unsafe_allow_html=True)

# Dos columnas principales
col_masivo, col_sep, col_individual = st.columns([10, 1, 6])

# ════════════════════════════════════════════════════════════════════════════
# PANEL IZQUIERDO — PROCESAMIENTO MASIVO
# ════════════════════════════════════════════════════════════════════════════
with col_masivo:
    st.markdown('<div class="panel-title">◈ PROCESAMIENTO MASIVO — ARCHIVO EXCEL</div>', unsafe_allow_html=True)

    # Upload
    archivo = st.file_uploader(
        "Cargar archivo Excel",
        type=["xlsx", "xls"],
        help="Columnas requeridas: CUIT. Opcionales: Nombre, TOTAL"
    )

    if archivo:
        try:
            df_input = pd.read_excel(archivo)
            df_input.columns = [c.strip().upper() for c in df_input.columns]

            if "CUIT" not in df_input.columns:
                st.error("❌ El archivo no tiene columna CUIT")
            else:
                st.success(f"✅ Archivo cargado: {len(df_input)} registros")

                # Vista previa
                with st.expander("Vista previa del archivo"):
                    st.dataframe(df_input.head(10), use_container_width=True)

                st.markdown('<hr class="divider">', unsafe_allow_html=True)

                # Parámetros
                c1, c2 = st.columns(2)
                with c1:
                    umbral = st.number_input(
                        "Umbral de riesgo (%)",
                        min_value=1, max_value=100, value=40,
                        help="Si el ratio deuda en riesgo / deuda total supera este %, no pasa"
                    )
                with c2:
                    tiene_total = "TOTAL" in df_input.columns
                    incluir_credito = st.checkbox(
                        "Incluir crédito propio",
                        value=tiene_total,
                        disabled=not tiene_total,
                        help="Requiere columna TOTAL en el Excel"
                    )

                if not tiene_total:
                    st.caption("💡 Para activar crédito propio, agregá columna TOTAL en el Excel")

                st.markdown('<hr class="divider">', unsafe_allow_html=True)

                # Botón procesar
                if st.button("⚡ PROCESAR ARCHIVO", use_container_width=True):
                    resultados = []
                    total = len(df_input)
                    progress = st.progress(0)
                    status = st.empty()

                    for i, row in df_input.iterrows():
                        cuit = str(row["CUIT"]).strip()
                        nombre = str(row.get("NOMBRE", "")).strip() if "NOMBRE" in df_input.columns else ""
                        total_credito = float(row["TOTAL"]) if (tiene_total and incluir_credito and pd.notna(row.get("TOTAL"))) else None

                        status.markdown(f"Consultando **{cuit}** ({i+1}/{total})...")

                        resp = consultar_bcra(cuit)
                        if resp["ok"]:
                            data_bcra = resp.get("data")
                            resultado = procesar_respuesta_bcra(
                                data_bcra.get("results") if data_bcra else None,
                                cuit, nombre, total_credito
                            )
                            # Recalcular data correctamente
                            if data_bcra:
                                resultado = procesar_respuesta_bcra(data_bcra, cuit, nombre, total_credito)
                            resultados.append(resultado)
                        else:
                            resultados.append({
                                "CUIT": cuit, "Nombre": nombre,
                                "error": resp["error"],
                                "Total_Credito": total_credito
                            })

                        progress.progress((i + 1) / total)
                        time.sleep(0.3)  # Evitar saturar la API

                    status.empty()
                    progress.empty()
                    st.session_state["resultados"] = resultados
                    st.session_state["umbral"] = umbral
                    st.success(f"✅ Procesados {total} registros")

        except Exception as e:
            st.error(f"Error al leer el archivo: {e}")

    # ── Mostrar resultados si existen ────────────────────────────────────────
    if "resultados" in st.session_state:
        resultados = st.session_state["resultados"]
        umbral_guardado = st.session_state["umbral"]

        st.markdown('<hr class="divider">', unsafe_allow_html=True)
        st.markdown('<div class="panel-title">◈ RESULTADOS</div>', unsafe_allow_html=True)

        # Estadísticas
        pasan = sum(1 for r in resultados if not r.get("error") and
                    calcular_pasa(r["Monto_Sit1"], r["Monto_Riesgo"], umbral_guardado)[1] == "PASA")
        no_pasan = sum(1 for r in resultados if not r.get("error") and
                       calcular_pasa(r["Monto_Sit1"], r["Monto_Riesgo"], umbral_guardado)[1] == "NO PASA")
        errores = sum(1 for r in resultados if r.get("error"))

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f'<div class="stat-box"><div class="stat-number">{len(resultados)}</div><div class="stat-label">Total</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="stat-box"><div class="stat-number" style="color:#2a9d8f">{pasan}</div><div class="stat-label">Pasan</div></div>', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div class="stat-box"><div class="stat-number" style="color:#e63946">{no_pasan}</div><div class="stat-label">No pasan</div></div>', unsafe_allow_html=True)
        with c4:
            st.markdown(f'<div class="stat-box"><div class="stat-number" style="color:#e9c46a">{errores}</div><div class="stat-label">Errores</div></div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Lista de resultados
        for r in resultados:
            if r.get("error"):
                st.markdown(f'<div class="resultado-warn">⚠ {r["CUIT"]} {r.get("Nombre","")} — {r["error"]}</div>', unsafe_allow_html=True)
                continue
            ratio, resultado = calcular_pasa(r["Monto_Sit1"], r["Monto_Riesgo"], umbral_guardado)
            nombre_str = f" | {r['Nombre']}" if r.get('Nombre') else ""
            monto_str = f"Sit.1: ${r['Monto_Sit1']:,.0f} | Riesgo: ${r['Monto_Riesgo']:,.0f} | Ratio: {ratio:.1f}%"
            css_class = "resultado-ok" if resultado == "PASA" else "resultado-mal"
            icono = "✔" if resultado == "PASA" else "✘"
            st.markdown(
                f'<div class="{css_class}">{icono} {r["CUIT"]}{nombre_str} — {resultado}<br><small>{monto_str}</small></div>',
                unsafe_allow_html=True
            )

        st.markdown('<hr class="divider">', unsafe_allow_html=True)

        # Descargas
        st.markdown('<div class="panel-title">◈ DESCARGAR REPORTES</div>', unsafe_allow_html=True)
        dc1, dc2 = st.columns(2)

        with dc1:
            excel_bytes = generar_excel(resultados, umbral_guardado)
            st.download_button(
                "📥 Descargar Excel (3 hojas)",
                data=excel_bytes,
                file_name=f"reporte_bcra_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        with dc2:
            pdf_bytes = generar_pdf_simple(resultados, umbral_guardado)
            st.download_button(
                "📥 Descargar PDF",
                data=pdf_bytes,
                file_name=f"reporte_bcra_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )

# Separador visual
with col_sep:
    st.markdown("<br>" * 8, unsafe_allow_html=True)
    st.markdown('<div style="border-left: 1px solid #2a2f3e; height: 600px; margin: auto;"></div>', unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# PANEL DERECHO — CONSULTA INDIVIDUAL
# ════════════════════════════════════════════════════════════════════════════
with col_individual:
    st.markdown('<div class="panel-title">◈ CONSULTA INDIVIDUAL</div>', unsafe_allow_html=True)

    cuit_input = st.text_input(
        "Ingresar CUIT / CUIL / CDI",
        placeholder="Ej: 20123456789",
        max_chars=13
    )

    umbral_ind = st.number_input(
        "Umbral (%)", min_value=1, max_value=100, value=40,
        key="umbral_individual"
    )

    if st.button("🔍 CONSULTAR", use_container_width=True):
        if not cuit_input.strip():
            st.warning("Ingresá un CUIT válido")
        else:
            with st.spinner("Consultando API BCRA..."):
                resp = consultar_bcra(cuit_input)

            if not resp["ok"]:
                st.error(f"Error: {resp['error']}")
            else:
                data_bcra = resp.get("data")
                resultado = procesar_respuesta_bcra(data_bcra, cuit_input)

                ratio, res_texto = calcular_pasa(resultado["Monto_Sit1"], resultado["Monto_Riesgo"], umbral_ind)

                # Badge resultado
                if resultado.get("Sin_Deuda"):
                    st.markdown('<div class="resultado-ok">✔ SIN DEUDA REGISTRADA EN BCRA</div>', unsafe_allow_html=True)
                elif res_texto == "PASA":
                    st.markdown(f'<div class="resultado-ok">✔ PASA — Ratio de riesgo: {ratio:.1f}%</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="resultado-mal">✘ NO PASA — Ratio de riesgo: {ratio:.1f}%</div>', unsafe_allow_html=True)

                # Métricas
                if not resultado.get("Sin_Deuda"):
                    m1, m2 = st.columns(2)
                    m1.metric("Deuda Sit. 1 (normal)", f"${resultado['Monto_Sit1']:,.0f}")
                    m2.metric("Deuda en riesgo (2-5)", f"${resultado['Monto_Riesgo']:,.0f}")

                # Detalle por entidad
                if resultado.get("Entidades"):
                    st.markdown("<br>**Detalle por entidad:**", unsafe_allow_html=True)
                    df_ent = pd.DataFrame(resultado["Entidades"])
                    df_ent.columns = ["Entidad", "Sit.", "Monto $", "Días atraso"]
                    st.dataframe(df_ent, use_container_width=True, hide_index=True)

                    # Descarga individual
                    buf = io.BytesIO()
                    df_ent.to_excel(buf, index=False)
                    st.download_button(
                        "📥 Descargar Excel",
                        data=buf.getvalue(),
                        file_name=f"bcra_{cuit_input}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )

# ── Footer ───────────────────────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
st.markdown(
    '<div style="text-align:center; color:#3a3f4e; font-size:0.75rem; font-family:IBM Plex Mono,monospace;">'
    'BCRA Central de Deudores API v1.0 — Solo uso interno — Los datos son confidenciales'
    '</div>',
    unsafe_allow_html=True
)
