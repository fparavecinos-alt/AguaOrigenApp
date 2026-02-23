import streamlit as st
import pandas as pd
import os, urllib.parse
from datetime import datetime
from streamlit_js_eval import get_geolocation

# 1. CONFIGURACIÓN E IDENTIDAD
st.set_page_config(page_title="Agua Origen - Sistema Integral", layout="wide")

if os.path.exists("logo.png"):
    st.sidebar.image("logo.png", width=200)

def cargar_db(archivo, columnas):
    if os.path.exists(archivo):
        try: return pd.read_excel(archivo)
        except: return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

# BASES DE DATOS
df_v = cargar_db("datos_agua.xlsx", ['Fecha', 'Cliente', 'Celular', 'Cantidad', 'Repartidor', 'Estado', 'Ubicacion'])
df_r = cargar_db("repartidores.xlsx", ['Nombre', 'Usuario', 'Clave', 'DNI', 'Celular', 'Placa', 'Bidones_Planta', 'Estado'])
df_a = cargar_db("alertas_envases.xlsx", ['Fecha', 'Repartidor', 'Cliente', 'Esperados', 'Recibidos', 'Faltante', 'Estado'])

rol = st.sidebar.selectbox("Módulo de Acceso", ["Cliente (Pedidos)", "Repartidor", "Administrador"])

# --- MÓDULO CLIENTE ---
if rol == "Cliente (Pedidos)":
    st.header("💧 Realiza tu pedido")
    with st.form("form_cli", clear_on_submit=True):
        col1, col2 = st.columns(2)
        n = col1.text_input("Tu Nombre")
        c = col2.text_input("WhatsApp (Ej: 987654321)")
        cant = st.number_input("Cantidad", 1, 100, 1)
        loc = get_geolocation()
        
        if st.form_submit_button("Confirmar Pedido"):
            if n and c:
                coords = "0,0"
                if loc and 'coords' in loc:
                    coords = f"{loc['coords']['latitude']},{loc['coords']['longitude']}"
                
                # ASIGNACIÓN EQUITATIVA
                reps_activos = df_r[df_r['Estado'] == 'Activo']['Nombre'].tolist()
                if reps_activos:
                    pendientes = df_v[df_v['Estado'] == 'Pendiente']['Repartidor'].value_counts()
                    rep_asig = min(reps_activos, key=lambda x: pendientes.get(x, 0))
                else:
                    rep_asig = "Pendiente"
                
                nuevo_p = pd.DataFrame([{'Fecha': datetime.now(), 'Cliente': n, 'Celular': c, 'Cantidad': cant, 'Repartidor': rep_asig, 'Estado': 'Pendiente', 'Ubicacion': coords}])
                df_v = pd.concat([df_v, nuevo_p], ignore_index=True)
                df_v.to_excel("datos_agua.xlsx", index=False)
                st.success(f"✅ Pedido enviado. Asignado a: {rep_asig}")

# --- MÓDULO REPARTIDOR ---
elif rol == "Repartidor":
    u_log = st.sidebar.text_input("Usuario")
    p_log = st.sidebar.text_input("Clave", type="password")
    
    if u_log and p_log:
        user_auth = df_r[(df_r['Usuario'].astype(str) == u_log) & (df_r['Clave'].astype(str) == p_log)]
        if not user_auth.empty:
            nom_rep = user_auth.iloc[0]['Nombre']
            st.header(f"🚚 Panel: {nom_rep}")
            
            mis_p = df_v[(df_v['Repartidor'] == nom_rep) & (df_v['Estado'] == 'Pendiente')]
            for i, r in mis_p.iterrows():
                with st.expander(f"📍 {r['Cliente']} - {r['Cantidad']} bidones"):
                    # 1. GPS NATIVO
                    url_nav = f"https://www.google.com/maps/dir/?api=1&destination={r['Ubicacion']}&travelmode=driving"
                    st.link_button("🚀 INICIAR NAVEGACIÓN GPS", url_nav)
                    
                    # 2. NOTIFICACIÓN AL CLIENTE (RESTURADA)
                    msg_llegada = urllib.parse.quote(f"Hola {r['Cliente']}, soy {nom_rep} de Agua Origen. Estoy afuera de su domicilio con su pedido de {r['Cantidad']} bidones.")
                    st.link_button("📲 AVISAR QUE LLEGUÉ", f"https://wa.me/51{r['Celular']}?text={msg_llegada}")
                    
                    st.divider()
                    
                    v_rec = st.number_input("Vacíos recibidos", 0, 100, int(r['Cantidad']), key=f"v_{i}")
                    if st.button("Finalizar Entrega", key=f"b_{i}"):
                        if r['Cantidad'] - v_rec > 0:
                            # Alerta vinculada al repartidor para asumir responsabilidad
                            alerta_n = pd.DataFrame([{'Fecha': datetime.now().strftime("%Y-%m-%d"), 'Repartidor': nom_rep, 'Cliente': r['Cliente'], 'Esperados': r['Cantidad'], 'Recibidos': v_rec, 'Faltante': r['Cantidad']-v_rec, 'Estado': 'Pendiente'}])
                            df_a = pd.concat([df_a, alerta_n], ignore_index=True)
                            df_a.to_excel("alertas_envases.xlsx", index=False)
                        
                        df_v.at[i, 'Estado'] = 'Entregado'
                        df_v.to_excel("datos_agua.xlsx", index=False)
                        st.rerun()

# --- MÓDULO ADMINISTRADOR ---
elif rol == "Administrador":
    if st.sidebar.text_input("Clave Maestra", type="password") == "admin123":
        t1, t2, t3, t4 = st.tabs(["👥 Personal", "🏭 Planta", "💸 Liquidación", "🚩 Alertas"])
        
        with t1:
            with st.form("reg_adm", clear_on_submit=True):
                c1, c2 = st.columns(2)
                fn, fd = c1.text_input("Nombre"), c2.text_input("DNI")
                fc, fp = c1.text_input("Celular"), c2.text_input("Placa")
                fu, fcl = c1.text_input("Usuario"), c2.text_input("Clave")
                if st.form_submit_button("Registrar"):
                    if fn and fc:
                        df_r = pd.concat([df_r, pd.DataFrame([{'Nombre':fn,'Usuario':fu,'Clave':fcl,'DNI':fd,'Celular':fc,'Placa':fp,'Bidones_Planta':0,'Estado':'Activo'}])], ignore_index=True)
                        df_r.to_excel("repartidores.xlsx", index=False)
                        
                        app_url = "https://agua-origen-tambopata.streamlit.app"
                        msg_reg = urllib.parse.quote(f"Bienvenido a Agua Origen\n\nApp: {app_url}\nUser: {fu}\nPass: {fcl}")
                        st.link_button("📲 Enviar Credenciales", f"https://wa.me/51{fc}?text={msg_reg}")
                        st.success("Registrado correctamente.")

        with t4:
            st.subheader("Control de Envases Pendientes")
            st.dataframe(df_a[df_a['Estado'] == 'Pendiente'])