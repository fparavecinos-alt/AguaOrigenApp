import streamlit as st
import pandas as pd
from datetime import datetime
import os
from PIL import Image
from streamlit_js_eval import get_geolocation
from fpdf import FPDF

# 1. CONFIGURACIÓN INICIAL
st.set_page_config(page_title="Agua Origen - Sistema", page_icon="💧", layout="wide")

# Carga de Logo
try:
    img = Image.open("logo.png")
except Exception:
    img = None

# 2. CAPA DE DATOS (Persistencia)
def cargar_excel(archivo, columnas):
    if os.path.exists(archivo):
        try:
            return pd.read_excel(archivo)
        except Exception:
            return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

# Inicializar bases de datos
df_ventas = cargar_excel("datos_agua.xlsx", ['Fecha', 'Cliente', 'Celular', 'Cantidad', 'Repartidor', 'Estado', 'Ubicacion'])
df_repartidores = cargar_excel("repartidores.xlsx", ['Nombre', 'Usuario', 'Clave', 'DNI', 'Celular', 'Placa', 'Bidones_Planta', 'Estado'])
df_alertas = cargar_excel("alertas_envases.xlsx", ['Fecha', 'Repartidor', 'Cliente', 'Esperados', 'Recibidos', 'Faltante', 'Estado'])

# 3. GENERADOR DE PDF
def generar_pdf(nombre_rep, entregados, alertas_p):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(200, 10, txt="REPORTE DE LIQUIDACIÓN - AGUA ORIGEN", ln=True, align='C')
        pdf.set_font("Arial", size=12)
        pdf.ln(10)
        pdf.cell(0, 10, txt=f"Repartidor: {nombre_rep}", ln=True)
        pdf.cell(0, 10, txt=f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True)
        pdf.cell(0, 10, txt=f"Bidones entregados: {entregados}", ln=True)
        pdf.ln(5)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, txt="ALERTAS DE ENVASES PENDIENTES:", ln=True)
        pdf.set_font("Arial", size=10)
        if not alertas_p.empty:
            for _, r in alertas_p.iterrows():
                pdf.cell(0, 8, txt=f"- Cliente: {r['Cliente']} | Faltante: {r['Faltante']}", ln=True)
        else:
            pdf.cell(0, 8, txt="Sin deudas de envases registradas.", ln=True)
        pdf.ln(20)
        pdf.cell(0, 10, txt="__________________________", ln=True, align='C')
        pdf.cell(0, 10, txt="Firma del Repartidor", ln=True, align='C')
        return pdf.output(dest='S').encode('latin-1', errors='replace')
    except Exception:
        return None

# 4. SIDEBAR - NAVEGACIÓN
if img:
    st.sidebar.image(img, width=120)
else:
    st.sidebar.title("💧 Agua Origen")

st.sidebar.markdown("---")
rol = st.sidebar.selectbox("Acceso de Usuario", ["Cliente (Pedidos)", "Repartidor", "Administrador"])

# --- MÓDULO 1: CLIENTE ---
if rol == "Cliente (Pedidos)":
    st.header("💧 Realiza tu pedido")
    with st.form("form_ped", clear_on_submit=True):
        nom = st.text_input("Nombre")
        cel = st.text_input("Celular")
        cant = st.number_input("Bidones", 1, 50, 1)
        st.write("📍 Captura tu ubicación:")
        loc = get_geolocation()
        if st.form_submit_button("Confirmar Pedido"):
            if nom and cel and loc:
                coords = f"{loc['coords']['latitude']},{loc['coords']['longitude']}"
                reps = df_repartidores[df_repartidores['Estado'] == 'Activo']['Nombre'].tolist()
                if reps:
                    asig = reps[0] # Lógica simple de asignación
                    nuevo = pd.DataFrame([{'Fecha': datetime.now(), 'Cliente': nom, 'Celular': cel, 'Cantidad': cant, 'Repartidor': asig, 'Estado': 'Pendiente', 'Ubicacion': coords}])
                    df_ventas = pd.concat([df_ventas, nuevo], ignore_index=True)
                    df_ventas.to_excel("datos_agua.xlsx", index=False)
                    st.success(f"Pedido recibido. Te visitará {asig}.")
                else:
                    st.error("No hay repartidores activos.")

