"""
setup.py — Panel de configuración de empresa (Mi empresa).
Los campos obligatorios deben completarse antes de poder realizar consultas.

BUG 4 FIX: se eliminó st.rerun() al guardar datos para evitar el loop
           cuando se llega desde el botón de "Cargar datos de empresa" en consulta individual.
BUG 7 FIX: botón Guardar datos movido debajo del bloque logo.
BUG 8 FIX: los campos se pre-cargan desde DB sin usar keys que se reseteen.
"""
import streamlit as st
import io as _io

from database import (
    get_cliente, actualizar_perfil_cliente, actualizar_logo_cliente,
)

# Campos obligatorios — sin estos no se pueden hacer consultas
CAMPOS_OBLIGATORIOS = {
    "nombre":        "Nombre de empresa",
    "cuit_empresa":  "CUIT",
    "domicilio":     "Domicilio",
    "ciudad":        "Ciudad",
    "provincia":     "Provincia",
    "telefono":      "Teléfono",
    "email_empresa": "Email de empresa",
}

def _logo_valido(logo_bytes) -> bool:
    if not logo_bytes or len(logo_bytes) < 16:
        return False
    try:
        from PIL import Image
        Image.open(_io.BytesIO(logo_bytes)).verify()
        return True
    except Exception:
        return False

def perfil_completo(cliente: dict) -> bool:
    return all(bool(((cliente or {}).get(f) or "").strip()) for f in CAMPOS_OBLIGATORIOS)

ESTILOS = """
<style>
.setup-section { font-size:11px; font-weight:600; letter-spacing:0.08em;
                 text-transform:uppercase; color:#86868b; margin-bottom:14px;
                 padding-bottom:8px; border-bottom:0.5px solid #f0f0f0; }
.setup-divider { border:none; border-top:0.5px solid #e5e5ea; margin:18px 0; }
.campo-req     { font-size:11px; color:#cc0000; margin:0 0 14px 0; }
</style>
"""

