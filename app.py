import streamlit as st
import pandas as pd
import os, urllib.parse
from datetime import datetime
from streamlit_js_eval import get_geolocation

# 1. CONFIGURACIÓN E IDENTIDAD
st.set_page_config(page_title="Agua Origen - Gestión Total", layout="wide")

def cargar_db(archivo, columnas):
    if os.path.exists(archivo):
        try:
            df = pd.read_excel(archivo)
            # Asegurar que las columnas existan
            for col in columnas:
                if col not in df.columns: df[col] = ""
            return df
        except: return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

# BASES DE DATOS (Preservando tus datos existentes)
df_v = cargar_db("datos_agua.xlsx", ['Fecha', 'Cliente', 'Celular', 'Cantidad', 'Repartidor', 'Estado', 'Ubicacion'])
df_r = cargar_db("repartidores.xlsx", ['Nombre', 'Usuario', 'Clave', 'DNI', 'Celular', 'Placa', 'Estado'])
df_a = cargar_db("alertas_envases.xlsx", ['Fecha', 'Repartidor', 'Cliente', 'Esperados', 'Recibidos', 'Faltante', 'Estado'])

rol = st.sidebar.selectbox("Módulo de Acceso", ["Cliente (Pedidos)", "Repartidor", "Administrador"])

# --- MÓDULO CLIENTE ---
if rol == "Cliente (Pedidos)":
    st.header("💧 Realiza tu pedido")
    with st.form("form_cli", clear_on_submit=True):
        n = st.text_input("Tu Nombre")
        c = st.text_input("WhatsApp (9XXXXXXXX)")
        cant = st.number_input("Cantidad", 1, 100, 1)
        loc = get_geolocation()
        if st.form_submit_button("Confirmar Pedido"):
            if n and c:
                coords = "0,0"
                if loc and 'coords' in loc:
                    coords = f"{loc['coords']['latitude']},{loc['coords']['longitude']}"
                
                # Asignación entre repartidores con estado 'Activo'
                reps_activos = df_r[df_r['Estado'] == 'Activo']['Nombre'].tolist()
                rep_asig = "Pendiente"
                if reps_activos:
                    pendientes = df_v[df_v['Estado'] == 'Pendiente']['Repartidor'].value_counts()
                    rep_asig = min(reps_activos, key=lambda x: pendientes.get(x, 0))
                
                nuevo_p = pd.DataFrame([{'Fecha': datetime.now(), 'Cliente': n, 'Celular': c, 'Cantidad': cant, 'Repartidor': rep_asig, 'Estado': 'Pendiente', 'Ubicacion': coords}])
                df_v = pd.concat([df_v, nuevo_p], ignore_index=True)
                df_v.to_excel("datos_agua.xlsx", index=False)
                st.success(f"Pedido recibido. Asignado a: {rep_asig}")

