import streamlit as st
import pandas as pd
from datetime import datetime
import os
from PIL import Image
from streamlit_js_eval import get_geolocation
from fpdf import FPDF
import urllib.parse

# 1. CONFIGURACIÓN E INTERFAZ
try:
    img = Image.open("logo.png")
except Exception:
    img = None

st.set_page_config(page_title="Agua Origen - Sistema Profesional", page_icon="💧", layout="wide")

# 2. CAPA DE DATOS (Persistencia)
def cargar_excel(archivo, columnas):
    if os.path.exists(archivo):
        try:
            return pd.read_excel(archivo)
        except Exception:
            return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

df_ventas = cargar_excel("datos_agua.xlsx", ['Fecha', 'Cliente', 'Celular', 'Cantidad', 'Repartidor', 'Estado', 'Ubicacion'])
df_repartidores = cargar_excel("repartidores.xlsx", ['Nombre', 'Usuario', 'Clave', 'DNI', 'Celular', 'Placa', 'Bidones_Planta', 'Estado'])
df_alertas = cargar_excel("alertas_envases.xlsx", ['Fecha', 'Repartidor', 'Cliente', 'Esperados', 'Recibidos', 'Faltante', 'Estado'])

# 3. FUNCIONES AUXILIARES
def generar_pdf_liquidacion(nombre_rep, total_entregados, alertas_pendientes):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(200, 10, txt="REPORTE DE LIQUIDACIÓN - AGUA ORIGEN", ln=True, align='C')
        pdf.set_font("Arial", size=12)
        pdf.ln(10)
        pdf.cell(200, 10, txt=f"Repartidor: {nombre_rep}", ln=True)
        pdf.cell(200, 10, txt=f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True)
        pdf.cell(200, 10, txt=f"Total Bidones Entregados: {total_entregados}", ln=True)
        pdf.ln(10)
        if not alertas_pendientes.empty:
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(200, 10, txt="DEUDAS DE ENVASES PENDIENTES:", ln=True)
            pdf.set_font("Arial", size=10)
            for _, row in alertas_pendientes.iterrows():
                pdf.cell(200, 8, txt=f"- Cliente: {row['Cliente']} | Faltante: {row['Faltante']} envases", ln=True)
        pdf.ln(20)
        pdf.cell(200, 10, txt="__________________________", ln=True, align='C')
        pdf.cell(200, 10, txt="Firma del Repartidor", ln=True, align='C')
        return pdf.output(dest='S').encode('latin-1', errors='replace')
    except Exception: return None

# 4. NAVEGACIÓN
rol = st.sidebar.selectbox("Acceso de Usuario", ["Cliente (Pedidos)", "Repartidor", "Administrador"])

# --- MÓDULO 1: PORTAL DEL CLIENTE ---
if rol == "Cliente (Pedidos)":
    st.header("💧 Realiza tu pedido")
    with st.form("form_cliente", clear_on_submit=True):
        nombre = st.text_input("Tu Nombre")
        celular = st.text_input("Número de Celular")
        cantidad = st.number_input("¿Cuántos bidones necesitas?", min_value=1, step=1)
        loc = get_geolocation()
        if st.form_submit_button("Confirmar Pedido"):
            if nombre and celular and loc:
                reps_activos = df_repartidores[df_repartidores['Estado'] == 'Activo']['Nombre'].tolist()
                if reps_activos:
                    asignado = reps_activos[0]
                    nuevo_p = pd.DataFrame([{'Fecha': datetime.now(), 'Cliente': nombre, 'Celular': celular, 'Cantidad': cantidad, 'Repartidor': asignado, 'Estado': 'Pendiente', 'Ubicacion': f"{loc['coords']['latitude']},{loc['coords']['longitude']}"}])
                    df_ventas = pd.concat([df_ventas, nuevo_p], ignore_index=True)
                    df_ventas.to_excel("datos_agua.xlsx", index=False)
                    st.success(f"Pedido recibido. Asignado a: {asignado}")

