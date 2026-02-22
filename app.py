import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
from PIL import Image

# 1. CONFIGURACIÓN Y LOGO
try:
    img = Image.open("logo.png")
except:
    img = None
st.set_page_config(page_title="Agua Origen - Gestión", page_icon=img if img else "💧")

# 2. FUNCIONES DE DATOS
def cargar_datos(archivo, columnas):
    if os.path.exists(archivo):
        return pd.read_excel(archivo)
    return pd.DataFrame(columns=columnas)

# Cargamos Ventas e Inventario
df = cargar_datos("datos_agua.xlsx", ['Fecha', 'Cliente', 'Cantidad', 'Repartidor', 'Estado'])
df_inv = cargar_datos("inventario.xlsx", ['Insumo', 'Cantidad_Actual'])

# Inicializar inventario con los 3 insumos clave
if df_inv.empty:
    df_inv = pd.DataFrame([
        {'Insumo': 'Tapas', 'Cantidad_Actual': 1000}, 
        {'Insumo': 'Etiquetas', 'Cantidad_Actual': 1000},
        {'Insumo': 'Precintos termo encogibles', 'Cantidad_Actual': 1000}
    ])

# 3. INTERFAZ
if img: st.image(img, width=150)
st.title("Sistema Agua Origen - Tambopata")
opcion = st.sidebar.radio("Ir a:", ["Panel de Control", "Registrar Venta", "Gastos e Insumos"])

# --- MODULO 1: PANEL DE CONTROL ---
if opcion == "Panel de Control":
    st.subheader("📊 Stock de Insumos Críticos")
    c1, c2, c3 = st.columns(3)
    
    # Obtener valores actuales
    tapas = df_inv[df_inv['Insumo'] == 'Tapas']['Cantidad_Actual'].values[0]
    etiq = df_inv[df_inv['Insumo'] == 'Etiquetas']['Cantidad_Actual'].values[0]
    prec = df_inv[df_inv['Insumo'] == 'Precintos termo encogibles']['Cantidad_Actual'].values[0]
    
    c1.metric("Tapas", f"{tapas} un.")
    c2.metric("Etiquetas", f"{etiq} un.")
    c3.metric("Precintos", f"{prec} un.")
    
    # Alerta de envases de 7 días (Responsabilidad del repartidor)
    st.markdown("---")
    st.subheader("⚠️ Alertas de Control de Envases")
    hoy = datetime.now()
    limite = hoy - timedelta(days=7)
    # Filtramos ventas antiguas no recuperadas
    if 'Estado' in df.columns:
        alertas = df[(df['Fecha'] <= limite) & (df['Estado'] == 'Entregado')]
        if not alertas.empty:
            for _, row in alertas.iterrows():
                st.error(f"RECOGER: {row['Cliente']} | Repartidor: {row['Repartidor']} (Entrega: {row['Fecha'].strftime('%d/%m')})")
        else:
            st.success("✅ Todos los envases están dentro del tiempo límite.")

# --- MODULO 2: REGISTRAR VENTA (DESCUENTO TRIPLE) ---
elif opcion == "Registrar Venta":
    st.subheader("📝 Nueva Venta / Despacho")
    with st.form("venta_form", clear_on_submit=True):
        nom = st.text_input("Cliente")
        cant = st.number_input("Cantidad de Bidones", min_value=1)
        rep = st.selectbox("Repartidor responsable", ["Carlos R.", "Luis M."])
        
        if st.form_submit_button("Guardar y Descontar"):
            # 1. Guardar Venta
            nueva = {'Fecha': datetime.now(), 'Cliente': nom, 'Cantidad': cant, 'Repartidor': rep, 'Estado': 'Entregado'}
            df = pd.concat([df, pd.DataFrame([nueva])], ignore_index=True)
            df.to_excel("datos_agua.xlsx", index=False)
            
            # 2. Descontar los 3 insumos
            df_inv.loc[df_inv['Insumo'] == 'Tapas', 'Cantidad_Actual'] -= cant
            df_inv.loc[df_inv['Insumo'] == 'Etiquetas', 'Cantidad_Actual'] -= cant
            df_inv.loc[df_inv['Insumo'] == 'Precintos termo encogibles', 'Cantidad_Actual'] -= cant
            df_inv.to_excel("inventario.xlsx", index=False)
            
            st.success(f"Venta de {cant} bidones registrada. Insumos actualizados.")

# --- MODULO 3: GASTOS E INSUMOS ---
elif opcion == "Gastos e Insumos":
    st.subheader("💰 Abastecimiento y Gastos")
    modo = st.selectbox("Acción:", ["Registrar Compra de Insumos", "Otros Gastos"])
    
    if modo == "Registrar Compra de Insumos":
        ins = st.selectbox("Insumo", ["Tapas", "Etiquetas", "Precintos termo encogibles"])
        c_compra = st.number_input("Cantidad ingresada", min_value=1)
        if st.button("Cargar a Stock"):
            df_inv.loc[df_inv['Insumo'] == ins, 'Cantidad_Actual'] += c_compra
            df_inv.to_excel("inventario.xlsx", index=False)
            st.success(f"Se sumaron {c_compra} unidades de {ins} al inventario.")