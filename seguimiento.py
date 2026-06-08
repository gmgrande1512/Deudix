"""
seguimiento.py — Seguimiento mensual de CUITs/CUILs vigilados.
El usuario registra CUITs, el sistema los consulta mensualmente y
muestra si la situación crediticia cambió respecto al mes anterior.
"""
import streamlit as st
import pandas as pd
import io
import time
from datetime import datetime

from database import (
    agregar_vigilado, agregar_vigilados_masivo, listar_vigilados,
    desactivar_vigilado, get_historial_vigilado, registrar_resultado_seguimiento,
    get_resumen_seguimiento, get_precio_cliente, consumir_saldo, tiene_saldo,
    get_saldo, guardar_reporte_seguimiento, listar_reportes_seguimiento,
    get_pdf_seguimiento, get_cliente, actualizar_umbral_vigilado,
)
from reportes import generar_pdf_seguimiento
from bcra import consultar_bcra, procesar_respuesta, normalizar_columnas

# ── Helpers visuales ──────────────────────────────────────────────────────────

VAR_COLOR = {
    "SUBE":       "#cc0000",
    "BAJA":       "#1a7a1a",
    "SIN_CAMBIO": "#86868b",
    "NUEVO":      "#0066cc",
    "ERROR":      "#cc6600",
}
VAR_LABEL = {
    "SUBE":       "↑ Sube",
    "BAJA":       "↓ Baja",
    "SIN_CAMBIO": "= Sin cambio",
    "NUEVO":      "★ Nuevo",
    "ERROR":      "✕ Error",
}


def _badge(variacion: str) -> str:
    color = VAR_COLOR.get(variacion, "#86868b")
    label = VAR_LABEL.get(variacion, variacion)
    return (
        f'<span style="background:{color}18;color:{color};'
        f'font-size:11px;font-weight:600;padding:2px 10px;'
        f'border-radius:4px;">{label}</span>'
    )


def _ejecutar_seguimiento(vigilados: list, cliente_id: int,
                           usuario_id: int, precio: float) -> list:
    """
    Procesa todos los vigilados activos:
    consulta BCRA, calcula variación, guarda en historial, descuenta saldo.
    Retorna lista de resultados con variación.
    """
    resultados = []
    total      = len(vigilados)
    prog_bar   = st.progress(0)
    prog_txt   = st.empty()
    log_box    = st.empty()
    log_msgs   = []

    for idx, v in enumerate(vigilados):
        if st.session_state.get("seg_cancelar"):
            log_msgs.append(
                f'<span style="color:#ff9500">[{datetime.now().strftime("%H:%M:%S")}] '
                f'Cancelado en {idx+1}/{total}</span>'
            )
            break

        cuit = v["cuit"]
        hora = datetime.now().strftime("%H:%M:%S")
        prog_txt.markdown(
            f'<p style="text-align:center;color:#86868b;font-size:13px;margin:6px 0;">'
            f'Procesando {idx+1} de {total} · {cuit}</p>',
            unsafe_allow_html=True,
        )

        # Verificar saldo antes de cada consulta
        if not tiene_saldo(cliente_id, 1):
            log_msgs.append(
                f'<span style="color:#ff453a">[{hora}] SALDO INSUFICIENTE — '
                f'se detuvo en {idx+1}/{total}</span>'
            )
            st.warning("Saldo insuficiente. Recargá para continuar el seguimiento.")
            break

        resp = consultar_bcra(cuit)
        if resp["ok"]:
            r = procesar_respuesta(resp.get("data"), cuit,
                                   v.get("alias",""), None)
            variacion = registrar_resultado_seguimiento(
                v["id"], cliente_id, usuario_id, r, precio
            )
            consumir_saldo(cliente_id, usuario_id, 1,
                           f"Seguimiento mensual — {cuit}")
            estado = "sin deuda" if r.get("Sin_Deuda") else "con deuda"
            color  = VAR_COLOR.get(variacion, "#86868b")
            log_msgs.append(
                f'<span style="color:#f5f5f7">[{hora}] {cuit} · {estado} · '
                f'<span style="color:{color};">{VAR_LABEL.get(variacion, variacion)}</span></span>'
            )
            resultados.append({**v, "variacion": variacion, "resultado": r, "error": None})
        else:
            registrar_resultado_seguimiento(
                v["id"], cliente_id, usuario_id,
                {"error": resp["error"]}, 0
            )
            log_msgs.append(
                f'<span style="color:#ff453a">[{hora}] error · {cuit} · '
                f'{resp["error"][:50]}</span>'
            )
            resultados.append({**v, "variacion": "ERROR", "resultado": None,
                                "error": resp["error"]})

        log_box.markdown(
            f'<div class="log"><div class="logh">'
            f'seguimiento mensual — {idx+1}/{total}</div>'
            f'{"<br>".join(log_msgs[-20:])}</div>',
            unsafe_allow_html=True,
        )
        prog_bar.progress((idx + 1) / total)
        time.sleep(1.5)  # respetar rate limit BCRA

    prog_txt.empty()
    return resultados


