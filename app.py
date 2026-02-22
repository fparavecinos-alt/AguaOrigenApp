# --- PORTAL ADMINISTRADOR (CLAVE: admin123) ---
elif rol == "Administrador":
    clave_adm = st.sidebar.text_input("Contraseña Maestra", type="password")
    if clave_adm == "admin123":
        # LÍNEA 91 CORREGIDA ABAJO:
        t1, t2, t3 = st.tabs(["👥 Gestión de Usuarios", "🏭 Carga Planta", "💸 Liquidación"])
        
        with t1:
            st.subheader("Registrar Nuevo Repartidor")
            with st.form("alta_rep"):
                f_nom = st.text_input("Nombre y Apellido")
                f_dni = st.text_input("DNI")
                f_cel = st.text_input("Celular (Ej: 987654321)")
                f_pla = st.text_input("Placa de Moto")
                f_user = st.text_input("Usuario de Acceso")
                f_pass = st.text_input("Contraseña")
                submitted = st.form_submit_button("Dar de Alta")
                
                if submitted:
                    nuevo = pd.DataFrame([{'Nombre': f_nom, 'Usuario': f_user, 'Clave': f_pass, 'DNI': f_dni, 'Celular': f_cel, 'Placa': f_pla, 'Bidones_Planta': 0, 'Estado': 'Activo'}])
                    df_repartidores = pd.concat([df_repartidores, nuevo], ignore_index=True)
                    df_repartidores.to_excel("repartidores.xlsx", index=False)
                    st.success(f"Repartidor {f_nom} guardado.")
                    
                    # Mensaje de bienvenida con URL
                    msg_cred = f"Bienvenido a Agua Origen. Accede aquí: {URL_APP} | Usuario: {f_user} | Clave: {f_pass}"
                    ws_url = f"https://wa.me/51{f_cel}?text={msg_cred.replace(' ', '%20')}"
                    st.link_button("📲 Enviar Acceso por WhatsApp", ws_url)
            st.dataframe(df_repartidores)
            
        with t2:
            st.subheader("Salida de Bidones (Planta)")
            if not df_repartidores.empty:
                rep_sel = st.selectbox("Seleccionar Repartidor", df_repartidores['Nombre'].tolist())
                cant_p = st.number_input("Cantidad de bidones cargados", min_value=1)
                if st.button("Registrar Carga en Planta"):
                    df_repartidores.loc[df_repartidores['Nombre'] == rep_sel, 'Bidones_Planta'] += cant_p
                    df_repartidores.to_excel("repartidores.xlsx", index=False)
                    st.success(f"Carga registrada para {rep_sel}")
            else:
                st.warning("Primero registra un repartidor en la pestaña de Usuarios.")

        with t3:
            st.subheader("Cierre y Liquidación")
            repartidores_activos = df_repartidores[df_repartidores['Estado'] == 'Activo']['Nombre'].tolist()
            for rep in repartidores_activos:
                deuda = df_ventas[(df_ventas['Repartidor'] == rep) & (df_ventas['Estado'] == 'Entregado')]['Cantidad'].sum()
                c1, c2 = st.columns([2,1])
                c1.write(f"**{rep}** tiene **{deuda}** bidones por devolver.")
                if deuda > 0:
                    if c2.button(f"Liquidar {rep}"):
                        df_ventas.loc[(df_ventas['Repartidor'] == rep) & (df_ventas['Estado'] == 'Entregado'), 'Estado'] = 'Completado'
                        df_ventas.to_excel("datos_agua.xlsx", index=False)
                        # Resetear carga tras liquidación
                        df_repartidores.loc[df_repartidores['Nombre'] == rep, 'Bidones_Planta'] = 0
                        df_repartidores.to_excel("repartidores.xlsx", index=False)
                        st.rerun()
    else:
        st.error("Acceso denegado.")