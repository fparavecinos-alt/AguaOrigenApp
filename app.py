import streamlit as st
import pandas as pd
from datetime import datetime
import os
from PIL import Image
from streamlit_js_eval import get_geolocation

# 1. CONFIGURACIÓN E INTERFAZ
try:
    img = Image.open("logo.png")
except Exception:
    img = None

st.set_page_config(page_title="Agua Origen - Sistema", page_icon="💧", layout="wide")

# 2. CAPA DE DATOS (PERSISTENCIA EXCEL)
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

# 3. BARRA LATERAL (NAVEGACIÓN)
if img:
    st.sidebar.image(img, width=120)
else:
    st.sidebar.title("💧 Agua Origen")

st.sidebar.markdown("---")
rol = st.sidebar.selectbox("Acceso de Usuario", ["Cliente (Pedidos)", "Repartidor", "Administrador"])
URL_APP = "https://agua-origen-tambopata.streamlit.app"

# --- MÓDULO 1: CLIENTE (PÚBLICO) ---
if rol == "Cliente (Pedidos)":
    st.header("💧 Realiza tu pedido - Agua Origen")
    with st.form("form_cliente"):
        nombre = st.text_input("Tu Nombre")
        celular = st.text_input("Número de Celular (WhatsApp)")
        cantidad = st.number_input("¿Cuántos bidones necesitas?", min_value=1, step=1)
        st.write("📍 Captura tu ubicación para la entrega:")
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
                st.success(f"¡Pedido recibido! El repartidor {asignado} te visitará pronto.")
            else:
                st.error("No hay repartidores activos disponibles.")

# --- MÓDULO 2: REPARTIDOR (PRIVADO) ---
elif rol == "Repartidor":
    u_i = st.sidebar.text_input("Usuario")
    p_i = st.sidebar.text_input("Contraseña", type="password")
    
    if u_i and p_i:
        user_match = df_repartidores[(df_repartidores['Usuario'].astype(str) == u_i) & (df_repartidores['Clave'].astype(str) == p_i)]
        
        if not user_match.empty:
            nombre_rep = user_match.iloc[0]['Nombre']
            st.header(f"🚚 Panel de {nombre_rep}")
            
            entregados = df_ventas[(df_ventas['Repartidor'] == nombre_rep) & (df_ventas['Estado'] == 'Entregado')]['Cantidad'].sum()
            c1, c2 = st.columns(2)
            c1.metric("Llevados de Planta", f"{user_match.iloc[0]['Bidones_Planta']}")
            c2.metric("Bidones por Liquidar", f"{entregados}")

            st.subheader("📋 Pedidos Pendientes")
            mis_pendientes = df_ventas[(df_ventas['Repartidor'] == nombre_rep) & (df_ventas['Estado'] == 'Pendiente')]
            
            if not mis_pendientes.empty:
                for idx, row in mis_pendientes.iterrows():
                    with st.expander(f"📍 Cliente: {row['Cliente']} ({row['Cantidad']} bidones)"):
                        st.write(f"📞 WhatsApp: {row['Celular']}")
                        
                        # CORRECCIÓN PARA GOOGLE MAPS EN CELULARES
                        maps_url = f"https://www.google.com/maps/search/?api=1&query={row['Ubicacion']}"
                        st.link_button("🌐 Ver en Google Maps (GPS)", maps_url)
                        
                        st.markdown("---")
                        if st.button(f"✅ Confirmar Entrega", key=f"ok_{idx}"):
                            df_ventas.at[idx, 'Estado'] = 'Entregado'
                            df_ventas.to_excel("datos_agua.xlsx", index=False)
                            for ins in ['Tapas', 'Etiquetas', 'Precintos termo encogibles']:
                                df_inv.loc[df_inv['Insumo'] == ins, 'Cantidad_Actual'] -= row['Cantidad']
                            df_inv.to_excel("inventario.xlsx", index=False)
                            st.rerun()
            else:
                st.