# ── Página principal ──────────────────────────────────────────────────────────

def render_seguimiento(usuario_actual: dict):
    cliente_id = usuario_actual.get("cliente_id")
    usuario_id = usuario_actual.get("id")
    precio     = get_precio_cliente(cliente_id) or 0.35
    saldo_act  = get_saldo(cliente_id)

    st.markdown('<p class="page-title">Seguimiento mensual</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="page-sub">Monitoreá la evolución crediticia de CUITs mes a mes</p>',
        unsafe_allow_html=True,
    )

    # ── Resumen ───────────────────────────────────────────────────────────────
    resumen = get_resumen_seguimiento(cliente_id)
    with st.container(border=True):
        st.markdown('<p class="sec-label">Estado del seguimiento</p>',
                    unsafe_allow_html=True)
        k1, k2, k3, k4, k5, k6 = st.columns(6)
        for col, val, lbl, color in [
            (k1, resumen["total"],      "Vigilados",   "#1d1d1f"),
            (k2, resumen["SIN_CAMBIO"], "Sin cambio",  "#86868b"),
            (k3, resumen["SUBE"],       "Subieron",    "#cc0000"),
            (k4, resumen["BAJA"],       "Bajaron",     "#1a7a1a"),
            (k5, resumen["NUEVO"],      "Nuevos",      "#0066cc"),
            (k6, resumen["ERROR"],      "Errores",     "#cc6600"),
        ]:
            col.markdown(
                f'<div class="kpi"><div class="n" style="color:{color}">{val}</div>'
                f'<div class="l">{lbl}</div></div>',
                unsafe_allow_html=True,
            )

    tab1, tab2, tab3, tab4 = st.tabs(["Lista y ejecución", "Agregar CUITs", "Historial detallado", "Reportes guardados"])

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 1 — LISTA + EJECUTAR SEGUIMIENTO
    # ══════════════════════════════════════════════════════════════════════════
    with tab1:
        vigilados = listar_vigilados(cliente_id)

        if not vigilados:
            st.markdown(
                '<div style="text-align:center;padding:60px 20px;color:#86868b;">'
                '<div style="font-size:40px;margin-bottom:12px;">👁</div>'
                '<p style="font-size:16px;font-weight:500;color:#1d1d1f;margin:0 0 6px 0;">'
                'No hay CUITs en seguimiento</p>'
                '<p style="font-size:14px;margin:0;">Agregá CUITs en la pestaña "Agregar CUITs"</p>'
                '</div>',
                unsafe_allow_html=True,
            )
        else:
            # ── Card por CUIT con línea de tiempo 12 meses ────────────────────
            from datetime import datetime as _dt

            # Últimos 12 periodos "YYYYMM"
            _hoy   = _dt.now()
            _meses = []
            for _d in range(11, -1, -1):
                _m = _hoy.month - _d
                _a = _hoy.year
                while _m <= 0:
                    _m += 12; _a -= 1
                _meses.append(f"{_a}{_m:02d}")
            _meses_cortos = {
                "01":"Ene","02":"Feb","03":"Mar","04":"Abr",
                "05":"May","06":"Jun","07":"Jul","08":"Ago",
                "09":"Sep","10":"Oct","11":"Nov","12":"Dic",
            }
            _VAR_ICONO = {
                "SUBE":       ("↑", "#cc0000", "#fff0f0"),
                "BAJA":       ("↓", "#1a7a1a", "#f0faf0"),
                "SIN_CAMBIO": ("=", "#86868b", "#f5f5f7"),
                "NUEVO":      ("★", "#0066cc", "#f0f6ff"),
                "ERROR":      ("✕", "#cc6600", "#fff8f0"),
            }

            # ── Buscador ──────────────────────────────────────────────────────
            _sb1, _sb2 = st.columns([4, 8])
            with _sb1:
                _busqueda = st.text_input(
                    "Buscar",
                    placeholder="Nombre o CUIT...",
                    key="seg_buscar",
                    label_visibility="collapsed",
                )
            with _sb2:
                st.markdown(
                    f'<p style="font-size:13px;color:#86868b;padding-top:10px;">'
                    f'{len(vigilados)} CUITs en seguimiento</p>',
                    unsafe_allow_html=True,
                )

            # Filtrar según búsqueda
            _busq = (_busqueda or "").strip().lower()
            _vigilados_filtrados = [
                v for v in vigilados
                if not _busq
                or _busq in (v.get("alias") or "").lower()
                or _busq in v.get("cuit","").lower()
            ]

            if _busq and not _vigilados_filtrados:
                st.info(f"No se encontró ningún CUIT que coincida con '{_busqueda}'")

            for v in _vigilados_filtrados:
                # Cargar historial completo del vigilado
                _hist = get_historial_vigilado(v["id"], limite=24)
                # Indexar por periodo BCRA
                _hist_idx = {}
                for _h in _hist:
                    _per = (_h.get("periodo_bcra") or "").strip()
                    if _per and _per not in _hist_idx:
                        _hist_idx[_per] = _h

                _sit1_act   = v.get("ultimo_sit1")   or 0
                _riesgo_act = v.get("ultimo_riesgo")  or 0
                _var_act    = v.get("ultima_variacion") or ("NUEVO" if not _hist else "SIN_CAMBIO")

                # ── Card compacta: 2 líneas por cliente ───────────────────
                _umbral_v   = float(v.get("umbral_pct") or 40.0)
                _ultimo_per = v.get("ultimo_periodo") or ""
                _total_act  = _sit1_act + _riesgo_act
                _pasa_act   = None if _total_act == 0 else (_riesgo_act / _total_act * 100) < _umbral_v
                _ico, _col_ico, _bg_ico = _VAR_ICONO.get(_var_act, ("?","#86868b","#f5f5f7"))

                # Etiqueta "Último: Mes YYYY" o montos
                if _total_act > 0:
                    _per_lbl = ""
                    if _ultimo_per and len(_ultimo_per) >= 6:
                        _per_lbl = f"{_meses_cortos.get(_ultimo_per[4:6],'')} {_ultimo_per[:4]}"
                    _badge_txt = "PASA" if _pasa_act else "NO PASA"
                    _badge_col = "#1a7a1a" if _pasa_act else "#cc0000"
                    _badge_bg  = "#f0faf0" if _pasa_act else "#fff0f0"
                    _resumen = (
                        f'<span style="background:{_badge_bg};color:{_badge_col};'
                        f'font-size:10px;font-weight:700;padding:1px 6px;border-radius:4px;'
                        f'margin-right:8px;">{_badge_txt}</span>'
                        f'<span style="font-size:11px;color:#86868b;">'
                        f'N: ${_sit1_act:,.0f} · R: ${_riesgo_act:,.0f} · T: ${_total_act:,.0f}'
                        + (f' · {_per_lbl}' if _per_lbl else '') + '</span>'
                    )
                else:
                    _resumen = '<span style="font-size:11px;color:#0066cc;">Sin deuda registrada</span>'

                # LÍNEA 1: ícono variación | nombre | resumen | umbral | quitar
                _l1a, _l1b, _l1c, _l1d = st.columns([5, 5, 1.2, 0.8])
                with _l1a:
                    st.markdown(
                        f'<div style="display:flex;align-items:center;gap:8px;padding:4px 0;">'
                        f'<div style="width:26px;height:26px;background:{_bg_ico};border-radius:6px;'
                        f'display:flex;align-items:center;justify-content:center;'
                        f'font-size:14px;font-weight:700;color:{_col_ico};flex-shrink:0;">{_ico}</div>'
                        f'<div>'
                        f'<span style="font-size:13px;font-weight:700;color:#1d1d1f;">'
                        f'{v.get("alias") or v["cuit"]}</span>'
                        f'<span style="font-size:10px;color:#aeaeb2;margin-left:6px;'
                        f'font-family:monospace;">{v["cuit"]}</span>'
                        f'</div></div>',
                        unsafe_allow_html=True,
                    )
                with _l1b:
                    st.markdown(
                        f'<div style="padding:6px 0;">{_resumen}</div>',
                        unsafe_allow_html=True,
                    )
                with _l1c:
                    _nuevo_umbral = st.number_input(
                        f"Umbral {v['id']}",
                        min_value=1, max_value=100,
                        value=int(_umbral_v),
                        key=f"umb_{v['id']}",
                        label_visibility="collapsed",
                        help="Umbral % pasa/no pasa",
                    )
                    if _nuevo_umbral != int(_umbral_v):
                        actualizar_umbral_vigilado(v["id"], cliente_id, float(_nuevo_umbral))
                        st.rerun()
                with _l1d:
                    if st.button("✕", key=f"del_{v['id']}",
                                 use_container_width=True, help="Quitar del seguimiento"):
                        desactivar_vigilado(v["id"], cliente_id)
                        st.rerun()

                # LÍNEA 2: 12 cuadraditos de meses
                _cols_meses = st.columns(12)
                for _ci, (_col_m, _per) in enumerate(zip(_cols_meses, _meses)):
                    _mes_txt   = _meses_cortos.get(_per[4:6], _per[4:6])
                    _anio      = _per[:4][2:]
                    _dato      = _hist_idx.get(_per)
                    _es_ultimo = (_ci == 11)

                    if _dato:
                        _var     = _dato.get("variacion") or "SIN_CAMBIO"
                        _s1      = _dato.get("monto_sit1")  or 0
                        _rg      = _dato.get("monto_riesgo") or 0
                        _sin_d   = _dato.get("sin_deuda")   or 0
                        _total_m = _s1 + _rg
                        _ico_m   = {"SUBE":"↑","BAJA":"↓","SIN_CAMBIO":"=",
                                    "NUEVO":"★","ERROR":"✕"}.get(_var, "?")

                        # Color = pasa/no pasa (no la variación)
                        if _sin_d or _total_m == 0:
                            _col_c = "#86868b"; _bg_c = "#f5f5f7"; _brd = "#d2d2d7"
                            _lbl   = "s/d"
                        else:
                            _ratio_m = _rg / _total_m * 100
                            if _ratio_m < _umbral_v:
                                _col_c = "#1a7a1a"; _bg_c = "#f0faf0"; _brd = "#1a7a1a"
                            else:
                                _col_c = "#cc0000"; _bg_c = "#fff0f0"; _brd = "#cc0000"
                            # Monto abreviado: K si > 999
                            _lbl = f"${_total_m/1000:.0f}K" if _total_m >= 1000 else f"${_total_m:.0f}"

                        # Borde: último mes = color del estado, resto = gris fino
                        _bw = "1.5px" if _es_ultimo else "0.5px"
                        _bc = _brd   if _es_ultimo else "#e5e5ea"

                        _col_m.markdown(
                            f'<div style="text-align:center;margin-bottom:4px;">'
                            f'<p style="font-size:9px;color:#aeaeb2;margin:0 0 2px 0;'
                            f'font-weight:600;">{_mes_txt} {_anio}</p>'
                            f'<div style="background:{_bg_c};border-radius:5px;'
                            f'padding:4px 1px;border:{_bw} solid {_bc};">'
                            f'<p style="font-size:13px;font-weight:700;color:{_col_c};'
                            f'margin:0;line-height:1;">{_ico_m}</p>'
                            f'<p style="font-size:8px;font-weight:700;color:{_col_c};'
                            f'margin:2px 0 0 0;white-space:nowrap;overflow:hidden;">'
                            f'{_lbl}</p>'
                            f'</div></div>',
                            unsafe_allow_html=True,
                        )
                    else:
                        _col_m.markdown(
                            f'<div style="text-align:center;margin-bottom:4px;">'
                            f'<p style="font-size:9px;color:#e5e5ea;margin:0 0 2px 0;'
                            f'font-weight:600;">{_mes_txt} {_anio}</p>'
                            f'<div style="background:#fafafa;border-radius:5px;'
                            f'padding:4px 1px;border:0.5px solid #f0f0f0;">'
                            f'<p style="font-size:13px;color:#e5e5ea;margin:0;line-height:1;">·</p>'
                            f'<p style="font-size:8px;color:#e5e5ea;margin:2px 0 0 0;">—</p>'
                            f'</div></div>',
                            unsafe_allow_html=True,
                        )
                st.markdown('<hr style="border:none;border-top:0.5px solid #f0f0f0;margin:4px 0 8px 0;">', unsafe_allow_html=True)

            # Botones de ejecución
            st.markdown("<br>", unsafe_allow_html=True)
            equiv_disp = int(saldo_act / precio) if precio > 0 else 0
            st.markdown(
                f'<p style="font-size:13px;color:#86868b;margin-bottom:12px;">'
                f'Saldo disponible: <strong style="color:#1d1d1f;">'
                f'USD {saldo_act:.2f}</strong> (~{equiv_disp} consultas) · '
                f'Costo de este seguimiento: '
                f'<strong style="color:#0066cc;">'
                f'USD {len(vigilados) * precio:.2f}</strong> '
                f'({len(vigilados)} CUITs × USD {precio:.4f})</p>',
                unsafe_allow_html=True,
            )

            bc1, bc2, _ = st.columns([3, 2, 5])
            with bc1:
                puede_ejecutar = (equiv_disp >= len(vigilados) and
                                  not st.session_state.get("seg_corriendo", False))
                if st.button(
                    "Ejecutar seguimiento mensual",
                    type="primary", use_container_width=True,
                    key="btn_ejecutar_seg",
                    disabled=not puede_ejecutar,
                ):
                    if equiv_disp < len(vigilados):
                        st.error(
                            f"Saldo insuficiente. Necesitás USD "
                            f"{len(vigilados)*precio:.2f} y tenés USD {saldo_act:.2f}."
                        )
                    else:
                        st.session_state["seg_corriendo"] = True
                        st.session_state["seg_cancelar"]  = False

            with bc2:
                if st.button("Cancelar", key="btn_cancel_seg",
                             use_container_width=True,
                             disabled=not st.session_state.get("seg_corriendo", False)):
                    st.session_state["seg_cancelar"] = True

            if not puede_ejecutar and equiv_disp < len(vigilados):
                st.error(
                    f"Saldo insuficiente para ejecutar el seguimiento completo. "
                    f"Necesitás USD {len(vigilados)*precio:.2f} — "
                    f"recargá en Estado de cuenta."
                )

            # Ejecutar
            if st.session_state.get("seg_corriendo"):
                st.markdown('<hr style="border:none;border-top:0.5px solid #e5e5ea;margin:16px 0;">',
                            unsafe_allow_html=True)
                resultados = _ejecutar_seguimiento(
                    vigilados, cliente_id, usuario_id, precio
                )
                st.session_state["seg_corriendo"]   = False
                st.session_state["seg_resultados"]  = resultados
                st.session_state["seg_fecha"]       = datetime.now().strftime("%d/%m/%Y %H:%M")

                # Generar y guardar PDF mensual
                stats_pdf = {
                    "total":      len(resultados),
                    "SUBE":       sum(1 for r in resultados if r.get("variacion")=="SUBE"),
                    "BAJA":       sum(1 for r in resultados if r.get("variacion")=="BAJA"),
                    "SIN_CAMBIO": sum(1 for r in resultados if r.get("variacion")=="SIN_CAMBIO"),
                    "ERROR":      sum(1 for r in resultados if r.get("variacion")=="ERROR"),
                }
                periodo_actual = datetime.now().strftime("%Y-%m")
                try:
                    empresa_d = get_cliente(cliente_id)
                    pdf_bytes = generar_pdf_seguimiento(resultados, empresa_d, periodo_actual)
                    if pdf_bytes:
                        guardar_reporte_seguimiento(
                            cliente_id, usuario_id,
                            periodo_actual, stats_pdf, pdf_bytes
                        )
                        st.session_state["seg_pdf_bytes"] = pdf_bytes
                except Exception as _e:
                    st.warning(f"PDF no generado: {_e}")

                st.rerun()

            # Resultados del último seguimiento
            if "seg_resultados" in st.session_state:
                res_list = st.session_state["seg_resultados"]
                fecha_ej = st.session_state.get("seg_fecha", "")
                st.markdown('<hr style="border:none;border-top:0.5px solid #e5e5ea;margin:16px 0;">',
                            unsafe_allow_html=True)
                with st.container(border=True):
                    st.markdown(
                        f'<p class="sec-label">Resultado del seguimiento · {fecha_ej}</p>',
                        unsafe_allow_html=True,
                    )
                    sube       = sum(1 for r in res_list if r.get("variacion") == "SUBE")
                    baja       = sum(1 for r in res_list if r.get("variacion") == "BAJA")
                    sin_cambio = sum(1 for r in res_list if r.get("variacion") == "SIN_CAMBIO")
                    errores    = sum(1 for r in res_list if r.get("variacion") == "ERROR")

                    rc1, rc2, rc3, rc4 = st.columns(4)
                    for col, val, lbl, color in [
                        (rc1, sube,       "Subieron",   "#cc0000"),
                        (rc2, baja,       "Bajaron",    "#1a7a1a"),
                        (rc3, sin_cambio, "Sin cambio", "#86868b"),
                        (rc4, errores,    "Errores",    "#cc6600"),
                    ]:
                        col.markdown(
                            f'<div class="kpi"><div class="n" style="color:{color}">{val}</div>'
                            f'<div class="l">{lbl}</div></div>',
                            unsafe_allow_html=True,
                        )

                    # Solo mostrar los que cambiaron
                    cambios = [r for r in res_list
                               if r.get("variacion") in ("SUBE", "BAJA", "ERROR")]
                    if cambios:
                        st.markdown("<br>", unsafe_allow_html=True)
                        st.markdown(
                            '<p class="sec-label">CUITs con variación</p>',
                            unsafe_allow_html=True,
                        )
                        for r in cambios:
                            resultado = r.get("resultado") or {}
                            var       = r.get("variacion", "")
                            st.markdown(
                                f'<div style="display:flex;justify-content:space-between;'
                                f'align-items:center;padding:8px 0;'
                                f'border-bottom:0.5px solid #f5f5f7;">'
                                f'<div>'
                                f'<span style="font-size:13px;font-weight:600;color:#1d1d1f;">'
                                f'{r.get("alias") or r["cuit"]}</span> '
                                f'<span style="font-size:11px;color:#86868b;">{r["cuit"]}</span>'
                                f'</div>'
                                f'<div style="text-align:right;">'
                                f'{_badge(var)}'
                                + (
                                    f'<br><span style="font-size:11px;color:#86868b;">'
                                    f'Normal: ${resultado.get("Monto_Sit1",0):,.0f} · '
                                    f'Riesgo: ${resultado.get("Monto_Riesgo",0):,.0f}</span>'
                                    if not r.get("error") else
                                    f'<br><span style="font-size:11px;color:#cc6600;">'
                                    f'{r.get("error","")[:60]}</span>'
                                ) +
                                f'</div></div>',
                                unsafe_allow_html=True,
                            )

                    # Descargar PDF del seguimiento
                    pdf_bytes_seg = st.session_state.get("seg_pdf_bytes")
                    if pdf_bytes_seg:
                        st.download_button(
                            "Descargar PDF del seguimiento",
                            data=pdf_bytes_seg,
                            file_name=f"seguimiento_{datetime.now().strftime('%Y%m')}.pdf",
                            mime="application/pdf",
                        )

                    # Exportar Excel del resultado
                    st.markdown("<br>", unsafe_allow_html=True)
                    rows_exp = []
                    for r in res_list:
                        res = r.get("resultado") or {}
                        rows_exp.append({
                            "CUIT":      r["cuit"],
                            "Alias":     r.get("alias",""),
                            "Variacion": VAR_LABEL.get(r.get("variacion",""), ""),
                            "Deuda Normal $": res.get("Monto_Sit1", 0),
                            "Deuda Riesgo $": res.get("Monto_Riesgo", 0),
                            "Período":   res.get("Periodo",""),
                            "Error":     r.get("error",""),
                        })
                    buf = io.BytesIO()
                    pd.DataFrame(rows_exp).to_excel(buf, index=False)
                    st.download_button(
                        "Exportar resultado Excel",
                        data=buf.getvalue(),
                        file_name=f"seguimiento_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 2 — AGREGAR CUITs
    # ══════════════════════════════════════════════════════════════════════════
    with tab2:
        col_ind, col_mas = st.columns([1, 1])

        with col_ind:
            with st.container(border=True):
                st.markdown('<p class="sec-label">Agregar un CUIT</p>',
                            unsafe_allow_html=True)
                cuit_nuevo  = st.text_input("CUIT / CUIL", placeholder="20123456789",
                                            key="seg_cuit_nuevo")
                alias_nuevo = st.text_input("Nombre / alias (opcional)",
                                            placeholder="Ej: Juan García",
                                            key="seg_alias_nuevo")
                if st.button("Agregar al seguimiento", type="primary",
                             key="btn_add_vigilado", use_container_width=True):
                    if not cuit_nuevo.strip():
                        st.error("Ingresá un CUIT válido")
                    else:
                        ok, msg = agregar_vigilado(
                            cliente_id, usuario_id,
                            cuit_nuevo.strip(), alias_nuevo.strip()
                        )
                        if ok:
                            st.success(f"✅ {msg}")
                            st.rerun()
                        else:
                            st.error(f"❌ {msg}")

        with col_mas:
            with st.container(border=True):
                st.markdown('<p class="sec-label">Carga masiva desde Excel</p>',
                            unsafe_allow_html=True)
                st.markdown(
                    '<p style="font-size:12px;color:#86868b;margin-bottom:8px;">'
                    'El archivo debe tener columnas CUIT (obligatoria) y '
                    'NOMBRE/ALIAS (opcional).</p>',
                    unsafe_allow_html=True,
                )
                archivo_seg = st.file_uploader(
                    "Archivo Excel", type=["xlsx","xls"], key="seg_upload"
                )
                if archivo_seg:
                    try:
                        df_raw = pd.read_excel(archivo_seg)
                        df_raw, cuit_col, nombre_col, _ = normalizar_columnas(df_raw)
                        if not cuit_col:
                            st.error(f"No encontré columna CUIT. Columnas: {df_raw.columns.tolist()}")
                        else:
                            st.success(f"{len(df_raw)} filas detectadas")
                            if st.button("Importar al seguimiento", type="primary",
                                         key="btn_import_seg", use_container_width=True):
                                lista = []
                                for _, row in df_raw.iterrows():
                                    cuit_v  = str(row[cuit_col]).replace(".0","").strip()
                                    alias_v = str(row[nombre_col]).strip() if nombre_col else ""
                                    lista.append({"cuit": cuit_v, "alias": alias_v})
                                ok_c, err_c = agregar_vigilados_masivo(
                                    cliente_id, usuario_id, lista
                                )
                                st.success(f"✅ {ok_c} CUITs importados")
                                if err_c:
                                    st.warning(f"{err_c} filas con error o duplicadas")
                                st.rerun()
                    except Exception as e:
                        st.error(f"Error al leer el archivo: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 3 — HISTORIAL DETALLADO
    # ══════════════════════════════════════════════════════════════════════════
    with tab3:
        vigilados_todos = listar_vigilados(cliente_id, solo_activos=False)
        if not vigilados_todos:
            st.info("Sin historial disponible.")
        else:
            opts = {
                f"{v.get('alias') or v['cuit']} ({v['cuit']})": v["id"]
                for v in vigilados_todos
            }
            sel_label = st.selectbox("Seleccioná un CUIT", list(opts.keys()),
                                     key="hist_sel_cuit")
            vid = opts[sel_label]
            historial = get_historial_vigilado(vid, limite=24)

            if not historial:
                st.info("Sin historial para este CUIT.")
            else:
                with st.container(border=True):
                    st.markdown(
                        f'<p class="sec-label">Evolución mensual — {sel_label}</p>',
                        unsafe_allow_html=True,
                    )

                    # Gráfico de evolución de montos
                    df_hist = pd.DataFrame(historial)
                    df_hist["fecha_consulta"] = pd.to_datetime(
                        df_hist["fecha_consulta"]
                    ).dt.strftime("%Y-%m-%d")

                    if df_hist["monto_sit1"].sum() + df_hist["monto_riesgo"].sum() > 0:
                        df_chart = df_hist[["fecha_consulta","monto_sit1","monto_riesgo"]].copy()
                        df_chart.columns = ["Fecha","Deuda Normal","Deuda Riesgo"]
                        df_chart = df_chart.set_index("Fecha").sort_index()
                        st.line_chart(df_chart, height=220)

                    # Tabla de historial
                    df_tabla = df_hist[[
                        "fecha_consulta","periodo_bcra","variacion",
                        "monto_sit1","monto_riesgo","cant_entidades",
                        "delta_sit1","delta_riesgo","error"
                    ]].copy()
                    df_tabla.columns = [
                        "Fecha consulta","Período BCRA","Variación",
                        "Deuda Normal $","Deuda Riesgo $","Entidades",
                        "Δ Normal","Δ Riesgo","Error"
                    ]
                    df_tabla["Variación"] = df_tabla["Variación"].map(
                        lambda v: VAR_LABEL.get(v, v)
                    )
                    st.dataframe(
                        df_tabla, use_container_width=True,
                        hide_index=True, height=300,
                    )

                    # Exportar historial individual
                    buf2 = io.BytesIO()
                    df_tabla.to_excel(buf2, index=False)
                    cuit_clean = sel_label.split("(")[-1].replace(")","").strip()
                    st.download_button(
                        "Exportar historial Excel",
                        data=buf2.getvalue(),
                        file_name=f"historial_{cuit_clean}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 4 — REPORTES GUARDADOS
    # ══════════════════════════════════════════════════════════════════════════
    with tab4:
        reportes = listar_reportes_seguimiento(cliente_id)
        if not reportes:
            st.markdown(
                '<div style="text-align:center;padding:60px 20px;color:#86868b;">'
                '<div style="font-size:40px;margin-bottom:12px;">📄</div>'
                '<p style="font-size:16px;font-weight:500;color:#1d1d1f;margin:0 0 6px 0;">'
                'Sin reportes guardados</p>'
                '<p style="font-size:14px;margin:0;">'
                'Ejecutá el seguimiento mensual para generar el primer reporte</p>'
                '</div>',
                unsafe_allow_html=True,
            )
        else:
            with st.container(border=True):
                st.markdown(
                    f'<p class="sec-label">{len(reportes)} reportes mensuales guardados</p>',
                    unsafe_allow_html=True,
                )
                for rep in reportes:
                    rc1, rc2, rc3, rc4 = st.columns([2, 4, 2, 2])
                    with rc1:
                        st.markdown(
                            f'<p style="font-size:14px;font-weight:600;color:#1d1d1f;'
                            f'margin:8px 0 2px 0;">{rep["periodo"]}</p>'
                            f'<p style="font-size:11px;color:#86868b;margin:0;">'
                            f'{rep["fecha_gen"][:10]}</p>',
                            unsafe_allow_html=True,
                        )
                    with rc2:
                        st.markdown(
                            f'<p style="font-size:12px;color:#1d1d1f;margin:8px 0 2px 0;">'
                            f'{rep["total_cuits"]} CUITs · '
                            f'<span style="color:#cc0000;">↑ {rep["suben"]} suben</span> · '
                            f'<span style="color:#1a7a1a;">↓ {rep["bajan"]} bajan</span> · '
                            f'<span style="color:#86868b;">= {rep["sin_cambio"]} sin cambio</span>'
                            f'</p>',
                            unsafe_allow_html=True,
                        )
                    with rc3:
                        pdf_data = get_pdf_seguimiento(rep["id"], cliente_id)
                        if pdf_data:
                            st.download_button(
                                "Descargar PDF",
                                data=pdf_data,
                                file_name=f"seguimiento_{rep['periodo']}.pdf",
                                mime="application/pdf",
                                key=f"dl_rep_{rep['id']}",
                                use_container_width=True,
                            )
                    with rc4:
                        st.markdown(
                            f'<p style="font-size:11px;color:#cc6600;margin:8px 0;">'
                            f'{rep["errores"]} errores</p>'
                            if rep["errores"] else "",
                            unsafe_allow_html=True,
                        )
                    st.markdown(
                        '<hr style="border:none;border-top:0.5px solid #f5f5f5;margin:4px 0;">',
                        unsafe_allow_html=True,
                    )
