import streamlit as st
import pandas as pd
from datetime import datetime
import os
from PIL import Image
from streamlit_js_eval import get_geolocation

# 1. CONFIGURACIÓN
try:
    img = Image.open("logo.png")
except Exception:
    img = None

st.set_page_config(page_title="Agua Origen - Sistema", page_icon="💧", layout="wide")

# 2. GESTIÓN DE DATOS
def cargar_excel(archivo, columnas):
    if os.path.exists(archivo):
        try:
            return pd.read_excel(archivo)
        except Exception:
            return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

df_ventas = cargar_excel("datos_agua.xlsx", ['Fecha', 'Cliente', 'Celular', 'Cantidad', 'Repartidor', 'Estado', 'Ubicacion'])
df_inv = cargar_excel("inventario.xlsx", ['Insumo', 'Cantidad_Actual'])
df_repartidores = cargar_excel("repartidores.xlsx", ['Nombre', 'Usuario', 'Clave', 'DNI', 'Celular', 'Placa', 'Bidones_Planta', 'Estado'])

# 3. INTERFAZ
if img:
    st.sidebar.image(img, width=120)
else:
    st.sidebar.title("💧 Agua Origen")

st.sidebar.markdown("---")
rol = st.sidebar.selectbox("Acceso de Usuario", ["Cliente (Pedidos)", "Repartidor", "Administrador"])
URL_APP = "https://agua-origen-tambopata.streamlit.app"

# --- PORTAL DEL CLIENTE ---
if rol == "Cliente (Pedidos)":
    st.header("💧 Realiza tu pedido")
    with st.form("form_cliente", clear_on_submit=True):
        nombre = st.text_input("Tu Nombre")
        celular = st.text_input("Celular (WhatsApp)")
        cantidad = st.number_input("¿Cuántos bidones?", min_value=1, step=1)
        st.write("📍 Captura tu ubicación:")
        loc = get_geolocation()
        enviar = st.form_submit_button("Confirmar Pedido")
        
        if enviar and nombre and celular and loc:
            coords = f"{loc['coords']['latitude']},{loc['coords']['longitude']}"
            repartidores_activos = df_repartidores[df_repartidores['Estado'] == 'Activo']['Nombre'].tolist()
            if repartidores_activos:
                pendientes = [len(df_ventas[(df_ventas['Repartidor'] == r) & (df_ventas['Estado'] == 'Pendiente')]) for r in repartidores_activos]
                asignado = repartidores_activos[pendientes.index(min(pendientes))]
                nuevo_p = pd.DataFrame([{'Fecha': datetime.now(), 'Cliente': nombre, 'Celular': celular, 'Cantidad': cantidad, 'Repartidor': asignado, 'Estado': 'Pendiente', 'Ubicacion': coords}])
                df_ventas = pd.concat([df_ventas, nuevo_p], ignore_index=True)
                df_ventas.to_excel("datos_agua.xlsx", index=False)
                st.success(f"Pedido recibido. Asignado a: {asignado}")

# --- PORTAL DEL REPARTIDOR ---
elif rol == "Repartidor":
    u_i = st.sidebar.text_input("Usuario")
    p_i = st.sidebar.text_input("Contraseña", type="password")
    
    if u_i and p_i:
        user_match = df_repartidores[(df_repartidores['Usuario'].astype(str) == u_i) & (df_repartidores['Clave'].astype(str) == p_i)]
        if not user_match.empty:
            nombre_rep = user_match.iloc[0]['Nombre']
            placa_rep = user_match.iloc[0]['Placa'] #
            st.header(f"🚚 Panel de {nombre_rep} (Placa: {placa_rep})")
            
            entregados = df_ventas[(df_ventas['Repartidor'] == nombre_rep) & (df_ventas['Estado'] == 'Entregado')]['Cantidad'].sum()
            c1, c2 = st.columns(2)
            c1.metric("En Custodia (Planta)", f"{user_match.iloc[0]['Bidones_Planta']}")
            c2.metric("Por Liquidar", f"{entregados}")

            st.subheader("📋 Pedidos Asignados")
            mis_pendientes = df_ventas[(df_ventas['Repartidor'] == nombre_rep) & (df_ventas['Estado'] == 'Pendiente')]
            for idx, row in mis_pendientes.iterrows():
                with st.expander(f"📍 Cliente: {row['Cliente']}"):
                    st.link_button("🌐 Ver en Maps", f"https://www.google.com/maps/search/?api=1&query={row['Ubicacion']}")
                    if st.button(f"✅ Entregado", key=f"ent_{idx}"):
                        df_ventas.at[idx, 'Estado'] = 'Entregado'
                        df_ventas.to_excel("datos_agua.xlsx", index=False)
                        st.rerun()
        else:
            st.error("Credenciales incorrectas.")

