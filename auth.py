"""
auth.py — Login y control de acceso Deudix
Flujo: login → verificar TyC → si no aceptó, mostrar pantalla TyC → app
"""
import streamlit as st
import bcrypt
from database import (
    get_usuario, get_usuario_cualquier_estado, actualizar_ultimo_acceso, init_db,
    usuario_acepto_tyc, registrar_aceptacion_tyc, TYC_VERSION,
    registrar_empresa_usuario,
)

TEXTO_TYC = """
**Fuente de la información:** Los datos presentados en esta plataforma provienen de la Central de Deudores del Sistema Financiero del Banco Central de la República Argentina (BCRA) y de boletines oficiales y judiciales de acceso público.

**Naturaleza de los datos:** La información publicada por el BCRA y los boletines es de carácter público y se difunde en cumplimiento de la normativa vigente. El BCRA no certifica ni avala el uso que terceros hagan de estos datos.

**Uso del sistema:** Esta plataforma procesa, organiza y presenta la información en distintos formatos con el objetivo de facilitar su consulta y análisis. El servicio ofrecido agrega valor mediante procesamiento, visualización y generación de reportes, pero no altera el contenido sustancial de los datos.

**Limitaciones:**
- La información aquí expuesta no constituye certificación oficial ni reemplaza la consulta directa a las fuentes originales.
- El sistema no garantiza la exhaustividad ni la actualización inmediata de los datos, dado que depende de la publicación oficial de las fuentes.
- Los derechos de rectificación o supresión de datos deben ejercerse ante la entidad financiera o el organismo que originó la información.

**Protección de datos personales:** El uso de esta plataforma se ajusta a la Ley 25.326 de Protección de Datos Personales. Los datos provienen de fuentes públicas y se utilizan exclusivamente con fines legítimos de evaluación crediticia y análisis de antecedentes financieros.
"""

