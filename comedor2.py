import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
import io
import calendar
from reportlab.pdfgen import canvas

# ---------------------------------------------------------
# CONFIGURACIÓN SUPABASE
# ---------------------------------------------------------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------------------------------------------------
# FUNCIONES DE BASE DE DATOS
# ---------------------------------------------------------
def db_select(table):
    data = supabase.table(table).select("*").execute().data
    return pd.DataFrame(data)

def db_insert(table, rows):
    supabase.table(table).insert(rows).execute()

def db_upsert(table, rows, conflict_cols=None):
    if conflict_cols:
        supabase.table(table).upsert(rows, on_conflict=conflict_cols).execute()
    else:
        supabase.table(table).upsert(rows).execute()


def db_delete(table, conditions):
    supabase.table(table).delete().match(conditions).execute()

# ---------------------------------------------------------
# LOGIN PROFESORADO
# ---------------------------------------------------------
def login():
    st.sidebar.subheader("Acceso Profesores")

    if "logged" not in st.session_state:
        st.session_state.logged = False
        st.session_state.profesor = None

    if not st.session_state.logged:
        usuario = st.sidebar.text_input("Usuario")
        password = st.sidebar.text_input("Contraseña", type="password")

        if st.sidebar.button("Entrar"):
            prof = supabase.table("profesores").select("*").eq("usuario", usuario).eq("password", password).execute().data
            if prof:
                st.session_state.logged = True
                st.session_state.profesor = prof[0]
                st.sidebar.success("Acceso concedido")
                st.rerun()
            else:
                st.sidebar.error("Usuario o contraseña incorrectos")
    else:
        st.sidebar.success(f"Conectado como {st.session_state.profesor['usuario']}")
        if st.sidebar.button("Cerrar sesión"):
            st.session_state.logged = False
            st.session_state.profesor = None
            st.rerun()


def draw_logo_centered(c, page_width, y):
    logo_width = 300
    logo_height = 300
    x = (page_width - logo_width) / 2
    c.drawImage("logo.png", x, y, width=logo_width, height=logo_height, preserveAspectRatio=True)

# ---------------------------------------------------------
# FUNCIÓN PARA NUMERAR PÁGINAS EN REPORTLAB
# ---------------------------------------------------------
from reportlab.pdfgen import canvas

def add_page_number(pdf_canvas):
    """
    Añade número de página en la parte inferior centrada.
    """
    page_num = pdf_canvas.getPageNumber()
    pdf_canvas.setFont("Helvetica", 9)
    pdf_canvas.drawCentredString(
        pdf_canvas._pagesize[0] / 2,   # centro horizontal
        20,                            # altura desde abajo
        f"Página {page_num}"
    )

# ---------------------------------------------------------
# CONFIGURACIÓN DE PÁGINA
# ---------------------------------------------------------
st.set_page_config(page_title="Gestión Comedor Escolar", layout="wide")

# Login obligatorio
login()
if not st.session_state.logged:
    st.stop()

# ---------------------------------------------------------
# CONTROLADOR DE NAVEGACIÓN ÚNICO
# ---------------------------------------------------------
if "nav" not in st.session_state:
    st.session_state.nav = None

def set_nav(value, group):
    st.session_state.nav = value

    # Resetear los otros grupos
    if group != "diario":
        st.session_state.diario = None
    if group != "gestion":
        st.session_state.gestion = None
    if group != "informes":
        st.session_state.informes = None
    if group != "fin_curso":
        st.session_state.fin_curso = None


# ---------------------------------------------------------
# MENÚ LATERAL PREMIUM (con roles)
# ---------------------------------------------------------

prof = st.session_state.profesor
rol = prof["rol"]

