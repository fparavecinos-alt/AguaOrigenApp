import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
from PIL import Image
from streamlit_js_eval import get_geolocation

# 1. CONFIGURACIÓN Y LOGO
try:
    img = Image.open("logo.png")
except:
    img = None

st.set_page_config(page_title="Agua Origen - Sistema", page_icon="💧")

# 2. CARGA DE DATOS MEJORADA
def cargar_excel(archivo, columnas):
    if os.path.exists(archivo):
        try:
            return pd.read_excel(archivo)
        except:
            return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

df_ventas = cargar_excel("datos_agua.xlsx", ['Fecha', 'Cliente', 'Celular', 'Cantidad', 'Repartidor', 'Estado', 'Ubicacion'])
df_inv = cargar_excel("inventario.xlsx", ['Insumo', 'Cantidad_Actual'])
# Cargamos repartidores
df_repartidores = cargar_excel("repartidores.xlsx", ['Nombre', 'Usuario', 'Clave', 'DNI', 'Celular', 'Placa', 'Bidones_Planta', 'Estado'])

# 3. INTERFAZ LATERAL
if img:
    st.sidebar.image(img, width=100)
else:
    st.sidebar.title("💧 Agua Origen")

st.sidebar.markdown("---")
rol = st.sidebar.selectbox("Acceso de Usuario", ["Cliente (Pedidos)", "Repartidor", "Administrador"])
URL_APP = "https://agua-origen-tambopata.streamlit.app"

# --- PORTAL DEL CLIENTE ---
if rol == "Cliente (Pedidos)":
    st.header("💧 Realiza tu pedido - Agua Origen")
    with st.form("form_cliente"):
        nombre = st.text_input("Tu Nombre")
        celular_c = st.text_input("Número de Celular")
        cantidad = st.number_input("¿Cuántos bidones?", min_value=1, step=1)
        st.write("📍 Ubicación para la entrega:")
        loc = get_geolocation()
        enviar = st.form_submit_button("Confirmar Pedido")
        
        if enviar and nombre and celular_c and loc:
            coords = f"{loc['coords']['latitude']},{loc['coords']['longitude']}"
            repartidores_activos = df_repartidores[df_repartidores['Estado'] == 'Activo']['Nombre'].tolist()
            if repartidores_activos:
                pendientes = [len(df_ventas[(df_ventas['Repartidor'] == r) & (df_ventas['Estado'] == 'Pendiente')]) for r in repartidores_activos]
                asignado = repartidores_activos[pendientes.index(min(pendientes))]
                nuevo_p = pd.DataFrame([{'Fecha': datetime.now(), 'Cliente': nombre, 'Celular': celular_c, 'Cantidad': cantidad, 'Repartidor': asignado, 'Estado': 'Pendiente', 'Ubicacion': coords}])
                df_ventas = pd.concat([df_ventas, nuevo_p], ignore_index=True)
                df_ventas.to_excel("datos_agua.xlsx", index=False)
                st.success(f"¡Recibido! {asignado} va en camino.")

# --- PORTAL DEL REPARTIDOR (LOGIN CORREGIDO) ---
elif rol == "Repartidor":
    user_i = st.sidebar.text_input("Usuario")
    pass_i = st.sidebar.text_input("Contraseña", type="password")
    
    if user_i and pass_i:
        # Convertimos a string para evitar problemas de formato
        df_repartidores['Usuario'] = df_repartidores['Usuario'].astype(str)
        df_repartidores['Clave'] = df_repartidores['Clave'].astype(str)
        
        user_data = df_repartidores[(df_repartidores['Usuario'] == user_i) & (df_repartidores['Clave'] == pass_i)]
        
        if not user_data.empty:
            nombre_rep = user_data.iloc[0]['Nombre']
            st.header(f"🚚 Panel de {nombre_rep}")
            # ... (Métricas y pedidos igual que antes)
        else:
            st.error("❌ Usuario o contraseña incorrectos.")
    else:
        st.info("Por favor, ingresa tus credenciales.")

# --- PORTAL ADMINISTRADOR ---
elif rol == "Administrador":
    clave_adm = st.sidebar.text_input("Contraseña Maestra", type="password")
    if clave_adm == "admin123":
        t1, t2, t3 = st.tabs(["👥 Usuarios", "🏭 Planta", "💸 Liquidación"])
        
        with t1:
            st.subheader("Registrar Nuevo Repartidor")
            with st.form("alta"):
                f_nom = st.text_input("Nombre y Apellido")
                f_dni = st.text_input("DNI (8 dígitos)")
                f_cel = st.text_input("Celular")
                f_pla = st.text_input("Placa")
                f_user = st.text_input("Usuario")
                f_pass = st.text_input("Clave")
                if st.form_submit_button("Dar de Alta"):
                    # VALIDACIÓN DE DNI EXISTENTE
                    if f_dni in df_repartidores['DNI'].astype(str).values:
                        st.error(f"⚠️ El DNI {f_dni} ya está registrado.")
                    elif f_nom and f_user and f_dni:
                        nuevo = pd.DataFrame([{'Nombre': f_nom, 'Usuario': f_user, 'Clave': f_pass, 'DNI': f_dni, 'Celular': f_cel, 'Placa': f_pla, 'Bidones_Planta': 0, 'Estado': 'Activo'}])
                        df_repartidores = pd.concat([df_repartidores, nuevo], ignore_index=True)
                        df_repartidores.to_excel("repartidores.xlsx", index=False)
                        st.success("¡Registrado!")
                        # Link WhatsApp
                        msg = f"Acceso Agua Origen: {URL_APP} | Usuario: {f_user} | Clave: {f_pass}"
                        st.link_button("📲 Enviar por WhatsApp", f"https://wa.me/51{f_cel}?text={msg.replace(' ', '%20')}")
            st.dataframe(df_repartidores)