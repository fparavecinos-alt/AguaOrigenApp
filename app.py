import streamlit as st
import pandas as pd
from datetime import datetime
import os
from streamlit_js_eval import get_geolocation
from fpdf import FPDF
import urllib.parse

# 1. CONFIGURACIÓN E INTEGRIDAD DE DATOS
st.set_page_config(page_title="Agua Origen", layout="wide")

def cargar_datos(archivo, columnas):
    if os.path.exists(archivo):
        try: return pd.read_excel(archivo)
        except: return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

df_ventas = cargar_datos("datos_agua.xlsx", ['Fecha', 'Cliente', 'Celular', 'Cantidad', 'Repartidor', 'Estado', 'Ubicacion'])
df_repartidores = cargar_datos("repartidores.xlsx", ['Nombre', 'Usuario', 'Clave', 'DNI', 'Celular', 'Placa', 'Bidones_Planta', 'Estado'])
df_alertas = cargar_datos("alertas_envases.xlsx", ['Fecha', 'Repartidor', 'Cliente', 'Esperados', 'Recibidos', 'Faltante', 'Estado'])

# 2. NAVEGACIÓN
rol = st.sidebar.selectbox("Acceso", ["Cliente (Pedidos)", "Repartidor", "Administrador"])

# --- MÓDULO CLIENTE ---
if rol == "Cliente (Pedidos)":
    st.header("💧 Nuevo Pedido")
    with st.form("f_cli", clear_on_submit=True):
        nom = st.text_input("Nombre")
        cel = st.text_input("WhatsApp")
        cant = st.number_input("Cantidad", 1, 100, 1)
        loc = get_geolocation()
        if st.form_submit_button("Enviar Pedido"):
            if nom and cel and loc:
                reps = df_repartidores[df_repartidores['Estado'] == 'Activo']['Nombre'].tolist()
                asig = reps[0] if reps else "Pendiente"
                nuevo = pd.DataFrame([{'Fecha': datetime.now(), 'Cliente': nom, 'Celular': cel, 'Cantidad': cant, 'Repartidor': asig, 'Estado': 'Pendiente', 'Ubicacion': f"{loc['coords']['latitude']},{loc['coords']['longitude']}"}])
                df_ventas = pd.concat([df_ventas, nuevo], ignore_index=True)
                df_ventas.to_excel("datos_agua.xlsx", index=False)
                st.success(f"Pedido asignado a {asig}")

# --- MÓDULO REPARTIDOR ---
elif rol == "Repartidor":
    u = st.sidebar.text_input("Usuario")
    p = st.sidebar.text_input("Clave", type="password")
    if u and p:
        user = df_repartidores[(df_repartidores['Usuario'].astype(str) == u) & (df_repartidores['Clave'].astype(str) == p)]
        if not user.empty:
            nombre_r = user.iloc[0]['Nombre']
            st.header(f"🚚 Repartidor: {nombre_r}")
            
            pendientes = df_ventas[(df_ventas['Repartidor'] == nombre_r) & (df_ventas['Estado'] == 'Pendiente')]
            for i, r in pendientes.iterrows():
                # Sintaxis corregida y probada
                with st.expander(f"📍 {r['Cliente']} - {r['Cantidad']} bidones"):
                    st.link_button("🌐 Ver Mapa", f"http://maps.google.com/?q={r['Ubicacion']}")
                    ret = st.number_input("Vacíos recibidos", 0, int(r['Cantidad']), int(r['Cantidad']), key=f"r_{i}")
                    if st.button("Finalizar Entrega", key=f"b_{i}"):
                        if (r['Cantidad'] - ret) > 0:
                            # Alerta vinculada al repartidor para asumir responsabilidad
                            na = pd.DataFrame([{'Fecha': datetime.now().strftime("%Y-%m-%d"), 'Repartidor': nombre_r, 'Cliente': r['Cliente'], 'Esperados': r['Cantidad'], 'Recibidos': ret, 'Faltante': r['Cantidad']-ret, 'Estado': 'Pendiente'}])
                            df_alertas = pd.concat([df_alertas, na], ignore_index=True)
                            df_alertas.to_excel("alertas_envases.xlsx", index=False)
                        df_ventas.at[i, 'Estado'] = 'Entregado'
                        df_ventas.to_excel("datos_agua.xlsx", index=False)
                        st.rerun()

# --- MÓDULO ADMINISTRADOR ---
elif rol == "Administrador":
    if st.sidebar.text_input("Clave Maestra", type="password") == "admin123":
        t1, t2, t3, t4 = st.tabs(["👥 Personal", "🏭 Planta", "💸 Liquidación", "🚩 Alertas"])
        
        with t1:
            st.subheader("Registrar Repartidor")
            with st.form("reg_adm", clear_on_submit=True):
                c1, c2 = st.columns(2)
                fn = c1.text_input("Nombre Completo")
                fd = c2.text_input("DNI")
                fc = c1.text_input("Celular")
                fp = c2.text_input("Placa")
                fu = c1.text_input("Usuario")
                fcl = c2.text_input("Contraseña")
                if st.form_submit_button("Registrar"):
                    if str(fd) in df_repartidores['DNI'].astype(str).values:
                        st.error("DNI ya existe")
                    elif fn and fd and fc:
                        nr = pd.DataFrame([{'Nombre': fn, 'Usuario': fu, 'Clave': fcl, 'DNI': fd, 'Celular': fc, 'Placa': fp, 'Bidones_Planta': 0, 'Estado': 'Activo'}])
                        df_repartidores = pd.concat([df_repartidores, nr], ignore_index=True)
                        df_repartidores.to_excel("repartidores.xlsx", index=False)
                        msg = f"Hola {fn}, tu usuario es: {fu} y clave: {fcl}"
                        st.success("Registrado correctamente")
                        st.link_button("📲 Notificar por WhatsApp", f"https://wa.me/51{fc}?text={urllib.parse.quote(msg)}")
            
            st.divider()
            for i, r in df_repartidores.iterrows():
                cols = st.columns([3, 2, 2])
                cols[0].write(f"**{r['Nombre']}** ({r['Estado']})")
                if cols[1].button("Activar/Inactivar", key=f"st_{i}"):
                    df_repartidores.at[i, 'Estado'] = "Inactivo" if r['Estado']=="Activo" else "Activo"
                    df_repartidores.to_excel("repartidores.xlsx", index=False)
                    st.rerun()
                if cols[2].button("Eliminar", key=f"dl_{i}"):
                    df_repartidores.drop(i).to_excel("repartidores.xlsx", index=False)
                    st.rerun()

        with t4:
            st.subheader("Alertas de Envases Pendientes")
            # Las alertas muestran al repartidor responsable para asumir la responsabilidad de entrega
            pend = df_alertas[df_alertas['Estado'] == 'Pendiente']
            if not pend.empty:
                st.table(pend)
                idx = st.selectbox("ID a resolver", pend.index)
                if st.button("Resolver Alerta"):
                    df_alertas.at[idx, 'Estado'] = 'Resuelto'
                    df_alertas.to_excel("alertas_envases.xlsx", index=False)
                    st.rerun()