with st.sidebar:

    st.markdown("""
        <style>
            .sidebar-title {
                font-size: 22px;
                font-weight: bold;
                margin-bottom: -10px;
            }
            .diario { color: #4A90E2; }
            .gestion { color: #F5A623; }
            .informes { color: #7ED321; }
            .fin { color: #9013FE; }
        </style>
    """, unsafe_allow_html=True)

    # ---------------------------
    # GRUPO: DIARIO
    # ---------------------------
    with st.expander("📅 Diario", expanded=True):

        if rol == "admin":
            opciones_diario = ["📋 Pasar lista", "🍽️ Panel cocina", "✔️ Control de asistencia"]
        else:
            opciones_diario = ["📋 Pasar lista"]

        diario = st.radio(
            " ",
            opciones_diario,
            label_visibility="collapsed",
            index=None,
            key="diario",
            on_change=set_nav,
            args=(st.session_state.get("diario"), "diario")
        )


    st.markdown("<hr>", unsafe_allow_html=True)

    # ---------------------------
    # GRUPO: GESTIÓN (solo admin)
    # ---------------------------
    if rol == "admin":
        with st.expander("⚙️ Gestión", expanded=False):
            gestion = st.radio(
                "  ",
                [
                    "👨‍🎓 Gestión de alumnos",
                    "👩‍🏫 Gestión de profesores",
                    "🏫 Gestión de cursos",
                    "📊 Gestión de asistencias"
                ],
                label_visibility="collapsed",
                index=None, 
                key="gestion", 
                on_change=set_nav, 
                args=(st.session_state.get("gestion"), "gestion")
            )

        st.markdown("<hr>", unsafe_allow_html=True)

        # ---------------------------
        # GRUPO: INFORMES (solo admin)
        # ---------------------------
        with st.expander("📄 Informes", expanded=False):
            informes = st.radio(
                "   ",
                ["📝 Informes PDF"],
                label_visibility="collapsed",
                index=None, 
                key="informes", 
                on_change=set_nav, 
                args=(st.session_state.get("informes"), "informes")
            )

        st.markdown("<hr>", unsafe_allow_html=True)

        # ---------------------------
        # GRUPO: FIN DE CURSO (solo admin)
        # ---------------------------
        with st.expander("🏁 Fin de curso", expanded=False):
            fin_curso = st.radio(
                "    ",
                ["🎓 Promoción de curso", "🔒 Cerrar curso académico"],
                label_visibility="collapsed",
                index=None, 
                key="fin_curso", 
                on_change=set_nav, 
                args=(st.session_state.get("fin_curso"), "fin_curso")
            )


# ---------------------------------------------------------
# NAVEGACIÓN PRINCIPAL SEGÚN EL MENÚ PREMIUM
# ---------------------------------------------------------

# =========================================================
# 📅 DIARIO
# =========================================================

# ---------------------------------------------------------
# PASAR LISTA
# ---------------------------------------------------------
if diario == "📋 Pasar lista":
    st.header("Pasar Lista")

    df_alumnos = db_select("alumnos")
    df_cursos = db_select("cursos")
    df_asistencia = db_select("asistencia")

    fecha_hoy = datetime.now().strftime("%Y-%m-%d")

    # ADMIN PUEDE ELEGIR CURSO, PROFESOR USA SU CURSO
    if rol == "admin":
        curso_sel = st.selectbox(
            "Selecciona curso",
            df_cursos.to_dict(orient="records"),
            format_func=lambda x: x["nombre"],
            key="curso_admin"
        )
        curso_id = curso_sel["id"]
    else:
        curso_id = prof["curso_id"]

    alumnos_curso = df_alumnos[df_alumnos["curso_id"] == curso_id]

    st.subheader(f"Curso seleccionado: {df_cursos[df_cursos['id'] == curso_id]['nombre'].iloc[0]}")

    # Asistencias del día
    asistencia_hoy = df_asistencia[
        (df_asistencia["fecha"] == fecha_hoy) &
        (df_asistencia["curso_id"] == curso_id)
    ]

    estado = {}
    motivos = {}

    st.write("Marca los alumnos que asisten hoy al comedor:")

    for _, alumno in alumnos_curso.iterrows():

        # Buscar registro previo
        registro_previo = asistencia_hoy[asistencia_hoy["alumno_id"] == alumno["id"]]

        if registro_previo.empty:
            valor_inicial = True   # ✔️ Por defecto: asiste
            motivo_inicial = ""
        else:
            valor_inicial = bool(registro_previo["asiste"].iloc[0])
            motivo_inicial = registro_previo["motivo"].iloc[0] or ""

        # Checkbox de asistencia
        estado_asiste = st.checkbox(
            alumno["nombre"],
            value=valor_inicial,
            key=f"asiste_{alumno['id']}"
        )

        estado[alumno["id"]] = estado_asiste

        # Si NO asiste → mostrar campo motivo
        if not estado_asiste:
            motivos[alumno["id"]] = st.text_input(
                f"Motivo ausencia - {alumno['nombre']}",
                value=motivo_inicial,
                key=f"motivo_{alumno['id']}"
            )
        else:
            motivos[alumno["id"]] = ""

    # Guardar asistencia
    if st.button("Guardar asistencia"):
        registros = []
        for alumno_id in estado.keys():
            registros.append({
                "fecha": fecha_hoy,
                "alumno_id": alumno_id,
                "curso_id": curso_id,
                "asiste": estado[alumno_id],
                "motivo": motivos[alumno_id]
            })

        db_upsert("asistencia", registros, conflict_cols="alumno_id,fecha")
        st.success("Asistencia guardada correctamente")
        st.rerun()


