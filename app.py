import streamlit as st
import pandas as pd
import os, urllib.parse
from datetime import datetime
from PIL import Image
from streamlit_js_eval import get_geolocation
from fpdf import FPDF

# 1. CONFIGURACIÓN E IDENTIDAD VISUAL
st.set_page_config(page_title="Agua Origen - Sistema Profesional", layout="wide")

# Restauración del Logotipo
if os.path.exists("logo.png"):
    st.sidebar.image("logo.png", width=200)

def cargar_db(archivo, columnas):
    if os.path.exists(archivo):
        try:
            return pd.read_excel(archivo)
        except Exception:
            return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

# Carga de datos asegurando consistencia
df_v = cargar_db("datos_agua.xlsx", ['Fecha', 'Cliente', 'Celular', 'Cantidad', 'Repartidor', 'Estado', 'Ubicacion'])
df_r = cargar_db("repartidores.xlsx", ['Nombre', 'Usuario', 'Clave', 'DNI', 'Celular', 'Placa', 'Bidones_Planta', 'Estado'])
df_a = cargar_db("alertas_envases.xlsx", ['Fecha', 'Repartidor', 'Cliente', 'Esperados', 'Recibidos', 'Faltante', 'Estado'])

# 2. NAVEGACIÓN
rol = st.sidebar.selectbox("Módulo de Acceso", ["Cliente (Pedidos)", "Repartidor", "Administrador"])

# --- MÓDULO CLIENTE ---
if rol == "Cliente (Pedidos)":
    st.header("💧 Solicita tu pedido")
    with st.form("form_pedido", clear_on_submit=True):
        col1, col2 = st.columns(2)
        n = col1.text_input("Tu Nombre")
        c = col2.text_input("WhatsApp (Ej: 987654321)")
        cant = st.number_input("¿Cuántos bidones?", min_value=1, value=1)
        loc = get_geolocation()
        
        if st.form_submit_button("Confirmar Pedido"):
            if n and c and loc:
                activos = df_r[df_r['Estado'] == 'Activo']['Nombre'].tolist()
                rep_asig = activos[0] if activos else "Pendiente"
                coords = f"{loc['coords']['latitude']},{loc['coords']['longitude']}"
                
                nuevo_p = pd.DataFrame([{'Fecha': datetime.now(), 'Cliente': n, 'Celular': c, 'Cantidad': cant, 'Repartidor': rep_asig, 'Estado': 'Pendiente', 'Ubicacion': coords}])
                df_v = pd.concat([df_v, nuevo_p], ignore_index=True)
                df_v.to_excel("datos_agua.xlsx", index=False)
                st.success(f"✅ Pedido registrado. Repartidor: {rep_asig}")
            else:
                st.error("⚠️ Por favor, completa todos los campos y permite la ubicación.")

# --- MÓDULO REPARTIDOR ---
elif rol == "Repartidor":
    u_log = st.sidebar.text_input("Usuario")
    p_log = st.sidebar.text_input("Contraseña", type="password")
    
    if u_log and p_log:
        user_auth = df_r[(df_r['Usuario'].astype(str) == u_log) & (df_r['Clave'].astype(str) == p_log)]
        if not user_auth.empty:
            nom_rep = user_auth.iloc[0]['Nombre']
            st.header(f"🚚 Panel de Control: {nom_rep}")
            
            mis_pendientes = df_v[(df_v['Repartidor'] == nom_rep) & (df_v['Estado'] == 'Pendiente')]
            
            if mis_pendientes.empty:
                st.info("No tienes pedidos pendientes por ahora.")
            
            for i, row in mis_pendientes.iterrows():
                with st.expander(f"📍 Cliente: {row['Cliente']} | {row['Cantidad']} Bidones"):
                    st.link_button("🌐 Abrir en Google Maps", f"https://www.google.com/maps?q={row['Ubicacion']}")
                    
                    ret_v = st.number_input("Bidones vacíos recibidos", 0, int(row['Cantidad']), int(row['Cantidad']), key=f"v_{i}")
                    
                    if st.button("Finalizar Entrega", key=f"f_{i}"):
                        faltante = row['Cantidad'] - ret_v
                        if faltante > 0:
                            # Alerta vinculada al repartidor para asumir responsabilidad de entrega
                            nueva_a = pd.DataFrame([{'Fecha': datetime.now().strftime("%Y-%m-%d"), 'Repartidor': nom_rep, 'Cliente': row['Cliente'], 'Esperados': row['Cantidad'], 'Recibidos': ret_v, 'Faltante': faltante, 'Estado': 'Pendiente'}])
                            df_a = pd.concat([df_a, nueva_a], ignore_index=True)
                            df_a.to_excel("alertas_envases.xlsx", index=False)
                        
                        df_v.at[i, 'Estado'] = 'Entregado'
                        df_v.to_excel("datos_agua.xlsx", index=False)
                        st.rerun()

