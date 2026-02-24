import streamlit as st
import pandas as pd
import os
import urllib.parse
from datetime import datetime, date, timedelta

st.set_page_config(page_title="Agua Origen - Gestión Total", layout="wide")

LLAVE_MAESTRA = "ORIGEN_MASTER_2026"
MAX_INTENTOS = 3
ADMIN_CONFIG_FILE = "admin_config.xlsx"

def _input_password(label, key, placeholder="••••••••"):
    try:
        return st.text_input(label, key=key, placeholder=placeholder, type="password")
    except TypeError:
        return st.text_input(label, key=key, placeholder=placeholder)

def _sidebar_password(label, key, placeholder="••••••••"):
    try:
        return st.sidebar.text_input(label, key=key, placeholder=placeholder, type="password")
    except TypeError:
        return st.sidebar.text_input(label, key=key, placeholder=placeholder)

def aplicar_estilos():
    st.markdown("""
    <style>
    .main .block-container { padding-top: 1.5rem; max-width: 1200px; }
    .logo-sidebar { margin-bottom: 1.5rem; }
    .logo-sidebar img { max-width: 100%; border-radius: 12px; }
    .logo-header { text-align: center; margin-bottom: 1.5rem; }
    .logo-header img { max-height: 120px; border-radius: 12px; }
    .form-container { padding: 1.5rem; border-radius: 12px; }
    </style>
    """, unsafe_allow_html=True)

def cargar_db(archivo, columnas_default):
    if os.path.exists(archivo):
        try:
            df = pd.read_excel(archivo)
            for col in columnas_default:
                if col not in df.columns:
                    df[col] = "" if col != "IntentosFallidos" else 0
            return df
        except Exception:
            pass
    return pd.DataFrame(columns=columnas_default)

def es_alfanumerico(s):
    if not s or not isinstance(s, str):
        return False
    return s.strip().replace(" ", "").isalnum() or s.isalnum()

def guardar_repartidores(df):
    df.to_excel("repartidores.xlsx", index=False)

def guardar_pedidos(df):
    df.to_excel("datos_agua.xlsx", index=False)

def guardar_alertas(df):
    df.to_excel("alertas_envases.xlsx", index=False)

def guardar_inventario(df):
    df.to_excel("inventario.xlsx", index=False)

def guardar_catalogo(df):
    df.to_excel("catalogo.xlsx", index=False)

def cargar_clave_admin():
    if os.path.exists(ADMIN_CONFIG_FILE):
        try:
            df = pd.read_excel(ADMIN_CONFIG_FILE)
            if not df.empty and "Clave" in df.columns:
                return str(df.iloc[0]["Clave"]).strip()
        except Exception:
            pass
    return None

def guardar_clave_admin(clave):
    pd.DataFrame([{"Clave": clave}]).to_excel(ADMIN_CONFIG_FILE, index=False)

def admin_login_valido(clave_ingresada):
    if not clave_ingresada:
        return False
    if clave_ingresada.strip() == LLAVE_MAESTRA:
        return True
    guardada = cargar_clave_admin()
    return guardada and guardada == clave_ingresada.strip()

COL_PEDIDOS = ['Fecha', 'Cliente', 'Celular', 'Cantidad', 'Repartidor', 'Estado', 'Ubicacion', 'TipoPago', 'RUC_DNI']
COL_REPARTIDORES = ['Nombre', 'Usuario', 'Clave', 'DNI', 'Celular', 'Placa', 'Estado', 'IntentosFallidos']
COL_ALERTAS = ['Fecha', 'Repartidor', 'Cliente', 'Esperados', 'Recibidos', 'Faltante', 'Estado']
COL_INVENTARIO = ['Fecha', 'Repartidor', 'Tipo', 'BidonesLlenos', 'BidonesVacios']
COL_CATALOGO = ['Producto', 'PrecioUnidad', 'PrecioEnvase']

df_v = cargar_db("datos_agua.xlsx", COL_PEDIDOS)
df_r = cargar_db("repartidores.xlsx", COL_REPARTIDORES)
df_a = cargar_db("alertas_envases.xlsx", COL_ALERTAS)
df_inv = cargar_db("inventario.xlsx", COL_INVENTARIO)
df_cat = cargar_db("catalogo.xlsx", COL_CATALOGO)

if df_cat.empty:
    df_cat = pd.DataFrame([{'Producto': 'Bidón 20L', 'PrecioUnidad': 5.0, 'PrecioEnvase': 15.0}])
    guardar_catalogo(df_cat)

