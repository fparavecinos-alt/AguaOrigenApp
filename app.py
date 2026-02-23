import streamlit as st
import pandas as pd
from datetime import datetime
import os
from PIL import Image
from streamlit_js_eval import get_geolocation
from fpdf import FPDF
import urllib.parse

# 1. CONFIGURACIÓN
st.set_page_config(page_title="Agua Origen - Sistema", page_icon="💧", layout="wide")

def cargar_excel(archivo, columnas):
    if os.path.exists(archivo):
        try:
            return pd.read_excel(archivo)
        except Exception:
            return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

# Bases de Datos
df_ventas = cargar_excel("datos_agua.xlsx", ['Fecha', 'Cliente', 'Celular', 'Cantidad', 'Repartidor', 'Estado', 'Ubicacion'])
df_repartidores = cargar_excel("repartidores.xlsx", ['Nombre', 'Usuario', 'Clave', 'DNI', 'Celular', 'Placa', 'Bidones_Planta', 'Estado'])
df_alertas = cargar_excel("alertas_envases.xlsx", ['Fecha', 'Repartidor', 'Cliente', 'Esperados', 'Recibidos', 'Faltante', 'Estado'])

# 2. GENERADOR PDF
def generar_pdf_liquidacion(nombre_rep, entregados, alertas_p):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(200, 10, txt="LIQUIDACIÓN - AGUA ORIGEN", ln=True, align='C')
        pdf.set_font("Arial", size=12)
        pdf.ln(10)
        pdf.cell(0, 10, txt=f"Repartidor: {nombre_rep}", ln=True)
        pdf.cell(0, 10, txt=f"Bidones Entregados: {entregados}", ln=True)
        if not alertas_p.empty:
            pdf.ln(5)
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 10, txt="ENVASES PENDIENTES:", ln=True)
            pdf.set_font("Arial", size=10)
            for _, r in alertas_p.iterrows():
                pdf.cell(0, 8, txt=f"- {r['Cliente']}: Faltan {r['Faltante']}", ln=True)
        return pdf.output(dest='S').encode('latin-1', errors='replace')
    except: return None

# 3. NAVEGACIÓN
rol = st.sidebar.selectbox("Acceso de Usuario", ["Cliente (Pedidos)", "Repartidor", "Administrador"])

# --- MÓDULO 1: CLIENTE ---
if rol == "Cliente (Pedidos)":
    st.header("💧 Realiza tu pedido")
    with st.form("form_cli", clear_on_submit=True):
        nom = st.text_input("Nombre")
        cel = st.text_input("Celular")
        cant = st.number_input("Cantidad", 1, 50, 1)
        loc = get_geolocation()
        if st.form_submit_button("Confirmar"):
            if nom and cel and loc:
                reps = df_repartidores[df_repartidores['Estado'] == 'Activo']['Nombre'].tolist()
                asig = reps[0] if reps else "Sin asignar"
                nuevo = pd.DataFrame([{'Fecha': datetime.now(), 'Cliente': nom, 'Celular': cel, 'Cantidad': cant, 'Repartidor': asig, 'Estado': 'Pendiente', 'Ubicacion': f"{loc['coords']['latitude']},{loc['coords']['longitude']}"}])
                df_ventas = pd.concat([df_ventas, nuevo], ignore_index=True)
                df_ventas.to_excel("datos_agua.xlsx", index=False)
                st.success(f"Pedido recibido. Repartidor: {asig}")

# --- MÓDULO 2: REPARTIDOR ---
elif rol == "Repartidor":
    u = st.sidebar.text_input("Usuario")
    p = st.sidebar.text_input("Clave", type="password")
    if u and p:
        user = df_repartidores[(df_repartidores['Usuario'].astype(str) == u) & (df_repartidores['Clave'].astype(str) == p)]
        if not user.empty:
            nombre_r = user.iloc[0]['Nombre']
            st.header(f"🚚 Panel: {nombre_r}")
            ent = df_ventas[(df_ventas['Repartidor'] == nombre_r) & (df_ventas['Estado'] == 'Entregado')]['Cantidad'].sum()
            alertas_r = df_alertas[(df_alertas['Repartidor'] == nombre_r) & (df_alertas['Estado'] == 'Pendiente')]
            
            c1, c2, c3 = st.columns(3)
            c1.metric("En Planta", f"{user.iloc[0]['Bidones_Planta']}")
            c2.metric("Ventas Hoy", f"{ent}")
            
            pdf = generar_pdf_liquidacion(nombre_r, ent, alertas_r)
            if pdf: c3.download_button("📥 PDF Liquidación", data=pdf, file_name=f"Liq_{nombre_r}.pdf", mime="application/pdf")

            mis_p = df_ventas[(df_ventas['Repartidor'] == nombre_r) & (df_ventas['Estado'] == 'Pendiente')]
            for i, r in mis_p.iterrows():
                # LÍNEA CORREGIDA:
                with st.expander(f"📍 {r['Cliente']} ({r['Cantidad']} Bidones)"):
                    st.link_button("🌐 RUTA", f"https://www.google.com/maps?q={r['Ubicacion']}")
                    ret = st.number_input("Vacíos recibidos", 0, int(r['Cantidad']), int(r['Cantidad']), key=f"r_{i}")
                    if st.button("FINALIZAR", key=f"b_{i}"):
                        if (r['Cantidad'] - ret) > 0:
                            na = pd.DataFrame([{'Fecha': datetime.now().strftime("%Y-%m-%d"), 'Repartidor': nombre_r, 'Cliente': r['Cliente'], 'Esperados': r['Cantidad'], 'Recibidos': ret, 'Faltante': r['Cantidad']-ret, 'Estado': 'Pendiente'}])
                            df_alertas = pd.concat([df_alertas, na], ignore_index=True)
                            df_alertas.to_excel("alertas_envases.xlsx", index=False)
                        df_ventas.at[i, 'Estado'] = 'Entregado'
                        df_ventas.to_excel("datos_agua.xlsx", index=False)
                        st.rerun()