# ---------------------------------------------------------
# PANEL DE COCINA
# ---------------------------------------------------------
elif diario == "🍽️ Panel cocina":
    st.header("Panel para Cocina")

    df_asistencia = db_select("asistencia")
    df_alumnos = db_select("alumnos")
    df_cursos = db_select("cursos")

    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    st.subheader(f"Día: {datetime.now().strftime('%d/%m/%Y')}")

    df_hoy = df_asistencia[df_asistencia["fecha"] == fecha_hoy]
    comen = df_hoy[df_hoy["asiste"] == True]

    if comen.empty:
        st.warning("Aún no se ha pasado lista hoy.")
        st.stop()

    resumen = comen.merge(df_alumnos, left_on="alumno_id", right_on="id")

    if "curso_id_y" in resumen.columns:
        resumen = resumen.rename(columns={"curso_id_y": "curso_id"})
    elif "curso_id_x" in resumen.columns:
        resumen = resumen.rename(columns={"curso_id_x": "curso_id"})

    resumen = resumen.merge(df_cursos, left_on="curso_id", right_on="id", suffixes=("", "_curso"))

    st.metric("TOTAL COMENSALES", len(resumen))

    col1, col2 = st.columns(2)

    with col1:
        st.write("### Comensales por Curso")
        conteo = resumen.groupby("nombre_curso").size().reset_index(name="Cantidad")
        st.table(conteo)

    with col2:
        st.write("### Observaciones Importantes")
        obs = resumen[resumen["motivo"].fillna("") != ""][["nombre", "motivo"]]
        if not obs.empty:
            st.dataframe(obs, hide_index=True)
        else:
            st.write("No hay observaciones para hoy.")

    st.write("### Lista Completa de Comensales")
    lista = resumen[["nombre", "nombre_curso"]].rename(columns={"nombre": "Alumno", "nombre_curso": "Curso"})
    st.dataframe(lista, hide_index=True)


# ---------------------------------------------------------
# CONTROL DE ASISTENCIA (solo admin)
# ---------------------------------------------------------
elif diario == "✔️ Control de asistencia" and rol == "admin":
    st.cache_data.clear()
    st.header("Control de Asistencia del Día")

    df_asistencia = db_select("asistencia")
    df_cursos = db_select("cursos")

    fecha_hoy = datetime.now().strftime("%Y-%m-%d")

    df_hoy = df_asistencia[
        (df_asistencia["fecha"] == fecha_hoy) &
        (df_asistencia["asiste"] == True)
    ]

    cursos_con_lista = df_hoy["curso_id"].unique()

    cursos_faltan = df_cursos[~df_cursos["id"].isin(cursos_con_lista)]

    st.subheader("Cursos que YA han pasado lista")
    if len(cursos_con_lista) == 0:
        st.info("Ningún curso ha pasado lista todavía.")
    else:
        df_ok = df_cursos[df_cursos["id"].isin(cursos_con_lista)]
        st.table(df_ok[["nombre"]].rename(columns={"nombre": "Curso"}))

    st.subheader("Cursos que FALTAN por pasar lista")
    if cursos_faltan.empty:
        st.success("Todos los cursos han pasado lista hoy.")
    else:
        st.error("Hay cursos pendientes de pasar lista.")
        st.table(cursos_faltan[["nombre"]].rename(columns={"nombre": "Curso"}))

    if st.button("Actualizar"):
        st.rerun()