# --- MÓDULO ADMINISTRADOR ---
elif rol == "Administrador":
    if st.sidebar.text_input("Clave Maestra", type="password") == "admin123":
        tab1, tab2, tab3 = st.tabs(["👥 Personal", "🏭 Planta", "🚩 Alertas de Envases"])
        
        with tab1:
            st.subheader("Registrar Nuevo Personal")
            with st.form("reg_personal", clear_on_submit=True):
                c1, c2 = st.columns(2)
                f_nom = c1.text_input("Nombre Completo")
                f_dni = c2.text_input("DNI")
                f_cel = c1.text_input("Celular (9 dígitos)")
                f_pla = c2.text_input("Placa del Vehículo")
                f_usr = c1.text_input("Usuario de Acceso")
                f_pas = c2.text_input("Contraseña")
                
                if st.form_submit_button("Guardar y Notificar"):
                    if f_nom and f_dni and f_cel:
                        nuevo_r = pd.DataFrame([{'Nombre': f_nom, 'Usuario': f_usr, 'Clave': f_pas, 'DNI': f_dni, 'Celular': f_cel, 'Placa': f_pla, 'Bidones_Planta': 0, 'Estado': 'Activo'}])
                        df_r = pd.concat([df_r, nuevo_r], ignore_index=True)
                        df_r.to_excel("repartidores.xlsx", index=False)
                        
                        # WhatsApp Link Corregido (Universal)
                        mensaje = f"Hola {f_nom}, tu acceso a Agua Origen es: \nUsuario: {f_usr}\nClave: {f_pas}"
                        mensaje_url = urllib.parse.quote(mensaje)
                        wa_link = f"https://wa.me/51{f_cel}?text={mensaje_url}"
                        
                        st.success(f"Repartidor {f_nom} registrado.")
                        st.link_button("📲 ENVIAR CREDENCIALES POR WHATSAPP", wa_link)
            
            st.write("---")
            st.subheader("Lista de Repartidores")
            for i, r in df_r.iterrows():
                col_a, col_b, col_c = st.columns([3, 2, 1])
                col_a.write(f"**{r['Nombre']}** | DNI: {r['DNI']} | ({r['Estado']})")
                
                btn_label = "Inactivar" if r['Estado'] == "Activo" else "Activar"
                if col_b.button(btn_label, key=f"switch_{i}"):
                    df_r.at[i, 'Estado'] = "Inactivo" if r['Estado'] == "Activo" else "Activo"
                    df_r.to_excel("repartidores.xlsx", index=False)
                    st.rerun()
                
                if col_c.button("🗑️", key=f"del_{i}"):
                    df_r.drop(i).to_excel("repartidores.xlsx", index=False)
                    st.rerun()

        with tab3:
            st.subheader("Control de Envases Pendientes")
            # Las alertas muestran al repartidor responsable para asumir responsabilidad de entrega
            pendientes_env = df_a[df_a['Estado'] == 'Pendiente']
            if not pendientes_env.empty:
                st.table(pendientes_env)
                id_res = st.selectbox("Seleccionar Alerta para resolver", pendientes_env.index)
                if st.button("Marcar como Envase Recuperado"):
                    df_a.at[id_res, 'Estado'] = 'Resuelto'
                    df_a.to_excel("alertas_envases.xlsx", index=False)
                    st.rerun()
            else:
                st.success("No hay alertas de envases pendientes.")