# --- MÓDULO 2: PORTAL DEL REPARTIDOR ---
elif rol == "Repartidor":
    u_i = st.sidebar.text_input("Usuario")
    p_i = st.sidebar.text_input("Contraseña", type="password")
    if u_i and p_i:
        user_match = df_repartidores[(df_repartidores['Usuario'].astype(str) == u_i) & (df_repartidores['Clave'].astype(str) == p_i)]
        if not user_match.empty:
            nombre_rep = user_match.iloc[0]['Nombre']
            st.header(f"🚚 Panel de {nombre_rep}")
            entregados_total = df_ventas[(df_ventas['Repartidor'] == nombre_rep) & (df_ventas['Estado'] == 'Entregado')]['Cantidad'].sum()
            alertas_rep = df_alertas[(df_alertas['Repartidor'] == nombre_rep) & (df_alertas['Estado'] == 'Pendiente')]
            
            c1, c2, c3 = st.columns(3)
            c1.metric("En Planta", f"{user_match.iloc[0]['Bidones_Planta']}")
            c2.metric("Por Liquidar", f"{entregados_total}")
            pdf_data = generar_pdf_liquidacion(nombre_rep, entregados_total, alertas_rep)
            if pdf_data: c3.download_button("📥 Descargar Liquidación", data=pdf_data, file_name=f"Liq_{nombre_rep}.pdf", mime="application/pdf")

            st.subheader("📋 Pedidos Asignados")
            mis_pendientes = df_ventas[(df_ventas['Repartidor'] == nombre_rep) & (df_ventas['Estado'] == 'Pendiente')]
            for idx, row in mis_pendientes.iterrows():
                with st.expander(f"📍 {row['Cliente']} | {row['Cantidad']} Bidones"):
                    st.link_button("🌐 VER EN MAPS", f"https://www.google.com/maps?q={row['Ubicacion']}")
                    ret = st.number_input(f"¿Cuántos vacíos recibes?", 0, int(row['Cantidad']), int(row['Cantidad']), key=f"ret_{idx}")
                    if st.button(f"FINALIZAR ENTREGA", key=f"ent_{idx}"):
                        faltante = row['Cantidad'] - ret
                        if faltante > 0:
                            # Alerta vinculada al repartidor para asumir responsabilidad
                            n_a = pd.DataFrame([{'Fecha': datetime.now().strftime("%Y-%m-%d"), 'Repartidor': nombre_rep, 'Cliente': row['Cliente'], 'Esperados': row['Cantidad'], 'Recibidos': ret, 'Faltante': faltante, 'Estado': 'Pendiente'}])
                            df_alertas = pd.concat([df_alertas, n_a], ignore_index=True)
                            df_alertas.to_excel("alertas_envases.xlsx", index=False)
                        df_ventas.at[idx, 'Estado'] = 'Entregado'
                        df_ventas.to_excel("datos_agua.xlsx", index=False)
                        st.rerun()

