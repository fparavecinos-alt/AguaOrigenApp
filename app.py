import streamlit as st
import pandas as pd
from datetime import datetime
import os
from PIL import Image
from streamlit_js_eval import get_geolocation

# 1. CONFIGURACIÓN DE INTERFAZ
try:
    img = Image.open("logo.png")
except Exception:
    img = None

st.set_page_config(page_title="Agua Origen - Sistema", page_icon="💧", layout="wide")

# 2. CAPA DE DATOS CON MANEJO DE EXCEPCIONES
def cargar_excel(archivo, columnas):
    if os.path.exists(archivo):
        try:
            return pd.read_excel(archivo)
        except Exception:
            return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

# Carga inicial de bases de datos
df_ventas = cargar_excel("datos_agua.xlsx", ['Fecha', 'Cliente', 'Celular', 'Cantidad', 'Repartidor', 'Estado', 'Ubicacion'])
df_inv = cargar_excel("inventario.xlsx", ['Insumo', 'Cantidad_Actual'])
df_repartidores = cargar_excel("repartidores.xlsx", ['Nombre', 'Usuario', 'Clave', 'DNI', 'Celular', 'Placa', 'Bidones_Planta', 'Estado'])

# 3. NAVEGACIÓN
if img:
    st.sidebar.image(img, width=120)
else:
    st.sidebar.title("💧 Agua Origen")

st.sidebar.markdown("---")
rol = st.sidebar.selectbox("Acceso de Usuario", ["Cliente (Pedidos)", "Repartidor", "Administrador"])
URL_APP = "https://agua-origen-tambopata.streamlit.app"

# --- MÓDULO 1: PORTAL DEL CLIENTE ---
if rol == "Cliente (Pedidos)":
    st.header("💧 Realiza tu pedido - Agua Origen")
    with st.form("form_cliente", clear_on_submit=True):
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
                # Asignación automática por carga de trabajo
                pendientes_count = [len(df_ventas[(df_ventas['Repartidor'] == r) & (df_ventas['Estado'] == 'Pendiente')]) for r in repartidores_activos]
                asignado = repartidores_activos[pendientes_count.index(min(pendientes_count))]
                
                nuevo_p = pd.DataFrame([{'Fecha': datetime.now(), 'Cliente': nombre, 'Celular': celular, 'Cantidad': cantidad, 'Repartidor': asignado, 'Estado': 'Pendiente', 'Ubicacion': coords}])
                df_ventas = pd.concat([df_ventas, nuevo_p], ignore_index=True)
                df_ventas.to_excel("datos_agua.xlsx", index=False)
                st.success(f"¡Pedido recibido! El repartidor {asignado} te visitará pronto.")
            else:
                st.error("Lo sentimos, no hay repartidores activos disponibles.")

# --- MÓDULO 2: PORTAL DEL REPARTIDOR ---
elif rol == "Repartidor":
    st.sidebar.subheader("Login de Repartidor")
    u_i = st.sidebar.text_input("Usuario")
    p_i = st.sidebar.text_input("Contraseña", type="password")
    
    if u_i and p_i:
        user_match = df_repartidores[(df_repartidores['Usuario'].astype(str) == u_i) & (df_repartidores['Clave'].astype(str) == p_i)]
        
        if not user_match.empty:
            nombre_rep = user_match.iloc[0]['Nombre']
            st.header(f"🚚 Panel de {nombre_rep}")
            
            # Indicadores de gestión y responsabilidad
            entregados_total = df_ventas[(df_ventas['Repartidor'] == nombre_rep) & (df_ventas['Estado'] == 'Entregado')]['Cantidad'].sum()
            c1, c2 = st.columns(2)
            c1.metric("Bidones en Custodia (Planta)", f"{user_match.iloc[0]['Bidones_Planta']}")
            c2.metric("Bidones por Liquidar", f"{entregados_total}")

            st.subheader("📋 Mi Hoja de Ruta (Pendientes)")
            mis_pendientes = df_ventas[(df_ventas['Repartidor'] == nombre_rep) & (df_ventas['Estado'] == 'Pendiente')]
            
            if not mis_pendientes.empty:
                for idx, row in mis_pendientes.iterrows():
                    with st.expander(f"📍 Cliente: {row['Cliente']} | {row['Cantidad']} unidad(es)"):
                        st.write(f"📞 Contacto: {row['Celular']}")
                        
                        # ENLACE DE MAPS OPTIMIZADO PARA CELULARES
                        maps_url = f"https://www.google.com/maps/search/?api=1&query={row['Ubicacion']}"
                        st.link_button("🌐 Iniciar Navegación GPS", maps_url)
                        
                        st.markdown("---")
                        if st.button(f"✅ Marcar como Entregado", key=f"ent_btn_{idx}"):
                            # Actualización de estado y descuento de inventario
                            df_ventas.at[idx, 'Estado'] = 'Entregado'
                            df_ventas.to_excel("datos_agua.xlsx", index=False)
                            for ins in ['Tapas', 'Etiquetas', 'Precintos termo encogibles']:
                                df_inv.loc[df_inv['Insumo'] == ins, 'Cantidad_Actual'] -= row['Cantidad']
                            df_inv.to_excel("inventario.xlsx", index=False)
                            st.rerun()
            else:
                st.info("No tienes pedidos pendientes de entrega.")
        else:
            st.error("Credenciales de acceso incorrectas.")