# --- MÓDULO 3: ADMINISTRADOR ---
elif rol == "Administrador":
    if st.sidebar.text_input("Clave Maestra", type="password") == "admin123":
        t1, t2, t3, t4 = st.tabs(["👥 Personal", "🏭 Planta", "💸 Liquidación", "🚩 Alertas"])
        
        with t1:
            st.subheader("Registro de Repartidores")
            with st.form("reg_admin", clear_on_submit=True):
                c1, c2 = st.columns(2)
                fn, fd = c1.text_input("Nombre Completo"), c2.text_input("DNI")
                fc, fp = c1.text_input("Celular"), c2.text_input("Placa")
                fu, fcl = c1.text_input("Usuario"), c2.text_input("Contraseña")
                if st.form_submit_button("Registrar y Notificar"):
                    if str(fd) in df_repartidores['DNI'].astype(str).values:
                        st.error("DNI ya registrado.")
                    elif fn and fd and fc:
                        nr = pd.DataFrame([{'Nombre': fn, 'Usuario': fu, 'Clave': fcl, 'DNI': fd, 'Celular': fc, 'Placa': fp, 'Bidones_Planta': 0, 'Estado': 'Activo'}])
                        df_repartidores = pd.concat([df_repartidores, nr], ignore_index=True)
                        df_repartidores.to_excel("repartidores.xlsx", index=False)
                        st.success("Registrado.")
                        txt = f"Hola {fn}, acceso Agua Origen. Usuario: {fu} | Clave: {fcl}"
                        st.link_button("📲 ENVIAR WHATSAPP", f"https://wa.me/51{fc}?text={urllib.parse.quote(txt)}")

            st.divider()
            st.subheader("Lista de Personal")
            for i, r in df_repartidores.iterrows():
                cols = st.columns([3, 2, 2])
                cols[0].write(f"**{r['Nombre']}** ({r['Estado']})")
                if cols[1].button("Activar/Inactivar", key=f"st_{i}"):
                    df_repartidores.at[i, 'Estado'] = "Inactivo" if r['Estado']=="Activo" else "Activo"
                    df_repartidores.to_excel("repartidores.xlsx", index=False)
                    st.rerun()
                if cols[2].button("Eliminar 🗑️", key=f"dl_{i}"):
                    df_repartidores.drop(i).to_excel("repartidores.xlsx", index=False)
                    st.rerun()

        with t2:
            st.subheader("Carga de Salida")
            activos = df_repartidores[df_repartidores['Estado'] == 'Activo']['Nombre'].tolist()
            if activos:
                rs = st.selectbox("Repartidor", activos)
                cc = st.number_input("Cantidad", 1)
                if st.button("Cargar"):
                    df_repartidores.loc[df_repartidores['Nombre'] == rs, 'Bidones_Planta'] += cc
                    df_repartidores.to_excel("repartidores.xlsx", index=False)
                    st.success("Cargado.")

        with t3:
            st.subheader("Liquidación Diaria")
            for i, r in df_repartidores.iterrows():
                deu = df_ventas[(df_ventas['Repartidor'] == r['Nombre']) & (df_ventas['Estado'] == 'Entregado')]['Cantidad'].sum()
                if deu > 0:
                    st.warning(f"{r['Nombre']} debe {deu} envases.")
                    if st.button(f"Liquidar {r['Nombre']}", key=f"liq_{i}"):
                        df_ventas.loc[(df_ventas['Repartidor'] == r['Nombre']) & (df_ventas['Estado'] == 'Entregado'), 'Estado'] = 'Completado'
                        df_ventas.to_excel("datos_agua.xlsx", index=False)
                        df_repartidores.at[i, 'Bidones_Planta'] = 0
                        df_repartidores.to_excel("repartidores.xlsx", index=False)
                        st.rerun()

        with t4:
            st.subheader("Control de Alertas")
            pend = df_alertas[df_alertas['Estado'] == 'Pendiente']
            if not pend.empty:
                st.table(pend)
                idx = st.selectbox("ID a resolver", pend.index)
                if st.button("Resolver"):
                    df_alertas.at[idx, 'Estado'] = 'Resuelto'
                    df_alertas.to_excel("alertas_envases.xlsx", index=False)
                    st.rerun()