for c in COL_REPARTIDORES:
    if c not in df_r.columns:
        df_r[c] = 0 if c == "IntentosFallidos" else ""
if "IntentosFallidos" in df_r.columns:
    df_r["IntentosFallidos"] = pd.to_numeric(df_r["IntentosFallidos"], errors="coerce").fillna(0).astype(int)

def round_robin_asignar(df_pedidos, df_repartidores):
    reps_activos = df_repartidores[df_repartidores['Estado'].astype(str) == 'Activo']['Nombre'].tolist()
    if not reps_activos:
        return "Pendiente"
    reps_activos = sorted(reps_activos)
    pendientes = df_pedidos[df_pedidos['Estado'].astype(str) == 'Pendiente']
    total_secuencia = len(pendientes)
    return reps_activos[total_secuencia % len(reps_activos)]

def obtener_ubicacion_gps():
    try:
        from streamlit_js_eval import get_geolocation
        loc = get_geolocation()
        if loc and isinstance(loc, dict) and 'coords' in loc:
            lat = loc['coords'].get('latitude', 0)
            lon = loc['coords'].get('longitude', 0)
            return f"{lat},{lon}"
    except Exception:
        pass
    return "0,0"

def mostrar_logo_sidebar():
    if os.path.exists("logo.png"):
        st.sidebar.markdown('<div class="logo-sidebar">', unsafe_allow_html=True)
        st.sidebar.image("logo.png", use_container_width=True)
        st.sidebar.markdown('</div>', unsafe_allow_html=True)

def mostrar_logo_header():
    if os.path.exists("logo.png"):
        st.markdown('<div class="logo-header">', unsafe_allow_html=True)
        st.image("logo.png", width=140)
        st.markdown('</div>', unsafe_allow_html=True)

def mensaje_whatsapp_arribo(nombre_cliente, nombre_repartidor, cantidad_bidones):
    return (
        f"Hola {nombre_cliente}, soy {nombre_repartidor} de Agua Origen. "
        f"Estoy afuera de tu ubicación con tu pedido de {cantidad_bidones} bidones. ¡Te espero!"
    )

aplicar_estilos()
mostrar_logo_sidebar()

rol = st.sidebar.selectbox("Módulo de Acceso", ["Cliente (Pedidos)", "Repartidor", "Administrador"])

if rol == "Cliente (Pedidos)":
    mostrar_logo_header()
    st.header("💧 Realiza tu pedido")
    st.markdown('<div class="form-container">', unsafe_allow_html=True)
    with st.form("form_cli", clear_on_submit=True):
        n = st.text_input("Tu Nombre", placeholder="Nombre completo")
        c = st.text_input("WhatsApp (9XXXXXXXX)", placeholder="Ej: 987654321")
        cant = st.number_input("Cantidad de bidones", 1, 100, 1)
        tipo_pago = st.selectbox("Tipo de Pago", ["Efectivo", "Yape", "Plin"])
        ruc_dni = st.text_input("RUC o DNI (opcional, para comprobantes)")
        st.caption("Activa la ubicación cuando confirmes el pedido.")
        submit = st.form_submit_button("Confirmar Pedido")
        if submit:
            if not n or not c:
                st.error("Nombre y celular son obligatorios.")
            else:
                coords = obtener_ubicacion_gps()
                rep_asig = round_robin_asignar(df_v, df_r)
                nuevo_p = pd.DataFrame([{
                    'Fecha': datetime.now(), 'Cliente': n, 'Celular': str(c).strip(),
                    'Cantidad': cant, 'Repartidor': rep_asig, 'Estado': 'Pendiente',
                    'Ubicacion': coords, 'TipoPago': tipo_pago, 'RUC_DNI': ruc_dni or ""
                }])
                df_v = pd.concat([df_v, nuevo_p], ignore_index=True)
                guardar_pedidos(df_v)
                st.success(f"Pedido recibido. Asignado a: {rep_asig}")
    st.markdown('</div>', unsafe_allow_html=True)

