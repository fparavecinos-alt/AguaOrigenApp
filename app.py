import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
from PIL import Image
from streamlit_js_eval import streamlit_js_eval, get_geolocation

# 1. CONFIGURACIÓN Y LOGO
try:
    img = Image.open("logo.png")
except:
    img = None
st.set_page_config(page_title="Agua Origen - Sistema", page_icon=img if img else "💧")

# 2. CARGA DE DATOS
def cargar_excel(archivo, columnas):
    if os.path.exists(archivo):
        return pd.read_excel(archivo)
    return pd.DataFrame(columns=columnas)

df_ventas = cargar_excel("datos_agua.xlsx", ['Fecha', 'Cliente', 'Celular', 'Cantidad', 'Repartidor', 'Estado', 'Ubicacion'])
df_inv = cargar_excel("inventario.xlsx", ['Insumo', 'Cantidad_Actual'])

# 3. SISTEMA DE SEGURIDAD
# --- Lógica del Logo y Menú (Reemplazo de líneas 25 y 26) ---
if img:
    st.sidebar.image(img, width=100)
else:
    st.sidebar.title("💧 Agua Origen")

st.sidebar.markdown("---")
rol = st.sidebar.selectbox("Acceso de Usuario", ["Cliente (Pedidos)", "Repartidor", "Administrador"])

# --- PORTAL DEL CLIENTE (PÚBLICO) ---
if rol == "Cliente (Pedidos)":
    st.header("💧 Realiza tu pedido - Agua Origen")
    with st.form("form_cliente"):
        nombre = st.text_input("Tu Nombre")
        celular = st.text_input("Número de Celular (WhatsApp)")
        cantidad = st.number_input("¿Cuántos bidones necesitas?", min_value=1, step=1)
        
        st.write("📍 Para entregarte el pedido, necesitamos tu ubicación:")
        loc = get_geolocation()
        
        enviar = st.form_submit_button("Confirmar Pedido")
        
        if enviar:
            if nombre and celular and loc:
                coords = f"{loc['coords']['latitude']},{loc['coords']['longitude']}"
                # ASIGNACIÓN ROUND ROBIN (Al que tiene menos pedidos pendientes)
                repartidores = ["Carlos R.", "Luis M."] # Puedes editarlos aquí
                pendientes = [len(df_ventas[(df_ventas['Repartidor'] == r) & (df_ventas['Estado'] == 'Pendiente')]) for r in repartidores]
                asignado = repartidores[pendientes.index(min(pendientes))]
                
                nuevo_p = pd.DataFrame([{
                    'Fecha': datetime.now(), 'Cliente': nombre, 'Celular': celular,
                    'Cantidad': cantidad, 'Repartidor': asignado, 'Estado': 'Pendiente', 'Ubicacion': coords
                }])
                df_ventas = pd.concat([df_ventas, nuevo_p], ignore_index=True)
                df_ventas.to_excel("datos_agua.xlsx", index=False)
                st.success(f"¡Gracias {nombre}! Tu pedido ha sido asignado a {asignado}. Te avisaremos al llegar.")
            else:
                st.warning("Por favor rellena todos los datos y acepta el permiso de ubicación.")

# --- PORTAL DEL REPARTIDOR (CON CLAVE) ---
elif rol == "Repartidor":
    clave = st.sidebar.text_input("Contraseña Repartidor", type="password")
    if clave == "reparto2026":
        st.header("🚚 Tus Entregas Pendientes")
        nombre_rep = st.selectbox("Selecciona tu nombre", ["Carlos R.", "Luis M."])
        mis_pedidos = df_ventas[(df_ventas['Repartidor'] == nombre_rep) & (df_ventas['Estado'] == 'Pendiente')]
        
        if not mis_pedidos.empty:
            for i, row in mis_pedidos.iterrows():
                with st.expander(f"Pedido de {row['Cliente']} - {row['Cantidad']} bidones"):
                    # Botón Google Maps
                    maps_url = f"https://www.google.com/maps?q={row['Ubicacion']}"
                    st.link_button("📍 Ver ruta en Maps", maps_url)
                    
                    # Botón WhatsApp (Opción A)
                    msg = f"Hola {row['Cliente']}, soy {nombre_rep} de Agua Origen. ¡Tu pedido está en la puerta! 💧"
                    ws_url = f"https://wa.me/51{row['Celular']}?text={msg.replace(' ', '%20')}"
                    st.link_button("📲 Avisar por WhatsApp", ws_url)
                    
                    if st.button(f"Confirmar Entrega #{i}"):
                        df_ventas.at[i, 'Estado'] = 'Entregado'
                        df_ventas.to_excel("datos_agua.xlsx", index=False)
                        # Descuento de 3 insumos
                        df_inv.loc[df_inv['Insumo'] == 'Tapas', 'Cantidad_Actual'] -= row['Cantidad']
                        df_inv.loc[df_inv['Insumo'] == 'Etiquetas', 'Cantidad_Actual'] -= row['Cantidad']
                        df_inv.loc[df_inv['Insumo'] == 'Precintos termo encogibles', 'Cantidad_Actual'] -= row['Cantidad']
                        df_inv.to_excel("inventario.xlsx", index=False)
                        st.rerun()
        else:
            st.info("No tienes pedidos pendientes. ¡Buen trabajo!")
    else:
        st.error("Clave de repartidor incorrecta.")

# --- PORTAL ADMINISTRADOR (CON CLAVE) ---
elif rol == "Administrador":
    clave_adm = st.sidebar.text_input("Contraseña Maestra", type="password")
    if clave_adm == "admin123":
        st.header("⚙️ Panel de Control Administrativo")
        # Mostrar Métricas de Stock
        c1, c2, c3 = st.columns(3)
        for i, row in df_inv.iterrows():
            st.columns(3)[i].metric(row['Insumo'], f"{row['Cantidad_Actual']} un.")
        
        # Alerta Envases +7 días (Responsabilidad)
        st.subheader("⚠️ Alerta de Envases")
        limite = datetime.now() - timedelta(days=7)
        df_ventas['Fecha'] = pd.to_datetime(df_ventas['Fecha'])
        alertas = df_ventas[(df_ventas['Fecha'] <= limite) & (df_ventas['Estado'] == 'Entregado')]
        st.dataframe(alertas[['Fecha', 'Cliente', 'Repartidor']])
        
        st.subheader("📊 Historial General")
        st.dataframe(df_ventas)
    else:
        st.error("Clave de administrador incorrecta.")