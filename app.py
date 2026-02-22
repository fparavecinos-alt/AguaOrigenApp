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

# 2. CARGA DE DATOS
def cargar_excel(archivo, columnas):
    if os.path.exists(archivo):
        return pd.read_excel(archivo)
    return pd.DataFrame(columns=columnas)

df_ventas = cargar_excel("datos_agua.xlsx", ['Fecha', 'Cliente', 'Celular', 'Cantidad', 'Repartidor', 'Estado', 'Ubicacion'])
df_inv = cargar_excel("inventario.xlsx", ['Insumo', 'Cantidad_Actual'])
df_repartidores = cargar_excel("repartidores.xlsx", ['Nombre', 'Usuario', 'Clave', 'DNI', 'Celular', 'Placa', 'Bidones_Planta', 'Estado'])

# 3. INTERFAZ LATERAL
if img:
    st.sidebar.image(img, width=100)
else:
    st.sidebar.title("💧 Agua Origen")

st.sidebar.markdown("---")
rol = st.sidebar.selectbox("Acceso de Usuario", ["Cliente (Pedidos)", "Repartidor", "Administrador"])

# URL de tu App (Ajústala si cambia)
URL_APP = "https://agua-origen-tambopata.streamlit.app"

# --- PORTAL DEL CLIENTE ---
if rol == "Cliente (Pedidos)":
    st.header("💧 Realiza tu pedido - Agua Origen")
    with st.form("form_cliente"):
        nombre = st.text_input("Tu Nombre")
        celular_c = st.text_input("Número de Celular")
        cantidad = st.number_input("¿Cuántos bidones necesitas?", min_value=1, step=1)
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
                st.success(f"¡Pedido recibido! {asignado} te visitará pronto.")

# --- PORTAL DEL REPARTIDOR (INDIVIDUAL) ---
elif rol == "Repartidor":
    user_input = st.sidebar.text_input("Usuario")
    pass_input = st.sidebar.text_input("Contraseña", type="password")
    user_data = df_repartidores[(df_repartidores['Usuario'] == user_input) & (df_repartidores['Clave'] == pass_input)]
    
    if not user_data.empty:
        nombre_rep = user_data.iloc[0]['Nombre']
        st.header(f"🚚 Panel de {nombre_rep}")
        
        # Métricas individuales basadas en entregas y recojo de planta
        entregados_hoy = df_ventas[(df_ventas['Repartidor'] == nombre_rep) & (df_ventas['Estado'] == 'Entregado')]['Cantidad'].sum()
        c1, c2 = st.columns(2)
        c1.metric("Llevados de Planta", f"{user_data.iloc[0]['Bidones_Planta']}")
        c2.metric("Bidones por Devolver", f"{entregados_hoy}")

        mis_pendientes = df_ventas[(df_ventas['Repartidor'] == nombre_rep) & (df_ventas['Estado'] == 'Pendiente')]
        for i, row in mis_pendientes.iterrows():
            with st.expander(f"Pedido: {row['Cliente']}"):
                st.link_button("📍 Abrir GPS", f"http://googleusercontent.com/maps.google.com/3{row['Ubicacion']}")
                if st.button(f"✅ Entregado #{i}"):
                    df_ventas.at[i, 'Estado'] = 'Entregado'
                    df_ventas.to_excel("datos_agua.xlsx", index=False)
                    st.rerun()
    else:
        st.info("Ingresa tus credenciales en el menú lateral.")

# --- PORTAL ADMINISTRADOR (CLAVE: admin123) ---
elif rol == "Administrador":
    clave_adm = st.sidebar.text_input("Contraseña Maestra", type="password")
    if clave_adm == "admin123":
        t1, t2, t3 = st.tabs(["👥 Gestión de Usuarios", "🏭 Carga Planta", "💸