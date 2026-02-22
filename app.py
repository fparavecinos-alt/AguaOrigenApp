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
        return pd.read_excel(archivo)
    return pd.DataFrame(columns=columnas)

df_ventas = cargar_excel("datos_agua.xlsx", ['Fecha', 'Cliente', 'Celular', 'Cantidad', 'Repartidor', 'Estado', 'Ubicacion'])
df_inv = cargar_excel("inventario.xlsx", ['Insumo', 'Cantidad_Actual'])
# Nueva tabla para usuarios
df_repartidores = cargar_excel("repartidores.xlsx", ['Nombre', 'DNI', 'Celular', 'Placa', 'Estado'])

# 3. INTERFAZ LATERAL
if img:
    st.sidebar.image(img, width=100)
else:
    st.sidebar.title("💧 Agua Origen")

st.sidebar.markdown("---")
rol = st.sidebar.selectbox("Acceso de Usuario", ["Cliente (Pedidos)", "Repartidor", "Administrador"])

# Obtener lista de repartidores activos para el sistema
repartidores_activos = df_repartidores[df_repartidores['Estado'] == 'Activo']['Nombre'].tolist()
if not repartidores_activos:
    repartidores_activos = ["Sin repartidores"]

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
            # ASIGNACIÓN ROUND ROBIN
            pendientes = [len(df_ventas[(df_ventas['Repartidor'] == r) & (df_ventas['Estado'] == 'Pendiente')]) for r in repartidores_activos]
            asignado = repartidores_activos[pendientes.index(min(pendientes))]
            
            nuevo_p = pd.DataFrame([{'Fecha': datetime.now(), 'Cliente': nombre, 'Celular': celular_c, 'Cantidad': cantidad, 'Repartidor': asignado, 'Estado': 'Pendiente', 'Ubicacion': coords}])
            df_ventas = pd.concat([df_ventas, nuevo_p], ignore_index=True)
            df_ventas.to_excel("datos_agua.xlsx", index=False)
            st.success(f"¡Pedido recibido! {asignado} te visitará pronto.")

# --- PORTAL DEL REPARTIDOR (CLAVE: reparto2026) ---
elif rol == "Repartidor":
    clave = st.sidebar.text_input("Contraseña Repartidor", type="password")
    if clave == "reparto2026":
        st.header("🚚 Panel de Reparto")
        nombre_rep = st.selectbox("Tu Nombre", repartidores_activos)
        mis_pedidos = df_ventas[(df_ventas['Repartidor'] == nombre_rep) & (df_ventas['Estado'] == 'Pendiente')]
        
        for i, row in mis_pedidos.iterrows():
            with st.expander(f"Pedido: {row['Cliente']}"):
                st.link_button("📍 Ver Maps", f"http://google.com/maps?q={row['Ubicacion']}")
                msg = f"Hola {row['Cliente']}, soy {nombre_rep} de Agua Origen. ¡Tu pedido llegó! 💧"
                st.link_button("📲 WhatsApp", f"https://wa.me/51{row['Celular']}?text={msg.replace(' ', '%20')}")
                if st.button(f"✅ Entregado #{i}"):
                    df_ventas.at[i, 'Estado'] = 'Entregado'
                    df_ventas.to_excel("datos_agua.xlsx", index=False)
                    for ins in ['Tapas', 'Etiquetas', 'Precintos termo encogibles']:
                        df_inv.loc[df_inv['Insumo'] == ins, 'Cantidad_Actual'] -= row['Cantidad']
                    df_inv.to_excel("inventario.xlsx", index=False)
                    st.rerun()

# --- PORTAL ADMINISTRADOR (CLAVE: admin123) ---
elif rol == "Administrador":
    clave_adm = st.sidebar.text_input("Contraseña Maestra", type="password")
    if clave_adm == "admin123":
        tab1, tab2, tab3 = st.tabs(["📊 Stock y Alertas", "👥 Gestión de Usuarios", "💸 Liquidación"])
        
        with tab1:
            st.subheader("Insumos Actuales")
            cols = st.columns(3)
            for idx, row in df_inv.iterrows():
                cols[idx].metric(row['Insumo'], f"{row['Cantidad_Actual']} un.")
            
            st.subheader("⚠️ Alertas (+7 días)")
            limite = datetime.now() - timedelta(days=7)
            df_ventas['Fecha'] = pd.to_datetime(df_ventas['Fecha'])
            atrasados = df_ventas[(df_ventas['Fecha'] <= limite) & (df_ventas['Estado'] == 'Entregado')]
            st.dataframe(atrasados[['Fecha', 'Cliente', 'Repartidor', 'Cantidad']])

        with tab2:
            st.subheader("Registrar Nuevo Repartidor")
            with st.form("nuevo_usuario"):
                n_nom = st.text_input("Nombre y Apellido")
                n_dni = st.text_input("DNI")
                n_cel = st.text_input("Celular")
                n_pla = st.text_input("Placa de moto")
                if st.form_submit_button("Dar de Alta"):
                    n_user = pd.DataFrame([{'Nombre': n_nom, 'DNI': n_dni, 'Celular': n_cel, 'Placa': n_pla, 'Estado': 'Activo'}])
                    df_repartidores = pd.concat([df_repartidores, n_user], ignore_index=True)
                    df_repartidores.to_excel("repartidores.xlsx", index=False)
                    st.success(f"Repartidor {n_nom} registrado con éxito.")
            st.dataframe(df_repartidores)

        with tab3:
            st.subheader("Cierre de Cuentas")
            for rep in repartidores_activos:
                pend = df_ventas[(df_ventas['Repartidor'] == rep) & (df_ventas['Estado'] == 'Entregado')]['Cantidad'].sum()
                c1, c2 = st.columns([2,1])
                c1.write(f"**{rep}** debe **{pend}** bidones.")
                if pend > 0 and c2.button(f"Liquidar {rep}"):
                    df_ventas.loc[(df_ventas['Repartidor'] == rep) & (df_ventas['Estado'] == 'Entregado'), 'Estado'] = 'Completado'
                    df_ventas.to_excel("datos_agua.xlsx", index=False)
                    st.rerun()