# --- PORTAL ADMINISTRADOR ---
elif rol == "Administrador":
    clave_adm = st.sidebar.text_input("Clave Maestra", type="password")
    if clave_adm == "admin123":
        t1, t2, t3 = st.tabs(["👥 Gestión de Repartidores", "🏭 Planta", "💸 Liquidación"])
        
        with t1:
            st.subheader("Registrar Nuevo Repartidor")
            with st.form("registro_profesional"):
                col1, col2 = st.columns(2)
                f_nom = col1.text_input("Nombre y Apellido")
                f_dni = col2.text_input("DNI")
                f_cel = col1.text_input("Celular")
                f_pla = col2.text_input("Placa del Vehículo") #
                f_user = col1.text_input("Usuario")
                f_pass = col2.text_input("Contraseña")
                
                if st.form_submit_button("Guardar Repartidor"):
                    if str(f_dni) in df_repartidores['DNI'].astype(str).values:
                        st.error("DNI ya registrado.")
                    elif f_nom and f_user and f_pla:
                        n_u = pd.DataFrame([{'Nombre': f_nom, 'Usuario': f_user, 'Clave': f_pass, 'DNI': f_dni, 'Celular': f_cel, 'Placa': f_pla, 'Bidones_Planta': 0, 'Estado': 'Activo'}])
                        df_repartidores = pd.concat([df_repartidores, n_u], ignore_index=True)
                        df_repartidores.to_excel("repartidores.xlsx", index=False)
                        st.success(f"Repartidor {f_nom} registrado.")
                        st.session_state['ultimo_registro'] = {'cel': f_cel, 'user': f_user, 'pass': f_pass, 'nom': f_nom}

            # BOTÓN DE NOTIFICACIÓN DE ALTA
            if 'ultimo_registro' in st.session_state:
                reg = st.session_state['ultimo_registro']
                msg_alta = f"Hola {reg['nom']}, has sido dado de ALTA en Agua Origen. Acceso: {URL_APP} | Usuario: {reg['user']} | Clave: {reg['pass']}"
                st.link_button(f"📲 Notificar ALTA a {reg['nom']}", f"https://wa.me/51{reg['cel']}?text={msg_alta.replace(' ', '%20')}")

            st.divider()
            st.subheader("Lista de Repartidores")
            for i, r in df_repartidores.iterrows():
                c_nom, c_est, c_acc = st.columns([3, 2, 2])
                c_nom.write(f"**{r['Nombre']}** ({r['Placa']})")
                c_est.write(f"Estado: {r['Estado']}")
                
                if r['Estado'] == 'Activo':
                    if c_acc.button("Dar de BAJA", key=f"baja_{i}"):
                        df_repartidores.at[i, 'Estado'] = 'Inactivo'
                        df_repartidores.to_excel("repartidores.xlsx", index=False)
                        msg_baja = f"Hola {r['Nombre']}, se te informa que has sido dado de BAJA en el sistema Agua Origen."
                        # Generamos el link de baja inmediatamente
                        st.warning(f"Baja procesada. Notifica al repartidor:")
                        st.link_button(f"📲 Notificar BAJA a {r['Nombre']}", f"https://wa.me/51{r['Celular']}?text={msg_baja.replace(' ', '%20')}")
                else:
                    if c_acc.button("Reactivar", key=f"alta_{i}"):
                        df_repartidores.at[i, 'Estado'] = 'Activo'
                        df_repartidores.to_excel("repartidores.xlsx", index=False)
                        st.rerun()

        with t2:
            st.subheader("Carga Planta")
            # ... (Lógica de carga planta sin cambios)

        with t3:
            st.subheader("Liquidación")
            # ... (Lógica de liquidación vinculada al repartidor responsable)
    else:
        st.error("Acceso administrador denegado.")