elif rol == "Repartidor":
    if st.session_state.get('repartidor_autenticado'):
        def cerrar_sesion_rep():
            st.session_state.pop('repartidor_autenticado', None)
            st.session_state.pop('repartidor_nombre', None)
        st.sidebar.success("Sesión activa")
        st.sidebar.button("Cerrar sesión", on_click=cerrar_sesion_rep)

        nom_rep = st.session_state.get('repartidor_nombre', '')
        precio_unidad = float(df_cat.iloc[0].get('PrecioUnidad', 5))
        precio_envase = float(df_cat.iloc[0].get('PrecioEnvase', 15))

        mostrar_logo_header()
        st.header(f"🚚 Pedidos de {nom_rep}")
        mis_p = df_v[(df_v['Repartidor'].astype(str) == nom_rep) & (df_v['Estado'].astype(str) == 'Pendiente')]

        if mis_p.empty:
            st.info("No tienes pedidos pendientes.")
        else:
            for i, r in mis_p.iterrows():
                with st.expander(f"📍 {r['Cliente']} — {int(r['Cantidad'])} bidones — {r.get('TipoPago', '')}"):
                    ub = str(r.get('Ubicacion', '0,0')).strip()
                    partes = ub.split(",")
                    lat = partes[0].strip() if partes else "0"
                    lon = partes[-1].strip() if len(partes) > 1 else "0"
                    try:
                        lat_f, lon_f = float(lat), float(lon)
                        ubicacion_ok = (lat_f != 0 or lon_f != 0)
                    except (ValueError, TypeError):
                        ubicacion_ok = False
                    if ubicacion_ok:
                        url_maps_search = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
                        url_maps_dir = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lon}&travelmode=driving"
                        st.link_button("🚀 Abrir en Maps (app)", url_maps_search)
                        st.link_button("🌐 Abrir en navegador", url_maps_dir)
                    else:
                        st.caption("⚠️ Ubicación no disponible (coordenadas no registradas)")
                    cantidad_bidones = int(r['Cantidad'])
                    msg_texto = mensaje_whatsapp_arribo(r['Cliente'], nom_rep, cantidad_bidones)
                    msg = urllib.parse.quote(msg_texto)
                    st.link_button("📲 Avisar llegada (WhatsApp)", f"https://wa.me/51{str(r['Celular']).replace(' ', '')}?text={msg}")
                    st.divider()
                    cant = int(r['Cantidad'])
                    v_rec = st.number_input("Vacíos recibidos (o marcar envase no recibido con menos)", 0, 100, cant, key=f"v_{i}")
                    envases_faltantes = max(0, cant - v_rec)
                    total_base = cant * precio_unidad
                    total_envase = envases_faltantes * precio_envase
                    total_cobrar = total_base + total_envase
                    st.caption(f"Total: S/ {total_base:.2f} (agua) + S/ {total_envase:.2f} (envases no devueltos) = **S/ {total_cobrar:.2f}**")
                    if st.button("Finalizar entrega", key=f"b_{i}"):
                        if envases_faltantes > 0:
                            alerta_n = pd.DataFrame([{
                                'Fecha': datetime.now().strftime("%Y-%m-%d"), 'Repartidor': nom_rep, 'Cliente': r['Cliente'],
                                'Esperados': cant, 'Recibidos': int(v_rec), 'Faltante': envases_faltantes, 'Estado': 'Pendiente'
                            }])
                            df_a = cargar_db("alertas_envases.xlsx", COL_ALERTAS)
                            df_a = pd.concat([df_a, alerta_n], ignore_index=True)
                            guardar_alertas(df_a)
                        df_v = cargar_db("datos_agua.xlsx", COL_PEDIDOS)
                        df_v.at[i, 'Estado'] = 'Entregado'
                        guardar_pedidos(df_v)
                        st.rerun()
    else:
        u_log = st.sidebar.text_input("Usuario", key="rep_user")
        p_log = _sidebar_password("Clave", "rep_pass", "Contraseña")
        btn_entrar = st.sidebar.button("Entrar")

        if btn_entrar:
            if not u_log or not p_log:
                st.sidebar.error("Usuario y/o contraseña inválidos")
            elif not es_alfanumerico(str(u_log)) or not es_alfanumerico(str(p_log)):
                st.sidebar.error("Usuario y/o contraseña inválidos")
            else:
                fila = df_r[df_r['Usuario'].astype(str).str.strip() == str(u_log).strip()]
                if fila.empty:
                    st.sidebar.error("Usuario y/o contraseña inválidos")
                else:
                    row = fila.iloc[0]
                    idx = fila.index[0]
                    if str(row['Estado']) == "Bloqueada":
                        st.sidebar.error("Cuenta bloqueada. Contacte al Administrador.")
                    elif str(p_log).strip() == LLAVE_MAESTRA:
                        st.sidebar.error("Usuario y/o contraseña inválidos")
                    elif str(row['Clave']).strip() != str(p_log).strip():
                        intentos = int(row.get('IntentosFallidos', 0)) + 1
                        df_r.at[idx, 'IntentosFallidos'] = intentos
                        if intentos >= MAX_INTENTOS:
                            df_r.at[idx, 'Estado'] = 'Bloqueada'
                            guardar_repartidores(df_r)
                            st.sidebar.error("Cuenta bloqueada por 3 intentos fallidos. Contacte al Administrador.")
                        else:
                            guardar_repartidores(df_r)
                            st.sidebar.error("Usuario y/o contraseña inválidos")
                    else:
                        df_r.at[idx, 'IntentosFallidos'] = 0
                        guardar_repartidores(df_r)
                        st.session_state['repartidor_nombre'] = row['Nombre']
                        st.session_state['repartidor_autenticado'] = True
                        # Limpiar campos de contraseña
                        st.session_state.pop('rep_pass', None)
                        st.rerun()

        if not st.session_state.get('repartidor_autenticado'):
            st.info("Ingresa usuario y contraseña en la barra lateral y pulsa **Entrar**.")

