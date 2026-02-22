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

# URL de tu App para los mensajes de WhatsApp
URL_APP = "https://agua-origen-tambopata.streamlit.app"

# --- PORTAL DEL CLIENTE (PÚBLICO) ---
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
                # Reparto equitativo (Round Robin)
                pendientes = [len(df_ventas[(df_ventas['Repartidor'] == r) & (df_ventas['Estado'] == 'Pendiente')]) for r in repartidores_activos]
                asignado = repartidores_activos[pendientes.index(min(pendientes))]
                nuevo_p = pd.DataFrame([{'Fecha': datetime.now(), 'Cliente': nombre, 'Celular': celular_c, 'Cantidad': cantidad, 'Repartidor': asignado, 'Estado': 'Pendiente', 'Ubicacion': coords}])
                df_ventas = pd.concat([df_ventas, nuevo_p], ignore_index=True)
                df_ventas.to_excel("datos_agua.xlsx", index=False)
                st.success(f"¡Pedido recibido! {asignado} te visitará pronto.")
            else:
                st.error("No hay repartidores activos en este momento.")

# --- PORTAL DEL REPARTIDOR (INDIVIDUAL) ---
elif rol == "Repartidor":
    user_input = st.sidebar.text_input("Usuario")
    pass_input = st.sidebar.text_input("Contraseña", type="password")
    user_data = df_repartidores[(df_repartidores['Usuario'] == user_input) & (df_repartidores['Clave'] == pass_input)]
    
    if not user_data.empty:
        nombre_rep = user_data.iloc[0]['Nombre']
        st.header(f"🚚 Panel de {nombre_rep}")
        
        entregados_hoy = df_ventas[(df_ventas['Repartidor'] == nombre_rep) & (df_ventas['Estado'] == 'Entregado')]['Cantidad'].sum()
        c1, c2 = st.columns(2)
        c1.metric("Llevados de Planta", f"{user_data.iloc[0]['Bidones_Planta']}")
        c2.metric("Bidones por Devolver", f"{entregados_hoy}")

        mis_pendientes = df_ventas[(df_ventas['Repartidor'] == nombre_rep) & (df_ventas['Estado'] == 'Pendiente')]
        for i, row in mis_pendientes.iterrows():
            with st.expander(f"Pedido: {row['Cliente']}"):
                st.link_button("📍 Abrir GPS", f"https://www.google.com/maps?q={row['Ubicacion']}")
                msg = f"Hola {row['Cliente']}, soy {nombre_rep} de Agua Origen. ¡Tu pedido llegó! 💧"
                st.link_button("📲 Avisar WhatsApp", f"https://wa.me/51{row['Celular']}?text={msg.replace(' ', '%20')}")
                if st.button(f"✅ Entregado #{i}"):
                    df_ventas.at[i, 'Estado'] = 'Entregado'
                    df_ventas.to_excel("datos_agua.xlsx", index=False)
                    for ins in ['Tapas', 'Etiquetas', 'Precintos termo encogibles']:
                        df_inv.loc[df_inv['Insumo'] == ins, 'Cantidad_Actual'] -= row['Cantidad']
                    df_inv.to_excel("inventario.xlsx", index=False)
                    st.rerun()
    else:
        st.info("Ingresa tus credenciales en el menú lateral.")

# --- PORTAL ADMINISTRADOR (CLAVE: admin123) ---
elif rol == "Administrador":
    clave_adm = st.sidebar.text_input("Contraseña Maestra", type="password")
    if clave_adm == "admin123":
        t1, t2, t3 = st.tabs(["👥 Gestión de Usuarios", "🏭 Carga Planta", "💸 Liquidación"])
        
        with t1:
            st.subheader("Registrar Nuevo Repartidor")
            with st.form("alta_rep"):
                f_nom = st.text_input("Nombre y Apellido")
                f_dni = st.text_input("DNI")
                f_cel = st.text_input("Celular")
                f_pla = st.text_input("Placa de Moto")
                f_user = st.text_input("Usuario de Acceso")
                f_pass = st.text_input("Contraseña")
                submitted = st.form_submit_button("Dar de Alta")
                
                if submitted and f_nom and f_user:
                    nuevo = pd.DataFrame([{'Nombre': f_nom, 'Usuario': f_user, 'Clave': f_pass, 'DNI': f_dni, 'Celular': f_cel, 'Placa': f_pla, 'Bidones_Planta': 0, 'Estado': 'Activo'}])
                    df_repartidores = pd.concat([df_repartidores, nuevo], ignore_index=True)
                    df_repartidores.to_excel("repartidores.xlsx", index=False)
                    st.success(f"Repartidor {f_nom} guardado.")
                    
                    msg_cred = f"Bienvenido a Agua Origen. Accede aquí: {URL_APP} | Usuario: {f_user} | Clave: {f_pass}"
                    ws_url = f"https://wa.me/51{f_cel}?text={msg_cred.replace(' ', '%20')}"
                    st.link_button("📲 Enviar Acceso por WhatsApp", ws_url)
            st.dataframe(df_repartidores)
            
        with t2:
            st.subheader("Salida de Bidones (Planta)")
            if not df_repartidores.empty:
                rep_sel = st.selectbox("Seleccionar Repartidor", df_repartidores['Nombre'].tolist())
                cant_p = st.number_input("Cantidad de bidones cargados", min_value=1)
                if st.button("Registrar Carga en Planta"):
                    df_repartidores.loc[df_repartidores['Nombre'] == rep_sel, 'Bidones_Planta'] += cant_p
                    df_repartidores.to_excel("repartidores.xlsx", index=False)
                    st.success(f"Carga registrada para {rep_sel}")

        with t3:
            st.subheader("Cierre y Liquidación")
            repartidores_activos = df_repartidores[df_repartidores['Estado'] == 'Activo']['Nombre'].tolist()
            for rep in repartidores_activos:
                deuda = df_ventas[(df_ventas['Repartidor'] == rep) & (df_ventas['Estado'] == 'Entregado')]['Cantidad'].sum()
                c1, c2 = st.columns([2,1])
                c1.write(f"**{rep}** debe **{deuda}** bidones.")
                if deuda > 0:
                    if c2.button(f"Liquidar {rep}"):
                        df_ventas.loc[(df_ventas['Repartidor'] == rep) & (df_ventas['Estado'] == 'Entregado'), 'Estado'] = 'Completado'
                        df_ventas.to_excel("datos_agua.xlsx", index=False)
                        df_repartidores.loc[df_repartidores['Nombre'] == rep, 'Bidones_Planta'] = 0
                        df_repartidores.to_excel("repartidores.xlsx", index=False)
                        st.rerun()
    else:
        st.error("Acceso denegado.")