# --- MÓDULO 3: PORTAL ADMINISTRADOR ---
elif rol == "Administrador":
    if st.sidebar.text_input("Clave Maestra", type="password") == "admin123":
        t1, t2, t3, t4 = st.tabs(["👥 Personal", "🏭 Planta", "💸 Liquidación", "🚩 Alertas"])
        
        with t1:
            st.subheader("Registro de Nuevo Repartidor")
            with st.form("reg_admin", clear_on_submit=True):
                c1, c2 = st.columns(2)
                f_nom = c1.text_input("Nombre y Apellido")
                f_dni = c2.text_input("DNI")
                f_cel = c1.text_input("Celular")
                f_pla = c2.text_input("Placa")
                f_user = c1.text_input("Usuario (Login)")
                f_pass = c2.text_input("Contraseña (Login)", type="password")
                if st.form_submit_button("Registrar e Informar"):
                    if str(f_dni) in df_repartidores['DNI'].astype(str).values:
                        st.error(f"Error: El DNI {f_dni} ya está registrado.")
                    elif f_nom and f_dni and f_user and f_cel:
                        n_u = pd.DataFrame([{'Nombre': f_nom, 'Usuario': f_user, 'Clave': f_pass, 'DNI': f_dni, 'Celular': f_cel, 'Placa': f_pla, 'Bidones_Planta': 0, 'Estado': 'Activo'}])
                        df_repartidores = pd.concat([df_repartidores, n_u], ignore_index=True)
                        df_repartidores.to_excel("repartidores.xlsx", index=False)
                        msg = f"Hola {f_nom}, bienvenido a Agua Origen. Usuario: {f_user} | Clave: {f_pass}."
                        st.success(f"Repartidor {f_nom} registrado.")
                        st.link_button("📲 NOTIFICAR WHATSAPP", f"https://wa.me/51{f_cel}?text={urllib.parse.quote(msg)}")
            
            st.markdown("---")
            st.subheader("Gestión de Repartidores Existentes")
            for i, r in df_repartidores.iterrows():
                col_a, col_b, col_c = st.columns([3, 2, 2])
                col_a.write(f"**{r['Nombre']}** ({r['Estado']})")
                nuevo_estado = "Inactivo" if r['Estado'] == "Activo" else "Activo"
                if col_b.button(f"Marcar como {nuevo_estado}", key=f"est_{i}"):
                    df_repartidores.at[i, 'Estado'] = nuevo_estado
                    df_repartidores.to_excel("repartidores.xlsx", index=False)
                    st.rerun()
                if col_c.button("Eliminar 🗑️", key=f"del_{i}"):
                    df_repartidores = df_repartidores.drop(i)
                    df_repartidores.to_excel("repartidores.xlsx", index=False)
                    st.rerun()

        with t2:
            st.subheader("Carga de Salida")
            reps_activos = df_repartidores[df_repartidores['Estado'] == 'Activo']['Nombre'].tolist()
            if reps_activos:
                rep_s = st.selectbox("Seleccionar Repartidor", reps_activos)
                cant_c = st.number_input("Bidones Llenos", min_value=1)
                if st.button("Asignar Carga"):
                    df_repartidores.loc[df_repartidores['Nombre'] == rep_s, 'Bidones_Planta'] += cant_c
                    df_repartidores.to_excel("repartidores.xlsx", index=False)
                    st.success("Carga asignada.")

        with t3:
            st.subheader("Liquidación")
            for i, r in df_repartidores.iterrows():
                deuda = df_ventas[(df_ventas['Repartidor'] == r['Nombre']) & (df_ventas['Estado'] == 'Entregado')]['Cantidad'].sum()
                if deuda > 0:
                    st.warning(f"{r['Nombre']} tiene {deuda} por liquidar.")
                    if st.button(f"Liquidar {r['Nombre']}", key=f"liq_btn_{i}"):
                        df_ventas.loc[(df_ventas['Repartidor'] == r['Nombre']) & (df_ventas['Estado'] == 'Entregado'), 'Estado'] = 'Completado'
                        df_ventas.to_excel("datos_agua.xlsx", index=False)
                        df_repartidores.at[i, 'Bidones_Planta'] = 0
                        df_repartidores.to_excel("repartidores.xlsx", index=False)
                        st.rerun()

        with t4:
            st.subheader("Alertas de Envases")
            pend = df_alertas[df_alertas['Estado'] == 'Pendiente']
            if not pend.empty:
                st.table(pend)
                idx_res = st.selectbox("ID para resolver", pend.index)
                if st.button("Marcar como Resuelto"):
                    df_alertas.at[idx_res, 'Estado'] = 'Resuelto'
                    df_alertas.to_excel("alertas_envases.xlsx", index=False)
                    st.rerun()