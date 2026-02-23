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

st.set_page_config(page_title="Agua Origen - Sistema", page_icon="💧", layout="wide")

# 2. CAPA DE DATOS
def cargar_excel(archivo, columnas):
    if os.path.exists(archivo):
        try:
            return pd.read_excel(archivo)
        except Exception:
            return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

df_ventas = cargar_excel("datos_agua.xlsx", ['Fecha', 'Cliente', 'Celular', 'Cantidad', 'Repartidor', 'Estado', 'Ubicacion'])
df_inv = cargar_excel("inventario.xlsx", ['Insumo', 'Cantidad_Actual'])
df_repartidores = cargar_excel("repartidores.xlsx", ['Nombre', 'Usuario', 'Clave', 'DNI', 'Celular', 'Placa', 'Bidones_Planta', 'Estado'])
df_alertas = cargar_excel("alertas_envases.xlsx", ['Fecha', 'Repartidor', 'Cliente', 'Esperados', 'Recibidos', 'Faltante', 'Estado'])

# 3. FUNCIÓN PARA GENERAR PDF DE LIQUIDACIÓN
def generar_pdf_liquidacion(nombre_rep, entregados, alertas_pendientes):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="REPORTE DE LIQUIDACIÓN - AGUA ORIGEN", ln=True, align='C')
    
    pdf.set_font("Arial", size=12)
    pdf.ln(10)
    pdf.cell(200, 10, txt=f"Repartidor: {nombre_rep}", ln=True)
    pdf.cell(200, 10, txt=f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True)
    pdf.cell(200, 10, txt=f"Bidones entregados hoy: {entregados}", ln=True)
    
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt="ALERTAS DE ENVASES PENDIENTES:", ln=True)
    pdf.set_font("Arial", size=10)
    
    if not alertas_pendientes.empty:
        for _, row in alertas_pendientes.iterrows():
            pdf.cell(200, 8, txt=f"- Cliente: {row['Cliente']} | Faltante: {row['Faltante']}", ln=True)
    else:
        pdf.cell(200, 8, txt="Sin deudas de envases registradas.", ln=True)
    
    pdf.ln(20)
    pdf.cell(200, 10, txt="__________________________", ln=True, align='C')
    pdf.cell(200, 10, txt="Firma del Repartidor", ln=True, align='C')
    
    # Se retorna el PDF como string de bytes compatible con download_button
    return pdf.output(dest='S').encode('latin-1', errors='replace')

# 4. NAVEGACIÓN
if img:
    st.sidebar.image(img, width=120)
else:
    st.sidebar.title("💧 Agua Origen")

st.sidebar.markdown("---")
rol = st.sidebar.selectbox("Acceso de Usuario", ["Cliente (Pedidos)", "Repartidor", "Administrador"])
URL_APP = "https://agua-origen-tambopata.streamlit.app"

# --- MÓDULO 1: PORTAL DEL CLIENTE ---
if rol == "Cliente (Pedidos)":
    st.header("💧 Realiza tu pedido - Agua Origen")
    with st.form("form_cliente", clear_on_submit=True):
        nombre = st.text_input("Tu Nombre")
        celular = st.text_input("Número de Celular (WhatsApp)")
        cantidad = st.number_input("¿Cuántos bidones necesitas?", min_value=1, step=1)
        st.write("📍 Captura tu ubicación para la entrega:")
        loc = get_geolocation()
        enviar = st.form_submit_button("Confirmar Pedido")
        
        if enviar and nombre and celular and loc:
            coords = f"{loc['coords']['latitude']},{loc['coords']['longitude']}"
            repartidores_activos = df_repartidores[df_repartidores['Estado'] == 'Activo']['Nombre'].tolist()
            if repartidores_activos:
                pendientes_count = [len(df_ventas[(df_ventas['Repartidor'] == r) & (df_ventas['Estado'] == 'Pendiente')]) for r in repartidores_activos]
                asignado = repartidores_activos[pendientes_count.index(min(pendientes_count))]
                
                nuevo_p = pd.DataFrame([{'Fecha': datetime.now(), 'Cliente': nombre, 'Celular': celular, 'Cantidad': cantidad, 'Repartidor': asignado, 'Estado': 'Pendiente', 'Ubicacion': coords}])
                df_ventas = pd.concat([df_ventas, nuevo_p], ignore_index=True)
                df_ventas.to_excel("datos_agua.xlsx", index=False)
                st.success(f"¡Pedido recibido! El repartidor {asignado} te visitará pronto.")