def render_setup(usuario_actual: dict):
    cliente_id = usuario_actual.get("cliente_id")
    if not cliente_id:
        st.error("Tu usuario no tiene empresa asociada. Contactá al administrador.")
        return

    # BUG 8 FIX: siempre leer desde DB — no depender de session_state para los valores del form
    cliente = get_cliente(cliente_id)
    if not cliente:
        st.error("No se encontró la empresa asociada.")
        return

    st.markdown(ESTILOS, unsafe_allow_html=True)

    # ── Header ────────────────────────────────────────────────────────────────
    col_logo, col_titulo = st.columns([1, 7])
    with col_logo:
        if _logo_valido(cliente.get("logo_bytes")):
            st.image(cliente["logo_bytes"], width=64)
        else:
            st.markdown(
                '<div style="width:64px;height:64px;background:#f5f5f7;border-radius:12px;'
                'border:0.5px solid #e5e5ea;display:flex;align-items:center;'
                'justify-content:center;font-size:24px;">🏢</div>',
                unsafe_allow_html=True,
            )
    with col_titulo:
        nombre_h = cliente.get("nombre","") or "Sin nombre"
        cuit_h   = cliente.get("cuit_empresa","") or "Sin CUIT"
        st.markdown(
            f'<p style="font-size:24px;font-weight:700;color:#1d1d1f;'
            f'letter-spacing:-0.02em;margin:0;">{nombre_h}</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<p style="font-size:13px;color:#86868b;margin:2px 0 0 0;">CUIT {cuit_h}</p>',
            unsafe_allow_html=True,
        )

    # Alerta de perfil incompleto
    faltantes = [CAMPOS_OBLIGATORIOS[f] for f in CAMPOS_OBLIGATORIOS
                 if not ((cliente or {}).get(f) or "").strip()]
    if faltantes:
        st.error(
            f"⚠️ Completá los campos obligatorios para poder realizar consultas: "
            f"**{', '.join(faltantes)}**"
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── DATOS DE EMPRESA ──────────────────────────────────────────────────────
    # BUG 4 FIX: NO usar st.rerun() después de guardar — eso causaba el loop
    #            cuando se llegaba desde pagina_individual via _ir_a_setup.
    #            Simplemente mostramos success y dejamos que Streamlit
    #            re-ejecute naturalmente al próximo evento del usuario.

    with st.container(border=True):
        st.markdown('<p class="setup-section">Datos de empresa</p>', unsafe_allow_html=True)
        st.markdown(
            '<p class="campo-req">* Campos obligatorios — requeridos para realizar consultas</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p style="font-size:12px;color:#86868b;margin:-8px 0 16px 0;">'
            'Estos datos se incluyen en el pie de página de todos los reportes PDF.</p>',
            unsafe_allow_html=True,
        )

        c1, c2 = st.columns(2)
        with c1:
            v_nombre    = st.text_input(
                "Nombre de empresa *",
                value=cliente.get("nombre","") or "",
                key="s_nombre",
                placeholder="Ej: Banco XYZ S.A.",
            )
            v_cuit      = st.text_input(
                "CUIT *",
                value=cliente.get("cuit_empresa","") or "",
                key="s_cuit",
                placeholder="30-12345678-9",
            )
            v_domicilio = st.text_input(
                "Domicilio *",
                value=cliente.get("domicilio","") or "",
                key="s_dom",
                placeholder="Av. Corrientes 1234",
            )
            v_ciudad    = st.text_input(
                "Ciudad *",
                value=cliente.get("ciudad","") or "",
                key="s_ciudad",
                placeholder="Buenos Aires",
            )

        with c2:
            v_provincia = st.text_input(
                "Provincia *",
                value=cliente.get("provincia","") or "",
                key="s_prov",
                placeholder="CABA",
            )
            v_telefono  = st.text_input(
                "Teléfono *",
                value=cliente.get("telefono","") or "",
                key="s_tel",
                placeholder="(011) 4000-0000",
            )
            v_email_emp = st.text_input(
                "Email de empresa *",
                value=cliente.get("email_empresa","") or "",
                key="s_email_emp",
                placeholder="contacto@empresa.com",
                help="Aparece en los reportes PDF",
            )
            v_web       = st.text_input(
                "Sitio web",
                value=cliente.get("web","") or "",
                key="s_web",
                placeholder="www.empresa.com.ar",
            )

        st.markdown('<hr class="setup-divider">', unsafe_allow_html=True)

        v_notas = st.text_area(
            "Notas internas",
            value=cliente.get("notas","") or "",
            height=70,
            key="s_notas",
            placeholder="Notas de uso interno, no aparecen en ningún reporte",
        )

    # ── Logo ──────────────────────────────────────────────────────────────────
    with st.container(border=True):
        st.markdown('<p class="setup-section">Logo de empresa</p>', unsafe_allow_html=True)
        col_img, col_up = st.columns([1, 2])
        with col_img:
            if _logo_valido(cliente.get("logo_bytes")):
                st.image(cliente["logo_bytes"], caption="Logo actual", width=150)
            else:
                st.markdown(
                    '<div style="width:150px;height:90px;background:#f5f5f7;border-radius:10px;'
                    'border:0.5px dashed #c7c7cc;display:flex;align-items:center;'
                    'justify-content:center;color:#86868b;font-size:13px;">Sin logo</div>',
                    unsafe_allow_html=True,
                )
        with col_up:
            st.markdown(
                '<p style="font-size:13px;color:#86868b;margin-bottom:8px;">'
                'Opcional. Se incluye en el encabezado de los reportes PDF.</p>',
                unsafe_allow_html=True,
            )
            logo_file = st.file_uploader(
                "Subir logo (PNG, JPG — máx 2MB)",
                type=["png","jpg","jpeg"],
                key="logo_upload",
            )
            if logo_file:
                if logo_file.size > 2 * 1024 * 1024:
                    st.error("El archivo no puede superar 2MB")
                else:
                    try:
                        from PIL import Image
                        Image.open(_io.BytesIO(logo_file.read())).verify()
                        logo_file.seek(0)
                        actualizar_logo_cliente(cliente_id, logo_file.read())
                        st.success("✅ Logo actualizado")
                        st.rerun()
                    except Exception:
                        st.error("El archivo no es una imagen válida")
            if _logo_valido(cliente.get("logo_bytes")):
                if st.button("Eliminar logo", key="btn_del_logo"):
                    actualizar_logo_cliente(cliente_id, None)
                    st.rerun()

    # ── BUG 7 FIX: Botón Guardar datos DEBAJO del logo ────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Guardar datos", type="primary", key="btn_save_perfil",
                 use_container_width=False):
        errores = []
        valores = {
            "nombre":        v_nombre.strip(),
            "cuit_empresa":  v_cuit.strip(),
            "domicilio":     v_domicilio.strip(),
            "ciudad":        v_ciudad.strip(),
            "provincia":     v_provincia.strip(),
            "telefono":      v_telefono.strip(),
            "email_empresa": v_email_emp.strip(),
        }
        for campo, label in CAMPOS_OBLIGATORIOS.items():
            if not valores.get(campo, ""):
                errores.append(label)

        if errores:
            st.error(f"Completá los siguientes campos obligatorios: **{', '.join(errores)}**")
        else:
            try:
                actualizar_perfil_cliente(cliente_id, {
                    **valores,
                    "web":   v_web.strip(),
                    "notas": v_notas,
                    # "email" NO se incluye — campo UNIQUE administrado por separado
                })
                st.success("✅ Datos guardados correctamente")
                # BUG 4 FIX: NO llamar st.rerun() aquí — evita el loop al volver
                # desde pagina_individual. El usuario ve el mensaje y puede navegar.
            except Exception as e:
                st.error(f"Error al guardar: {e}")

    # ── Vista previa pie de página ─────────────────────────────────────────────
    # Recargamos cliente para mostrar los datos actualizados en la vista previa
    cliente_actual = get_cliente(cliente_id)
    with st.container(border=True):
        st.markdown(
            '<p class="setup-section">Vista previa — pie de página en reportes</p>',
            unsafe_allow_html=True,
        )
        nombre_pdf   = cliente_actual.get("nombre","") or "Nombre de empresa"
        cuit_pdf     = cliente_actual.get("cuit_empresa","")
        dom_pdf      = " · ".join(filter(None, [
            cliente_actual.get("domicilio",""),
            cliente_actual.get("ciudad",""),
            cliente_actual.get("provincia",""),
        ])) or "Domicilio · Ciudad · Provincia"
        contacto_pdf = " · ".join(filter(None, [
            cliente_actual.get("telefono",""),
            cliente_actual.get("email_empresa",""),
            cliente_actual.get("web",""),
        ])) or "Teléfono · Email · Web"

        st.markdown(f"""
        <div style="background:#f5f5f7;border-radius:10px;padding:14px 18px;
                    border:0.5px solid #e5e5ea;font-size:11px;">
            <div style="border-top:0.5px solid #c7c7cc;padding-top:10px;">
                <strong style="color:#1d1d1f;">{nombre_pdf}</strong>
                {"  ·  CUIT " + cuit_pdf if cuit_pdf else ""}
                <br><span style="color:#86868b;">{dom_pdf}</span>
                <br><span style="color:#86868b;">{contacto_pdf}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("""
    <div style="margin-top:32px;padding:16px 24px;border-top:0.5px solid #e5e5ea;text-align:center;">
      <p style="color:#86868b;font-size:10px;margin:0;line-height:1.6;">
        <strong style="color:#1d1d1f;">Aviso:</strong>
        Los datos provienen de la API pública del BCRA.
        Este sitio es independiente del BCRA y no almacena datos personales.
        Nuestro sistema agrega valor mediante procesamiento y presentación, pero no modifica la información.
        El BCRA no avala ni certifica este servicio.
      </p>
    </div>
    """, unsafe_allow_html=True)
