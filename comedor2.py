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
    try:
        response = supabase.table(table).select("*").execute()
        data = response.data or []
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error leyendo {table}: {e}")
        return pd.DataFrame()


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
    if group != "maestros": # ← NUEVO GRUPO 
        st.session_state.maestros = None

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
            .maestros { color: #E67E22; }
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

        st.markdown("<hr>", unsafe_allow_html=True)

        # ---------------------------
        # GRUPO: COMEDOR MAESTROS (solo admin)
        # ---------------------------
        with st.expander("👨‍🏫 Comedor Maestros", expanded=False):
            maestros = st.radio(
                "     ",
                ["🍽️ Comidas", "💧 Agua"],
                label_visibility="collapsed",
                index=None,
                key="maestros",
                on_change=set_nav,
                args=(st.session_state.get("maestros"), "maestros")
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

        st.subheader("Alumnos existentes (agrupados por curso)")

        for _, curso in df_cursos.sort_values("orden").iterrows():
            alumnos_curso = df_alumnos[df_alumnos["curso_id"] == curso["id"]]

            with st.expander(f"{curso['nombre']}  ({len(alumnos_curso)} alumnos)", expanded=False):
                if alumnos_curso.empty:
                    st.info("No hay alumnos en este curso.")
                else:
                    st.table(
                        alumnos_curso[["nombre"]].rename(columns={"nombre": "Alumno"}),
                    )


        st.subheader("Añadir nuevo alumno")

        with st.form("nuevo_alumno"):
            nombre = st.text_input("Nombre del alumno")
            curso = st.selectbox(
                "Curso",
                df_cursos.to_dict(orient="records"),
                format_func=lambda x: x["nombre"]
            )

            if st.form_submit_button("Guardar"):
                # Normalizar nombre (evitar mayúsculas/minúsculas y espacios)
                nombre_normalizado = nombre.strip().lower()

                # Comprobar si ya existe un alumno con ese nombre
                existe = df_alumnos[
                    df_alumnos["nombre"].str.strip().str.lower() == nombre_normalizado
                ]

                if not existe.empty:
                    st.error("Este alumno ya está registrado en la base de datos.")
                    st.stop()
    
                # Insertar alumno si no existe
                db_insert("alumnos", [{
                    "nombre": nombre.strip(),
                    "curso_id": curso["id"]
                }])

                st.success("Alumno añadido correctamente")
                st.rerun()

        st.subheader("Modificar alumno")

        if df_alumnos.empty:
            st.info("No hay alumnos para modificar.")
        else:
            alumno_sel = st.selectbox(
                "Selecciona alumno",
                df_alumnos.to_dict(orient="records"),
                format_func=lambda x: x["nombre"],
                key="mod_alumno"
            )

            nuevo_nombre = st.text_input("Nuevo nombre", value=alumno_sel["nombre"])
            nuevo_curso = st.selectbox(
                "Nuevo curso",
                df_cursos.to_dict(orient="records"),
                format_func=lambda x: x["nombre"],
                index=df_cursos.index[df_cursos["id"] == alumno_sel["curso_id"]].tolist()[0]
            )

            if st.button("Guardar cambios"):
                supabase.table("alumnos").update({
                    "nombre": nuevo_nombre.strip(),
                    "curso_id": nuevo_curso["id"]
                }).eq("id", alumno_sel["id"]).execute()

                st.success("Alumno modificado correctamente.")
                st.rerun()

        st.subheader("Eliminar alumno")

        if df_alumnos.empty:
            st.info("No hay alumnos para eliminar.")
        else:
            alumno_del = st.selectbox(
                "Selecciona alumno a eliminar",
                df_alumnos.to_dict(orient="records"),
                format_func=lambda x: x["nombre"],
                key="del_alumno"
            )

            if st.button("Eliminar alumno"):
                db_delete("alumnos", {"id": alumno_del["id"]})
                st.success("Alumno eliminado correctamente.")
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

        st.subheader("Modificar datos del profesor")

        if not df_profes.empty:
            prof_sel = st.selectbox(
                "Selecciona profesor",
                df_profes.to_dict(orient="records"),
                format_func=lambda x: x["usuario"],
                key="prof_mod"
            )

            # ============================
            # MODIFICAR NOMBRE
            # ============================
            nuevo_nombre = st.text_input(
                "Nuevo nombre del profesor",
                value=prof_sel.get("usuario", "")
            )

            if st.button("Actualizar nombre"):
                if nuevo_nombre.strip() == "":
                    st.error("El nombre no puede estar vacío.")
                else:
                    supabase.table("profesores").update({
                        "usuario": nuevo_nombre.strip()
                    }).eq("id", prof_sel["id"]).execute()

                    st.success("Nombre actualizado correctamente.")
                    st.rerun()

            # ============================
            # MODIFICAR CURSO
            # ============================
            curso_actual = prof_sel["curso_id"]

            # Buscar índice del curso actual de forma segura
            indices = df_cursos.index[df_cursos["id"] == curso_actual].tolist()
            index_curso = indices[0] if indices else 0  # si no existe, usar el primero

            nuevo_curso = st.selectbox(
                "Nuevo curso asignado",
                df_cursos.to_dict(orient="records"),
                format_func=lambda x: x["nombre"],
                index=index_curso,
                key="curso_mod"
            )

            if st.button("Actualizar curso"):
                supabase.table("profesores").update({
                    "curso_id": nuevo_curso["id"]
                }).eq("id", prof_sel["id"]).execute()

                st.success("Curso actualizado correctamente.")
                st.rerun()


            # ============================
            # MODIFICAR CONTRASEÑA
            # ============================
            nueva_pass = st.text_input("Nueva contraseña", type="password", key="pass_mod")

            if st.button("Actualizar contraseña"):
                if nueva_pass.strip() == "":
                    st.error("La contraseña no puede estar vacía.")
                else:
                    supabase.table("profesores").update({
                        "password": nueva_pass
                    }).eq("id", prof_sel["id"]).execute()

                    st.success("Contraseña actualizada correctamente.")
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
    if st.session_state.informes == "📝 Informes PDF":

        st.header("Generación de Informes PDF")

        df_asistencia = db_select("asistencia")
        df_alumnos = db_select("alumnos")
        df_cursos = db_select("cursos")
        df_comidas = db_select("maestros_comidas")
        df_agua = db_select("maestros_agua")

        fecha_hoy = datetime.now().strftime("%Y-%m-%d")

       # =========================
        # INFORME DIARIO PARA COCINA
        # =========================
        st.subheader("Informe Diario para Cocina")

        # Selector de fecha
        fecha_diario = st.date_input(
            "Selecciona la fecha del informe",
            value=datetime.now().date(),
            key="fecha_informe_diario"
        )
        fecha_diario_str = fecha_diario.strftime("%Y-%m-%d")

        if st.button("Generar PDF Diario"):
            buffer = io.BytesIO()
            c = canvas.Canvas(buffer, pagesize=A4)
            page_width, page_height = A4

            draw_logo_centered(c, page_width, page_height - 190)
            c.setFont("Helvetica-Bold", 18)
            c.drawCentredString(page_width/2, 750, f"Informe Diario - {fecha_diario.strftime('%d/%m/%Y')}")

            df_dia = df_asistencia[df_asistencia["fecha"] == fecha_diario_str]
            comen = df_dia[df_dia["asiste"] == True]

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
                file_name=f"informe_diario_{fecha_diario_str}.pdf",
                mime="application/pdf"
            )


        # =========================
        # INFORME POR CURSO
        # =========================
        st.subheader("Informe por Curso")

        opciones_cursos = ["Todos los cursos"] + df_cursos["nombre"].tolist()
        curso_sel = st.selectbox("Selecciona curso", opciones_cursos, key="curso_pdf")

        # Selector de fecha
        fecha_curso = st.date_input(
            "Selecciona la fecha del informe",
            value=datetime.now().date(),
            key="fecha_informe_curso"
        )
        fecha_curso_str = fecha_curso.strftime("%Y-%m-%d")

        if st.button("Generar PDF por Curso"):

            buffer = io.BytesIO()
            c = canvas.Canvas(buffer, pagesize=A4)
            page_width, page_height = A4

            # Determinar lista de cursos
            if curso_sel == "Todos los cursos":
                lista_cursos = df_cursos.to_dict(orient="records")
            else:
                lista_cursos = df_cursos[df_cursos["nombre"] == curso_sel].to_dict(orient="records")

            # Filtrar asistencias del día
            df_dia = df_asistencia[df_asistencia["fecha"] == fecha_curso_str]
            datos = df_dia.merge(df_alumnos, left_on="alumno_id", right_on="id")

            # Normalizar curso_id
            if "curso_id_y" in datos.columns:
                datos = datos.rename(columns={"curso_id_y": "curso_id"})
            elif "curso_id_x" in datos.columns:
                datos = datos.rename(columns={"curso_id_x": "curso_id"})

            # =========================
            # GENERAR UNA PÁGINA POR CURSO
            # =========================
            primera_pagina = True 
            
            for curso in lista_cursos: 
                
                if not primera_pagina: 
                    c.showPage() 
                primera_pagina = False

                # Logo
                draw_logo_centered(c, page_width, page_height - 190)

                nombre_curso = curso["nombre"]
                curso_id = curso["id"]

                # Título
                c.setFont("Helvetica-Bold", 18)
                c.drawCentredString(page_width/2, 750, f"Informe por Curso - {nombre_curso}")

                c.setFont("Helvetica", 12)
                c.drawCentredString(page_width/2, 720, f"Fecha: {fecha_curso.strftime('%d/%m/%Y')}")

                # Filtrar alumnos del curso
                datos_curso = datos[datos["curso_id"] == curso_id]

                # Construir tabla
                tabla_data = [["Alumno", "Come", "Motivo"]]

                if datos_curso.empty:
                    tabla_data.append(["No hay datos", "-", "-"])
                else:
                    for _, row in datos_curso.iterrows():
                        tabla_data.append([
                            row["nombre"],
                            "Sí" if row["asiste"] else "No",
                            row["motivo"] or ""
                        ])

                tabla = Table(tabla_data, colWidths=[200, 80, 200])
                tabla.setStyle(TableStyle([
                    ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
                    ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
                    ("ALIGN", (0,0), (-1,-1), "CENTER"),
                    ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                    ("FONTSIZE", (0,0), (-1,-1), 11),
                ]))

                w, h = tabla.wrap(page_width, page_height)
                tabla.drawOn(c, 50, 680 - h)

                add_page_number(c)

            c.save()

            # Nombre del archivo
            nombre_archivo = (
                f"informe_curso_TODOS_{fecha_curso_str}.pdf"
                if curso_sel == "Todos los cursos"
                else f"informe_curso_{curso_sel}_{fecha_curso_str}.pdf"
            )

            st.download_button(
                label="Descargar Informe por Curso",
                data=buffer.getvalue(),
                file_name=nombre_archivo,
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
        # INFORME DE FALTAS
        # =========================
        st.subheader("Informe de Faltas")
        
        col1, col2 = st.columns(2)
        with col1:
            mes_f = st.selectbox("Selecciona mes", list(range(1, 13)), key="mes_faltas")
            año_f = st.number_input("Año", min_value=2020, max_value=2030, value=datetime.now().year, key="año_faltas")
        with col2:
            opciones_curso = ["Todos los cursos"] + df_cursos["nombre"].tolist()
            curso_f_nombre = st.selectbox("Selecciona curso", opciones_curso, key="curso_faltas")

        if st.button("Generar PDF de Faltas"):
            buffer = io.BytesIO()
            # Usamos landscape (apaisado) para que quepan todos los días del mes
            c = canvas.Canvas(buffer, pagesize=landscape(A4))
            page_width, page_height = landscape(A4)
            
            # Filtrar cursos a procesar
            if curso_f_nombre == "Todos los cursos":
                cursos_a_procesar = df_cursos.to_dict(orient="records")
            else:
                cursos_a_procesar = df_cursos[df_cursos["nombre"] == curso_f_nombre].to_dict(orient="records")

            dias_mes = calendar.monthrange(año_f, mes_f)[1]
            y_offset = page_height - 120 # Posición inicial debajo del logo/título
            cursos_en_pagina = 0

            for i, curso in enumerate(cursos_a_procesar):
                # Si ya hay 2 cursos en la página, saltamos de hoja
                if cursos_en_pagina == 2:
                    add_page_number(c)
                    c.showPage()
                    draw_logo_centered(c, page_width, page_height - 200)
                    y_offset = page_height - 120
                    cursos_en_pagina = 0

                # Dibujar logo y título solo si es el primer curso de la página
                if cursos_en_pagina == 0:
                    draw_logo_centered(c, page_width, page_height - 200)
                    c.setFont("Helvetica-Bold", 16)
                    c.drawCentredString(page_width/2, page_height - 90, f"Informe de Faltas - {mes_f}/{año_f}")

                # Título del curso actual
                c.setFont("Helvetica-Bold", 12)
                c.drawString(30, y_offset, f"Curso: {curso['nombre']}")
                y_offset -= 15

                # Cabecera de la tabla de faltas
                tabla_data = [["Alumno"] + [str(d) for d in range(1, dias_mes+1)]]
                
                # Obtener alumnos del curso
                alumnos_curso = df_alumnos[df_alumnos["curso_id"] == curso["id"]]
                
                # Estilos específicos para las "F" rojas
                estilos_celdas = [
                    ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
                    ("GRID", (0,0), (-1,-1), 0.25, colors.grey),
                    ("ALIGN", (0,0), (-1,-1), "CENTER"),
                    ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                    ("FONTSIZE", (0,0), (-1,-1), 8),
                    ("LEFTPADDING", (0,0), (-1,-1), 1),
                    ("RIGHTPADDING", (0,0), (-1,-1), 1),
                ]

                # Rellenar datos por alumno
                for fila_idx, (_, alumno) in enumerate(alumnos_curso.iterrows()):
                    fila = [alumno["nombre"]]
                    for dia in range(1, dias_mes+1):
                        fecha = f"{año_f}-{mes_f:02d}-{dia:02d}"
                        asistencia = df_asistencia[
                            (df_asistencia["alumno_id"] == alumno["id"]) & 
                            (df_asistencia["fecha"] == fecha)
                        ]
                        
                        # Si existe registro y "asiste" es False, es una falta
                        if not asistencia.empty and not asistencia.iloc[0]["asiste"]:
                            fila.append("F")
                            # Aplicar color rojo a esta celda específica (columna, fila)
                            col_idx = dia # La columna 0 es el nombre
                            estilos_celdas.append(('TEXTCOLOR', (col_idx, fila_idx + 1), (col_idx, fila_idx + 1), colors.red))
                            estilos_celdas.append(('FONTNAME', (col_idx, fila_idx + 1), (col_idx, fila_idx + 1), "Helvetica-Bold"))
                        else:
                            fila.append("")
                    tabla_data.append(fila)

                # Crear la tabla
                # Ajustamos anchos: nombre 120px, días 18px cada uno
                tabla = Table(tabla_data, colWidths=[120] + [18.5]*dias_mes)
                tabla.setStyle(TableStyle(estilos_celdas))

                w, h = tabla.wrap(0, 0)
                
                # Control de seguridad: Si el curso es tan largo que no cabe, saltar página
                if y_offset - h < 50:
                    add_page_number(c)
                    c.showPage()
                    draw_logo_centered(c, page_width, page_height - 200)
                    y_offset = page_height - 120
                    cursos_en_pagina = 0
                    # (Re-dibujar título del curso en la nueva página si fuera necesario)

                tabla.drawOn(c, 30, y_offset - h)
                y_offset -= (h + 40) # Espacio extra para el siguiente curso
                cursos_en_pagina += 1

            add_page_number(c)
            c.save()

            st.download_button(
                label="Descargar Informe de Faltas",
                data=buffer.getvalue(),
                file_name=f"faltas_{curso_f_nombre}_{mes_f}_{año_f}.pdf",
                mime="application/pdf"
            )


        # =========================
        # INFORME INDIVIDUAL (FACTURA)
        # =========================
        st.subheader("Informe Individual (Factura)")
        opciones_alumnos = ["Todos los alumnos"] + [a["nombre"] for _, a in df_alumnos.iterrows()]
        alumno_sel = st.selectbox("Selecciona alumno", opciones_alumnos, key="alumno_pdf")

        precio_menu = st.number_input("Precio del menú (€)", min_value=0.0, step=0.1)

        col1, col2 = st.columns(2)

        with col1:
            mes_sel = st.selectbox(
                "Selecciona mes",
                list(range(1, 13)),
                index=datetime.now().month - 1,
                key="mes_factura"
            )

        with col2:
            año_sel = st.number_input(
                "Año",
                min_value=2020,
                max_value=2035,
                value=datetime.now().year,
                key="año_factura"
            )

        if st.button("Generar Factura"):

            buffer = io.BytesIO()
            c = canvas.Canvas(buffer, pagesize=A4)
            page_width, page_height = A4

            # Determinar si es uno o todos
            if alumno_sel == "Todos los alumnos":
                lista_alumnos = df_alumnos.to_dict(orient="records")
            else:
                lista_alumnos = df_alumnos[df_alumnos["nombre"] == alumno_sel].to_dict(orient="records")

            mes_actual = mes_sel
            año_actual = año_sel


            primera_pagina = True

            for alumno in lista_alumnos:

                if not primera_pagina:
                    c.showPage()
                primera_pagina = False

                draw_logo_centered(c, page_width, page_height - 200)

                nombre = alumno["nombre"]
                curso = df_cursos[df_cursos["id"] == alumno["curso_id"]]["nombre"].iloc[0]

                c.setFont("Helvetica-Bold", 18)
                c.drawCentredString(page_width/2, 720, f"Factura Comedor - {nombre}")
                c.setFont("Helvetica", 12)
                c.drawCentredString(page_width/2, 700, f"Curso: {curso}")
                c.drawCentredString(page_width/2, 680, f"Fecha: {datetime.now().strftime('%d/%m/%Y')}")

                df_mes = df_asistencia[
                    (df_asistencia["alumno_id"] == alumno["id"]) &
                    (df_asistencia["fecha"].str.startswith(f"{año_actual}-{mes_actual:02d}"))
                ]

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

                w, h = tabla.wrap(page_width, page_height)
                y_tabla = 650 - h
                tabla.drawOn(c, 50, y_tabla)

                dias_comidos = df_mes["asiste"].sum()
                total_pagar = dias_comidos * precio_menu

                y_texto = y_tabla - 40
                c.setFont("Helvetica-Bold", 14)
                c.drawString(50, y_texto, f"Días asistidos: {dias_comidos}")
                c.drawString(50, y_texto - 20, f"Precio por menú: {precio_menu:.2f} €")
                c.setFont("Helvetica-Bold", 16)
                c.drawString(50, y_texto - 50, f"TOTAL A PAGAR: {total_pagar:.2f} €")

                add_page_number(c)

            c.save()

            st.download_button(
                label="Descargar Facturas",
                data=buffer.getvalue(),
                file_name=f"facturas_{mes_actual}_{año_actual}.pdf",
                mime="application/pdf"
            )

     
        # =========================================================
        # CUADRANTE MENSUAL OPTIMIZADO (SOLO MAESTROS ACTIVOS)
        # =========================================================
        st.subheader("Cuadrante Mensual de Maestros (Filtrado)")

        col_m1, col_m2 = st.columns(2)
        with col_m1:
            mes_m = st.selectbox("Selecciona mes", list(range(1, 13)), key="mes_maestros_filter")
        with col_m2:
            año_m = st.number_input("Año", min_value=2020, max_value=2030, value=datetime.now().year, key="año_maestros_filter")

        if st.button("Generar Informe Filtrado"):
            df_profes = db_select("profesores")
            df_comidas_raw = db_select("maestros_comidas")
            df_agua_raw = db_select("maestros_agua")
    
            prefix = f"{año_m}-{mes_m:02d}"
            dias_mes = calendar.monthrange(año_m, mes_m)[1]

            # --- FILTRAR MAESTROS QUE HAN COMIDO ALGÚN DÍA ---
            comidas_mes = df_comidas_raw[df_comidas_raw["fecha"].str.startswith(prefix)]
            ids_comen = comidas_mes["maestro_id"].unique()
            profes_comen = df_profes[df_profes["id"].isin(ids_comen)]

            # --- FILTRAR MAESTROS QUE HAN COGIDO AGUA ALGÚN DÍA ---
            agua_mes = df_agua_raw[df_agua_raw["fecha"].str.startswith(prefix)]
            ids_agua = agua_mes["maestro_id"].unique()
            profes_agua = df_profes[df_profes["id"].isin(ids_agua)]

            buffer = io.BytesIO()
            c = canvas.Canvas(buffer, pagesize=landscape(A4))
            page_width, page_height = landscape(A4)

            draw_logo_centered(c, page_width, page_height - 180)
            c.setFont("Helvetica-Bold", 16)
            c.drawCentredString(page_width/2, page_height - 80, f"Control Mensual Maestros - {mes_m}/{año_m}")

            y_pos = page_height - 100

            # -----------------------------------------------------
            # 1. TABLA DE COMIDAS (Solo si hay datos)
            # -----------------------------------------------------
            c.setFont("Helvetica-Bold", 11)
            c.drawString(30, y_pos, "Maestros que han comido este mes:")
            y_pos -= 15

            if not profes_comen.empty:
                data_c = [["Maestro"] + [str(d) for d in range(1, dias_mes+1)] + ["Total"]]
                for _, prof in profes_comen.iterrows():
                    fila = [prof["usuario"]]
                    total = 0
                    for d in range(1, dias_mes+1):
                        f = f"{prefix}-{d:02d}"
                        asiste = not comidas_mes[(comidas_mes["maestro_id"] == prof["id"]) & (comidas_mes["fecha"] == f)].empty
                        fila.append("X" if asiste else "")
                        if asiste: total += 1
                    fila.append(total)
                    data_c.append(fila)

                t1 = Table(data_c, colWidths=[90] + [20]*dias_mes + [35])
                t1.setStyle(TableStyle([
                    ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
                    ("FONTSIZE", (0,0), (-1,-1), 7),
                    ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
                    ("ALIGN", (1,0), (-1,-1), "CENTER"),
                ]))
                w1, h1 = t1.wrap(0,0)
                t1.drawOn(c, 30, y_pos - h1)
                y_pos -= (h1 + 40)
            else:
                c.setFont("Helvetica", 9)
                c.drawString(40, y_pos, "No hay registros de comidas para este mes.")
                y_pos -= 30

            # -----------------------------------------------------
            # 2. TABLA DE AGUA (Solo si hay datos)
            # -----------------------------------------------------
            c.setFont("Helvetica-Bold", 11)
            c.drawString(30, y_pos, "Consumo de Agua (Botellas 0.25 | 0.60):")
            y_pos -= 15

            if not profes_agua.empty:
                data_a = [["Maestro"] + [str(d) for d in range(1, dias_mes+1)]]
                for _, prof in profes_agua.iterrows():
                    fila = [prof["usuario"]]
                    for d in range(1, dias_mes+1):
                        f = f"{prefix}-{d:02d}"
                        reg = agua_mes[(agua_mes["maestro_id"] == prof["id"]) & (agua_mes["fecha"] == f)]
                        if not reg.empty:
                            a25, a60 = reg.iloc[0].get("agua_025", 0), reg.iloc[0].get("agua_060", 0)
                            fila.append(f"{int(a25)}|{int(a60)}" if (a25 > 0 or a60 > 0) else "")
                        else:
                            fila.append("")
                    data_a.append(fila)

                t2 = Table(data_a, colWidths=[90] + [20]*dias_mes)
                t2.setStyle(TableStyle([
                    ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
                    ("FONTSIZE", (0,0), (-1,-1), 6),
                    ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
                    ("ALIGN", (1,0), (-1,-1), "CENTER"),
                ]))
                w2, h2 = t2.wrap(0,0)
                t2.drawOn(c, 30, y_pos - h2)
            else:
                c.setFont("Helvetica", 9)
                c.drawString(40, y_pos, "No hay registros de agua para este mes.")
            
            # Nota explicativa
            c.setFont("Helvetica-Oblique", 8)
            c.drawString(30, 20, "* En la tabla de agua, el formato es: (Botellas 0.25€ | Botellas 0.60€)")
         
            c.save()
            st.download_button("Descargar Informe", data=buffer.getvalue(), file_name=f"cuadrante_activo_{mes_m}.pdf")
            
    
        # =========================================================
        # FACTURACIÓN DE MAESTROS (INDIVIDUAL Y MASIVA)
        # =========================================================
        st.subheader("Generación de Facturas - Maestros")

        # Controles de mes y precios
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            mes_f = st.selectbox("Mes de facturación", list(range(1, 13)), index=datetime.now().month-1, key="mes_fac_m")
        with col_f2:
            año_f = st.number_input("Año", value=datetime.now().year, key="año_fac_m")
        with col_f3:
            p_menu = st.number_input("Precio Menú (€)", value=4.50, step=0.10)

        col_f4, col_f5 = st.columns(2)
        with col_f4:
            p_agua_025 = st.number_input("Precio Agua 0.25€ (€)", value=0.25, step=0.05)
        with col_f5:
            p_agua_060 = st.number_input("Precio Agua 0.60€ (€)", value=0.60, step=0.05)

        # Función interna para dibujar una factura en el canvas
        def dibujar_factura_maestro(canvas_obj, maestro, mes, año, p_m, p_a25, p_a60):
            page_width, page_height = A4
            prefix = f"{año}-{mes:02d}"
    
            # Obtener datos
            df_c = db_select("maestros_comidas")
            df_a = db_select("maestros_agua")
    
            total_comidas = len(df_c[(df_c["maestro_id"] == maestro["id"]) & (df_c["fecha"].str.startswith(prefix))])
            reg_agua = df_a[(df_a["maestro_id"] == maestro["id"]) & (df_a["fecha"].str.startswith(prefix))]
            total_a25 = reg_agua["agua_025"].sum() if not reg_agua.empty else 0
            total_a60 = reg_agua["agua_060"].sum() if not reg_agua.empty else 0
    
            if total_comidas == 0 and total_a25 == 0 and total_a60 == 0:
                return False # No hay consumo

            # Encabezado y Logo
            draw_logo_centered(canvas_obj, page_width, page_height - 180)
            canvas_obj.setFont("Helvetica-Bold", 20)
            canvas_obj.drawCentredString(page_width/2, 700, "RECIBO DE COMEDOR")
    
            # Datos del Maestro
            canvas_obj.setFont("Helvetica-Bold", 12)
            canvas_obj.drawString(70, 650, f"MAESTRO/A: {maestro['usuario']}")
            canvas_obj.setFont("Helvetica", 12)
            canvas_obj.drawString(70, 635, f"Periodo: {calendar.month_name[mes]} {año}")
            canvas_obj.drawString(70, 620, f"Fecha emisión: {datetime.now().strftime('%d/%m/%Y')}")

            # Tabla de conceptos
            data = [
                ["CONCEPTO", "CANTIDAD", "PRECIO", "TOTAL"],
                ["Menú Escolar", total_comidas, f"{p_m:.2f} €", f"{total_comidas * p_m:.2f} €"],
                ["Agua 0.25€", int(total_a25), f"{p_a25:.2f} €", f"{total_a25 * p_a25:.2f} €"],
                ["Agua 0.60€", int(total_a60), f"{p_a60:.2f} €", f"{total_a60 * p_a60:.2f} €"]
            ]
    
            t = Table(data, colWidths=[200, 80, 80, 80])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
                ("GRID", (0,0), (-1,-1), 1, colors.black),
                ("ALIGN", (1,0), (-1,-1), "CENTER"),
                ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                ("BOTTOMPADDING", (0,0), (-1,-1), 10),
                ("TOPPADDING", (0,0), (-1,-1), 10),
            ]))
    
            w, h = t.wrap(page_width, page_height)
            t.drawOn(canvas_obj, 70, 500)
    
            # TOTAL FINAL
            gran_total = (total_comidas * p_m) + (total_a25 * p_a25) + (total_a60 * p_a60)
            canvas_obj.setFont("Helvetica-Bold", 16)
            canvas_obj.drawString(350, 470, f"TOTAL A PAGAR: {gran_total:.2f} €")
    
            # Pie de página / Firma
            canvas_obj.setFont("Helvetica-Oblique", 10)
            canvas_obj.drawString(70, 400, "Firma del responsable:")
            canvas_obj.line(70, 350, 200, 350)
    
            return True

        # --- Interfaz de Botones ---
        df_p = db_select("profesores")

        col_b1, col_b2 = st.columns(2)
        with col_b1:
            maestro_u = st.selectbox("Seleccionar Maestro para factura individual", 
                                    df_p.to_dict(orient="records"), format_func=lambda x: x["usuario"])
            if st.button("Generar Factura Individual"):
                buffer = io.BytesIO()
                c = canvas.Canvas(buffer, pagesize=A4)
                if dibujar_factura_maestro(c, maestro_u, mes_f, año_f, p_menu, p_agua_025, p_agua_060):
                    c.save()
                    st.download_button(f"Descargar Factura {maestro_u['usuario']}", buffer.getvalue(), f"factura_{maestro_u['usuario']}.pdf")
                else:
                    st.warning("Este maestro no tiene consumos en el mes seleccionado.")

        with col_b2:
            st.write("Generar todas las facturas del mes:")
            if st.button("Generar TODAS las Facturas (PDF Masivo)"):
                buffer = io.BytesIO()
                c = canvas.Canvas(buffer, pagesize=A4)
                facturas_generadas = 0
        
                for _, prof in df_p.iterrows():
                    # Intentamos dibujar la factura del maestro
                    if dibujar_factura_maestro(c, prof, mes_f, año_f, p_menu, p_agua_025, p_agua_060):
                        c.showPage() # Crear nueva página para el siguiente maestro
                        facturas_generadas += 1
        
                if facturas_generadas > 0:
                    c.save()
                    st.success(f"Se han generado {facturas_generadas} facturas.")
                    st.download_button("Descargar PDF Masivo", buffer.getvalue(), f"facturas_maestros_{mes_f}_{año_f}.pdf")
                else:
                    st.error("No hay consumos registrados para ningún maestro en este mes.")
                    
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


    # ---------------------------------------------------------
    # COMEDOR MAESTROS
    # ---------------------------------------------------------
    elif st.session_state.maestros in ["🍽️ Comidas", "💧 Agua"]:
        st.header("Comedor Maestros")

        # Cargamos profesores (maestros)
        df_profes = db_select("profesores")

        if df_profes.empty:
            st.info("No hay profesores registrados.")
        else:
            # sub_opcion = st.radio(
                # "Selecciona sección",
                # ["Comidas", "Agua"],
                # horizontal=True
            # )

            # =========================
            # SUBAPARTADO: COMIDAS MAESTROS
            # =========================
            if st.session_state.maestros == "🍽️ Comidas":
                st.subheader("Comidas de Maestros")

                # Selector de fecha
                fecha_comidas = st.date_input(
                    "Selecciona la fecha",
                    value=datetime.now().date(),
                    key="fecha_maestros_comidas"
                )
                fecha_comidas_str = fecha_comidas.strftime("%Y-%m-%d")

                # Cargamos registros existentes de esa fecha
                df_comidas = db_select("maestros_comidas")
                
                # Cargamos registros existentes de esa fecha
                df_comidas = db_select("maestros_comidas")

                # Verificamos si el DataFrame tiene la columna 'fecha'
                if not df_comidas.empty and "fecha" in df_comidas.columns:
                    df_comidas_dia = df_comidas[df_comidas["fecha"] == fecha_comidas_str]
                else:
                    # Si está vacío o no tiene la columna, creamos un DF vacío con la estructura correcta
                    df_comidas_dia = pd.DataFrame(columns=["maestro_id", "fecha", "come"])

                # Conjunto de maestros que ya tienen marcado 'come' ese día
                # Nota: 'maestro_id' es el nombre en la tabla 'maestros_comidas'
                maestros_que_comen = set(df_comidas_dia["maestro_id"].tolist())

                st.write("Marca los maestros que se quedan a comer:")

                checks_comen = {}
                for _, prof in df_profes.iterrows():
                    # ID de la tabla profesores para vincular
                    id_real = prof["id"] 
                    # Columna que identifica al maestro para mostrar en pantalla
                    nombre_maestro = prof["usuario"] 

                    marcado = id_real in maestros_que_comen

                    checks_comen[id_real] = st.checkbox(
                        nombre_maestro,
                        value=marcado,
                        key=f"come_maestro_{id_real}_{fecha_comidas_str}"
                    )

                if st.button("Guardar comidas de maestros"):
                    # Borramos registros existentes de ese día
                    supabase.table("maestros_comidas").delete().eq("fecha", fecha_comidas_str).execute()

                    # Insertamos solo los que están marcados
                    filas_insertar = []
                    for maestro_id, come in checks_comen.items():
                        if come:
                            filas_insertar.append({
                                "maestro_id": maestro_id,
                                "fecha": fecha_comidas_str,
                                "come": True
                            })

                    if filas_insertar:
                        supabase.table("maestros_comidas").insert(filas_insertar).execute()

                    st.success("Comidas de maestros guardadas correctamente.")

            # =========================
            # SUBAPARTADO: AGUA MAESTROS
            # =========================
            elif st.session_state.maestros == "💧 Agua":
                st.subheader("Consumo de agua por Maestros")

                # Selector de fecha
                fecha_agua = st.date_input(
                    "Selecciona la fecha",
                    value=datetime.now().date(),
                    key="fecha_maestros_agua"
                )
                fecha_agua_str = fecha_agua.strftime("%Y-%m-%d")

                # Cargamos registros existentes de esa fecha
                df_agua = db_select("maestros_agua")
                # Sección Agua Maestros
                df_agua = db_select("maestros_agua")

                if not df_agua.empty and "fecha" in df_agua.columns:
                    df_agua_dia = df_agua[df_agua["fecha"] == fecha_agua_str]
                else:
                    df_agua_dia = pd.DataFrame(columns=["maestro_id", "fecha", "agua_025", "agua_060"])

                # Diccionario maestro_id -> (agua_025, agua_060)
                agua_existente = {
                    row["maestro_id"]: (row.get("agua_025", 0), row.get("agua_060", 0))
                    for _, row in df_agua_dia.iterrows()
                }

                st.write("Registra el consumo de botellas de agua por maestro:")

                # 1. Ajustamos proporciones: [1.5, 1, 1] hace la columna del nombre más pequeña
                proporciones = [1.5, 1, 1]

                h_col1, h_col2, h_col3 = st.columns(proporciones)
                # Alineamos también los encabezados para que coincidan
                h_col1.markdown("<p style='text-align: right; font-weight: bold; margin-bottom: 0;'>Maestro</p>", unsafe_allow_html=True)
                # Aguas centradas sobre sus columnas
                h_col2.markdown("<p style='text-align: center; font-weight: bold; margin-bottom: 0;'>Agua 0,25€</p>", unsafe_allow_html=True)
                h_col3.markdown("<p style='text-align: center; font-weight: bold; margin-bottom: 0;'>Agua 0,60€</p>", unsafe_allow_html=True)

                inputs_agua = {}

                for _, prof in df_profes.iterrows():
                    id_real = prof["id"]
                    nombre_maestro = prof["usuario"]
                    valor_025, valor_060 = agua_existente.get(id_real, (0, 0))

                    row_col1, row_col2, row_col3 = st.columns(proporciones)

                    with row_col1:
                        # text-align: right para que el nombre se acerque a los números
                        st.markdown(
                            f"<div style='padding-top: 10px; text-align: right; padding-right: 15px;'>"
                            f"{nombre_maestro}</div>", 
                            unsafe_allow_html=True
                        )
    
                    with row_col2:
                        n_025 = st.number_input(
                            "Cantidad 0.25", 
                            min_value=0, max_value=20, value=int(valor_025),
                            step=1, key=f"agua025_{id_real}_{fecha_agua_str}",
                            label_visibility="collapsed"
                        )
        
                    with row_col3:
                        n_060 = st.number_input(
                            "Cantidad 0.60", 
                            min_value=0, max_value=20, value=int(valor_060),
                            step=1, key=f"agua060_{id_real}_{fecha_agua_str}",
                            label_visibility="collapsed" 
                    )

                    inputs_agua[id_real] = (n_025, n_060)

                if st.button("Guardar consumo de agua"):
                    # Borramos registros existentes de ese día
                    supabase.table("maestros_agua").delete().eq("fecha", fecha_agua_str).execute()

                    # Insertamos solo los maestros que tienen consumo
                    filas_insertar = []
                    for maestro_id, (n_025, n_060) in inputs_agua.items():
                        if n_025 > 0 or n_060 > 0:
                            filas_insertar.append({
                                "maestro_id": maestro_id,
                                "fecha": fecha_agua_str,
                                "agua_025": int(n_025),
                                "agua_060": int(n_060)
                            })

                    if filas_insertar:
                        supabase.table("maestros_agua").insert(filas_insertar).execute()

                    st.success("Consumo de agua de maestros guardado correctamente.")
