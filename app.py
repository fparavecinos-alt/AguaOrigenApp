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

# 3. INTERFAZ LATERAL (LIMPIA)
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
        st.write("📍 Necesitamos tu ubicación para la entrega:")
        loc = get_geolocation()
        enviar = st.form_submit_button("Confirmar Pedido")
        
        if enviar:
            if nombre and celular and loc:
                coords = f"{loc['coords']['latitude']},{loc['coords']['longitude']}"
                # ASIGNACIÓN ROUND ROBIN (Reparto equitativo)
                repartidores = ["Carlos R.", "Luis M."]
                pendientes = [len(df_ventas[(df_ventas['Repartidor'] == r) & (df_ventas['Estado'] == 'Pendiente')]) for r in repartidores]
                asignado = repartidores[pendientes.index(min(pendientes))]
                
                nuevo_p = pd.DataFrame([{
                    'Fecha': datetime.now(), 'Cliente': nombre, 'Celular': celular,
                    'Cantidad': cantidad, 'Repartidor': asignado, 'Estado': 'Pendiente', 'Ubicacion': coords
                }])
                df_ventas = pd.concat([df_ventas, nuevo_p], ignore_index=True)
                df_ventas.to_excel("datos_agua.xlsx", index=False)
                st.success(f"¡Pedido recibido! {asignado} te visitará pronto.")
            else:
                st.warning("Completa tus datos y activa el GPS.")

# --- PORTAL DEL REPARTIDOR (CLAVE: reparto2026) ---
elif rol == "Repartidor":
    clave = st.sidebar.text_input("Contraseña Repartidor", type="password")
    if clave == "reparto2026":
        st.header("🚚 Panel de Reparto")
        nombre_rep = st.selectbox("Selecciona tu nombre", ["Carlos R.", "Luis M."])
        mis_pedidos = df_ventas[(df_ventas['Repartidor'] == nombre_rep) & (df_ventas['Estado'] == 'Pendiente')]
        
        if not mis_pedidos.empty:
            for i, row in mis_pedidos.iterrows():
                with st.expander(f"Pedido: {row['Cliente']} ({row['Cantidad']} bidones)"):
                    st.link_button("📍 Ver en Google Maps", f"https://www.google.com/maps?q={row['Ubicacion']}")
                    msg = f"Hola {row['Cliente']}, soy {nombre_rep} de Agua Origen. ¡Tu pedido llegó! 💧"
                    st.link_button("📲 Avisar por WhatsApp", f"https://wa.me/51{row['Celular']}?text={msg.replace(' ', '%20')}")
                    
                    if st.button(f"✅ Confirmar Entrega #{i}"):
                        df_ventas.at[i, 'Estado'] = 'Entregado'
                        df_ventas.to_excel("datos_agua.xlsx", index=False)
                        # Descuento de insumos
                        for insumo in ['Tapas', 'Etiquetas', 'Precintos termo encogibles']:
                            df_inv.loc[df_inv['Insumo'] == insumo, 'Cantidad_Actual'] -= row['Cantidad']
                        df_inv.to_excel("inventario.xlsx", index=False)
                        st.rerun()
        else:
            st.info("No tienes rutas pendientes.")

# --- PORTAL ADMINISTRADOR (CLAVE: admin123) ---
elif rol == "Administrador":
    clave_adm = st.sidebar.text_input("Contraseña Maestra", type="password")
    if clave_adm == "admin123":
        st.header("⚙️ Control de Operaciones")
        
        # 1. Stock Insumos
        cols = st.columns(3)
        for idx, row in df_inv.iterrows():
            cols[idx].metric(row['Insumo'], f"{row['Cantidad_Actual']} un.")
        
        # 2. GESTIÓN DE REPARTIDORES Y LIQUIDACIÓN
        st.markdown("---")
        st.subheader("👥 Estado de Activos por Repartidor")
        repartidores_lista = ["Carlos R.", "Luis M."]
        
        for rep in repartidores_lista:
            # Envases en calle (Entregado pero no liquidado)
            pendientes = df_ventas[(df_ventas['Repartidor'] == rep) & (df_ventas['Estado'] == 'Entregado')]
            num_pendientes = pendientes['Cantidad'].sum()
            
            col_a, col_b = st.columns([2, 1])
            col_a.write(f"**{rep}** tiene **{num_pendientes}** bidones pendientes.")
            
            if num_pendientes > 0:
                if col_b.button(f"💸 Liquidar {rep}"):
                    df_ventas.loc[(df_ventas['Repartidor'] == rep) & (df_ventas['Estado'] == 'Entregado'), 'Estado'] = 'Completado'
                    df_ventas.to_excel("datos_agua.xlsx", index=False)
                    st.success(f"Cuentas cerradas para {rep}")
                    st.rerun()
        
        # 3. Alertas de Envases (+7 días)
        st.markdown("---")
        st.subheader("⚠️ Alertas de Retorno (+7 días)")
        limite = datetime.now() - timedelta(days=7)
        df_ventas['Fecha'] = pd.to_datetime(df_ventas['Fecha'])
        atrasados = df_ventas[(df_ventas['Fecha'] <= limite) & (df_ventas['Estado'] == 'Entregado')]
        if not atrasados.empty:
            st.warning("Los siguientes clientes tienen envases hace más de una semana:")
            st.dataframe(atrasados[['Fecha', 'Cliente', 'Repartidor', 'Cantidad']])
        else:
            st.success("No hay alertas de envases pendientes.")
    else:
        st.error("Acceso denegado.")