# =========================================================
# ⚙️ GESTIÓN (solo admin)
# =========================================================
if rol == "admin":

    # ---------------------------------------------------------
    # GESTIÓN DE ALUMNOS
    # ---------------------------------------------------------
    if gestion == "👨‍🎓 Gestión de alumnos":
        st.header("Gestión de Alumnos")

        df_cursos = db_select("cursos")
        df_alumnos = db_select("alumnos")

        st.subheader("Alumnos existentes")
        tabla = df_alumnos.merge(df_cursos, left_on="curso_id", right_on="id")
        tabla = tabla[["nombre_x", "nombre_y"]].rename(columns={"nombre_x": "Alumno", "nombre_y": "Curso"})
        st.dataframe(tabla, hide_index=True)

        st.subheader("Añadir alumno")
        with st.form("nuevo_alumno"):
            nombre = st.text_input("Nombre del alumno")
            curso = st.selectbox("Curso", df_cursos.to_dict(orient="records"), format_func=lambda x: x["nombre"])

            if st.form_submit_button("Guardar"):
                db_insert("alumnos", [{
                    "nombre": nombre,
                    "curso_id": curso["id"]
                }])
                st.success("Alumno añadido")
                st.rerun()

        st.subheader("Eliminar alumno")
        alumno_del = st.selectbox("Selecciona alumno", df_alumnos.to_dict(orient="records"), format_func=lambda x: x["nombre"])
        if st.button("Eliminar alumno"):
            db_delete("alumnos", {"id": alumno_del["id"]})
            st.success("Alumno eliminado")
            st.rerun()


    # ---------------------------------------------------------
    # GESTIÓN DE PROFESORES
    # ---------------------------------------------------------
    elif gestion == "👩‍🏫 Gestión de profesores":
        st.header("Gestión de Profesores")

        df_profes = db_select("profesores")
        df_cursos = db_select("cursos")

        st.subheader("Profesores registrados")

        df_profes["curso_id"] = pd.to_numeric(df_profes["curso_id"], errors="coerce").astype("Int64")

        if not df_profes.empty:
            tabla = df_profes.merge(df_cursos, left_on="curso_id", right_on="id", suffixes=("", "_curso"))
            tabla = tabla[["usuario", "password", "nombre"]].rename(columns={"nombre": "Curso"})
            st.dataframe(tabla, hide_index=True)
        else:
            st.info("No hay profesores registrados todavía.")

        st.subheader("Añadir nuevo profesor")
        with st.form("nuevo_profesor"):
            usuario = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            curso = st.selectbox("Curso asignado", df_cursos.to_dict(orient="records"), format_func=lambda x: x["nombre"])

            if st.form_submit_button("Guardar"):
                db_insert("profesores", [{
                    "usuario": usuario,
                    "password": password,
                    "curso_id": curso["id"]
                }])
                st.success("Profesor añadido")
                st.rerun()

        st.subheader("Cambiar contraseña")
        if not df_profes.empty:
            prof_sel = st.selectbox(
                "Selecciona profesor",
                df_profes.to_dict(orient="records"),
                format_func=lambda x: x["usuario"]
            )

            nueva_pass = st.text_input("Nueva contraseña", type="password")

            if st.button("Actualizar contraseña"):
                if nueva_pass.strip() == "":
                    st.error("La contraseña no puede estar vacía.")
                else:
                    db_upsert("profesores", [{
                        "id": prof_sel["id"],
                        "password": nueva_pass
                    }])
                    st.success("Contraseña actualizada correctamente")
                    st.rerun()


        st.subheader("Eliminar profesor")
        if not df_profes.empty:
            prof_del = st.selectbox("Profesor a eliminar", df_profes.to_dict(orient="records"), format_func=lambda x: x["usuario"], key="del_prof")
            if st.button("Eliminar profesor"):
                db_delete("profesores", {"id": prof_del["id"]})
                st.success("Profesor eliminado")
                st.rerun()


    # ---------------------------------------------------------
    # GESTIÓN DE CURSOS
    # ---------------------------------------------------------
    elif gestion == "🏫 Gestión de cursos":
        st.header("Gestión de Cursos")

        df_cursos = db_select("cursos")

        st.subheader("Cursos existentes")
        st.dataframe(df_cursos, hide_index=True)

        st.subheader("Añadir nuevo curso")
        with st.form("nuevo_curso"):
            nombre = st.text_input("Nombre del curso (ej: 2ºA)")
            orden = st.number_input("Orden (nivel)", min_value=1, step=1)
            letra = st.text_input("Letra", max_chars=1)

            if st.form_submit_button("Guardar"):
                db_insert("cursos", [{
                    "nombre": nombre,
                    "orden": orden,
                    "letra": letra.upper()
                }])
                st.success("Curso añadido")
                st.rerun()

        st.subheader("Eliminar curso")
        curso_del = st.selectbox("Selecciona curso", df_cursos.to_dict(orient="records"), format_func=lambda x: x["nombre"])
        if st.button("Eliminar curso"):
            db_delete("cursos", {"id": curso_del["id"]})
            st.success("Curso eliminado")
            st.rerun()


    # ---------------------------------------------------------
    # GESTIÓN DE ASISTENCIAS
    # ---------------------------------------------------------
    elif gestion == "📊 Gestión de asistencias":
        st.header("Gestión de asistencias por día")

        df_asistencia = db_select("asistencia")
        df_alumnos = db_select("alumnos")

        fecha_sel = st.date_input("Selecciona un día", datetime.now())
        fecha_str = fecha_sel.strftime("%Y-%m-%d")

        datos = df_asistencia[df_asistencia["fecha"] == fecha_str]

        if datos.empty:
            st.info("No hay registros de asistencia para este día.")
            st.stop()

        datos = datos.merge(df_alumnos, left_on="alumno_id", right_on="id", suffixes=("", "_alumno"))

        st.subheader(f"Asistencias del {fecha_sel.strftime('%d/%m/%Y')}")

        editable = st.data_editor(
            datos[["alumno_id", "nombre", "asiste", "motivo", "curso_id", "curso_academico"]],
            num_rows="fixed",
            hide_index=True
        )

        if st.button("Guardar cambios"):
            for _, row in editable.iterrows():
                db_upsert(
                    "asistencia",
                    [{
                        "alumno_id": row["alumno_id"],
                        "fecha": fecha_str,
                        "curso_id": row["curso_id"],
                        "curso_academico": row["curso_academico"],
                        "asiste": row["asiste"],
                        "motivo": row["motivo"]
                    }],
                    conflict_cols="alumno_id,fecha"
                )

            st.success("Cambios guardados correctamente.")

        st.divider()

        st.subheader("Eliminar registro de asistencia")

        opciones_borrar = editable[["alumno_id", "nombre"]].copy()
        opciones_borrar["opcion"] = opciones_borrar["alumno_id"].astype(str) + " - " + opciones_borrar["nombre"]

        seleccion = st.selectbox("Selecciona el registro a eliminar", options=opciones_borrar["opcion"])

        if st.button("Eliminar registro seleccionado"):
            alumno_id_borrar = int(seleccion.split(" - ")[0])

            db_delete("asistencia", {
                "alumno_id": alumno_id_borrar,
                "fecha": fecha_str
            })

            st.success("Registro eliminado. Recarga la página para ver los cambios.")

    # ---------------------------------------------------------
    # INFORMES PDF
    # ---------------------------------------------------------
    if informes == "📝 Informes PDF":
        st.header("Generación de Informes PDF")

        df_asistencia = db_select("asistencia")
        df_alumnos = db_select("alumnos")
        df_cursos = db_select("cursos")

        fecha_hoy = datetime.now().strftime("%Y-%m-%d")

        # =========================
        # INFORME DIARIO PARA COCINA
        # =========================
        st.subheader("Informe Diario para Cocina")

        if st.button("Generar PDF Diario"):
            buffer = io.BytesIO()
            c = canvas.Canvas(buffer, pagesize=A4)
            page_width, page_height = A4

            draw_logo_centered(c, page_width, page_height - 190)
            c.setFont("Helvetica-Bold", 18)
            c.drawCentredString(page_width/2, 750, f"Informe Diario - {datetime.now().strftime('%d/%m/%Y')}")

            df_hoy = df_asistencia[df_asistencia["fecha"] == fecha_hoy]
            comen = df_hoy[df_hoy["asiste"] == True]

            resumen = comen.merge(df_alumnos, left_on="alumno_id", right_on="id")
            if "curso_id_y" in resumen.columns:
                resumen = resumen.rename(columns={"curso_id_y": "curso_id"})
            elif "curso_id_x" in resumen.columns:
                resumen = resumen.rename(columns={"curso_id_x": "curso_id"})

            resumen = resumen.merge(df_cursos, left_on="curso_id", right_on="id", suffixes=("", "_curso"))

            tabla_data = [["Curso", "Comensales"]]
            conteo = resumen.groupby("nombre_curso").size().reset_index(name="Cantidad")
            for _, row in conteo.iterrows():
                tabla_data.append([row["nombre_curso"], row["Cantidad"]])

            tabla = Table(tabla_data, colWidths=[250, 100])
            tabla.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
                ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
                ("ALIGN", (0,0), (-1,-1), "CENTER"),
                ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                ("FONTSIZE", (0,0), (-1,-1), 11),
            ]))

            w, h = tabla.wrap(page_width, page_height)
            y_actual = 700 - h
            tabla.drawOn(c, 50, y_actual)

            y_actual -= 40
            c.setFont("Helvetica-Bold", 14)
            c.drawString(50, y_actual, "Observaciones:")
            y_actual -= 20

            obs = resumen[resumen["motivo"].fillna("") != ""][["nombre", "motivo"]]
            c.setFont("Helvetica", 10)
            if obs.empty:
                c.drawString(60, y_actual, "No hay observaciones.")
            else:
                for _, row in obs.iterrows():
                    if y_actual < 50:
                        add_page_number(c)
                        c.showPage()
                        y_actual = 800
                    text = f"• {row['nombre']}: {row['motivo']}"
                    c.drawString(60, y_actual, text)
                    y_actual -= 15

            add_page_number(c)
            c.save()

            st.download_button(
                label="Descargar Informe Diario",
                data=buffer.getvalue(),
                file_name=f"informe_diario_{fecha_hoy}.pdf",
                mime="application/pdf"
            )

        # =========================
        # INFORME POR CURSO
        # =========================
        st.subheader("Informe por Curso")

        curso_sel = st.selectbox(
            "Selecciona curso",
            df_cursos.to_dict(orient="records"),
            format_func=lambda x: x["nombre"],
            key="curso_pdf"
        )

        if st.button("Generar PDF por Curso"):
            buffer = io.BytesIO()
            c = canvas.Canvas(buffer, pagesize=A4)
            page_width, page_height = A4

            draw_logo_centered(c, page_width, page_height - 190)
            c.setFont("Helvetica-Bold", 18)
            c.drawCentredString(page_width/2, 750, f"Informe por Curso - {curso_sel['nombre']}")
            c.setFont("Helvetica", 12)
            c.drawCentredString(page_width/2, 720, f"Fecha: {datetime.now().strftime('%d/%m/%Y')}")

            df_hoy = df_asistencia[df_asistencia["fecha"] == fecha_hoy]
            datos = df_hoy.merge(df_alumnos, left_on="alumno_id", right_on="id")
       
            if "curso_id_y" in datos.columns:
                datos = datos.rename(columns={"curso_id_y": "curso_id"})
            elif "curso_id_x" in datos.columns:
                datos = datos.rename(columns={"curso_id_x": "curso_id"})

            datos = datos[datos["curso_id"] == curso_sel["id"]]

            tabla_data = [["Alumno", "Come", "Motivo"]]
            for _, row in datos.iterrows():
                tabla_data.append([row["nombre"], "Sí" if row["asiste"] else "No", row["motivo"] or ""])

            tabla = Table(tabla_data, colWidths=[200, 80, 200])
            tabla.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
                ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
                ("ALIGN", (0,0), (-1,-1), "CENTER"),
                ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                ("FONTSIZE", (0,0), (-1,-1), 11),
            ]))

            w, h = tabla.wrap(page_width, page_height)
            # Dibujamos la tabla y si no cabe, ReportLab Canvas requiere gestión manual o Platypus. 
            # Para mantener tu estructura, bajamos el punto de inicio:
            tabla.drawOn(c, 50, 680 - h)

            add_page_number(c)
            c.save()

            st.download_button(
                label="Descargar Informe por Curso",
                data=buffer.getvalue(),
                file_name=f"informe_curso_{curso_sel['nombre']}_{fecha_hoy}.pdf",
                mime="application/pdf"
            )
    
        # =========================
        # INFORME MENSUAL
        # =========================
        st.subheader("Informe Mensual")
        mes = st.selectbox("Selecciona mes", list(range(1, 13)), key="mes_pdf")
        año = st.number_input("Año", min_value=2020, max_value=2030, value=datetime.now().year, key="año_pdf")

        if st.button("Generar PDF Mensual"):
            buffer = io.BytesIO()
            c = canvas.Canvas(buffer, pagesize=landscape(A4))
            page_width, page_height = landscape(A4)

            draw_logo_centered(c, page_width, page_height - 200)
            c.setFont("Helvetica-Bold", 18)
            c.drawCentredString(page_width/2, page_height - 110, f"Informe Mensual - {mes}/{año}")

            dias_mes = calendar.monthrange(año, mes)[1]
            tabla_data = [["Curso"] + [str(d) for d in range(1, dias_mes+1)] + ["Total"]]

            for _, curso in df_cursos.iterrows():
                fila = [curso["nombre"]]
                total = 0
                for dia in range(1, dias_mes+1):
                    fecha = f"{año}-{mes:02d}-{dia:02d}"
                    asistencias = df_asistencia[(df_asistencia["fecha"] == fecha) & (df_asistencia["asiste"] == True)]
                    alumnos_dia = asistencias.merge(df_alumnos, left_on="alumno_id", right_on="id")
                    
                    if "curso_id_y" in alumnos_dia.columns:
                        alumnos_dia = alumnos_dia.rename(columns={"curso_id_y": "curso_id"})
                    elif "curso_id_x" in alumnos_dia.columns:
                        alumnos_dia = alumnos_dia.rename(columns={"curso_id_x": "curso_id"})

                    alumnos_dia = alumnos_dia[alumnos_dia["curso_id"] == curso["id"]]
                    n = len(alumnos_dia)
                    fila.append(n)
                    total += n
                fila.append(total)
                tabla_data.append(fila)

            tabla = Table(tabla_data, colWidths=[70] + [18]*dias_mes + [40])
            tabla.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
                ("GRID", (0,0), (-1,-1), 0.25, colors.grey),
                ("ALIGN", (0,0), (-1,-1), "CENTER"),
                ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                ("FONTSIZE", (0,0), (-1,-1), 11), # Bajado un poco para que quepa bien
                ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ]))

            w, h = tabla.wrap(0, 0)
            tabla_y = page_height - 150 - h
            tabla.drawOn(c, 20, tabla_y)

            add_page_number(c)
            c.save()

            st.download_button(
                label="Descargar Informe Mensual",
                data=buffer.getvalue(),
                file_name=f"informe_mensual_{mes}_{año}.pdf",
                mime="application/pdf"
            )

        # =========================
        # INFORME INDIVIDUAL (FACTURA)
        # =========================
        st.subheader("Informe Individual (Factura)")
        alumno_sel = st.selectbox("Selecciona alumno", df_alumnos.to_dict(orient="records"), format_func=lambda x: x["nombre"], key="alumno_pdf")
        precio_menu = st.number_input("Precio del menú (€)", min_value=0.0, step=0.1)

        if st.button("Generar Factura"):
            buffer = io.BytesIO()
            c = canvas.Canvas(buffer, pagesize=A4)
            page_width, page_height = A4

            draw_logo_centered(c, page_width, page_height - 200)
            nombre = alumno_sel["nombre"]
            curso = df_cursos[df_cursos["id"] == alumno_sel["curso_id"]]["nombre"].iloc[0]

            c.setFont("Helvetica-Bold", 18)
            c.drawCentredString(page_width/2, 720, f"Factura Comedor - {nombre}")
            c.setFont("Helvetica", 12)
            c.drawCentredString(page_width/2, 700, f"Curso: {curso}")
            c.drawCentredString(page_width/2, 680, f"Fecha: {datetime.now().strftime('%d/%m/%Y')}")

            mes_actual = datetime.now().month
            año_actual = datetime.now().year
            df_mes = df_asistencia[(df_asistencia["alumno_id"] == alumno_sel["id"]) & (df_asistencia["fecha"].str.startswith(f"{año_actual}-{mes_actual:02d}"))]

            tabla_data = [["Fecha", "Come", "Motivo"]]
            for _, row in df_mes.iterrows():
                tabla_data.append([row["fecha"], "Sí" if row["asiste"] else "No", row["motivo"] or ""])

            tabla = Table(tabla_data, colWidths=[120, 60, 250])
            tabla.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
                ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
                ("ALIGN", (0,0), (-1,-1), "CENTER"),
                ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                ("FONTSIZE", (0,0), (-1,-1), 11),
            ]))

            # --- CORRECCIÓN CLAVE: Posicionamiento dinámico ---
            w, h = tabla.wrap(page_width, page_height)
            y_tabla = 650 - h # Empezamos un poco más arriba
            tabla.drawOn(c, 50, y_tabla)

            dias_comidos = df_mes["asiste"].sum()
            total_pagar = dias_comidos * precio_menu

            y_texto = y_tabla - 40 # El texto aparecerá 40px debajo de donde acabe la tabla
            c.setFont("Helvetica-Bold", 14)
            c.drawString(50, y_texto, f"Días asistidos: {dias_comidos}")
            c.drawString(50, y_texto - 20, f"Precio por menú: {precio_menu:.2f} €")
            c.setFont("Helvetica-Bold", 16)
            c.drawString(50, y_texto - 50, f"TOTAL A PAGAR: {total_pagar:.2f} €")

            add_page_number(c)
            c.save()

            st.download_button(
                label="Descargar Factura",
                data=buffer.getvalue(),
                file_name=f"factura_{nombre}.pdf",
                mime="application/pdf"
            )
     
    # ---------------------------------------------------------
    # PROMOCIÓN DE CURSO
    # ---------------------------------------------------------
    if fin_curso == "🎓 Promoción de curso":
        st.header("Promoción automática de alumnos")

        PROMOCIONES = {
        "INF 3": "INF 4",
        "INF 4": "INF 5",
        "INF 5": "1º A",
        "1º A": "2º A",
        "2º A": "3º A",
        "3º A": "4º A",
        "4º A": "5º A",
        "5º A": "6º A",
        "5º B": "6º B",
        "6º A": "6º A",
        "6º B": "6º B"
        }

        df_alumnos = db_select("alumnos")
        df_cursos = db_select("cursos")

        datos = df_alumnos.merge(
            df_cursos,
            left_on="curso_id",
            right_on="id",
            suffixes=("", "_curso")
        )

        datos["curso_destino_nombre"] = datos["nombre_curso"].map(PROMOCIONES)

        datos_promocionables = datos[~datos["curso_destino_nombre"].isna()].copy()

        if datos_promocionables.empty:
            st.info("No hay alumnos con curso de destino definido.")
            st.stop()

        df_cursos_dict = df_cursos.set_index("nombre")["id"].to_dict()
        datos_promocionables["curso_destino_id"] = datos_promocionables["curso_destino_nombre"].map(df_cursos_dict)

        if "promocion_estado" not in st.session_state:
            st.session_state.promocion_estado = {
                row["id"]: True
                for _, row in datos_promocionables.iterrows()
            }

        st.subheader("Alumnos que promocionan (agrupados por curso)")

        for curso, grupo in datos_promocionables.groupby("nombre_curso"):
            st.markdown(f"### {curso}")

            for _, row in grupo.iterrows():
                alumno_id = row["id"]
                alumno_nombre = row["nombre"]

                nuevo_estado = st.checkbox(
                    f"{alumno_nombre} → {row['curso_destino_nombre']}",
                    value=st.session_state.promocion_estado[alumno_id],
                    key=f"promo_{alumno_id}"
                )

                st.session_state.promocion_estado[alumno_id] = nuevo_estado

        st.subheader("Alumnos que repiten curso")

        repetidores = [
            row for _, row in datos_promocionables.iterrows()
            if not st.session_state.promocion_estado[row["id"]]
        ]

        if not repetidores:
            st.info("Ningún alumno repite curso.")
        else:
            df_rep = pd.DataFrame(repetidores)
            for curso, grupo in df_rep.groupby("nombre_curso"):
                st.markdown(f"### {curso}")
                for _, row in grupo.iterrows():
                    alumno_id = row["id"]
                    alumno_nombre = row["nombre"]

                    volver_a_promocionar = st.checkbox(
                        f"{alumno_nombre} (se queda en {curso})",
                        value=False,
                        key=f"rep_{alumno_id}"
                    )

                    if volver_a_promocionar:
                        st.session_state.promocion_estado[alumno_id] = True

        if st.button("Aplicar promoción"):
            st.warning("Esta acción actualizará el curso de todos los alumnos seleccionados. ¿Deseas continuar?")

            col1, col2 = st.columns(2)

            with col1:
                confirmar = st.button("Sí, confirmar promoción")

            with col2:
                cancelar = st.button("Cancelar")

            if confirmar:

                seleccionados = datos_promocionables[
                    datos_promocionables["id"].apply(lambda x: st.session_state.promocion_estado[x])
                ]

                for _, row in seleccionados.iterrows():

                    db_insert("promociones_log", [{
                        "alumno_id": row["id"],
                        "curso_origen": row["curso_id"],
                        "curso_destino": row["curso_destino_id"],
                        "fecha": datetime.now().strftime("%Y-%m-%d")
                    }])

                    db_upsert("alumnos", [{
                        "id": row["id"],
                        "curso_id": row["curso_destino_id"]
                    }])

                st.success("Promoción aplicada correctamente.")

            elif cancelar:
                st.info("Promoción cancelada.")

        st.divider()

        st.subheader("Deshacer última promoción")

        log = db_select("promociones_log")

        if log.empty:
            st.info("No hay promociones para deshacer.")
        else:
            log = log.sort_values("fecha", ascending=False)

            if st.button("Deshacer última promoción"):
                ultima_fecha = log.iloc[0]["fecha"]
                lote = log[log["fecha"] == ultima_fecha]

                for _, row in lote.iterrows():
                    db_upsert("alumnos", [{
                        "id": row["alumno_id"],
                        "curso_id": row["curso_origen"]
                    }])

                for _, row in lote.iterrows():
                    db_delete("promociones_log", {"id": row["id"]})

                st.success("Promoción revertida correctamente.")

      
    # ---------------------------------------------------------
    # CIERRE DE CURSO ACADÉMICO
    # ---------------------------------------------------------
    elif fin_curso == "🔒 Cerrar curso académico":
        st.header("Cierre de Curso Académico")

        curso_actual = st.text_input("Curso académico actual", "2025/2026")
        curso_nuevo = st.text_input("Nuevo curso académico", "2026/2027")

        st.info("Este proceso permite guardar copia del curso actual, promocionar alumnos y preparar el nuevo curso.")

        # ---------------------------------------------------------
        # 1. Copia de seguridad
        # ---------------------------------------------------------
        st.subheader("1. Copia de seguridad del curso actual")

        if st.button("Generar copia de seguridad"):
            df_asistencia = db_select("asistencia")
            df_alumnos = db_select("alumnos")
            df_cursos = db_select("cursos")
            df_profesores = db_select("profesores")
            df_promolog = db_select("promociones_log")

            st.download_button("Descargar asistencia", df_asistencia.to_csv(index=False), "asistencia_backup.csv")
            st.download_button("Descargar alumnos", df_alumnos.to_csv(index=False), "alumnos_backup.csv")
            st.download_button("Descargar cursos", df_cursos.to_csv(index=False), "cursos_backup.csv")
            st.download_button("Descargar profesores", df_profesores.to_csv(index=False), "profesores_backup.csv")
            st.download_button("Descargar promociones_log", df_promolog.to_csv(index=False), "promociones_log_backup.csv")

            st.success("Copia de seguridad generada correctamente.")

        st.divider()

        # ---------------------------------------------------------
        # 2. Promoción de alumnos
        # ---------------------------------------------------------
        st.subheader("2. Promoción de alumnos")
        st.write("Para promocionar alumnos, usa el módulo 'Promoción de Curso' del menú lateral.")

        st.divider()

        # ---------------------------------------------------------
        # 3. Crear nuevo curso académico
        # ---------------------------------------------------------
        st.subheader("3. Crear nuevo curso académico")

        if st.button("Preparar nuevo curso académico"):
            st.warning("Esto limpiará asistencias y promociones del nuevo curso. ¿Deseas continuar?")

            col1, col2 = st.columns(2)

            with col1:
                confirmar = st.button("Sí, preparar nuevo curso")

            with col2:
                cancelar = st.button("Cancelar")

            if confirmar:
                supabase.table("asistencia").delete().match({"curso_academico": curso_nuevo}).execute()
                supabase.table("promociones_log").delete().match({"curso_academico": curso_nuevo}).execute()

                st.success(f"Nuevo curso académico {curso_nuevo} preparado correctamente.")

            elif cancelar:
                st.info("Operación cancelada.")

        st.divider()

        # ---------------------------------------------------------
        # 4. Deshacer última promoción
        # ---------------------------------------------------------
        st.subheader("4. Deshacer última promoción")

        log = db_select("promociones_log")

        if log.empty:
            st.info("No hay promociones para deshacer.")
        else:
            log = log.sort_values("fecha", ascending=False)
            ultima_fecha = log.iloc[0]["fecha"]
            lote = log[log["fecha"] == ultima_fecha]

            st.write(f"Última promoción realizada el {ultima_fecha}: {len(lote)} alumnos.")

            if st.button("Deshacer última promoción"):
                for _, row in lote.iterrows():
                    db_upsert("alumnos", [{
                        "id": row["alumno_id"],
                        "curso_id": row["curso_origen"]
                    }])

                for _, row in lote.iterrows():
                    db_delete("promociones_log", {"id": row["id"]})

                st.success("Promoción revertida correctamente.")