# --- MÓDULO 2: REPARTIDOR ---
elif rol == "Repartidor":
    u = st.sidebar.text_input("Usuario")
    p = st.sidebar.text_input("Clave", type="password")
    if u and p:
        user = df_repartidores[(df_repartidores['Usuario'].astype(str) == u) & (df_repartidores['Clave'].astype(str) == p)]
        if not user.empty:
            nombre_r = user.iloc[0]['Nombre']
            st.header(f"🚚 Panel: {nombre_r}")
            
            entregados = df_ventas[(df_ventas['Repartidor'] == nombre_r) & (df_ventas['Estado'] == 'Entregado')]['Cantidad'].sum()
            alertas_r = df_alertas[(df_alertas['Repartidor'] == nombre_r) & (df_alertas['Estado'] == 'Pendiente')]
            
            c1, c2, c3 = st.columns(3)
            c1.metric("En Planta", user.iloc[0]['Bidones_Planta'])
            c2.metric("Por Liquidar", entregados)
            
            pdf = generar_pdf(nombre_r, entregados, alertas_r)
            if pdf:
                c3.download_button("📥 Descargar Reporte", data=pdf, file_name=f"Liq_{nombre_r}.pdf", mime="application/pdf")

            st.subheader("📋 Pedidos Pendientes")
            mis_p = df_ventas[(df_ventas['Repartidor'] == nombre_r) & (df_ventas['Estado'] == 'Pendiente')]
            for i, r in mis_p.iterrows():
                with st.expander(f"📍 {r['Cliente']} ({r['Cantidad']} bidones)"):
                    st.link_button("🌐 IR A MAPS", f"https://www.google.com/maps?q={r['Ubicacion']}")
                    ret = st.number_input("Envases recibidos", 0, int(r['Cantidad']), int(r['Cantidad']), key=f"r_{i}")
                    if st.button("FINALIZAR ENTREGA", key=f"b_{i}"):
                        faltante = r['Cantidad'] - ret
                        if faltante > 0:
                            # Alerta vinculada al repartidor para asumir responsabilidad
                            n_a = pd.DataFrame([{'Fecha': datetime.now().strftime("%Y-%m-%d"), 'Repartidor': nombre_r, 'Cliente': r['Cliente'], 'Esperados': r['Cantidad'], 'Recibidos': ret, 'Faltante': faltante, 'Estado': 'Pendiente'}])
                            df_alertas = pd.concat([df_alertas, n_a], ignore_index=True)
                            df_alertas.to_excel("alertas_envases.xlsx", index=False)
                        df_ventas.at[i, 'Estado'] = 'Entregado'
                        df_ventas.to_excel("datos_agua.xlsx", index=False)
                        st.rerun()

# --- MÓDULO 3: ADMINISTRADOR (Corregido) ---
elif rol == "Administrador":
    pwd = st.sidebar.text_input("Clave Maestra", type="password")
    if pwd == "admin123":
        t1, t2, t3, t4 = st.tabs(["👥 Personal", "🏭 Planta", "💸 Liquidación", "🚩 Alertas"])
        
        with t1:
            st.subheader("Registro de Repartidores")
            with st.form("new_rep", clear_on_submit=True):
                c1, c2 = st.columns(2)
                fn = c1.text_input("Nombre Completo")
                fu = c2.text_input("Usuario")
                fp = c1.text_input("Contraseña")
                fpl = c2.text_input("Placa")
                if st.form_submit_button("Registrar"):
                    if fn and fu:
                        nr = pd.DataFrame([{'Nombre': fn, 'Usuario': fu, 'Clave': fp, 'Placa': fpl, 'Bidones_Planta': 0, 'Estado': 'Activo'}])
                        df_repartidores = pd.concat([df_repartidores, nr], ignore_index=True)
                        df_repartidores.to_excel("repartidores.xlsx", index=False)
                        st.success("Repartidor registrado.")
                        st.rerun()

        with t2:
            st.subheader("Carga de Salida")
            lista_r = df_repartidores[df_repartidores['Estado'] == 'Activo']['Nombre'].tolist()
            if lista_r:
                rs = st.selectbox("Repartidor", lista_r)
                cc = st.number_input("Cantidad", 1)
                if st.button("Cargar Bidones"):
                    df_repartidores.loc[df_repartidores['Nombre'] == rs, 'Bidones_Planta'] += cc
                    df_repartidores.to_excel("repartidores.xlsx", index=False)
                    st.success("Carga exitosa.")

        with t3:
            st.subheader("Cierre Diarios")
            for i, r in df_repartidores.iterrows():
                deuda = df_ventas[(df_ventas['Repartidor'] == r['Nombre']) & (df_ventas['Estado'] == 'Entregado')]['Cantidad'].sum()
                if deuda > 0:
                    st.warning(f"{r['Nombre']} debe liquidar {deuda} bidones.")
                    if st.button(f"Liquidar {r['Nombre']}", key=f"lq_{i}"):
                        df_ventas.loc[(df_ventas['Repartidor'] == r['Nombre']) & (df_ventas['Estado'] == 'Entregado'), 'Estado'] = 'Completado'
                        df_ventas.to_excel("datos_agua.xlsx", index=False)
                        df_repartidores.at[i, 'Bidones_Planta'] = 0
                        df_repartidores.to_excel("repartidores.xlsx", index=False)
                        st.rerun()

        with t4:
            st.subheader("Alertas de Envases Faltantes")
            pend = df_alertas[df_alertas['Estado'] == 'Pendiente']
            if not pend.empty:
                st.table(pend)
                idx = st.selectbox("Resolver Alerta (Fila)", pend.index)
                if st.button("Marcar como Resuelto"):
                    df_alertas.at[idx, 'Estado'] = 'Resuelto'
                    df_alertas.to_excel("alertas_envases.xlsx", index=False)
                    st.rerun()
            else:
                st.info("No hay alertas.")