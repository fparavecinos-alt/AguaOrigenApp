import streamlit as st
import pandas as pd
from datetime import datetime
import os
from PIL import Image
from streamlit_js_eval import get_geolocation

# 1. CONFIGURACIÓN INICIAL
try:
    img = Image.open("logo.png")
except:
    img = None

st.set_page_config(page_title="Agua Origen - Sistema", page_icon="💧", layout="wide")

# 2. GESTIÓN DE DATOS (PERSISTENCIA)
def cargar_excel(archivo, columnas):
    if os.path.exists(archivo):
        try:
            return pd.read_excel(archivo)
        except:
            return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

df_ventas = cargar_excel("datos_agua.xlsx", ['Fecha', 'Cliente', 'Celular', 'Cantidad', 'Repartidor', 'Estado', 'Ubicacion'])
df_inv = cargar_excel("inventario.xlsx", ['Insumo', 'Cantidad_Actual'])
df_repartidores = cargar_excel("repartidores.xlsx", ['Nombre', 'Usuario', 'Clave', 'DNI', 'Celular', 'Placa', 'Bidones_Planta', 'Estado'])

# 3. INTERFAZ LATERAL
if img:
    st.sidebar.image(img, width=120)
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
        celular_c = st.text_input("Número de Celular (WhatsApp)")
        cantidad = st.number_input("¿Cuántos bidones necesitas?", min_value=1, step=1)
        st.write("📍 Presiona para capturar tu ubicación actual:")
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
                st.success(f"¡Pedido recibido! El repartidor {asignado} te visitará pronto.")
            else:
                st.error("No hay repartidores activos en el sistema.")

# --- PORTAL DEL REPARTIDOR ---
elif rol == "Repartidor":
    st.sidebar.subheader("Inicio de Sesión")
    u_i = st.sidebar.text_input("Usuario")
    p_i = st.sidebar.text_input("Contraseña", type="password")
    
    if u_i and p_i:
        user_match = df_repartidores[(df_repartidores['Usuario'].astype(str) == u_i) & (df_repartidores['Clave'].astype(str) == p_i)]
        
        if not user_match.empty:
            nombre_rep = user_match.iloc[0]['Nombre']
            st.header(f"🚚 Panel de {nombre_rep}")
            
            # Métricas de control individual
            entregados_hoy = df_ventas[(df_ventas['Repartidor'] == nombre_rep) & (df_ventas['Estado'] == 'Entregado')]['Cantidad'].sum()
            c1, c2 = st.columns(2)
            c1.metric("Llevados de Planta", f"{user_match.iloc[0]['Bidones_Planta']}")
            c2.metric("Bidones por Devolver (Ventas)", f"{entregados_hoy}")

            st.subheader("📋 Mis Pedidos Pendientes")
            mis_pendientes = df_ventas[(df_ventas['Repartidor'] == nombre_rep) & (df_ventas['Estado'] == 'Pendiente')]
            
            if not mis_pendientes.empty:
                for idx, row in mis_pendientes.iterrows():
                    with st.expander(f"📍 Cliente: {row['Cliente']} - Cantidad: {row['Cantidad']}"):
                        st.write(f"📞 WhatsApp: {row['Celular']}")
                        # BOTÓN DE GOOGLE MAPS CORREGIDO
                        st.link_button("🌐 Ver Ubicación en Google Maps", f"https://www.google.com/maps?q={row['Ubicacion']}")
                        
                        st.markdown("---")
                        col_ok, col_no = st.columns(2)
                        if col_ok.button(f"✅ Marcar Entregado", key=f"btn_ent_{idx}"):
                            df_ventas.at[idx, 'Estado'] = 'Entregado'
                            df_ventas.to_excel("datos_agua.xlsx", index=False)
                            # Descuento de inventario automático
                            for ins in ['Tapas', 'Etiquetas', 'Precintos termo encogibles']:
                                df_inv.loc[df_inv['Insumo'] == ins, 'Cantidad_Actual'] -= row['Cantidad']
                            df_inv.to_excel("inventario.xlsx", index=False)
                            st.rerun()
                            
                        if col_no.button(f"❌ No se pudo entregar", key=f"btn_fail_{idx}"):
                            st.warning("El pedido permanece en lista como pendiente.")
            else:
                st.info("No tienes pedidos pendientes asignados.")
        else:
            st.error("Usuario o contraseña incorrectos.")
    else:
        st.info("Ingresa tus credenciales en el menú lateral para ver tu ruta.")

# --- PORTAL ADMINISTRADOR ---
elif rol == "Administrador":
    clave_adm = st.sidebar.text_input("Contraseña Maestra", type="password")
    if clave_adm == "admin123":
        t1, t2, t3 = st.tabs(["👥 Usuarios", "🏭 Carga Planta", "💸 Liquidación"])
        
        with t1:
            st.subheader("Registrar Repartidor")
            with st.form("alta_