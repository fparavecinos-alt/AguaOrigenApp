import streamlit as st
import pandas as pd
import os, urllib.parse
from datetime import datetime
from PIL import Image
from streamlit_js_eval import get_geolocation
from fpdf import FPDF

# 1. CONFIGURACIÓN E IDENTIDAD
st.set_page_config(page_title="Agua Origen - Sistema Integral", layout="wide")

if os.path.exists("logo.png"):
    st.sidebar.image("logo.png", width=200)

def cargar_db(archivo, columnas):
    if os.path.exists(archivo):
        try: return pd.read_excel(archivo)
        except: return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

# Bases de datos
df_v = cargar_db("datos_agua.xlsx", ['Fecha', 'Cliente', 'Celular', 'Cantidad', 'Repartidor', 'Estado', 'Ubicacion'])
df_r = cargar_db("repartidores.xlsx", ['Nombre', 'Usuario', 'Clave', 'DNI', 'Celular', 'Placa', 'Bidones_Planta', 'Estado'])
df_a = cargar_db("alertas_envases.xlsx", ['Fecha', 'Repartidor', 'Cliente', 'Esperados', 'Recibidos', 'Faltante', 'Estado'])

# Generador de reporte PDF para liquidación
def generar_pdf(nombre_rep, ventas_total, alertas_pend):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="REPORTE DE LIQUIDACIÓN - AGUA ORIGEN", ln=True, align='C')
    pdf.set_font("Arial", size=12)
    pdf.ln(10)
    pdf.cell(0, 10, txt=f"Repartidor: {nombre_rep}", ln=True)
    pdf.cell(0, 10, txt=f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True)
    pdf.cell(0, 10, txt=f"Total Bidones Vendidos: {ventas_total}", ln=True)
    if not alertas_pend.empty:
        pdf.ln(5)
        pdf.cell(0, 10, txt="ALERTAS DE ENVASES PENDIENTES:", ln=True)
        for _, fila in alertas_pend.iterrows():
            pdf.cell(0, 10, txt=f"- Cliente: {fila['Cliente']} | Faltante: {fila['Faltante']}", ln=True)
    return pdf.output(dest='S').encode('latin-1')

rol = st.sidebar.selectbox("Módulo de Acceso", ["Cliente (Pedidos)", "Repartidor", "Administrador"])

# --- MÓDULO CLIENTE ---
if rol == "Cliente (Pedidos)":
    st.header("💧 Realiza tu pedido")
    with st.form("form_cli", clear_on_submit=True):
        col1, col2 = st.columns(2)
        n = col1.text_input("Tu Nombre")
        c = col2.text_input("WhatsApp (Ej: 987654321)")
        cant = st.number_input("¿Cuántos bidones?", 1, 100, 1)
        loc = get_geolocation()
        
        if st.form_submit_button("Confirmar Pedido"):
            if n and c:
                coords = "0,0"
                if loc and 'coords' in loc:
                    coords = f"{loc['coords']['latitude']},{loc['coords']['longitude']}"
                
                reps_activos = df_r[df_r['Estado'] == 'Activo']['Nombre'].tolist()
                rep_asig = reps_activos[0] if reps_activos else "Pendiente"
                
                nuevo_p = pd.DataFrame([{'Fecha': datetime.now(), 'Cliente': n, 'Celular': c, 'Cantidad': cant, 'Repartidor': rep_asig, 'Estado': 'Pendiente', 'Ubicacion': coords}])
                df_v = pd.concat([df_v, nuevo_p], ignore_index=True)
                df_v.to_excel("datos_agua.xlsx", index=False)
                st.success(f"✅ Pedido registrado. Repartidor asignado: {rep_asig}")

# --- MÓDULO REPARTIDOR ---
elif rol == "Repartidor":
    u_log = st.sidebar.text_input("Usuario")
    p_log = st.sidebar.text_input("Clave", type="password")
    if u_log and p_log:
        user_auth = df_r[(df_r['Usuario'].astype(str) == u_log) & (df_r['Clave'].astype(str) == p_log)]
        if not user_auth.empty:
            nom_rep = user_auth.iloc[0]['Nombre']
            st.header(f"🚚 Panel: {nom_rep}")
            
            entregados_hoy = df_v[(df_v['Repartidor'] == nom_rep) & (df_v['Estado'] == 'Entregado')]['Cantidad'].sum()
            alertas_rep = df_a[(df_a['Repartidor'] == nom_rep) & (df_a['Estado'] == 'Pendiente')]
            
            col_m1, col_m2 = st.columns(2)
            col_m1.metric("Vendido Hoy", entregados_hoy)
            col_m2.metric("Alertas Envases", len(alertas_rep))
            
            if st.button("Cerrar Día (PDF)"):
                pdf_bytes = generar_pdf(nom_rep, entregados_hoy, alertas_rep)
                st.download_button("📥 Descargar Reporte", pdf_bytes, f"Liquidacion_{nom_rep}.pdf", "application/pdf")

            st.subheader("Pedidos Pendientes")
            mis_p = df_v[(df_v['Repartidor'] == nom_rep) & (df_v['Estado'] == 'Pendiente')]
            for i, r in mis_p.iterrows():
                with st.expander(f"📍 {r['Cliente']} - {r['Cantidad']} bidones"):
                    st.link_button("🌐 Ver Mapa", f"https://www.google.com/maps?q={r['Ubicacion']}")
                    v_rec = st.number_input("Vacíos recibidos", 0, 100, int(r['Cantidad']), key=f"v_{i}")
                    if st.button("Finalizar Entrega", key=f"b_{i}"):
                        if r['Cantidad'] - v_rec > 0:
                            # Alerta vinculada al repartidor para responsabilidad de entrega
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
            st.subheader("Registro de Repartidores")
            with st.form("reg_adm", clear_on_submit=True):
                c1, c2 = st.columns(2)
                fn, fd = c1.text_input("Nombre Completo"), c2.text_input("DNI")
                fc, fp = c1.text_input("Celular"), c2.text_input("Placa")
                fu, fcl = c1.text_input("Usuario"), c2.text_input("Clave")
                if st.form_submit_button("Registrar"):
                    if fn and fc:
                        df_r = pd.concat([df_r, pd.DataFrame([{'Nombre':fn,'Usuario':fu,'Clave':fcl,'DNI':fd,'Celular':fc,'Placa':fp,'Bidones_Planta':0,'Estado':'Activo'}])], ignore_index=True)
                        df_r.to_excel("repartidores.xlsx", index=False)
                        
                        # WHATSAPP CON LINK DE ACCESO IMPLEMENTADO
                        app_url = "https://agua-origen-tambopata.streamlit.app"
                        msg = urllib.parse.quote(f"Bienvenido a Agua Origen\n\nAcceso: {app_url}\nUsuario: {fu}\nClave: {fcl}")
                        st.link_button("📲 Enviar Credenciales y Link", f"https://wa.me/51{fc}?text={msg}")
                        st.success(f"Registrado: {fn}")

            st.write("### Personal Activo")
            st.table(df_r[['Nombre', 'Celular', 'Placa', 'Estado']])

        with t4:
            st.subheader("Control de Envases (Por Repartidor)")
            st.write(df_a[df_a['Estado'] == 'Pendiente'])