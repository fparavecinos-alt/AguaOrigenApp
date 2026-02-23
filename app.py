import streamlit as st
import pandas as pd
import os, urllib.parse
from datetime import datetime
from PIL import Image
from streamlit_js_eval import get_geolocation
from fpdf import FPDF

# 1. CONFIGURACIÓN E IDENTIDAD
st.set_page_config(page_title="Agua Origen - Sistema Integral", layout="wide")

# Logo restaurado
if os.path.exists("logo.png"):
    st.sidebar.image("logo.png", width=200)

def cargar_db(archivo, columnas):
    if os.path.exists(archivo):
        try: return pd.read_excel(archivo)
        except: return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

# Bases de datos completas
df_v = cargar_db("datos_agua.xlsx", ['Fecha', 'Cliente', 'Celular', 'Cantidad', 'Repartidor', 'Estado', 'Ubicacion'])
df_r = cargar_db("repartidores.xlsx", ['Nombre', 'Usuario', 'Clave', 'DNI', 'Celular', 'Placa', 'Bidones_Planta', 'Estado'])
df_a = cargar_db("alertas_envases.xlsx", ['Fecha', 'Repartidor', 'Cliente', 'Esperados', 'Recibidos', 'Faltante', 'Estado'])

# Generador de reporte PDF
def generar_pdf(nombre_rep, ventas_total, alertas_pend):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="REPORTE DE LIQUIDACIÓN", ln=True, align='C')
    pdf.set_font("Arial", size=12)
    pdf.ln(10)
    pdf.cell(0, 10, txt=f"Repartidor: {nombre_rep}", ln=True)
    pdf.cell(0, 10, txt=f"Total Vendidos: {ventas_total}", ln=True)
    return pdf.output(dest='S').encode('latin-1')

rol = st.sidebar.selectbox("Acceso", ["Cliente (Pedidos)", "Repartidor", "Administrador"])

# --- MÓDULO CLIENTE ---
if rol == "Cliente (Pedidos)":
    st.header("💧 Nuevo Pedido")
    with st.form("f_cli", clear_on_submit=True):
        n = st.text_input("Nombre")
        c = st.text_input("WhatsApp")
        cant = st.number_input("Cantidad", 1, 100, 1)
        loc = get_geolocation()
        
        if st.form_submit_button("Confirmar Pedido"):
            if n and c:
                # BLINDAJE GPS: Si falla, guarda 0,0 en lugar de dar error
                coords = "0,0"
                try:
                    if loc and 'coords' in loc:
                        coords = f"{loc['coords']['latitude']},{loc['coords']['longitude']}"
                except: pass
                
                reps = df_r[df_r['Estado'] == 'Activo']['Nombre'].tolist()
                asig = reps[0] if reps else "Pendiente"
                
                nuevo = pd.DataFrame([{'Fecha': datetime.now(), 'Cliente': n, 'Celular': c, 'Cantidad': cant, 'Repartidor': asig, 'Estado': 'Pendiente', 'Ubicacion': coords}])
                df_v = pd.concat([df_v, nuevo], ignore_index=True)
                df_v.to_excel("datos_agua.xlsx", index=False)
                st.success("Pedido recibido.")

# --- MÓDULO REPARTIDOR ---
elif rol == "Repartidor":
    u = st.sidebar.text_input("Usuario")
    p = st.sidebar.text_input("Clave", type="password")
    if u and p:
        user = df_r[(df_r['Usuario'].astype(str) == u) & (df_r['Clave'].astype(str) == p)]
        if not user.empty:
            nom_r = user.iloc[0]['Nombre']
            st.header(f"🚚 {nom_r}")
            
            # Métricas y Liquidación
            entregados = df_v[(df_v['Repartidor'] == nom_r) & (df_v['Estado'] == 'Entregado')]['Cantidad'].sum()
            st.metric("Vendido Hoy", entregados)
            
            if st.button("Cerrar Día (PDF)"):
                pdf_bytes = generar_pdf(nom_r, entregados, None)
                st.download_button("Descargar Reporte", pdf_bytes, "cierre.pdf")

            pend = df_v[(df_v['Repartidor'] == nom_r) & (df_v['Estado'] == 'Pendiente')]
            for i, r in pend.iterrows():
                with st.expander(f"Pedido: {r['Cliente']}"):
                    st.link_button("🌐 Mapa", f"https://www.google.com/maps?q={r['Ubicacion']}")
                    v_rec = st.number_input("Vacíos", 0, 100, int(r['Cantidad']), key=f"v_{i}")
                    if st.button("Finalizar", key=f"b_{i}"):
                        if r['Cantidad'] - v_rec > 0:
                            # Alerta vinculada al repartidor para responsabilidad de entrega
                            alerta = pd.DataFrame([{'Fecha':datetime.now().strftime("%Y-%m-%d"), 'Repartidor':nom_r, 'Cliente':r['Cliente'], 'Esperados':r['Cantidad'], 'Recibidos':v_rec, 'Faltante':r['Cantidad']-v_rec, 'Estado':'Pendiente'}])
                            df_a = pd.concat([df_a, alerta], ignore_index=True)
                            df_a.to_excel("alertas_envases.xlsx", index=False)
                        df_v.at[i, 'Estado'] = 'Entregado'
                        df_v.to_excel("datos_agua.xlsx", index=False)
                        st.rerun()

# --- MÓDULO ADMINISTRADOR ---
elif rol == "Administrador":
    pwd = st.sidebar.text_input("Clave Maestra", type="password")
    if pwd == "admin123":
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
                        st.success(f"Registrado: {fn}")
                        # WHATSAPP CORREGIDO: Sin parámetros basura
                        msg = urllib.parse.quote(f"Acceso Agua Origen\nUser: {fu}\nPass: {fcl}")
                        st.link_button("📲 Enviar WhatsApp", f"https://wa.me/51{fc}?text={msg}")

            for i, r in df_r.iterrows():
                col = st.columns([3, 1])
                col[0].write(f"{r['Nombre']} - {r['Estado']}")
                if col[1].button("Eliminar", key=f"del_{i}"):
                    df_r.drop(i).to_excel("repartidores.xlsx", index=False); st.rerun()
        
        with t4:
            st.subheader("Control de Envases")
            st.table(df_a[df_a['Estado'] == 'Pendiente'])