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

# Inicialización con columnas completas (incluyendo Placa)
df_ventas = cargar_excel("datos_agua.xlsx", ['Fecha', 'Cliente', 'Celular', 'Cantidad', 'Repartidor', 'Estado', 'Ubicacion'])
df_inv = cargar_excel("inventario.xlsx", ['Insumo', 'Cantidad_Actual'])
df_repartidores = cargar_excel("repartidores.xlsx", ['Nombre', 'Usuario', 'Clave', 'DNI', 'Celular', 'Placa', 'Bidones_Planta', 'Estado'])

# 3. NAVEGACIÓN LATERAL
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
                pendientes_count = [len(df_ventas[(df_ventas['Repartidor'] == r) & (df_ventas['Estado'] == 'Pendiente')]) for r in repartidores_activos]
                asignado = repartidores_activos[pendientes_count.index(min(pendientes_count))]
                
                nuevo_p = pd.DataFrame([{'Fecha': datetime.now(), 'Cliente': nombre, 'Celular': celular, 'Cantidad': cantidad, 'Repartidor': asignado, 'Estado': 'Pendiente', 'Ubicacion': coords}])
                df_ventas = pd.concat([df_ventas, nuevo_p], ignore_index=True)
                df_ventas.to_excel("datos_agua.xlsx", index=False)
                st.success(f"¡Pedido recibido! El repartidor {asignado} te visitará pronto.")
            else:
                st.error("No hay repartidores activos disponibles.")

# --- MÓDULO 2: PORTAL DEL REPARTIDOR ---
elif rol == "Repartidor":
    st.sidebar.subheader("Acceso Repartidor")
    u_i = st.sidebar.text_input("Usuario")
    p_i = st.sidebar.text_input("Contraseña", type="password")
    
    if u_i and p_i:
        user_match = df_repartidores[(df_repartidores['Usuario'].astype(str) == u_i) & (df_repartidores['Clave'].astype(str) == p_i)]
        
        if not user_match.empty:
            nombre_rep = user_match.iloc[0]['Nombre']
            placa_rep = user_match.iloc[0]['Placa']
            st.header(f"🚚 Panel de {nombre_rep} (Placa: {placa_rep})")
            
            entregados_total = df_ventas[(df_ventas['Repartidor'] == nombre_rep) & (df_ventas['Estado'] == 'Entregado')]['Cantidad'].sum()
            c1, c2 = st.columns(2)
            c1.metric("Bidones en Custodia", f"{user_match.iloc[0]['Bidones_Planta']}")
            c2.metric("Bidones por Liquidar", f"{entregados_total}")

            st.subheader("📋 Pedidos Asignados")
            mis_pendientes = df_ventas[(df_ventas['Repartidor'] == nombre_rep) & (df_ventas['Estado'] == 'Pendiente')]
            
            if not mis_pendientes.empty:
                for idx, row in mis_pendientes.iterrows():
                    with st.expander(f"📍 Cliente: {row['Cliente']} | {row['Cantidad']} Bidón(es)"):
                        st.write(f"📞 WhatsApp: {row['Celular']}")
                        # URL de Maps optimizada para celulares
                        maps_url = f"https://www.google.com/maps/search/?api=1&query={row['Ubicacion']}"
                        st.link_button("🌐 Abrir GPS (Google Maps)", maps_url)
                        
                        st.markdown("---")
                        if st.button(f"✅ Marcar como Entregado", key=f"ent_{idx}"):
                            df_ventas.at[idx, 'Estado'] = 'Entregado'
                            df_ventas.to_excel("datos_agua.xlsx", index=False)
                            for ins in ['Tapas', 'Etiquetas', 'Precintos termo encogibles']:
                                df_inv.loc[df_inv['Insumo'] == ins, 'Cantidad_Actual'] -= row['Cantidad']
                            df_inv.to_excel("inventario.xlsx", index=False)
                            st.rerun()
            else:
                st.info("Sin pedidos pendientes.")
        else:
            st.error("Credenciales incorrectas.")

# --- MÓDULO 3: PORTAL ADMINISTRADOR ---
elif rol == "Administrador":
    clave_adm = st.sidebar.text_input("Clave Maestra", type="password")
    if clave_adm == "admin123":
        t1, t2, t3 = st.tabs(["👥 Repartidores", "🏭 Planta", "💸 Liquidación"])
        
        with t1:
            st.subheader("Registrar Nuevo Repartidor")
            with st.form("registro_profesional"):
                col_a, col_b = st.columns(2)
                f_nom = col_a.text_input("Nombre y Apellido")
                f_dni = col_b.text_input("DNI")
                f_cel = col_a.text_input("Celular")
                f_pla = col_b.text_input("Placa del Vehículo") # CAMPO PLACA AÑADIDO
                f_user = col_a.text_input("Usuario")
                f_pass = col_b.text_input("Contraseña")
                
                if st.form_submit_button("Guardar Repartidor"):
                    if str(f_dni) in df_repartidores['DNI'].astype(str).values:
                        st.error("❌ El DNI ya existe.")
                    elif f_nom and f_user and f_pla:
                        n_u = pd.DataFrame([{'Nombre': f_nom, 'Usuario': f_user, 'Clave': f_pass, 'DNI': f_dni, 'Celular': f_cel, 'Placa': f_pla, 'Bidones_Planta': 0, 'Estado': 'Activo'}])
                        df_repartidores = pd.concat([df_repartidores, n_u], ignore_index=True)
                        df_repartidores.to_excel("repartidores.xlsx", index=False)
                        st.success(f"Repartidor {f_nom} registrado.")
            st.dataframe(df_repartidores)

        with t2:
            st.subheader("Salida de Carga")
            if not df_repartidores.empty:
                rep_sel = st.selectbox("Elegir Repartidor", df_repartidores['Nombre'].tolist())
                cant_sal = st.number_input("Cantidad de bidones", min_value=1)
                if st.button("Registrar Salida de Planta"):
                    df_repartidores.loc[df_repartidores['Nombre'] == rep_sel, 'Bidones_Planta'] += cant_sal
                    df_repartidores.to_excel("repartidores.xlsx", index=False)
                    st.success("Carga guardada.")

        with t3:
            st.subheader("Cierre y Control de Envases")
            for idx_r, r_row in df_repartidores.iterrows():
                v_nom = r_row['Nombre']
                deuda = df_ventas[(df_ventas['Repartidor'] == v_nom) & (df_ventas['Estado'] == 'Entregado')]['Cantidad'].sum()
                if deuda > 0:
                    st.warning(f"{v_nom} debe retornar {deuda} envases.")
                    if st.button(f"Liquidar {v_nom}", key=f"liq_{idx_r}"):
                        df_ventas.loc[(df_ventas['Repartidor'] == v_nom) & (df_ventas['Estado'] == 'Entregado'), 'Estado'] = 'Completado'
                        df_ventas.to_excel("datos_agua.xlsx", index=False)
                        df_repartidores.at[idx_r, 'Bidones_Planta'] = 0
                        df_repartidores.to_excel("repartidores.xlsx", index=False)
                        st.rerun()
    else:
        st.error("Acceso denegado.")