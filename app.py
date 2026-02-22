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
                st.success(f"¡Pedido recibido! {asignado} te visitará pronto.")

# --- PORTAL DEL REPARTIDOR (CORREGIDO PARA MOSTRAR PEDIDOS) ---
elif rol == "Repartidor":
    u_i = st.sidebar.text_input("Usuario")
    p_i = st.sidebar.text_input("Contraseña", type="password")
    
    if u_i and p_i:
        user_data = df_repartidores[(df_repartidores['Usuario'].astype(str) == u_i) & (df_repartidores['Clave'].astype(str) == p_i)]
        
        if not user_data.empty:
            nombre_rep = user_data.iloc[0]['Nombre']
            st.header(f"🚚 Panel de {nombre_rep}")
            
            # Métricas rápidas
            entregados = df_ventas[(df_ventas['Repartidor'] == nombre_rep) & (df_ventas['Estado'] == 'Entregado')]['Cantidad'].sum()
            c1, c2 = st.columns(2)
            c1.metric("Llevados de Planta", f"{user_data.iloc[0]['Bidones_Planta']}")
            c2.metric("Bidones por Devolver", f"{entregados}")

            st.subheader("📋 Mis Pedidos Pendientes")
            mis_pendientes = df_ventas[(df_ventas['Repartidor'] == nombre_rep) & (df_ventas['Estado'] == 'Pendiente')]
            
            if not mis_pendientes.empty:
                for i, row in mis_pendientes.iterrows():
                    with st.expander(f"📍 Cliente: {row['Cliente']} ({row['Cantidad']} bidones)"):
                        st.write(f"📞 Celular: {row['Celular']}")
                        
                        # Botones de Acción
                        col_gps, col_wa = st.columns(2)
                        col_gps.link_button("🌐 Ver en Google Maps", f"https://www.google.com/maps?q={row['Ubicacion']}")
                        msg_wa = f"Hola {row['Cliente']}, soy {nombre_rep} de Agua Origen. Estoy cerca con tu pedido."
                        col_wa.link_button("📲 Avisar por WhatsApp", f"https://wa.me/51{row['Celular']}?text={msg_wa.replace(' ', '%20')}")
                        
                        st.markdown("---")
                        col1, col2 = st.columns(2)
                        if col1.button(f"✅ Marcar Entregado #{i}", key=f"ent_{i}"):
                            df_ventas.at[i, 'Estado'] = 'Entregado'
                            df_ventas.to_excel("datos_agua.xlsx", index=False)
                            # Descuento automático de stock
                            for ins in ['Tapas', 'Etiquetas', 'Precintos termo encogibles']:
                                df_inv.loc[df_inv['Insumo'] == ins, 'Cantidad_Actual'] -= row['Cantidad']
                            df_inv.to_excel("inventario.xlsx", index=False)
                            st.success("¡Entrega confirmada!")
                            st.rerun()
                            
                        if col2.button(f"❌ No Entregado #{i}", key=f"no_ent_{i}"):
                            # Se mantiene en pendiente o se puede crear un estado 'Fallido'
                            st.warning("Pedido marcado como no entregado.")
            else:
                st.info("No tienes pedidos asignados por ahora. ¡Buen trabajo!")
        else:
            st.error("Credenciales incorrectas.")

# --- PORTAL ADMINISTRADOR (Se mantiene igual) ---
elif rol == "Administrador":
    # ... (El código de Administrador que ya tienes funcionando)