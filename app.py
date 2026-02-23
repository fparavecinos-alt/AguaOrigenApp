import streamlit as st
import pandas as pd
import os, urllib.parse
from datetime import datetime
from streamlit_js_eval import get_geolocation

# 1. CONFIGURACIÓN E IDENTIDAD
st.set_page_config(page_title="Agua Origen", layout="wide")

# Logo restaurado
if os.path.exists("logo.png"):
    st.sidebar.image("logo.png", width=200)

def cargar_db(archivo, columnas):
    if os.path.exists(archivo):
        try: return pd.read_excel(archivo)
        except: return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

df_v = cargar_db("datos_agua.xlsx", ['Fecha', 'Cliente', 'Celular', 'Cantidad', 'Repartidor', 'Estado', 'Ubicacion'])
df_r = cargar_db("repartidores.xlsx", ['Nombre', 'Usuario', 'Clave', 'DNI', 'Celular', 'Placa', 'Bidones_Planta', 'Estado'])
df_a = cargar_db("alertas_envases.xlsx", ['Fecha', 'Repartidor', 'Cliente', 'Esperados', 'Recibidos', 'Faltante', 'Estado'])

rol = st.sidebar.selectbox("Acceso", ["Cliente (Pedidos)", "Repartidor", "Administrador"])

# --- MÓDULO CLIENTE ---
if rol == "Cliente (Pedidos)":
    st.header("💧 Nuevo Pedido")
    with st.form("f_cli", clear_on_submit=True):
        n = st.text_input("Nombre")
        c = st.text_input("Celular")
        cant = st.number_input("Cantidad", 1, 100, 1)
        loc = get_geolocation()
        
        if st.form_submit_button("Confirmar Pedido"):
            if n and c:
                # Verificación de GPS para evitar el KeyError
                coords = "0,0"
                if loc and 'coords' in loc:
                    coords = f"{loc['coords']['latitude']},{loc['coords']['longitude']}"
                
                reps = df_r[df_r['Estado'] == 'Activo']['Nombre'].tolist()
                asig = reps[0] if reps else "Pendiente"
                
                nuevo = pd.DataFrame([{'Fecha': datetime.now(), 'Cliente': n, 'Celular': c, 'Cantidad': cant, 'Repartidor': asig, 'Estado': 'Pendiente', 'Ubicacion': coords}])
                df_v = pd.concat([df_v, nuevo], ignore_index=True)
                df_v.to_excel("datos_agua.xlsx", index=False)
                st.success(f"Pedido para {n} registrado.")
            else:
                st.error("Faltan datos.")

# --- MÓDULO REPARTIDOR ---
elif rol == "Repartidor":
    u = st.sidebar.text_input("Usuario")
    p = st.sidebar.text_input("Clave", type="password")
    if u and p:
        user = df_r[(df_r['Usuario'].astype(str) == u) & (df_r['Clave'].astype(str) == p)]
        if not user.empty:
            nom_r = user.iloc[0]['Nombre']
            st.header(f"🚚 Repartidor: {nom_r}")
            pend = df_v[(df_v['Repartidor'] == nom_r) & (df_v['Estado'] == 'Pendiente')]
            for i, r in pend.iterrows():
                with st.expander(f"📍 {r['Cliente']} - {r['Cantidad']} bidones"):
                    st.link_button("🌐 Mapa", f"https://www.google.com/maps?q={r['Ubicacion']}")
                    v_rec = st.number_input("Vacíos", 0, int(r['Cantidad']), int(r['Cantidad']), key=f"v_{i}")
                    if st.button("Finalizar", key=f"b_{i}"):
                        if r['Cantidad'] - v_rec > 0:
                            # Alerta vinculada al repartidor por responsabilidad de entrega
                            df_a = pd.concat([df_a, pd.DataFrame([{'Fecha':datetime.now().strftime("%Y-%m-%d"), 'Repartidor':nom_r, 'Cliente':r['Cliente'], 'Esperados':r['Cantidad'], 'Recibidos':v_rec, 'Faltante':r['Cantidad']-v_rec, 'Estado':'Pendiente'}])])
                            df_a.to_excel("alertas_envases.xlsx", index=False)
                        df_v.at[i, 'Estado'] = 'Entregado'
                        df_v.to_excel("datos_agua.xlsx", index=False)
                        st.rerun()

# --- MÓDULO ADMINISTRADOR ---
elif rol == "Administrador":
    if st.sidebar.text_input("Clave Maestra", type="password") == "admin123":
        t1, t2 = st.tabs(["👥 Personal", "🚩 Alertas"])
        with t1:
            with st.form("reg"):
                c1, c2 = st.columns(2)
                fn, fd = c1.text_input("Nombre"), c2.text_input("DNI")
                fc, fp = c1.text_input("Celular"), c2.text_input("Placa")
                fu, fcl = c1.text_input("Usuario"), c2.text_input("Clave")
                if st.form_submit_button("Registrar"):
                    if fn and fd and fc:
                        df_r = pd.concat([df_r, pd.DataFrame([{'Nombre':fn,'Usuario':fu,'Clave':fcl,'DNI':fd,'Celular':fc,'Placa':fp,'Bidones_Planta':0,'Estado':'Activo'}])])
                        df_r.to_excel("repartidores.xlsx", index=False)
                        # LINK WHATSAPP LIMPIO (Cambiado a wa.me directo)
                        txt = urllib.parse.quote(f"Acceso Agua Origen. Usuario: {fu} Clave: {fcl}")
                        st.markdown(f'[📲 Enviar Credenciales a WhatsApp](https://wa.me/51{fc}?text={txt})', unsafe_with_広告=True)
                        st.success("Registrado.")

            for i, r in df_r.iterrows():
                col = st.columns([3, 1])
                col[0].write(f"{r['Nombre']} ({r['Estado']})")
                if col[1].button("Eliminar", key=f"d_{i}"):
                    df_r.drop(i).to_excel("repartidores.xlsx", index=False); st.rerun()
        with t2:
            st.table(df_a[df_a['Estado'] == 'Pendiente'])