# --- MÓDULO REPARTIDOR ---
elif rol == "Repartidor":
    u_log = st.sidebar.text_input("Usuario")
    p_log = st.sidebar.text_input("Clave", type="password")
    
    user_auth = df_r[(df_r['Usuario'].astype(str) == u_log) & (df_r['Clave'].astype(str) == p_log) & (df_r['Estado'] == 'Activo')]
    if not user_auth.empty:
        nom_rep = user_auth.iloc[0]['Nombre']
        st.header(f"🚚 Pedidos de {nom_rep}")
        
        mis_p = df_v[(df_v['Repartidor'] == nom_rep) & (df_v['Estado'] == 'Pendiente')]
        for i, r in mis_p.iterrows():
            with st.expander(f"📍 {r['Cliente']} - {r['Cantidad']} bidones"):
                # GPS ANDROID NATIVO: Usa el esquema intent de Google Maps
                # Si esto falla en el navegador, el respaldo es la URL de búsqueda
                url_gps = f"https://www.google.com/maps/dir/?api=1&destination={r['Ubicacion']}&travelmode=driving"
                st.link_button("🚀 ABRIR NAVEGACIÓN GPS", url_gps)
                
                # NOTIFICACIÓN ARRIBO
                msg = urllib.parse.quote(f"Hola {r['Cliente']}, soy {nom_rep} de Agua Origen. Estoy afuera con su pedido.")
                st.link_button("📲 AVISAR LLEGADA", f"https://wa.me/51{r['Celular']}?text={msg}")
                
                st.divider()
                v_rec = st.number_input("Vacíos recibidos", 0, 100, int(r['Cantidad']), key=f"v_{i}")
                if st.button("Finalizar Entrega", key=f"b_{i}"):
                    if r['Cantidad'] - v_rec > 0:
                        # Alerta vinculada al repartidor responsable
                        alerta_n = pd.DataFrame([{'Fecha': datetime.now().strftime("%Y-%m-%d"), 'Repartidor': nom_rep, 'Cliente': r['Cliente'], 'Esperados': r['Cantidad'], 'Recibidos': v_rec, 'Faltante': r['Cantidad']-v_rec, 'Estado': 'Pendiente'}])
                        df_a = pd.concat([df_a, alerta_n], ignore_index=True)
                        df_a.to_excel("alertas_envases.xlsx", index=False)
                    df_v.at[i, 'Estado'] = 'Entregado'
                    df_v.to_excel("datos_agua.xlsx", index=False)
                    st.rerun()

# --- MÓDULO ADMINISTRADOR ---
elif rol == "Administrador":
    if st.sidebar.text_input("Clave Maestra", type="password") == "admin123":
        t1, t2, t3 = st.tabs(["👥 Gestionar Personal", "💸 Liquidación", "🚩 Alertas"])
        
        with t1:
            st.subheader("Control de Repartidores")
            # Registro Nuevo
            with st.expander("➕ Registrar Nuevo Repartidor"):
                with st.form("reg_adm", clear_on_submit=True):
                    c1, c2 = st.columns(2)
                    fn = c1.text_input("Nombre Completo")
                    fd = c2.text_input("DNI")
                    fc = c1.text_input("Celular")
                    fp = c2.text_input("Placa")
                    fu = c1.text_input("Usuario Acceso")
                    fcl = c2.text_input("Clave Acceso")
                    if st.form_submit_button("Guardar Repartidor"):
                        if fn and fu:
                            nueva_r = pd.DataFrame([{'Nombre':fn,'Usuario':fu,'Clave':fcl,'DNI':fd,'Celular':fc,'Placa':fp,'Estado':'Activo'}])
                            df_r = pd.concat([df_r, nueva_r], ignore_index=True)
                            df_r.to_excel("repartidores.xlsx", index=False)
                            st.success("Registrado.")
                            msg_w = urllib.parse.quote(f"Acceso Agua Origen\nUser: {fu}\nPass: {fcl}\nLink: https://agua-origen-tambopata.streamlit.app")
                            st.link_button("📲 Enviar Credenciales", f"https://wa.me/51{fc}?text={msg_w}")

            # Lista y Edición
            st.write("### Listado de Personal")
            for idx, row in df_r.iterrows():
                col = st.columns([2, 1, 1, 1])
                col[0].write(f"**{row['Nombre']}** ({row['Estado']})")
                
                # Botón de Alta/Baja
                nuevo_estado = "Inactivo" if row['Estado'] == "Activo" else "Activo"
                if col[1].button(f"Dar de {nuevo_estado}", key=f"est_{idx}"):
                    df_r.at[idx, 'Estado'] = nuevo_estado
                    df_r.to_excel("repartidores.xlsx", index=False)
                    st.rerun()
                
                if col[2].button("Eliminar", key=f"del_{idx}"):
                    df_r = df_r.drop(idx)
                    df_r.to_excel("repartidores.xlsx", index=False)
                    st.rerun()

        with t3:
            st.subheader("Alertas de Envases")
            st.dataframe(df_a[df_a['Estado'] == 'Pendiente'])