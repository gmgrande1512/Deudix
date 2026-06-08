"""
admin.py — Back Office Deudix
Los reportes muestran métricas operacionales (cantidades, costos, fechas).
No se expone ningún dato de las personas consultadas.
"""
import streamlit as st
import pandas as pd
import io
from datetime import datetime
from database import (
    listar_clientes, listar_usuarios, crear_cliente, crear_usuario,
    actualizar_precio_cliente, actualizar_perfil_cliente, actualizar_logo_cliente,
    get_cliente, get_resumen_mes, get_eventos_periodo,
    get_actividad_diaria, get_top_clientes, get_conn,
    listar_aceptaciones_tyc, TYC_VERSION,
    listar_usuarios_pendientes, aprobar_usuario,
)

import io as _io

def _logo_valido(logo_bytes) -> bool:
    if not logo_bytes or len(logo_bytes) < 16:
        return False
    try:
        from PIL import Image
        Image.open(_io.BytesIO(logo_bytes)).verify()
        return True
    except Exception:
        return False

def render_admin(usuario_actual):

    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600;9..40,700&display=swap');
    html, body, [class*="css"] { font-family:'DM Sans',sans-serif !important; background:#f5f5f7 !important; color:#1d1d1f !important; }
    .stApp { background:#f5f5f7 !important; }

    div[data-testid="stTabs"] { background:#ffffff; border-radius:16px; padding:0 24px; border:0.5px solid #e5e5ea; }
    div[data-testid="stTabs"] button { font-size:14px !important; font-weight:500 !important; color:#86868b !important; border:none !important; background:transparent !important; padding:16px 4px !important; margin-right:24px !important; }
    div[data-testid="stTabs"] button[aria-selected="true"] { color:#1d1d1f !important; border-bottom:2px solid #1d1d1f !important; font-weight:600 !important; }

    .bo-card { background:#ffffff; border-radius:16px; padding:24px 28px; border:0.5px solid #e5e5ea; margin-bottom:16px; }
    .bo-section { font-size:11px; font-weight:600; letter-spacing:0.08em; text-transform:uppercase; color:#86868b; margin-bottom:16px; padding-bottom:12px; border-bottom:0.5px solid #f0f0f0; }

    .kpi-grid { display:flex; gap:12px; margin-bottom:24px; }
    .kpi-item { flex:1; background:#ffffff; border-radius:14px; padding:20px; border:0.5px solid #e5e5ea; text-align:center; }
    .kpi-val  { font-size:2rem; font-weight:700; letter-spacing:-0.04em; color:#1d1d1f; line-height:1; }
    .kpi-lbl  { font-size:11px; font-weight:500; color:#86868b; text-transform:uppercase; letter-spacing:0.06em; margin-top:6px; }
    .kpi-sub  { font-size:12px; color:#aeaeb2; margin-top:4px; }

    .section-divider { border:none; border-top:0.5px solid #e5e5ea; margin:20px 0; }

    div[data-testid="stDataFrame"] { border-radius:12px !important; overflow:hidden !important; }
    div[data-testid="stDataFrame"] table { font-size:13px !important; }

    div[data-testid="stTextInput"] input,
    div[data-testid="stNumberInput"] input,
    div[data-testid="stTextArea"] textarea {
        background:#f5f5f7 !important; border:none !important; border-radius:10px !important;
        color:#1d1d1f !important; font-size:14px !important; padding:10px 14px !important;
    }
    div[data-testid="stTextInput"] label,
    div[data-testid="stNumberInput"] label,
    div[data-testid="stSelectbox"] label,
    div[data-testid="stTextArea"] label { color:#1d1d1f !important; font-size:13px !important; font-weight:500 !important; }
    div[data-baseweb="select"] > div { background:#f5f5f7 !important; border:none !important; border-radius:10px !important; color:#1d1d1f !important; }
    div[data-baseweb="select"] * { color:#1d1d1f !important; }

    div[data-testid="stButton"] button[kind="primary"]    { background:#1d1d1f !important; color:#ffffff !important; font-weight:600 !important; font-size:14px !important; border:none !important; border-radius:980px !important; padding:10px 20px !important; }
    div[data-testid="stButton"] button[kind="primary"]:hover { background:#3a3a3c !important; }
    div[data-testid="stButton"] button[kind="secondary"]  { background:transparent !important; color:#1d1d1f !important; font-weight:500 !important; border:0.5px solid #c7c7cc !important; border-radius:980px !important; }
    div[data-testid="stDownloadButton"] button { background:#0066cc !important; color:#ffffff !important; font-weight:600 !important; border:none !important; border-radius:980px !important; font-size:14px !important; }
    div[data-testid="stFormSubmitButton"] button { background:#1d1d1f !important; color:#ffffff !important; font-weight:600 !important; border:none !important; border-radius:980px !important; width:100% !important; }

    div[data-testid="stMetric"] { background:#ffffff; border-radius:12px; padding:16px !important; border:0.5px solid #e5e5ea; }
    div[data-testid="stMetric"] label { color:#86868b !important; font-size:12px !important; }
    div[data-testid="stMetricValue"] { color:#1d1d1f !important; font-weight:600 !important; }
    div[data-testid="stAlert"] { border-radius:12px !important; border:none !important; }
    div[data-testid="stSelectbox"] div { color:#1d1d1f !important; }
    </style>
    """, unsafe_allow_html=True)

    # ── Header ────────────────────────────────────────────────────────────────
    h1, h2 = st.columns([6, 2])
    with h1:
        st.markdown('<p style="font-size:28px;font-weight:700;color:#1d1d1f;letter-spacing:-0.03em;margin:0;padding-top:8px;">Back Office</p>', unsafe_allow_html=True)
        st.markdown(f'<p style="font-size:14px;color:#86868b;margin-bottom:24px;">Bienvenido, {usuario_actual["nombre"]}</p>', unsafe_allow_html=True)
    with h2:
        st.markdown(f'<p style="font-size:13px;color:#86868b;text-align:right;padding-top:16px;">{datetime.now().strftime("%d %b %Y · %H:%M")}</p>', unsafe_allow_html=True)

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Dashboard", "Clientes", "Usuarios", "Reportes", "TyC / Aceptaciones", "Pendientes de aprobación"])

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 1 — DASHBOARD
    # ══════════════════════════════════════════════════════════════════════════
    with tab1:
        now     = datetime.now()
        periodo = f"{now.year}-{now.month:02d}"
        mes_txt = now.strftime("%B %Y").capitalize()
        res     = get_resumen_mes(anio=now.year, mes=now.month)

        conn        = get_conn()
        cl_activos  = conn.execute("SELECT COUNT(*) FROM clientes WHERE activo=1").fetchone()[0]
        us_activos  = conn.execute("SELECT COUNT(*) FROM usuarios WHERE activo=1").fetchone()[0]
        conn.close()

        st.markdown(f'<p style="font-size:11px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:#86868b;margin-bottom:12px;">{mes_txt}</p>', unsafe_allow_html=True)

        # Fila 1 — métricas globales
        k1, k2, k3, k4 = st.columns(4)
        for col, val, lbl, sub, color in [
            (k1, res["total_consultas"],          "Consultas",   "este mes",  "#1d1d1f"),
            (k2, f"${res['total_costo']:,.2f}",   "A facturar",  "este mes",  "#0066cc"),
            (k3, cl_activos,                      "Clientes",    "activos",   "#1d1d1f"),
            (k4, us_activos,                      "Usuarios",    "activos",   "#1d1d1f"),
        ]:
            col.markdown(f'<div class="kpi-item"><div class="kpi-val" style="color:{color}">{val}</div><div class="kpi-lbl">{lbl}</div><div class="kpi-sub">{sub}</div></div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Fila 2 — desglose consultas individuales
        st.markdown('<p style="font-size:11px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:#86868b;margin-bottom:12px;">Consultas individuales</p>', unsafe_allow_html=True)
        k5, k6, k7, k8, k9 = st.columns(5)
        for col, val, lbl, color in [
            (k5, res["ind_total"],    "Total",     "#1d1d1f"),
            (k6, res["ind_pasan"],    "Pasan",     "#1a7a1a"),
            (k7, res["ind_no_pasan"], "No pasan",  "#cc0000"),
            (k8, res["ind_sin_deuda"],"Sin deuda", "#0066cc"),
            (k9, res["ind_errores"],  "Errores",   "#86868b"),
        ]:
            col.markdown(f'<div class="kpi-item"><div class="kpi-val" style="color:{color}">{val}</div><div class="kpi-lbl">{lbl}</div><div class="kpi-sub">este mes</div></div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Fila 3 — desglose corridas masivas
        st.markdown('<p style="font-size:11px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:#86868b;margin-bottom:12px;">Corridas masivas</p>', unsafe_allow_html=True)
        m1, m2, m3, m4, m5, m6 = st.columns(6)
        for col, val, lbl, color in [
            (m1, res["mas_corridas"],  "Corridas",  "#1d1d1f"),
            (m2, res["mas_casos"],     "Casos",     "#1d1d1f"),
            (m3, res["mas_pasan"],     "Pasan",     "#1a7a1a"),
            (m4, res["mas_no_pasan"],  "No pasan",  "#cc0000"),
            (m5, res["mas_sin_deuda"], "Sin deuda", "#0066cc"),
            (m6, res["mas_errores"],   "Errores",   "#86868b"),
        ]:
            col.markdown(f'<div class="kpi-item"><div class="kpi-val" style="color:{color}">{val}</div><div class="kpi-lbl">{lbl}</div><div class="kpi-sub">este mes</div></div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Top clientes + gráfico actividad
        col_top, col_act = st.columns([3, 2])

        with col_top:
            st.markdown('<div class="bo-card">', unsafe_allow_html=True)
            st.markdown('<p class="bo-section">Top clientes por volumen</p>', unsafe_allow_html=True)
            top = get_top_clientes(periodo)
            if top:
                df_top = pd.DataFrame(top)
                df_top.columns = ["Cliente", "Consultas", "A facturar $"]
                df_top["A facturar $"] = df_top["A facturar $"].apply(lambda x: f"${x:,.2f}")
                st.dataframe(df_top, use_container_width=True, hide_index=True, height=280)
            else:
                st.markdown('<p style="color:#86868b;font-size:14px;text-align:center;padding:40px 0;">Sin actividad este mes</p>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with col_act:
            st.markdown('<div class="bo-card">', unsafe_allow_html=True)
            st.markdown('<p class="bo-section">Actividad últimos 7 días</p>', unsafe_allow_html=True)
            act = get_actividad_diaria(7)
            if act:
                df_act = pd.DataFrame(act)
                df_act.columns = ["Día", "Consultas"]
                st.bar_chart(df_act.set_index("Día"), height=240)
            else:
                st.markdown('<p style="color:#86868b;font-size:14px;text-align:center;padding:40px 0;">Sin actividad reciente</p>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 2 — CLIENTES
    # ══════════════════════════════════════════════════════════════════════════
    with tab2:

        # ── Lista y precio ─────────────────────────────────────────────────────
        with st.container(border=False):
            st.markdown('<div class="bo-card">', unsafe_allow_html=True)
            st.markdown('<p class="bo-section">Clientes registrados</p>', unsafe_allow_html=True)
            clientes = listar_clientes()
            if clientes:
                df_cl = pd.DataFrame(clientes)[["id","nombre","email","email_empresa","precio_consulta","activo","fecha_alta"]]
                df_cl.columns = ["ID","Nombre","Email admin","Email empresa","$/consulta","Activo","Alta"]
                st.dataframe(df_cl, use_container_width=True, hide_index=True, height=220)
            st.markdown('</div>', unsafe_allow_html=True)

        col_edit, col_new_cl = st.columns([3, 2])

        with col_edit:
            st.markdown('<div class="bo-card">', unsafe_allow_html=True)
            st.markdown('<p class="bo-section">Editar cliente</p>', unsafe_allow_html=True)
            clientes   = listar_clientes()
            cl_opts    = {c["nombre"]: c["id"] for c in clientes}
            cl_sel     = st.selectbox("Seleccioná cliente:", list(cl_opts.keys()), key="cl_edit_sel")
            cl_id_sel  = cl_opts[cl_sel]
            cl_data    = get_cliente(cl_id_sel)

            sub1, sub2 = st.tabs(["Precio · Perfil", "Logo"])

            with sub1:
                e1, e2 = st.columns(2)
                with e1:
                    v_nombre   = st.text_input("Nombre comercial",  value=cl_data.get("nombre",""), key="ae_nombre")
                    v_cuit     = st.text_input("CUIT empresa",       value=cl_data.get("cuit_empresa","") or "", key="ae_cuit")
                    v_dom      = st.text_input("Domicilio",          value=cl_data.get("domicilio","") or "", key="ae_dom")
                    v_ciudad   = st.text_input("Ciudad",             value=cl_data.get("ciudad","") or "", key="ae_ciudad")
                    v_prov     = st.text_input("Provincia",          value=cl_data.get("provincia","") or "", key="ae_prov")
                with e2:
                    precio_act = float(cl_data.get("precio_consulta", 0))
                    v_precio   = st.number_input("Precio por consulta ($)", min_value=0.0, step=50.0,
                                                  value=precio_act, key="ae_precio")
                    v_tel      = st.text_input("Teléfono",           value=cl_data.get("telefono","") or "", key="ae_tel")
                    v_web      = st.text_input("Web",                value=cl_data.get("web","") or "", key="ae_web")
                    v_email_a  = st.text_input("Email administrativo", value=cl_data.get("email","") or "", key="ae_email_a")
                    v_email_e  = st.text_input("Email empresa",      value=cl_data.get("email_empresa","") or "", key="ae_email_e")
                    v_notas    = st.text_area("Notas", value=cl_data.get("notas","") or "", height=68, key="ae_notas")

                if st.button("Guardar cambios", type="primary", key="btn_save_cl"):
                    actualizar_perfil_cliente(cl_id_sel, {
                        "nombre": v_nombre, "cuit_empresa": v_cuit,
                        "domicilio": v_dom, "ciudad": v_ciudad, "provincia": v_prov,
                        "precio_consulta": v_precio, "telefono": v_tel, "web": v_web,
                        "email": v_email_a, "email_empresa": v_email_e, "notas": v_notas,
                    })
                    st.success(f"✅ Cliente actualizado")
                    st.rerun()

            with sub2:
                logo_actual = cl_data.get("logo_bytes")
                if _logo_valido(logo_actual):
                    st.image(logo_actual, caption="Logo actual", width=180)
                else:
                    st.info("Sin logo cargado")
                logo_up = st.file_uploader("Subir logo (PNG/JPG — máx 2MB)", type=["png","jpg","jpeg"], key="admin_logo_up")
                if logo_up:
                    if logo_up.size > 2 * 1024 * 1024:
                        st.error("Máx 2MB")
                    else:
                        actualizar_logo_cliente(cl_id_sel, logo_up.read())
                        st.success("✅ Logo actualizado")
                        st.rerun()
                if _logo_valido(logo_actual):
                    if st.button("Eliminar logo", key="btn_del_logo_admin"):
                        actualizar_logo_cliente(cl_id_sel, None)
                        st.rerun()

            st.markdown('</div>', unsafe_allow_html=True)

        with col_new_cl:
            st.markdown('<div class="bo-card">', unsafe_allow_html=True)
            st.markdown('<p class="bo-section">Nuevo cliente</p>', unsafe_allow_html=True)
            with st.form("form_cliente"):
                nc_nombre  = st.text_input("Nombre empresa *")
                nc_email_a = st.text_input("Email administrativo *")
                nc_email_e = st.text_input("Email público empresa")
                nc_cuit    = st.text_input("CUIT empresa")
                nc_dom     = st.text_input("Domicilio")
                nc_ciudad  = st.text_input("Ciudad")
                nc_prov    = st.text_input("Provincia")
                nc_tel     = st.text_input("Teléfono")
                nc_web     = st.text_input("Web")
                nc_precio  = st.number_input("Precio por consulta ($)", min_value=0.0, step=50.0)
                nc_notas   = st.text_area("Notas", height=60)
                if st.form_submit_button("Crear cliente", use_container_width=True):
                    if not nc_nombre or not nc_email_a:
                        st.error("Nombre y email son obligatorios")
                    else:
                        ok, msg = crear_cliente(
                            nc_nombre, nc_email_a, nc_precio, nc_notas,
                            nc_email_e, "", nc_cuit,
                            nc_dom, nc_ciudad, nc_prov, nc_tel, nc_web,
                        )
                        st.success(f"✅ {msg}") if ok else st.error(f"❌ {msg}")
                        if ok: st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 3 — USUARIOS
    # ══════════════════════════════════════════════════════════════════════════
    with tab3:
        col_us, col_new_us = st.columns([3, 2])

        with col_us:
            st.markdown('<div class="bo-card">', unsafe_allow_html=True)
            st.markdown('<p class="bo-section">Usuarios registrados</p>', unsafe_allow_html=True)
            usuarios = listar_usuarios()
            if usuarios:
                df_u = pd.DataFrame(usuarios)[["id","nombre","email","rol","cliente_nombre","activo","ultimo_acceso"]]
                df_u.columns = ["ID","Nombre","Email","Rol","Cliente","Activo","Último acceso"]
                st.dataframe(df_u, use_container_width=True, hide_index=True, height=350)
            else:
                st.info("Sin usuarios registrados")
            st.markdown('</div>', unsafe_allow_html=True)

        with col_new_us:
            st.markdown('<div class="bo-card">', unsafe_allow_html=True)
            st.markdown('<p class="bo-section">Nuevo usuario</p>', unsafe_allow_html=True)
            clientes = listar_clientes()
            cl_map   = {c["nombre"]: c["id"] for c in clientes}
            with st.form("form_usuario"):
                nu_nombre  = st.text_input("Nombre completo")
                nu_email   = st.text_input("Email (usuario)")
                nu_pass    = st.text_input("Contraseña", type="password")
                nu_pass2   = st.text_input("Confirmar contraseña", type="password")
                nu_cliente = st.selectbox("Cliente", list(cl_map.keys()))
                nu_rol     = st.selectbox("Rol", ["user", "admin"])
                if st.form_submit_button("Crear usuario", use_container_width=True):
                    if not all([nu_nombre, nu_email, nu_pass]):
                        st.error("Todos los campos son obligatorios")
                    elif nu_pass != nu_pass2:
                        st.error("Las contraseñas no coinciden")
                    elif len(nu_pass) < 6:
                        st.error("Mínimo 6 caracteres")
                    else:
                        ok, msg = crear_usuario(nu_nombre, nu_email.lower(), nu_pass,
                                                cl_map[nu_cliente], nu_rol)
                        st.success(f"✅ {msg}") if ok else st.error(f"❌ {msg}")
                        if ok: st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 4 — REPORTES
    # ══════════════════════════════════════════════════════════════════════════
    with tab4:

        # Filtros
        st.markdown('<div class="bo-card">', unsafe_allow_html=True)
        st.markdown('<p class="bo-section">Filtros</p>', unsafe_allow_html=True)
        f1, f2, f3 = st.columns(3)
        with f1:
            clientes  = listar_clientes()
            cl_opts2  = {"Todos los clientes": None}
            cl_opts2.update({c["nombre"]: c["id"] for c in clientes})
            cl_filtro = st.selectbox("Cliente", list(cl_opts2.keys()), key="rep_cl")
        with f2:
            anio_sel  = st.selectbox("Año", list(range(datetime.now().year, datetime.now().year - 3, -1)), key="rep_anio")
        with f3:
            meses     = {"Enero":1,"Febrero":2,"Marzo":3,"Abril":4,"Mayo":5,"Junio":6,
                         "Julio":7,"Agosto":8,"Septiembre":9,"Octubre":10,"Noviembre":11,"Diciembre":12}
            mes_sel_n = st.selectbox("Mes", list(meses.keys()), index=datetime.now().month - 1, key="rep_mes")
            mes_sel   = meses[mes_sel_n]
        st.markdown('</div>', unsafe_allow_html=True)

        cliente_id_filtro = cl_opts2[cl_filtro]
        res = get_resumen_mes(cliente_id=cliente_id_filtro, anio=anio_sel, mes=mes_sel)

        # KPIs del período
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f'<p style="font-size:11px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:#86868b;margin-bottom:12px;">Resumen — {mes_sel_n} {anio_sel}</p>', unsafe_allow_html=True)

        r1, r2, r3, r4 = st.columns(4)
        for col, val, lbl, color in [
            (r1, res["total_consultas"],        "Total casos",  "#1d1d1f"),
            (r2, f"${res['total_costo']:,.2f}", "A facturar",   "#0066cc"),
            (r3, res["mas_corridas"],           "Corridas batch","#1d1d1f"),
            (r4, res["ind_total"],              "Individuales",  "#1d1d1f"),
        ]:
            col.markdown(f'<div class="kpi-item"><div class="kpi-val" style="color:{color}">{val}</div><div class="kpi-lbl">{lbl}</div></div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Detalle del período
        eventos = get_eventos_periodo(cliente_id=cliente_id_filtro, anio=anio_sel, mes=mes_sel)

        # ── Corridas masivas ──────────────────────────────────────────────────
        st.markdown('<div class="bo-card">', unsafe_allow_html=True)
        masivos = eventos["masivos"]
        st.markdown(f'<p class="bo-section">Corridas masivas — {len(masivos)} eventos</p>', unsafe_allow_html=True)

        if masivos:
            df_mas = pd.DataFrame(masivos)
            df_mas = df_mas[["fecha_hora","cliente","usuario","total_casos",
                             "pasan","no_pasan","sin_deuda","errores","costo_total","umbral_usado"]]
            df_mas.columns = ["Fecha","Cliente","Usuario","Casos","Pasan",
                               "No pasan","Sin deuda","Errores","Costo $","Umbral %"]
            df_mas["Costo $"] = df_mas["Costo $"].apply(lambda x: f"${x:,.2f}")
            st.dataframe(df_mas, use_container_width=True, hide_index=True, height=280)
        else:
            st.markdown(f'<p style="color:#86868b;font-size:14px;text-align:center;padding:24px 0;">Sin corridas masivas en {mes_sel_n} {anio_sel}</p>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # ── Consultas individuales ────────────────────────────────────────────
        st.markdown('<div class="bo-card">', unsafe_allow_html=True)
        individuales = eventos["individuales"]
        st.markdown(f'<p class="bo-section">Consultas individuales — {len(individuales)} eventos</p>', unsafe_allow_html=True)

        if individuales:
            df_ind = pd.DataFrame(individuales)
            df_ind = df_ind[["fecha_hora","cliente","usuario","resultado_cat","costo"]]
            df_ind.columns = ["Fecha","Cliente","Usuario","Resultado","Costo $"]
            df_ind["Costo $"] = df_ind["Costo $"].apply(lambda x: f"${x:,.2f}")
            st.dataframe(df_ind, use_container_width=True, hide_index=True, height=280)
        else:
            st.markdown(f'<p style="color:#86868b;font-size:14px;text-align:center;padding:24px 0;">Sin consultas individuales en {mes_sel_n} {anio_sel}</p>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # ── Exportar Excel de facturación ─────────────────────────────────────
        hay_datos = masivos or individuales
        if hay_datos:
            st.markdown('<div class="bo-card">', unsafe_allow_html=True)
            st.markdown('<p class="bo-section">Exportar facturación</p>', unsafe_allow_html=True)

            ex1, ex2, ex3 = st.columns([2, 1, 1])

            with ex1:
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine="openpyxl") as writer:

                    # Hoja resumen
                    resumen_rows = [{
                        "Período":           f"{mes_sel_n} {anio_sel}",
                        "Total casos":       res["total_consultas"],
                        "Individuales":      res["ind_total"],
                        "Corridas batch":    res["mas_corridas"],
                        "Casos en batch":    res["mas_casos"],
                        "Pasan (total)":     res["ind_pasan"]    + res["mas_pasan"],
                        "No pasan (total)":  res["ind_no_pasan"] + res["mas_no_pasan"],
                        "Sin deuda (total)": res["ind_sin_deuda"]+ res["mas_sin_deuda"],
                        "Errores (total)":   res["ind_errores"]  + res["mas_errores"],
                        "Total a facturar":  res["total_costo"],
                    }]
                    pd.DataFrame(resumen_rows).to_excel(writer, sheet_name="Resumen", index=False)

                    # Hoja masivas
                    if masivos:
                        df_exp_mas = pd.DataFrame(masivos)[
                            ["fecha_hora","cliente","usuario","total_casos",
                             "pasan","no_pasan","sin_deuda","errores","costo_total","precio_unitario","umbral_usado"]
                        ]
                        df_exp_mas.columns = ["Fecha","Cliente","Usuario","Casos","Pasan",
                                              "No pasan","Sin deuda","Errores","Costo $","Precio unit.","Umbral %"]
                        df_exp_mas.to_excel(writer, sheet_name="Corridas masivas", index=False)

                    # Hoja individuales
                    if individuales:
                        df_exp_ind = pd.DataFrame(individuales)[
                            ["fecha_hora","cliente","usuario","resultado_cat","costo","precio_unitario"]
                        ]
                        df_exp_ind.columns = ["Fecha","Cliente","Usuario","Resultado","Costo $","Precio unit."]
                        df_exp_ind.to_excel(writer, sheet_name="Individuales", index=False)

                    # Hoja por cliente (si es vista global)
                    if not cliente_id_filtro:
                        rows_cl = []
                        for c in clientes:
                            r_cl = get_resumen_mes(cliente_id=c["id"], anio=anio_sel, mes=mes_sel)
                            if r_cl["total_consultas"] > 0:
                                rows_cl.append({
                                    "Cliente":        c["nombre"],
                                    "Total casos":    r_cl["total_consultas"],
                                    "Corridas batch": r_cl["mas_corridas"],
                                    "Individuales":   r_cl["ind_total"],
                                    "Pasan":          r_cl["ind_pasan"]    + r_cl["mas_pasan"],
                                    "No pasan":       r_cl["ind_no_pasan"] + r_cl["mas_no_pasan"],
                                    "Total $":        r_cl["total_costo"],
                                })
                        if rows_cl:
                            pd.DataFrame(rows_cl).to_excel(writer, sheet_name="Por cliente", index=False)

                st.download_button(
                    f"Exportar Excel — {mes_sel_n} {anio_sel}",
                    data=buf.getvalue(),
                    file_name=f"facturacion_{anio_sel}_{mes_sel:02d}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

            with ex2:
                st.metric("Total casos", res["total_consultas"])
            with ex3:
                st.metric("Total a facturar", f"${res['total_costo']:,.2f}")

            st.markdown('</div>', unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 5 — TyC / ACEPTACIONES
    # ══════════════════════════════════════════════════════════════════════════
    with tab5:
        st.markdown('<div class="bo-card">', unsafe_allow_html=True)
        st.markdown(f'<p class="bo-section">Estado de aceptación — versión vigente: {TYC_VERSION}</p>', unsafe_allow_html=True)

        aceptaciones = listar_aceptaciones_tyc()

        if aceptaciones:
            total      = len(aceptaciones)
            aceptaron  = sum(1 for a in aceptaciones if a["acepto"])
            pendientes = total - aceptaron

            k1, k2, k3 = st.columns(3)
            for col, val, lbl, color in [
                (k1, total,      "Usuarios totales", "#1d1d1f"),
                (k2, aceptaron,  "Aceptaron TyC",    "#1a7a1a"),
                (k3, pendientes, "Pendientes",        "#cc6600"),
            ]:
                col.markdown(
                    f'<div class="kpi-item"><div class="kpi-val" style="color:{color}">{val}</div>'
                    f'<div class="kpi-lbl">{lbl}</div></div>',
                    unsafe_allow_html=True,
                )

            st.markdown("<br>", unsafe_allow_html=True)

            filas = []
            for a in aceptaciones:
                filas.append({
                    "Usuario":          a["usuario"],
                    "Email":            a["email"],
                    "Cliente":          a["cliente"] or "—",
                    "Estado":           "✅ Aceptó" if a["acepto"] else "⚠️ Pendiente",
                    "Fecha aceptación": a["fecha_aceptacion"] or "—",
                    "Versión TyC":      a["tyc_version"]      or "—",
                    "IP (hash)":        a["ip_hash"]          or "—",
                    "Navegador":        (a["user_agent"] or "—")[:60],
                })
            df_tyc = pd.DataFrame(filas)
            st.dataframe(df_tyc, use_container_width=True, hide_index=True, height=400)

            # Exportar
            st.markdown("<br>", unsafe_allow_html=True)
            buf_tyc = io.BytesIO()
            df_tyc_full = pd.DataFrame([{
                "Usuario":          a["usuario"],
                "Email":            a["email"],
                "Cliente":          a["cliente"] or "",
                "Alta usuario":     a["fecha_alta"] or "",
                "Acepto TyC":       "SI" if a["acepto"] else "NO",
                "Fecha aceptacion": a["fecha_aceptacion"] or "",
                "Version TyC":      a["tyc_version"]      or "",
                "Hash version":     a["tyc_hash"]         or "",
                "IP hash":          a["ip_hash"]          or "",
                "Navegador":        a["user_agent"]       or "",
            } for a in aceptaciones])
            df_tyc_full.to_excel(buf_tyc, index=False)
            st.download_button(
                "Exportar registro de aceptaciones",
                data=buf_tyc.getvalue(),
                file_name=f"tyc_aceptaciones_{TYC_VERSION}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=False,
            )
        else:
            st.info("No hay usuarios registrados aún.")

        st.markdown('</div>', unsafe_allow_html=True)

        # Texto completo de los TyC para referencia
        st.markdown('<div class="bo-card">', unsafe_allow_html=True)
        st.markdown(f'<p class="bo-section">Texto vigente — {TYC_VERSION}</p>', unsafe_allow_html=True)
        st.markdown("""
> **Fuente de la información:** Los datos presentados en esta plataforma provienen de la Central de Deudores del Sistema Financiero del BCRA y de boletines oficiales y judiciales de acceso público.
>
> **Naturaleza de los datos:** La información publicada por el BCRA y los boletines es de carácter público y se difunde en cumplimiento de la normativa vigente. El BCRA no certifica ni avala el uso que terceros hagan de estos datos.
>
> **Uso del sistema:** Esta plataforma procesa, organiza y presenta la información en distintos formatos con el objetivo de facilitar su consulta y análisis. El servicio agrega valor mediante procesamiento, visualización y generación de reportes, pero no altera el contenido sustancial de los datos.
>
> **Limitaciones:** La información aquí expuesta no constituye certificación oficial ni reemplaza la consulta directa a las fuentes originales. El sistema no garantiza la exhaustividad ni la actualización inmediata de los datos. Los derechos de rectificación o supresión deben ejercerse ante la entidad financiera o el organismo que originó la información.
>
> **Protección de datos personales:** El uso de esta plataforma se ajusta a la Ley 25.326. Los datos provienen de fuentes públicas y se utilizan exclusivamente con fines legítimos de evaluación crediticia y análisis de antecedentes financieros.
        """)
        st.markdown('</div>', unsafe_allow_html=True)


    # ══════════════════════════════════════════════════════════════════════════
    # TAB 6 — PENDIENTES DE APROBACION
    # ══════════════════════════════════════════════════════════════════════════
    with tab6:
        pendientes = listar_usuarios_pendientes()

        if not pendientes:
            st.markdown(
                '<div style="text-align:center;padding:60px 20px;">'
                '<p style="font-size:40px;">✅</p>'
                '<p style="font-size:16px;font-weight:600;color:#1d1d1f;margin:0 0 6px 0;">'
                'Sin solicitudes pendientes</p>'
                '<p style="font-size:14px;color:#86868b;margin:0;">'
                'Todas las cuentas están aprobadas</p></div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<p style="font-size:11px;font-weight:600;letter-spacing:0.08em;'
                f'text-transform:uppercase;color:#cc6600;margin-bottom:12px;">'
                f'⚠ {len(pendientes)} solicitudes esperando aprobación</p>',
                unsafe_allow_html=True,
            )
            for p in pendientes:
                with st.container(border=True):
                    pc1, pc2, pc3 = st.columns([4, 3, 2])
                    with pc1:
                        st.markdown(
                            f'<p style="font-size:14px;font-weight:700;color:#1d1d1f;margin:0;">'
                            f'{p["cliente_nombre"] or "—"}</p>'
                            f'<p style="font-size:12px;color:#86868b;margin:2px 0 0 0;">'
                            f'CUIT: {p.get("cuit_empresa") or "—"}</p>',
                            unsafe_allow_html=True,
                        )
                    with pc2:
                        st.markdown(
                            f'<p style="font-size:13px;color:#1d1d1f;margin:0;">'
                            f'{p["nombre"]}</p>'
                            f'<p style="font-size:12px;color:#86868b;margin:2px 0 0 0;">'
                            f'{p["email"]}</p>'
                            f'<p style="font-size:11px;color:#aeaeb2;margin:2px 0 0 0;">'
                            f'Solicitó: {(p.get("fecha_alta") or "")[:10]}</p>',
                            unsafe_allow_html=True,
                        )
                    with pc3:
                        if st.button(
                            "Aprobar y dar 100 consultas",
                            key=f"apr_{p['id']}",
                            type="primary",
                            use_container_width=True,
                        ):
                            ok = aprobar_usuario(
                                p["id"],
                                usuario_actual["id"],
                                credito_consultas=100,
                            )
                            if ok:
                                st.success(
                                    f"✅ {p['nombre']} aprobado con 100 consultas de crédito"
                                )
                                st.rerun()
                            else:
                                st.error("Error al aprobar")
                        if st.button(
                            "Rechazar",
                            key=f"rej_{p['id']}",
                            use_container_width=True,
                        ):
                            from database import get_conn as _gc
                            _c = _gc()
                            _c.execute(
                                "UPDATE usuarios SET activo=0 WHERE id=?",
                                (p["id"],)
                            )
                            _c.commit(); _c.close()
                            st.rerun()


    # ── Aviso legal ───────────────────────────────────────────────────────────
    st.markdown("""
    <div style="margin-top:32px;padding:16px 24px;border-top:0.5px solid #e5e5ea;text-align:center;">
      <p style="color:#86868b;font-size:10px;margin:0;line-height:1.6;max-width:900px;display:inline-block;">
        <strong style="color:#1d1d1f;">Aviso:</strong>
        Los datos provienen de fuentes públicas (BCRA y boletines oficiales).
        Nuestro sistema agrega valor mediante procesamiento y presentación, pero no modifica la información.
        El BCRA no avala ni certifica este servicio.
      </p>
    </div>""", unsafe_allow_html=True)