# --- MÓDULO 2: PORTAL DEL REPARTIDOR ---
elif rol == "Repartidor":
    st.sidebar.subheader("Acceso Repartidor")
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
            
            # Botón de Reporte PDF
            pdf_data = generar_pdf_liquidacion(nombre_rep, entregados_total, alertas_rep)
            c3.download_button("📥 Reporte PDF", data=pdf_data, file_name=f"Liq_{nombre_rep}.pdf", mime="application/pdf")

            st.subheader("📋 Pedidos Pendientes")
            mis_pendientes = df_ventas[(df_ventas['Repartidor'] == nombre_rep) & (df_ventas['Estado'] == 'Pendiente')]
            
            for idx, row in mis_pendientes.iterrows():
                with st.expander(f"📍 {row['Cliente']} | {row['Cantidad']} Bidón(es)"):
                    maps_url = f"https://www.google.com/maps?q={row['Ubicacion']}"
                    st.link_button("🌐 VER RUTA", maps_url)
                    
                    st.divider()
                    st.write("**Control de Envases:**")
                    retornados = st.number_input(f"¿Cuántos vacíos recibes?", 0, int(row['Cantidad']), int(row['Cantidad']), key=f"ret_{idx}")
                    
                    if st.button(f"✅ FINALIZAR ENTREGA", key=f"ent_{idx}"):
                        faltante = row['Cantidad'] - retornados
                        if faltante > 0:
                            # Alerta vinculada al repartidor por responsabilidad de entrega
                            n_alerta = pd.DataFrame([{'Fecha': datetime.now().strftime("%Y-%m-%d"), 'Repartidor': nombre_rep, 'Cliente': row['Cliente'], 'Esperados': row['Cantidad'], 'Recibidos': retornados, 'Faltante': faltante, 'Estado': 'Pendiente'}])
                            df_alertas = pd.concat([df_alertas, n_alerta], ignore_index=True)
                            df_alertas.to_excel("alertas_envases.xlsx", index=False)
                        
                        df_ventas.at[idx, 'Estado'] = 'Entregado'
                        df_ventas.to_excel("datos_agua.xlsx", index=False)
                        
                        for ins in ['Tapas', 'Etiquetas', 'Precintos termo encogibles']:
                            df_inv.loc[df_inv['Insumo'] == ins, 'Cantidad_Actual'] -= row['Cantidad']
                        df_inv.to_excel("inventario.xlsx", index=False)
                        
                        st.success("Venta registrada.")
                        st.rerun()
        else:
            st.error("Credenciales incorrectas.")

# --- MÓDULO 3: PORTAL ADMINISTRADOR ---
elif rol == "Administrador":
    if st.sidebar.text_input("Clave Maestra", type="password") == "admin123":
        t1, t2, t3, t4 = st.tabs(["👥 Repartidores", "🏭 Planta", "💸 Liquidación", "🚩 Alertas"])
        
        with t1:
            st.subheader("Gestión de Personal")
            # ... (código de registro de repartidores de la versión anterior)
            st.write("Panel para añadir o dar de baja repartidores.")

        with t2:
            st.subheader("Carga de Salida")
            reps_activos = df_repartidores[df_repartidores['Estado'] == 'Activo']['Nombre'].tolist()
            if reps_activos:
                rep_s = st.selectbox("Elegir Repartidor", reps_activos)
                cant_c = st.number_input("Bidones cargados", min_value=1)
                if st.button("Registrar Salida"):
                    df_repartidores.loc[df_repartidores['Nombre'] == rep_s, 'Bidones_Planta'] += cant_c
                    df_repartidores.to_excel("repartidores.xlsx", index=False)
                    st.success("Carga registrada.")

        with t3:
            st.subheader("Liquidación Diaria")
            for idx_r, r_row in df_repartidores.iterrows():
                deuda = df_ventas[(df_ventas['Repartidor'] == r_row['Nombre']) & (df_ventas['Estado'] == 'Entregado')]['Cantidad'].sum()
                if deuda > 0:
                    st.warning(f"{r_row['Nombre']} tiene {deuda} envases por retornar.")
                    if st.button(f"Liquidar a {r_row['Nombre']}", key=f"liq_{idx_r}"):
                        df_ventas.loc[(df_ventas['Repartidor'] == r_row['Nombre']) & (df_ventas['Estado'] == 'Entregado'), 'Estado'] = 'Completado'
                        df_ventas.to_excel("datos_agua.xlsx", index=False)
                        df_repartidores.at[idx_r, 'Bidones_Planta'] = 0
                        df_repartidores.to_excel("repartidores.xlsx", index=False)
                        st.rerun()

        with t4:
            st.subheader("Control de Responsabilidad de Envases")
            alertas_pendientes = df_alertas[df_alertas['Estado'] == 'Pendiente']
            if not alertas_pendientes.empty:
                st.dataframe(alertas_pendientes)
                id_res = st.selectbox("Seleccione fila para resolver", alertas_pendientes.index)
                if st.button("Marcar como Recuperado/Cobrado"):
                    df_alertas.at[id_res, 'Estado'] = 'Resuelto'
                    df_alertas.to_excel("alertas_envases.xlsx", index=False)
                    st.success("Alerta cerrada.")
                    st.rerun()
            else:
                st.success("No hay alertas de envases pendientes.")