import streamlit as st
import pandas as pd
from datetime import datetime
import os
from PIL import Image
from streamlit_js_eval import get_geolocation
from fpdf import FPDF
import urllib.parse

# 1. CONFIGURACIÓN DEL SISTEMA
st.set_page_config(page_title="Agua Origen - Sistema Oficial", page_icon="💧", layout="wide")

def cargar_excel(archivo, columnas):
    if os.path.exists(archivo):
        try:
            return pd.read_excel(archivo)
        except Exception:
            return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

# Carga de Bases de Datos con estructura completa
df_ventas = cargar_excel("datos_agua.xlsx", ['Fecha', 'Cliente', 'Celular', 'Cantidad', 'Repartidor', 'Estado', 'Ubicacion'])
df_repartidores = cargar_excel("repartidores.xlsx", ['Nombre', 'Usuario', 'Clave', 'DNI', 'Celular', 'Placa', 'Bidones_Planta', 'Estado'])
df_alertas = cargar_excel("alertas_envases.xlsx", ['Fecha', 'Repartidor', 'Cliente', 'Esperados', 'Recibidos', 'Faltante', 'Estado'])

# 2. MOTOR DE REPORTES PDF
def generar_pdf_liquidacion(nombre_rep, entregados, alertas_p):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(200, 10, txt="LIQUIDACIÓN DE CAJA Y ENVASES", ln=True, align='C')
        pdf.set_font("Arial", size=12)
        pdf.ln(10)
        pdf.cell(0, 10, txt=f"Repartidor: {nombre_rep}", ln=True)
        pdf.cell(0, 10, txt=f"Fecha: {datetime.now().strftime('%d/%m/%Y')}", ln=True)
        pdf.cell(0, 10, txt=f"Total Bidones Entregados: {entregados}", ln=True)
        if not alertas_p.empty:
            pdf.ln(5)
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 10, txt="ENVASES PENDIENTES POR RECOGER:", ln=True)
            pdf.set_font("Arial", size=10)
            for _, r in alertas_p.iterrows():
                pdf.cell(0, 8, txt=f"- Cliente: {r['Cliente']} | Faltan: {r['Faltante']}", ln=True)
        return pdf.output(dest='S').encode('latin-1', errors='replace')
    except: return None

# 3. INTERFAZ DE NAVEGACIÓN
rol = st.sidebar.selectbox("Módulo de Acceso", ["Cliente (Pedidos)", "Repartidor", "Administrador"])

# --- MÓDULO CLIENTE ---
if rol == "Cliente (Pedidos)":
    st.header("💧 Solicita tu pedido")
    with st.form("form_cli", clear_on_submit=True):
        nom, cel = st.columns(2)
        nombre_c = nom.text_input("Nombre completo")
        celular_c = cel.text_input("WhatsApp")
        cant_c = st.number_input("Cantidad de bidones", 1, 100, 1)
        loc = get_geolocation()
        if st.form_submit_button("Confirmar Pedido"):
            if nombre_c and celular_c and loc:
                activos = df_repartidores[df_repartidores['Estado'] == 'Activo']['Nombre'].tolist()
                rep_asig = activos[0] if activos else "Pendiente"
                n_p = pd.DataFrame([{'Fecha': datetime.now(), 'Cliente': nombre_c, 'Celular': celular_c, 'Cantidad': cant_c, 'Repartidor': rep_asig, 'Estado': 'Pendiente', 'Ubicacion': f"{loc['coords']['latitude']},{loc['coords']['longitude']}"}])
                df_ventas = pd.concat([df_ventas, n_p], ignore_index=True)
                df_ventas.to_excel("datos_agua.xlsx", index=False)
                st.success(f"Pedido enviado. Repartidor asignado: {rep_asig}")

# --- MÓDULO REPARTIDOR ---
elif rol == "Repartidor":
    u, p = st.sidebar.text_input("Usuario"), st.sidebar.text_input("Clave", type="password")
    if u and p:
        user = df_repartidores[(df_repartidores['Usuario'].astype(str) == u) & (df_repartidores['Clave'].astype(str) == p)]
        if not user.empty:
            nombre_r = user.iloc[0]['Nombre']
            st.header(f"🚚 Panel: {nombre_r}")
            ent_total = df_ventas[(df_ventas['Repartidor'] == nombre_r) & (df_ventas['Estado'] == 'Entregado')]['Cantidad'].sum()
            alertas_r = df_alertas[(df_alertas['Repartidor'] == nombre_r) & (df_alertas['Estado'] == 'Pendiente')]
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Stock en Planta", user.iloc[0]['Bidones_Planta'])
            c2.metric("Entregas de hoy", ent_total)
            pdf = generar_pdf_liquidacion(nombre_r, ent_total, alertas_r)
            if pdf: c3.download_button("📥 Reporte PDF", data=pdf, file_name=f"Liq_{nombre_r}.pdf", mime="application/pdf")

            st.subheader("📋 Pedidos en Ruta")
            pendientes = df_ventas[(df_ventas['Repartidor'] == nombre_r) & (df_ventas['Estado'] == 'Pendiente')]
            for i, r in pendientes.iterrows():
                with st.expander(f"📍 {r['Cliente']} ({r['Cantidad']}