# --- MÓDULO 3: ADMINISTRADOR ---
elif rol == "Administrador":
    clave_adm = st.sidebar.text_input("Clave Maestra", type="password")
    if clave_adm == "admin123":
        t1, t2, t3 = st.tabs(["👥 Repartidores", "🏭 Carga de Planta", "💸 Cierres"])
        
        with t1:
            st.subheader("Alta de Nuevo Repartidor")
            with st.form("registro_rep"):
                f_nom = st.text_input("Nombre y Apellido")
                f_dni = st.text_input("DNI")
                f_cel = st.text_input("Número de Celular")
                f_user = st.text_input("Usuario de Acceso")
                f_pass = st.text_input("Contraseña")
                if st.form_submit_button("Registrar Repartidor"):
                    # VALIDACIÓN DE DNI ÚNICO
                    if str(f_dni) in df_repartidores['DNI'].astype(str).values:
                        st.error("❌ Error: Este DNI ya está registrado.")
                    elif f_nom and f_user and f_dni:
                        n_u = pd.DataFrame([{'Nombre': f_nom, 'Usuario': f_user, 'Clave': f_pass, 'DNI': f_dni, 'Celular': f_cel, 'Bidones_Planta': 0, 'Estado': 'Activo'}])
                        df_repartidores = pd.concat([df_repartidores, n_u], ignore_index=True)
                        df_repartidores.to_excel("repartidores.xlsx", index=False)
                        st.success(f"Repartidor {f_nom} registrado correctamente.")
            st.dataframe(df_repartidores)

        with t2:
            st.subheader("Salida de Bidones Llenos")
            if not df_repartidores.empty:
                rep_sel = st.selectbox("Repartidor en Planta", df_repartidores['Nombre'].tolist())
                cant_salida = st.number_input("Cantidad de bidones cargados", min_value=1)
                if st.button("Confirmar Carga"):
                    df_repartidores.loc[df_repartidores['Nombre'] == rep_sel, 'Bidones_Planta'] += cant_salida
                    df_repartidores.to_excel("repartidores.xlsx", index=False)
                    st.success(f"Carga registrada para {rep_sel}.")

        with t3:
            st.subheader("Liquidación de Ventas y Retorno de Envases")
            for idx_r, r_row in df_repartidores.iterrows():
                v_nom = r_row['Nombre']
                por_liquidar = df_ventas[(df_ventas['Repartidor'] == v_nom) & (df_ventas['Estado'] == 'Entregado')]['Cantidad'].sum()
                if por_liquidar > 0:
                    st.warning(f"{v_nom} debe retornar {por_liquidar} envases vacíos.")
                    if st.button(f"Completar Liquidación de {v_nom}", key=f"liq_key_{idx_r}"):
                        # Cierre de ciclo: se asume responsabilidad de entrega y retorno
                        df_ventas.loc[(df_ventas['Repartidor'] == v_nom) & (df_ventas['Estado'] == 'Entregado'), 'Estado']