import streamlit as st
import pandas as pd
from datetime import datetime
import os
from PIL import Image
from streamlit_js_eval import get_geolocation
from fpdf import FPDF

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

# Inicialización con todos los campos requeridos
df_ventas = cargar_excel("datos_agua.xlsx", ['Fecha', 'Cliente', 'Celular', 'Cantidad', 'Repartidor', 'Estado', 'Ubicacion'])
df_repartidores = cargar_excel("repartidores.xlsx", ['Nombre', 'Usuario', 'Clave', 'DNI', 'Celular', 'Placa', 'Bidones_Planta', 'Estado'])
df_alertas = cargar_excel("alertas_envases.xlsx", ['Fecha', 'Repartidor', 'Cliente', 'Esperados', 'Recibidos', 'Faltante', 'Estado'])

# 3. FUNCIONES AUXILIARES (PDF)
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
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(200, 10, txt="DEUDAS DE ENVASES PENDIENTES:", ln=True)
        pdf.set_font("Arial", size=10)
        
        if not alertas_pendientes.empty:
            for _, row in alertas_pendientes.iterrows():
                pdf.cell(200, 8, txt=f"- Cliente: {row['Cliente']} | Faltante: {row['Faltante']} envases", ln=True)
        else:
            pdf.cell(200, 8, txt="Sin faltantes de envases registrados.", ln=True)
            
        pdf.ln(20)
        pdf.cell(200, 10, txt="__________________________", ln=True, align='C')
        pdf.cell(200, 10, txt="Firma del Repartidor", ln=True, align='C')
        
        return pdf.output(dest='S').encode('latin-1', errors='replace')
    except Exception:
        return None

# 4. NAVEGACIÓN
if img:
    st.sidebar.image(img, width=120)
else:
    st.sidebar.title("💧 Agua Origen")

st.sidebar.markdown("---")
rol = st.sidebar.selectbox("Acceso de Usuario", ["Cliente (Pedidos)", "Repartidor", "Administrador"])

# --- MÓDULO 1: PORTAL DEL CLIENTE ---
if rol == "Cliente (Pedidos)":
    st.header("💧 Realiza tu pedido")
    with st.form("form_cliente", clear_on_submit=True):
        nombre = st.text_input("Tu Nombre")
        celular = st.text_input("Número de Celular")
        cantidad = st.number_input("¿Cuántos bidones necesitas?", min_value=1, step=1)
        st.write("📍 Ubicación para la entrega:")
        loc = get_geolocation()
        enviar = st.form_submit_button("Confirmar Pedido")
        
        if enviar and nombre and celular and loc:
            coords = f"{loc['coords']['latitude']},{loc['coords']['longitude']}"
            reps_activos = df_repartidores[df_repartidores['Estado'] == 'Activo']['Nombre'].tolist()
            if reps_activos:
                asignado = reps_activos[0] # Asignación por defecto
                nuevo_p = pd.DataFrame([{'Fecha': datetime.now(), 'Cliente': nombre, 'Celular': celular, 'Cantidad': cantidad, 'Repartidor': asignado, 'Estado': 'Pendiente', 'Ubicacion': coords}])
                df_ventas = pd.concat([df_ventas, nuevo_p], ignore_index=True)
                df_ventas.to_excel("datos_agua.xlsx", index=False)
                st.success(f"Pedido recibido. El repartidor {asignado} está en camino.")

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
            if pdf_data:
                c3.download_button("📥 Descargar Liquidación", data=pdf_data, file_name=f"Liquidacion_{nombre_rep}.pdf", mime="application/pdf")

            st.subheader("📋 Pedidos Asignados")
            mis_pendientes = df_ventas[(df_ventas['Repartidor'] == nombre_rep) & (df_ventas['Estado'] == 'Pendiente')]
            
            for idx, row in mis_pendientes.iterrows():
                with st.expander(f"📍 {row['Cliente']} | {row['Cantidad']} Bidones"):
                    st.link_button("🌐 VER EN MAPAS", f"https://www.google.com/maps?q={row['Ubicacion']}")
                    
                    st.write("**Control de Envases Retornados:**")
                    retornados = st.number_input(f"¿Cuántos vacíos recibes?", 0, int(row['Cantidad']), int(row['Cantidad']), key=f"ret_{idx}")
                    
                    if st.button(f"FINALIZAR ENTREGA", key=f"ent_{idx}"):
                        faltante = row['Cantidad'] - retornados
                        if faltante > 0:
                            # Se vincula la alerta al repartidor para asumir responsabilidad
                            n_alerta = pd.DataFrame([{'Fecha': datetime.now().strftime("%Y-%m-%d"), 'Repartidor': nombre_rep, 'Cliente': row['Cliente'], 'Esperados': row['Cantidad'], 'Recibidos': retornados, 'Faltante': faltante, 'Estado': 'Pendiente'}])
                            df_alertas = pd.concat([df_alertas, n_alerta], ignore_index=True)
                            df_alertas.to_excel("alertas_envases.xlsx", index=False)
                        
                        df_ventas.at[idx, 'Estado'] = 'Entregado'
                        df_ventas.to_excel("datos_agua.xlsx", index=False)
                        st.success("Venta finalizada con éxito.")
                        st.rerun()
        else:
            st.error("Credenciales incorrectas.")