elif rol == "Administrador":
    if st.session_state.get('admin_autenticado'):
        def cerrar_sesion_admin():
            st.session_state.pop('admin_autenticado', None)
        st.sidebar.success("Sesión activa (Admin)")
        st.sidebar.button("Cerrar sesión", key="admin_logout", on_click=cerrar_sesion_admin)

        df_v = cargar_db("datos_agua.xlsx", COL_PEDIDOS)
        df_r = cargar_db("repartidores.xlsx", COL_REPARTIDORES)
        df_a = cargar_db("alertas_envases.xlsx", COL_ALERTAS)
        df_inv = cargar_db("inventario.xlsx", COL_INVENTARIO)
        df_cat = cargar_db("catalogo.xlsx", COL_CATALOGO)
        if "IntentosFallidos" not in df_r.columns:
            df_r["IntentosFallidos"] = 0
        df_r["IntentosFallidos"] = pd.to_numeric(df_r["IntentosFallidos"], errors="coerce").fillna(0).astype(int)

        mostrar_logo_header()
        pedidos_hoy = df_v[pd.to_datetime(df_v['Fecha'], errors='coerce').dt.date == date.today()]
        nuevos = len(pedidos_hoy[pedidos_hoy['Estado'].astype(str) == 'Pendiente'])
        if nuevos > 0:
            st.success(f"🔔 {nuevos} pedido(s) nuevo(s) pendiente(s) hoy. Revisa el panel de monitoreo.")

        t1, t2, t3, t4, t5, t6, t7 = st.tabs([
            "👥 Gestionar Personal", "📦 Inventario", "📊 Monitoreo",
            "💸 Liquidación", "🛒 Catálogo", "🚩 Alertas Envases", "🔐 Seguridad"
        ])

        with t1:
            st.subheader("Control de Repartidores")
            with st.expander("➕ Registrar Nuevo Repartidor"):
                with st.form("reg_adm", clear_on_submit=True):
                    c1, c2 = st.columns(2)
                    fn = c1.text_input("Nombre Completo")
                    fd = c2.text_input("DNI")
                    fc = c1.text_input("Celular")
                    fp = c2.text_input("Placa")
                    fu = c1.text_input("Usuario Acceso")
                    fcl = c2.text_input("Clave Acceso")
                    if st.form_submit_button("Guardar Repartidor"):
                        if fn and fu:
                            nueva_r = pd.DataFrame([{
                                'Nombre': fn, 'Usuario': fu, 'Clave': fcl or '', 'DNI': fd or '', 'Celular': fc or '',
                                'Placa': fp or '', 'Estado': 'Activo', 'IntentosFallidos': 0
                            }])
                            df_r = pd.concat([df_r, nueva_r], ignore_index=True)
                            guardar_repartidores(df_r)
                            st.success("Registrado.")
                            msg_w = urllib.parse.quote(
                                f"Bienvenido a Agua Origen.\nUsuario: {fu}\nContraseña: {fcl}\nApp: https://agua-origen-tambopata.streamlit.app\nCuenta activa."
                            )
                            cel = str(fc).replace(' ', '') if fc else ''
                            if cel:
                                st.link_button("📲 Enviar credenciales por WhatsApp", f"https://wa.me/51{cel}?text={msg_w}")

            st.write("### Listado de Personal")
            for idx, row in df_r.iterrows():
                col = st.columns([2, 1, 1, 1, 1])
                col[0].write(f"**{row['Nombre']}** — {row['Estado']}")
                if str(row['Estado']) == "Bloqueada":
                    if col[1].button("Desbloquear", key=f"unblock_{idx}"):
                        df_r.at[idx, 'Estado'] = 'Activo'
                        df_r.at[idx, 'IntentosFallidos'] = 0
                        guardar_repartidores(df_r)
                        st.rerun()
                else:
                    nuevo_estado = "Inactivo" if row['Estado'] == "Activo" else "Activo"
                    if col[1].button(f"Dar de {nuevo_estado}", key=f"est_{idx}"):
                        df_r.at[idx, 'Estado'] = nuevo_estado
                        guardar_repartidores(df_r)
                        if nuevo_estado == "Inactivo":
                            msg_baja = urllib.parse.quote(
                                "Agua Origen: Su cuenta ha sido dada de baja. Para reactivar, contacte al administrador."
                            )
                            cel = str(row.get('Celular', '')).replace(' ', '')
                            if cel:
                                st.link_button("📲 Notificar baja por WhatsApp", f"https://wa.me/51{cel}?text={msg_baja}")
                        st.rerun()
                with col[2].expander("Editar"):
                    with st.form(f"edit_{idx}"):
                        e_n = st.text_input("Nombre", value=str(row.get('Nombre', '')), key=f"en_{idx}")
                        e_u = st.text_input("Usuario", value=str(row.get('Usuario', '')), key=f"eu_{idx}")
                        e_c = st.text_input("Clave", value=str(row.get('Clave', '')), key=f"ec_{idx}")
                        e_dni = st.text_input("DNI", value=str(row.get('DNI', '')), key=f"edni_{idx}")
                        e_cel = st.text_input("Celular", value=str(row.get('Celular', '')), key=f"ecel_{idx}")
                        e_p = st.text_input("Placa", value=str(row.get('Placa', '')), key=f"ep_{idx}")
                        if st.form_submit_button("Guardar"):
                            df_r.at[idx, 'Nombre'] = e_n
                            df_r.at[idx, 'Usuario'] = e_u
                            df_r.at[idx, 'Clave'] = e_c
                            df_r.at[idx, 'DNI'] = e_dni
                            st.rerun()
                if col[3].button("Eliminar", key=f"del_{idx}"):
                    df_r = df_r.drop(idx).reset_index(drop=True)
                    guardar_repartidores(df_r)
                    st.rerun()

        with t2:
            st.subheader("Control de Inventario")
            reps = df_r[df_r['Estado'].astype(str).isin(['Activo', 'Inactivo'])]['Nombre'].tolist()
            if reps:
                rep_sel = st.selectbox("Repartidor", reps)
                c1, c2 = st.columns(2)
                with c1:
                    salida = st.number_input("Salida de bidones llenos", 0, 500, 0)
                    if st.button("Registrar salida"):
                        if salida > 0:
                            df_inv = pd.concat([df_inv, pd.DataFrame([{
                                'Fecha': datetime.now(), 'Repartidor': rep_sel, 'Tipo': 'Salida',
                                'BidonesLlenos': salida, 'BidonesVacios': 0
                            }])], ignore_index=True)
                            guardar_inventario(df_inv)
                            st.success("Salida registrada.")
                            st.rerun()
                with c2:
                    retorno = st.number_input("Retorno de bidones vacíos", 0, 500, 0)
                    if st.button("Registrar retorno"):
                        if retorno > 0:
                            df_inv = pd.concat([df_inv, pd.DataFrame([{
                                'Fecha': datetime.now(), 'Repartidor': rep_sel, 'Tipo': 'Retorno',
                                'BidonesLlenos': 0, 'BidonesVacios': retorno
                            }])], ignore_index=True)
                            guardar_inventario(df_inv)
                            st.success("Retorno registrado.")
                            st.rerun()
                st.divider()
                inv_rep = df_inv[df_inv['Repartidor'].astype(str) == rep_sel]
                salidas = inv_rep[inv_rep['Tipo'].astype(str) == 'Salida']['BidonesLlenos'].sum()
                retornos = inv_rep[inv_rep['Tipo'].astype(str) == 'Retorno']['BidonesVacios'].sum()
                st.metric("Total salidas (llenos)", int(salidas))
                st.metric("Total retornos (vacíos)", int(retornos))
                st.metric("Balance (salidas - retornos)", int(salidas - retornos))
            else:
                st.info("No hay repartidores para asignar inventario.")

        with t3:
            st.subheader("Monitoreo de Pedidos")
            f_ini = st.date_input("Desde", value=date.today() - timedelta(days=7))
            f_fin = st.date_input("Hasta", value=date.today())
            df_v['Fecha_d'] = pd.to_datetime(df_v['Fecha'], errors='coerce').dt.date
            mask = (df_v['Fecha_d'] >= f_ini) & (df_v['Fecha_d'] <= f_fin)
            filtrado = df_v[mask]
            pend = filtrado[filtrado['Estado'].astype(str) == 'Pendiente']
            ent = filtrado[filtrado['Estado'].astype(str) == 'Entregado']
            st.metric("Pendientes", len(pend))
            st.metric("Entregados", len(ent))
            st.dataframe(filtrado.drop(columns=['Fecha_d'], errors='ignore'), use_container_width=True)

        with t4:
            st.subheader("Liquidación Financiera")
            dia = st.date_input("Fecha del reporte", value=date.today())
            df_v['Fecha_d'] = pd.to_datetime(df_v['Fecha'], errors='coerce').dt.date
            df_dia = df_v[(df_v['Fecha_d'] == dia) & (df_v['Estado'].astype(str) == 'Entregado')]
            if not df_dia.empty:
                precio_u = float(df_cat.iloc[0].get('PrecioUnidad', 5))
                df_dia = df_dia.copy()
                df_dia['Monto'] = df_dia['Cantidad'].astype(float) * precio_u
                res = df_dia.groupby('Repartidor').apply(
                    lambda g: pd.Series({
                        'Total_Efectivo': g[g['TipoPago'].astype(str) == 'Efectivo']['Monto'].sum(),
                        'Total_Yape': g[g['TipoPago'].astype(str) == 'Yape']['Monto'].sum(),
                        'Total_Plin': g[g['TipoPago'].astype(str) == 'Plin']['Monto'].sum(),
                    })
                )
                res['Total_Día'] = res['Total_Efectivo'] + res['Total_Yape'] + res['Total_Plin']
                st.dataframe(res, use_container_width=True)
            else:
                st.info("No hay entregas en esa fecha.")

        with t5:
            st.subheader("Gestión de Catálogo")
            ed = st.data_editor(df_cat, num_rows="dynamic", use_container_width=True)
            if st.button("Guardar catálogo"):
                df_cat = ed
                guardar_catalogo(df_cat)
                st.success("Catálogo guardado.")

        with t6:
            st.subheader("Alertas de Envases")
            st.caption("Todas las alertas quedan vinculadas al repartidor responsable de la entrega.")
            st.dataframe(df_a[df_a['Estado'].astype(str) == 'Pendiente'], use_container_width=True)

        with t7:
            st.subheader("Cambiar contraseña de administrador")
            with st.form("cambiar_clave_admin"):
                actual = _input_password("Contraseña actual", "clave_actual")
                nueva = _input_password("Nueva contraseña", "clave_nueva")
                repetir = _input_password("Repetir nueva contraseña", "clave_repetir")
                if st.form_submit_button("Actualizar contraseña"):
                    if not actual or not nueva or not repetir:
                        st.error("Completa todos los campos.")
                    elif nueva != repetir:
                        st.error("La nueva contraseña y la repetición no coinciden.")
                    elif not admin_login_valido(actual):
                        st.error("Contraseña actual incorrecta.")
                    else:
                        guardar_clave_admin(nueva)
                        st.success("Contraseña actualizada correctamente.")
    else:
        clave_admin = _sidebar_password("Contraseña de administrador", "admin_pass", "Contraseña")
        btn_admin = st.sidebar.button("Entrar como administrador")

        if btn_admin and clave_admin:
            if admin_login_valido(clave_admin):
                st.session_state['admin_autenticado'] = True
                # Limpiar campo de contraseña
                st.session_state.pop('admin_pass', None)
                st.rerun()
            else:
                st.sidebar.error("Usuario y/o contraseña inválidos")
        elif not st.session_state.get('admin_autenticado'):
            st.info("Ingresa la contraseña de administrador en la barra lateral y pulsa **Entrar como administrador**.")