ESTILOS_AUTH = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600;9..40,700&display=swap');
html, body, [class*="css"] {
    font-family: 'DM Sans', -apple-system, sans-serif !important;
    background: #ffffff !important;
}
.stApp { background: #ffffff !important; }
section[data-testid="stSidebar"] { display: none !important; }
div[data-testid="stToolbar"]     { display: none !important; }
#MainMenu { visibility: hidden; } footer { visibility: hidden; } header { visibility: hidden; }

div[data-testid="stTextInput"] input {
    background: #f5f5f7 !important; border: none !important;
    border-radius: 12px !important; color: #1d1d1f !important;
    font-size: 16px !important; padding: 14px 16px !important;
}
div[data-testid="stTextInput"] input:focus {
    background: #ebebed !important; outline: none !important; box-shadow: none !important;
}
div[data-testid="stTextInput"] label {
    color: #1d1d1f !important; font-size: 13px !important; font-weight: 500 !important;
}
div[data-testid="stButton"] button {
    background: #1d1d1f !important; color: #ffffff !important; font-weight: 600 !important;
    font-size: 15px !important; border: none !important; border-radius: 980px !important;
    padding: 14px 24px !important; width: 100% !important; transition: background 0.2s !important;
}
div[data-testid="stButton"] button:hover { background: #3a3a3c !important; }
div[data-testid="stAlert"] { border-radius: 12px !important; border: none !important; font-size: 14px !important; }
div[data-testid="stCheckbox"] label p { color: #1d1d1f !important; font-size: 14px !important; font-weight: 500 !important; }

/* Caja de TyC con scroll */
.tyc-box {
    background: #f5f5f7;
    border-radius: 14px;
    padding: 24px 28px;
    height: 380px;
    overflow-y: auto;
    font-size: 13px;
    line-height: 1.7;
    color: #3a3a3c;
    margin-bottom: 20px;
    border: 0.5px solid #e5e5ea;
}
.tyc-box strong { color: #1d1d1f; }
.tyc-box ul { padding-left: 20px; margin: 8px 0; }
.tyc-box li { margin-bottom: 4px; }
</style>
"""

def verificar_password(password: str, hash_guardado: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hash_guardado.encode())
    except Exception:
        return False

def _capturar_contexto() -> tuple[str, str]:
    """
    Intenta obtener IP y user-agent del contexto HTTP de Streamlit.
    En Streamlit Cloud / producción estos headers están disponibles.
    Devuelve (ip_raw, user_agent).
    """
    try:
        from streamlit.web.server.websocket_headers import _get_websocket_headers
        headers = _get_websocket_headers()
        ip  = (headers.get("X-Forwarded-For") or
               headers.get("X-Real-Ip")       or
               headers.get("Remote-Addr")      or "")
        ua  = headers.get("User-Agent", "")
        return ip.split(",")[0].strip(), ua
    except Exception:
        pass
    # Fallback: leer desde st.context si existe (Streamlit ≥ 1.37)
    try:
        ip = getattr(st.context, "ip", "") or ""
        ua = getattr(st.context, "headers", {}).get("User-Agent", "")
        return ip, ua
    except Exception:
        return "", ""

def login_screen():
    st.markdown(ESTILOS_AUTH, unsafe_allow_html=True)
    _, col, _ = st.columns([1, 1.2, 1])

    with col:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        st.markdown("""
        <div style="text-align:center;margin-bottom:32px;">
            <div style="width:72px;height:72px;background:#1d1d1f;border-radius:20px;
                        display:inline-flex;align-items:center;justify-content:center;margin-bottom:20px;">
                <span style="font-size:32px;">🏦</span>
            </div>
            <h1 style="font-family:'DM Sans',sans-serif;font-size:32px;font-weight:700;
                       color:#1d1d1f;letter-spacing:-0.03em;margin:0;">Deudix</h1>
        </div>
        """, unsafe_allow_html=True)

        email    = st.text_input("Email", placeholder="nombre@empresa.com")
        password = st.text_input("Contraseña", type="password", placeholder="••••••••")
        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("Ingresar", use_container_width=True):
            if not email or not password:
                st.error("Completá email y contraseña")
                return
            # Primero verificar si existe en cualquier estado
            usuario_raw = get_usuario_cualquier_estado(email.strip().lower())
            if not usuario_raw:
                st.error("Usuario no encontrado")
                return
            if not verificar_password(password, usuario_raw["password_hash"]):
                st.error("Contraseña incorrecta")
                return
            if not usuario_raw.get("aprobado"):
                st.warning(
                    "Tu cuenta está pendiente de aprobación. "
                    "Te notificaremos cuando esté activa."
                )
                return
            if not usuario_raw.get("activo"):
                st.error("Tu cuenta está desactivada. Contactá al administrador.")
                return
            usuario = usuario_raw
            # Login correcto — marcar pendiente de TyC si no aceptó
            actualizar_ultimo_acceso(usuario["id"])
            st.session_state["usuario"]         = usuario
            st.session_state["logueado"]        = True
            st.session_state["tyc_pendiente"]   = not usuario_acepto_tyc(usuario["id"])
            st.query_params["sid"] = usuario["email"]
            st.rerun()

        r1, r2 = st.columns(2)
        with r1:
            if st.button("Crear cuenta nueva", use_container_width=True, key="btn_ir_registro"):
                st.session_state["pantalla"] = "registro"
                st.rerun()
        st.markdown(
            '<p style="text-align:center;color:#c7c7cc;font-size:11px;margin-top:32px;">'
            '© 2026 Deudix · Todos los derechos reservados</p>',
            unsafe_allow_html=True,
        )

def tyc_screen(usuario: dict):
    """Pantalla de aceptación de TyC — bloquea el acceso hasta que se acepte."""
    st.markdown(ESTILOS_AUTH, unsafe_allow_html=True)
    _, col, _ = st.columns([1, 1.6, 1])

    with col:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("""
        <div style="text-align:center;margin-bottom:24px;">
            <div style="width:56px;height:56px;background:#1d1d1f;border-radius:16px;
                        display:inline-flex;align-items:center;justify-content:center;margin-bottom:14px;">
                <span style="font-size:26px;">📋</span>
            </div>
            <h2 style="font-family:'DM Sans',sans-serif;font-size:24px;font-weight:700;
                       color:#1d1d1f;letter-spacing:-0.02em;margin:0 0 6px 0;">Términos y Condiciones</h2>
            <p style="font-size:14px;color:#86868b;margin:0;">
                Revisá y aceptá los términos antes de continuar
            </p>
        </div>
        """, unsafe_allow_html=True)

        # Texto de TyC en caja con scroll — HTML para poder controlar el diseño
        html_tyc = TEXTO_TYC
        # Convertir markdown básico a HTML para la caja
        import re
        html_tyc = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html_tyc)
        html_tyc = re.sub(r'^- (.+)$', r'<li>\1</li>', html_tyc, flags=re.MULTILINE)
        html_tyc = re.sub(r'(<li>.*</li>\n?)+', lambda m: f'<ul>{m.group()}</ul>', html_tyc)
        html_tyc = re.sub(r'\n\n', '</p><p>', html_tyc.strip())
        html_tyc = f'<p>{html_tyc}</p>'

        st.markdown(f'<div class="tyc-box">{html_tyc}</div>', unsafe_allow_html=True)

        # Versión del documento
        st.markdown(
            f'<p style="font-size:11px;color:#aeaeb2;text-align:right;margin:-12px 0 16px 0;">'
            f'Versión {TYC_VERSION} · Hash: {__import__("database").TYC_HASH}</p>',
            unsafe_allow_html=True,
        )

        acepto = st.checkbox(
            f"Leí y acepto los Términos y Condiciones de uso de Deudix (versión {TYC_VERSION})"
        )

        st.markdown("<br>", unsafe_allow_html=True)

        col_b1, col_b2 = st.columns(2)
        with col_b1:
            if st.button("Cancelar y salir", use_container_width=True, key="tyc_cancelar"):
                logout()
        with col_b2:
            if st.button("Continuar →", use_container_width=True, key="tyc_aceptar",
                         type="primary", disabled=not acepto):
                if acepto:
                    ip_raw, user_agent = _capturar_contexto()
                    registrar_aceptacion_tyc(usuario["id"], ip_raw, user_agent)
                    st.session_state["tyc_pendiente"] = False
                    st.success("Aceptación registrada. Ingresando…")
                    st.rerun()
                else:
                    st.warning("Debés marcar la casilla para continuar")

        st.markdown("""
        <p style="text-align:center;color:#c7c7cc;font-size:11px;margin-top:24px;">
            © 2026 Deudix · Uso exclusivo de clientes autorizados
        </p>
        """, unsafe_allow_html=True)

def logout():
    for key in list(st.session_state.keys()):
        st.session_state.pop(key, None)
    st.query_params.clear()
    st.rerun()

def require_login():
    init_db()

    # Recuperar sesión desde query_params si se perdió por F5 o reinicio
    if not st.session_state.get("logueado"):
        _sid = st.query_params.get("sid", "")
        if _sid:
            _u = get_usuario_cualquier_estado(_sid)
            if _u and _u.get("aprobado") and _u.get("activo"):
                st.session_state["usuario"]       = _u
                st.session_state["logueado"]      = True
                st.session_state["tyc_pendiente"] = not usuario_acepto_tyc(_u["id"])

    # Paso 1 — ¿está logueado?
    if not st.session_state.get("logueado"):
        pantalla = st.session_state.get("pantalla", "login")
        if pantalla == "registro":
            registro_screen()
        else:
            login_screen()
        st.stop()

    usuario = st.session_state["usuario"]

    # Paso 2 — ¿aceptó los TyC vigentes?
    if st.session_state.get("tyc_pendiente", False):
        tyc_screen(usuario)
        st.stop()

    # Re-verificar en DB por si se actualizó la versión de TyC
    if not usuario_acepto_tyc(usuario["id"]):
        st.session_state["tyc_pendiente"] = True
        tyc_screen(usuario)
        st.stop()

    return usuario

def require_admin():
    u = st.session_state.get("usuario", {})
    return u.get("rol") == "admin"


def registro_screen():
    """Pantalla de registro de nueva empresa + usuario."""
    st.markdown(ESTILOS_AUTH, unsafe_allow_html=True)
    _, col, _ = st.columns([1, 1.4, 1])

    with col:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("""
        <div style="text-align:center;margin-bottom:28px;">
            <div style="width:64px;height:64px;background:#1d1d1f;border-radius:18px;
                        display:inline-flex;align-items:center;justify-content:center;
                        margin-bottom:16px;">
                <span style="font-size:28px;">🏢</span>
            </div>
            <h2 style="font-family:'DM Sans',sans-serif;font-size:26px;font-weight:700;
                       color:#1d1d1f;letter-spacing:-0.02em;margin:0 0 6px 0;">
                Crear cuenta</h2>
            <p style="font-size:14px;color:#86868b;margin:0;">
                Completá los datos de tu empresa para solicitar acceso</p>
        </div>
        """, unsafe_allow_html=True)

        # Datos de empresa
        st.markdown(
            '<p style="font-size:11px;font-weight:600;letter-spacing:0.08em;'
            'text-transform:uppercase;color:#86868b;margin:0 0 10px 0;">Empresa</p>',
            unsafe_allow_html=True,
        )
        nombre_empresa = st.text_input("Nombre de empresa *",
                                        placeholder="Banco XYZ S.A.",
                                        key="reg_empresa")
        cuit_empresa   = st.text_input("CUIT *",
                                        placeholder="30-12345678-9",
                                        key="reg_cuit")

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            '<p style="font-size:11px;font-weight:600;letter-spacing:0.08em;'
            'text-transform:uppercase;color:#86868b;margin:0 0 10px 0;">Tu cuenta</p>',
            unsafe_allow_html=True,
        )
        nombre_usuario = st.text_input("Nombre completo *",
                                        placeholder="Juan García",
                                        key="reg_nombre")
        email          = st.text_input("Email *",
                                        placeholder="juan@empresa.com",
                                        key="reg_email")
        password       = st.text_input("Contraseña *", type="password",
                                        placeholder="Mínimo 8 caracteres",
                                        key="reg_pass")
        password2      = st.text_input("Repetir contraseña *", type="password",
                                        placeholder="••••••••",
                                        key="reg_pass2")

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Solicitar acceso", use_container_width=True,
                     key="btn_registrar"):
            # Validaciones
            errores = []
            if not nombre_empresa.strip(): errores.append("Nombre de empresa")
            if not cuit_empresa.strip():   errores.append("CUIT")
            if not nombre_usuario.strip(): errores.append("Nombre completo")
            if not email.strip():          errores.append("Email")
            if not password:               errores.append("Contraseña")
            if errores:
                st.error(f"Campos obligatorios faltantes: {', '.join(errores)}")
            elif len(password) < 8:
                st.error("La contraseña debe tener al menos 8 caracteres")
            elif password != password2:
                st.error("Las contraseñas no coinciden")
            else:
                ok, msg = registrar_empresa_usuario(
                    nombre_empresa.strip(),
                    cuit_empresa.strip().replace("-","").replace(".",""),
                    nombre_usuario.strip(),
                    email.strip().lower(),
                    password,
                )
                if ok:
                    st.success(
                        "✅ Solicitud enviada correctamente. "
                        "Recibirás acceso en las próximas 24 horas."
                    )
                    st.markdown(
                        '<p style="text-align:center;font-size:13px;color:#86868b;'
                        'margin-top:12px;">Podés cerrar esta ventana o volver al login.</p>',
                        unsafe_allow_html=True,
                    )
                    if st.button("Volver al login", key="btn_volver_ok"):
                        st.session_state["pantalla"] = "login"
                        st.rerun()
                else:
                    st.error(f"❌ {msg}")

        if st.button("← Volver al login", key="btn_volver_login",
                     use_container_width=True):
            st.session_state["pantalla"] = "login"
            st.rerun()

        st.markdown(
            '<p style="text-align:center;color:#c7c7cc;font-size:11px;margin-top:24px;">'
            '© 2026 Deudix · Todos los derechos reservados</p>',
            unsafe_allow_html=True,
        )