# --- MÓDULO 3: PORTAL ADMINISTRADOR ---
elif rol == "Administrador":
    if st.sidebar.text_input("Clave Maestra", type="password") == "admin123":
        t1, t2, t3, t4 = st.tabs(["👥 Personal", "🏭 Planta", "💸 Liquidación", "🚩 Alertas"])
        
        with t1:
            st.subheader("Registro y Gestión de Repartidores")
            with st.form("registro_completo", clear_on_submit=True):
                col1, col2 = st.columns(2)
                f_nom = col1.text_input("Nombre y Apellido")
                f_dni = col2.text_input("DNI")
                f_cel = col1.text_input("Celular")
                f_pla = col2.text_input("Placa")
                f_user = col1.text_input("Usuario (Login)")
                f_pass = col2.text_input("Contraseña (Login)", type="password")
                
                if st.form_submit_button("Registrar Repartidor"):
                    if f_nom and f_dni and f_user:
                        n_u = pd.DataFrame([{'Nombre': f_nom, 'Usuario': f_user, 'Clave': f_pass, 'DNI': f_dni, 'Celular': f_cel, 'Placa': f_pla, 'Bidones_Planta': 0, 'Estado': 'Activo'}])
                        df_repartidores = pd.concat([df_repartidores, n_u], ignore_index=True)
                        df_repartidores.to_excel("repartidores.xlsx", index=False)
                        st.success(f"Repartidor {f_nom} dado de alta.")
                        st.rerun()
                    else:
                        st.error("Por favor completa los campos principales.")

        with t2:
            st.subheader("Carga de Salida")
            reps_activos = df_repartidores[df_repartidores['Estado'] == 'Activo']['Nombre'].tolist()
            if reps_activos:
                rep_s = st.selectbox("Seleccionar Repartidor", reps_activos)
                cant_c = st.number_input("Cantidad de Bidones Llenos", min_value=1)
                if st.button("Asignar Carga"):
                    df_repartidores.loc[df_repartidores['Nombre'] == rep_s, 'Bidones_Planta'] += cant_c
                    df_repartidores.to_excel("repartidores.xlsx", index=False)
                    st.success(f"Carga de {cant_c} asignada a {rep_s}.")

        with t3:
            st.subheader("Cierre de Liquidación Diaria")
            for idx_r, r_row in df_repartidores.iterrows():
                deuda = df_ventas[(df_ventas['Repartidor'] == r_row['Nombre']) & (df_ventas['Estado'] == 'Entregado')]['Cantidad'].sum()
                if deuda > 0:
                    st.warning(f"**{r_row['Nombre']}** tiene {deuda} envases por retornar.")
                    if st.button(f"Liquidar a {r_row['Nombre']}", key=f"liq_{idx_r}"):
                        df_ventas.loc[(df_ventas['Repartidor'] == r_row['Nombre']) & (df_ventas['Estado'] == 'Entregado'), 'Estado'] = 'Completado'
                        df_ventas.to_excel("datos_agua.xlsx", index=False)
                        df_repartidores.at[idx_r, 'Bidones_Planta'] = 0
                        df_repartidores.to_excel("repartidores.xlsx", index=False)
                        st.success(f"Liquidación cerrada para {r_row['Nombre']}.")
                        st.rerun()

        with t4:
            st.subheader("Reporte de Alertas y Responsabilidad")
            alertas_pendientes = df_alertas[df_alertas['Estado'] == 'Pendiente']
            if not alertas_pendientes.empty:
                st.table(alertas_pendientes)
                idx_res = st.selectbox("Seleccione ID de Alerta a resolver", alertas_pendientes.index)
                if st.button("Marcar como Resuelto (Envases devueltos)"):
                    df_alertas.at[idx_res, 'Estado'] = 'Resuelto'
                    df_alertas.to_excel("alertas_envases.xlsx", index=False)
                    st.success("Alerta resuelta.")
                    st.rerun()
            else:
                st.info("No hay alertas de envases pendientes.")