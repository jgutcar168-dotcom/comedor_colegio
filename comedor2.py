import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
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

import unicodedata

def normalizar(texto):
    if not isinstance(texto, str):
        return ""
    texto = texto.strip().lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto


# ---------------------------------------------------------
# LOGIN PROFESORADO
# ---------------------------------------------------------
def login():
    st.sidebar.subheader("Acceso Profesores")

    if "logged" not in st.session_state:
        st.session_state.logged = False
        st.session_state.profesor = None

    if not st.session_state.logged:
        usuario_input = st.sidebar.text_input("Usuario")
        password_input = st.sidebar.text_input("Contraseña", type="password")

        if st.sidebar.button("Entrar"):

            # Normalizar lo que escribe el profesor
            usuario_norm = normalizar(usuario_input)

            # Traer todos los profesores
            profesores = supabase.table("profesores").select("*").execute().data

            # Buscar coincidencia normalizada
            profesor_encontrado = None
            for prof in profesores:
                if normalizar(prof["usuario"]) == usuario_norm:
                    profesor_encontrado = prof
                    break

            # Validar
            if profesor_encontrado and profesor_encontrado["password"] == password_input:
                st.session_state.logged = True
                st.session_state.profesor = profesor_encontrado
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

def obtener_info_etapa(nombre_curso):
    nombre = nombre_curso.upper()
    if any(x in nombre for x in ["INF", "INFANTIL"]):
        return 1, colors.Color(0.9, 0.9, 1) # Azul muy claro
    if any(x in nombre for x in ["1º", "2º"]):
        return 2, colors.Color(0.9, 1, 0.9) # Verde muy claro
    if any(x in nombre for x in ["3º", "4º"]):
        return 3, colors.Color(1, 1, 0.8) # Amarillento
    if any(x in nombre for x in ["5º", "6º"]):
        return 4, colors.Color(1, 0.9, 0.9) # Rojizo/Salmón
    return 5, colors.white

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
# PASAR LISTA (ACTUALIZADO PARA MÚLTIPLES CURSOS)
# ---------------------------------------------------------
if diario == "📋 Pasar lista":
    st.header("Pasar Lista")

    df_alumnos = db_select("alumnos")
    df_cursos = db_select("cursos")
    df_asistencia = db_select("asistencia")

    fecha_hoy = datetime.now().strftime("%Y-%m-%d")

    # --- LÓGICA DE SELECCIÓN DE CURSO ---
    if rol == "admin":
        # El administrador ve todos los cursos
        cursos_disponibles = df_cursos.to_dict(orient="records")
        msg_seleccionar = "Selecciona curso (Admin)"
    else:
        # El profesor ve solo sus cursos asignados (convertimos el string "1,2,5" en lista)
        ids_profe = str(prof["curso_id"]).split(",")
        cursos_disponibles = df_cursos[df_cursos["id"].astype(str).isin(ids_profe)].to_dict(orient="records")
        msg_seleccionar = "Selecciona uno de tus cursos asignados"

    if not cursos_disponibles:
        st.warning("No tienes cursos asignados. Contacta con el administrador.")
    else:
        curso_sel = st.selectbox(
            msg_seleccionar,
            cursos_disponibles,
            format_func=lambda x: x["nombre"],
            key="curso_selector_lista"
        )
        curso_id = curso_sel["id"]

        # Filtrar alumnos del curso seleccionado
        alumnos_curso = df_alumnos[df_alumnos["curso_id"] == curso_id]

        st.subheader(f"Curso: {curso_sel['nombre']}")

        # Asistencias del día para este curso
        asistencia_hoy = df_asistencia[
            (df_asistencia["fecha"] == fecha_hoy) &
            (df_asistencia["curso_id"] == curso_id)
        ]

        estado = {}
        
        st.write("Marca los alumnos que asisten hoy al comedor:")

        # --- LISTADO DE ALUMNOS ---
        for _, alumno in alumnos_curso.iterrows():
            # Buscar si ya se había pasado lista hoy
            registro_previo = asistencia_hoy[asistencia_hoy["alumno_id"] == alumno["id"]]

            if registro_previo.empty:
                valor_inicial = True   # Por defecto: asiste
            else:
                valor_inicial = bool(registro_previo["asiste"].iloc[0])

            # Checkbox con nombre del alumno
            estado_asiste = st.checkbox(
                alumno["nombre"],
                value=valor_inicial,
                key=f"asiste_{alumno['id']}_{curso_id}" # Key única combinando alumno y curso
            )

            estado[alumno["id"]] = estado_asiste

        # --- GUARDAR ASISTENCIA ---
        if st.button("Guardar asistencia"):
            registros = []
            for alumno_id, asiste_val in estado.items():
                registros.append({
                    "fecha": fecha_hoy,
                    "alumno_id": alumno_id,
                    "curso_id": curso_id,
                    "asiste": asiste_val,
                    "motivo": "" # Siempre vacío según tu petición anterior
                })

            if registros:
                db_upsert("asistencia", registros, conflict_cols="alumno_id,fecha")
                st.success(f"Asistencia de {curso_sel['nombre']} guardada correctamente")
                st.rerun()
            else:
                st.error("No hay alumnos en este curso para registrar.")

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

        if not df_profes.empty:
            # --- NUEVA LÓGICA PARA MOSTRAR MÚLTIPLES CURSOS EN LA TABLA ---
            lista_final = []
            
            # Diccionario auxiliar para buscar nombres de cursos rápido por su ID
            dict_cursos = dict(zip(df_cursos['id'].astype(str), df_cursos['nombre']))

            for _, p in df_profes.iterrows():
                # Obtenemos los IDs del string "1,2" -> ["1", "2"]
                ids_str = str(p["curso_id"]).split(",")
                # Buscamos los nombres correspondientes
                nombres_cursos = [dict_cursos.get(i.strip(), "Desconocido") for i in ids_str]
                
                lista_final.append({
                    "usuario": p["usuario"],
                    "password": p["password"],
                    "Cursos": ", ".join(nombres_cursos) # Los unimos bonitos: "1ºA, 2ºB"
                })

            df_tabla_visual = pd.DataFrame(lista_final)
            st.dataframe(df_tabla_visual, hide_index=True, use_container_width=True)
        else:
            st.info("No hay profesores registrados todavía.")

        # ======================================================
        # AÑADIR NUEVO PROFESOR (CON MULTI-CURSO)
        # ======================================================
        st.subheader("Añadir nuevo profesor")
        with st.form("nuevo_profesor"):
            usuario = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
    
            # Multiselección para permitir varios cursos
            cursos_sel = st.multiselect(
                "Cursos asignados", 
                df_cursos.to_dict(orient="records"), 
                format_func=lambda x: x["nombre"]
            )

            if st.form_submit_button("Guardar"):
                usuario_norm = normalizar(usuario)
                duplicado = any(normalizar(u) == usuario_norm for u in df_profes["usuario"].tolist())

                if duplicado:
                    st.error("Este profesor ya está registrado.")
                elif not cursos_sel:
                    st.error("Debes asignar al menos un curso al profesor.")
                else:
                    try:
                        # Convertimos la lista de IDs seleccionados en un string separado por comas: "1,4,7"
                        ids_cursos_str = ",".join([str(c["id"]) for c in cursos_sel])
                
                        db_insert("profesores", [{
                            "usuario": usuario.strip(),
                            "password": password,
                            "curso_id": ids_cursos_str
                        }])
                        st.success(f"Profesor {usuario} añadido con {len(cursos_sel)} cursos.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al registrar: {e}")

        # ======================================================
        # MODIFICAR DATOS DEL PROFESOR
        # ======================================================
        st.subheader("Modificar datos del profesor")

        if not df_profes.empty:
            prof_sel = st.selectbox(
                "Selecciona profesor",
                df_profes.to_dict(orient="records"),
                format_func=lambda x: x["usuario"],
                key="prof_mod"
            )

            col_edit1, col_edit2 = st.columns(2)

            with col_edit1:
                # --- MODIFICAR NOMBRE Y CONTRASEÑA ---
                nuevo_nombre = st.text_input("Nuevo nombre", value=prof_sel.get("usuario", ""))
                nueva_pass = st.text_input("Nueva contraseña (vacío para no cambiar)", type="password")
        
                if st.button("Actualizar Datos Básicos"):
                    if nuevo_nombre.strip() == "":
                        st.error("El nombre no puede estar vacío.")
                    else:
                        update_data = {"usuario": nuevo_nombre.strip()}
                        if nueva_pass.strip() != "":
                            update_data["password"] = nueva_pass
                
                        supabase.table("profesores").update(update_data).eq("id", prof_sel["id"]).execute()
                        st.success("Datos actualizados.")
                        st.rerun()

            with col_edit2:
                # --- MODIFICAR CURSOS (MULTIPLE) ---
                # Recuperar IDs actuales y convertirlos en objetos para el multiselect
                ids_actuales = [i.strip() for i in str(prof_sel.get("curso_id", "")).split(",") if i.strip()]
                cursos_default = df_cursos[df_cursos["id"].astype(str).isin(ids_actuales)].to_dict(orient="records")

                nuevos_cursos_multi = st.multiselect(
                    "Modificar cursos asignados",
                    df_cursos.to_dict(orient="records"),
                    default=cursos_default,
                    format_func=lambda x: x["nombre"],
                    key="multi_mod_cursos"
                )

                if st.button("Actualizar Cursos"):
                    if not nuevos_cursos_multi:
                        st.error("Debe tener al menos un curso.")
                    else:
                        nuevos_ids_str = ",".join([str(c["id"]) for c in nuevos_cursos_multi])
                        supabase.table("profesores").update({"curso_id": nuevos_ids_str}).eq("id", prof_sel["id"]).execute()
                        st.success("Lista de cursos actualizada.")
                        st.rerun()

        # ======================================================
        # ELIMINAR PROFESOR
        # ======================================================
        st.write("---")
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

       
        st.subheader("Modificar curso")

        if not df_cursos.empty:

            curso_mod = st.selectbox(
                "Selecciona curso a modificar",
                df_cursos.to_dict(orient="records"),
                format_func=lambda x: x["nombre"],
                key="curso_mod"
            )

            # Normalizar orden para evitar errores
            try:
                orden_actual = int(curso_mod["orden"])
                if orden_actual < 1:
                    orden_actual = 1
            except:
                orden_actual = 1

            nuevo_nombre = st.text_input(
                "Nuevo nombre del curso",
                value=curso_mod["nombre"],
                key="nuevo_nombre_curso"
            )

            nuevo_orden = st.number_input(
                "Nuevo orden (nivel)",
                min_value=1,
                step=1,
                value=orden_actual,
                key="nuevo_orden_curso"
            )

            nueva_letra = st.text_input(
                "Nueva letra",
                value=curso_mod["letra"],
                max_chars=1,
                key="nueva_letra_curso"
            )

            if st.button("Actualizar curso"):
                if nuevo_nombre.strip() == "":
                    st.error("El nombre no puede estar vacío.")
                else:
                    supabase.table("cursos").update({
                        "nombre": nuevo_nombre.strip(),
                        "orden": nuevo_orden,
                        "letra": nueva_letra.upper()
                    }).eq("id", curso_mod["id"]).execute()

                    st.success("Curso actualizado correctamente.")
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
            # ... (código anterior igual hasta la creación de 'conteo')

            conteo = resumen.groupby("nombre_curso").size().reset_index(name="Cantidad")

            # 1. Calculamos el total general
            total_comensales = conteo["Cantidad"].sum()

            for _, row in conteo.iterrows():
                tabla_data.append([row["nombre_curso"], row["Cantidad"]])

            # 2. Añadimos la fila de TOTAL al final de la tabla
            tabla_data.append(["TOTAL GENERAL", total_comensales])

            tabla = Table(tabla_data, colWidths=[250, 100])

            # 3. Actualizamos el estilo para resaltar la última fila
            tabla.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
                ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
                ("ALIGN", (0,0), (-1,-1), "CENTER"),
                ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                # Ponemos en negrita la última fila (la del total)
                ("FONTNAME", (0,-1), (-1,-1), "Helvetica-Bold"), 
                # Un fondo ligeramente distinto para el total si lo deseas
                ("BACKGROUND", (0,-1), (-1,-1), colors.whitesmoke),
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

        
        # =========================================================
        # INFORME DE SITUACIÓN EN MESA (CON MEMORIA PERMANENTE)
        # =========================================================
        st.write("---")
        st.subheader("📍 Informe de Situación en Mesa")
        st.info("Configura la distribución de los alumnos en las tres filas del comedor. Esta configuración se guardará hasta que realices cambios.")

        # 1. CARGA DE DATOS
        df_cursos = db_select("cursos")
        df_alumnos = db_select("alumnos")
        
        try:
            df_config_prev = db_select("config_mesas")
        except:
            df_config_prev = pd.DataFrame()

        # --- UNIÓN LIMPIA DE DATOS ---
        # Renombramos 'nombre' en cursos para evitar conflictos con 'nombre' de alumno
        df_cursos_ren = df_cursos.rename(columns={"nombre": "nombre_curso"})
        
        # Hacemos el merge
        df_alumnos_full = df_alumnos.merge(df_cursos_ren[["id", "nombre_curso"]], 
                                           left_on="curso_id", 
                                           right_on="id", 
                                           suffixes=("", "_c"))
        
        # Nos aseguramos de que solo queden las columnas necesarias y sin nombres extraños
        df_alumnos_full = df_alumnos_full[["id", "nombre", "nombre_curso", "curso_id"]]
        df_alumnos_full = df_alumnos_full.sort_values(by="curso_id")

        # --- FUNCIÓN DE DEFAULTS ---
        def obtener_defaults(fila_num):
            if df_config_prev is not None and not df_config_prev.empty:
                if "fila" in df_config_prev.columns and "id_alumno" in df_config_prev.columns:
                    ids_en_fila = df_config_prev[df_config_prev["fila"] == fila_num]["id_alumno"].tolist()
                    # Filtrar y asegurar que los diccionarios tengan las llaves correctas
                    seleccionados = df_alumnos_full[df_alumnos_full["id"].isin(ids_en_fila)]
                    return seleccionados.to_dict('records')
            return []
            
        # 2. INTERFAZ DE EDICIÓN (3 Columnas)
        col_m1, col_m2, col_m3 = st.columns(3)

        with col_m1:
            st.markdown("### 🪑 INFANTIL")
            m1_sel = st.multiselect("Alumnos fila 1", df_alumnos_full.to_dict('records'), 
                                   default=obtener_defaults(1), 
                                   format_func=lambda x: f"{x['nombre']} ({x['nombre_curso']})", 
                                   key="m1_final")
        with col_m2:
            st.markdown("### 🪑 MEDIANOS")
            m2_sel = st.multiselect("Alumnos fila 2", df_alumnos_full.to_dict('records'), 
                                   default=obtener_defaults(2), 
                                   format_func=lambda x: f"{x['nombre']} ({x['nombre_curso']})", 
                                   key="m2_final")
        with col_m3:
            st.markdown("### 🪑 GRANDES")
            m3_sel = st.multiselect("Alumnos fila 3", df_alumnos_full.to_dict('records'), 
                                   default=obtener_defaults(3), 
                                   format_func=lambda x: f"{x['nombre']} ({x['nombre_curso']})", 
                                   key="m3_final")

        # 3. ACCIONES: GUARDAR Y GENERAR
        c_btn1, c_btn2 = st.columns(2)

        with c_btn1:
            if st.button("💾 Guardar Cambios de Mesa", use_container_width=True):
                try:
                    # Borramos la configuración vieja para escribir la nueva
                    supabase.table("config_mesas").delete().neq("id", -1).execute() 
                    
                    nuevos_reg = []
                    for a in m1_sel: nuevos_reg.append({"id_alumno": a["id"], "fila": 1})
                    for a in m2_sel: nuevos_reg.append({"id_alumno": a["id"], "fila": 2})
                    for a in m3_sel: nuevos_reg.append({"id_alumno": a["id"], "fila": 3})
                    
                    if nuevos_reg:
                        db_insert("config_mesas", nuevos_reg)
                        st.success("Configuración guardada correctamente.")
                        st.rerun()
                    else:
                        st.warning("No has seleccionado alumnos para guardar.")
                except Exception as e:
                    st.error(f"Error al guardar: {e}")

        with c_btn2:
            # --- MODIFICACIÓN EN LA GENERACIÓN DEL PDF DE MESAS ---

            if st.button("🖨️ Generar PDF de Situación", type="primary", use_container_width=True):
            # 1. Obtener la asistencia de HOY
            fecha_hoy_str = datetime.now().strftime("%Y-%m-%d")
            df_asistencia_hoy = db_select("asistencia")
            df_asistencia_hoy = df_asistencia_hoy[df_asistencia_hoy["fecha"] == fecha_hoy_str]
    
            ids_asisten_hoy = df_asistencia_hoy[df_asistencia_hoy["asiste"] == True]["alumno_id"].tolist()

            if not any([m1_sel, m2_sel, m3_sel]):
                st.error("Debes asignar alumnos a las mesas primero.")
            else:
                if not ids_asisten_hoy:
                    st.warning("No hay registros de asistencia hoy. Usando selección completa.")
                    ids_asisten_hoy = [a["id"] for a in (m1_sel + m2_sel + m3_sel)] 

                # Filtrar y ordenar
                m1_pdf = sorted([a for a in m1_sel if a["id"] in ids_asisten_hoy], key=lambda x: x['curso_id'])
                m2_pdf = sorted([a for a in m2_sel if a["id"] in ids_asisten_hoy], key=lambda x: x['curso_id'])
                m3_pdf = sorted([a for a in m3_sel if a["id"] in ids_asisten_hoy], key=lambda x: x['curso_id'])

                buffer = io.BytesIO()
                # Usamos SimpleDocTemplate para multipágina automático
                doc = SimpleDocTemplate(
                    buffer, 
                    pagesize=landscape(A4),
                    rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30
                )
        
                elementos = []
                estilos_p = getSampleStyleSheet()
        
                # --- TÍTULO ---
                titulo = f"SITUACIÓN EN MESA - {datetime.now().strftime('%d/%m/%Y')}"
                elementos.append(Paragraph(f"<b>{titulo}</b>", estilos_p['Title']))
                elementos.append(Spacer(1, 10))

                # --- PREPARAR DATOS DE LA TABLA ---
                max_filas = max(len(m1_pdf), len(m2_pdf), len(m3_pdf))
                tabla_data = [["INFANTIL", "MEDIANOS", "GRANDES"]]
        
                estilos_tabla = [
                    ("BACKGROUND", (0,0), (-1,0), colors.black),
                    ("TEXTCOLOR", (0,0), (-1,0), colors.white),
                    ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
                    ("ALIGN", (0,0), (-1,-1), "CENTER"),
                    ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                    ("FONTSIZE", (0,0), (-1,-1), 9),
                ]

                # Cuerpo de la tabla
                for i in range(max_filas):
                    fila_cont = []
                    for col_idx, lista in enumerate([m1_pdf, m2_pdf, m3_pdf]):
                        if i < len(lista):
                            alu = lista[i]
                            fila_cont.append(f"{alu['nombre']}\n({alu['nombre_curso']})")
                            _, color_f = obtener_info_etapa(alu['nombre_curso'])
                            estilos_tabla.append(("BACKGROUND", (col_idx, i+1), (col_idx, i+1), color_f))
                        else:
                            fila_cont.append("")
                    tabla_data.append(fila_cont)

                # --- FILA DE SUMATORIOS POR COLUMNA ---
                total_m1, total_m2, total_m3 = len(m1_pdf), len(m2_pdf), len(m3_pdf)
                total_general = total_m1 + total_m2 + total_m3
        
                tabla_data.append([f"SUBTOTAL: {total_m1}", f"SUBTOTAL: {total_m2}", f"SUBTOTAL: {total_m3}"])
                idx_ultima = len(tabla_data) - 1
                estilos_tabla.append(("BACKGROUND", (0, idx_ultima), (-1, idx_ultima), colors.lightgrey))
                estilos_tabla.append(("FONTNAME", (0, idx_ultima), (-1, idx_ultima), "Helvetica-Bold"))

                # Construir tabla
                ancho_col = (doc.width) / 3
                t_mesas = Table(tabla_data, colWidths=[ancho_col]*3, repeatRows=1)
                t_mesas.setStyle(TableStyle(estilos_tabla))
                elementos.append(t_mesas)
        
                # --- TOTAL GENERAL ---
                elementos.append(Spacer(1, 15))
                elementos.append(Paragraph(f"<para align='right'><b>TOTAL ALUMNOS COMEDOR: {total_general}</b></para>", estilos_p['Normal']))

                # Función para números de página
                def numeracion(canvas, doc):
                    num = canvas.getPageNumber()
                    canvas.drawRightString(landscape(A4)[0] - 30, 20, f"Página {num}")

                # Generar el documento
                doc.build(elementos, onLaterPages=numeracion, onFirstPage=numeracion)
        
                st.download_button(
                    "📩 Descargar PDF de Situación Real", 
                    buffer.getvalue(), 
                    f"mesas_completo_{fecha_hoy_str}.pdf", 
                    "application/pdf", 
                    use_container_width=True
                )

        # =========================
        # INFORME POR CURSO (MODIFICADO: Sin Motivo y Centrado)
        # =========================
        st.subheader("Informe por Curso")

        opciones_cursos = ["Todos los cursos"] + df_cursos[df_cursos["nombre"].str.lower() != "ninguno"]["nombre"].tolist()
        curso_sel = st.selectbox("Selecciona curso", opciones_cursos, key="curso_pdf")

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

            if curso_sel == "Todos los cursos":
                lista_cursos = df_cursos[df_cursos["nombre"].str.lower() != "ninguno"].to_dict(orient="records")
            else:
                lista_cursos = df_cursos[df_cursos["nombre"] == curso_sel].to_dict(orient="records")

            df_dia = df_asistencia[df_asistencia["fecha"] == fecha_curso_str]
            datos = df_dia.merge(df_alumnos, left_on="alumno_id", right_on="id")

            if "curso_id_y" in datos.columns:
                datos = datos.rename(columns={"curso_id_y": "curso_id"})
            elif "curso_id_x" in datos.columns:
                datos = datos.rename(columns={"curso_id_x": "curso_id"})

            primera_pagina = True 
            
            for curso in lista_cursos: 
                if not primera_pagina: 
                    c.showPage() 
                primera_pagina = False

                draw_logo_centered(c, page_width, page_height - 190)

                nombre_curso = curso["nombre"]
                curso_id = curso["id"]

                c.setFont("Helvetica-Bold", 18)
                c.drawCentredString(page_width/2, 750, f"Informe por Curso - {nombre_curso}")

                c.setFont("Helvetica", 12)
                c.drawCentredString(page_width/2, 720, f"Fecha: {fecha_curso.strftime('%d/%m/%Y')}")

                datos_curso = datos[datos["curso_id"] == curso_id]

                # --- 1. CABECERA MODIFICADA (Sin Motivo) ---
                tabla_data = [["Alumno", "Come"]]

                if datos_curso.empty:
                    tabla_data.append(["No hay datos", "-"])
                else:
                    for _, row in datos_curso.iterrows():
                        # --- 2. FILA MODIFICADA (Solo 2 columnas) ---
                        tabla_data.append([
                            row["nombre"],
                            "Sí" if row["asiste"] else "No"
                        ])

                # --- 3. TABLA CENTRADA ---
                # Definimos anchos: Alumno (300) y Come (100) = 400 total
                anchos = [300, 100]
                total_tabla = sum(anchos)
                x_centrada = (page_width - total_tabla) / 2

                tabla = Table(tabla_data, colWidths=anchos)
                tabla.setStyle(TableStyle([
                    ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
                    ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
                    ("ALIGN", (0,0), (-1,-1), "CENTER"),
                    ("ALIGN", (0,0), (0,-1), "LEFT"), # Nombre a la izquierda para mejor lectura
                    ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                    ("FONTSIZE", (0,0), (-1,-1), 11),
                    ("LEFTPADDING", (0,0), (0,-1), 15), # Margen interno para el nombre
                ]))

                w, h = tabla.wrap(page_width, page_height)
                # Usamos x_centrada para que la tabla quede en medio
                tabla.drawOn(c, x_centrada, 680 - h)

                add_page_number(c)

            c.save()

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

            # EXCLUIR CURSO "NINGUNO"
            df_cursos_filtrado = df_cursos[df_cursos["nombre"].str.lower() != "ninguno"]

            # Cabecera
            tabla_data = [["Curso"] + [str(d) for d in range(1, dias_mes+1)] + ["Total"]]

            # Para totales verticales
            totales_por_dia = [0] * dias_mes

            for _, curso in df_cursos_filtrado.iterrows():
                fila = [curso["nombre"]]
                total_curso = 0

                for dia in range(1, dias_mes+1):
                    fecha = f"{año}-{mes:02d}-{dia:02d}"
                    asistencias = df_asistencia[(df_asistencia["fecha"] == fecha) & (df_asistencia["asiste"] == True)]
                    alumnos_dia = asistencias.merge(df_alumnos, left_on="alumno_id", right_on="id")

                    # Normalizar columna curso_id
                    if "curso_id_y" in alumnos_dia.columns:
                        alumnos_dia = alumnos_dia.rename(columns={"curso_id_y": "curso_id"})
                    elif "curso_id_x" in alumnos_dia.columns:
                        alumnos_dia = alumnos_dia.rename(columns={"curso_id_x": "curso_id"})

                    alumnos_dia = alumnos_dia[alumnos_dia["curso_id"] == curso["id"]]
                    n = len(alumnos_dia)

                    fila.append(n)
                    total_curso += n
                    totales_por_dia[dia - 1] += n

                fila.append(total_curso)
                tabla_data.append(fila)

            # Añadir fila de totales verticales
            fila_totales = ["Total día"] + totales_por_dia + [sum(totales_por_dia)]
            tabla_data.append(fila_totales)

            # Crear tabla
            tabla = Table(tabla_data, colWidths=[70] + [18]*dias_mes + [40])
            tabla.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
                ("BACKGROUND", (0, len(tabla_data)-1), (-1, len(tabla_data)-1), colors.lightgrey),
                ("GRID", (0,0), (-1,-1), 0.25, colors.grey),
                ("ALIGN", (0,0), (-1,-1), "CENTER"),
                ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                ("FONTNAME", (0, len(tabla_data)-1), (-1, len(tabla_data)-1), "Helvetica-Bold"),
                ("FONTSIZE", (0,0), (-1,-1), 12),
                ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ]))

            # ============================
            # SOMBREADO ALTERNADO DE FILAS
            # ============================
            for fila_idx in range(1, len(tabla_data) - 1):  # desde 1 para no afectar cabecera ni fila total
                if fila_idx % 2 == 0:  # filas pares
                    tabla.setStyle(TableStyle([
                        ("BACKGROUND", (0, fila_idx), (-1, fila_idx), colors.whitesmoke)
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
            opciones_curso = ["Todos los cursos"] + df_cursos[df_cursos["nombre"].str.lower() != "ninguno"]["nombre"].tolist()
            curso_f_nombre = st.selectbox("Selecciona curso", opciones_curso, key="curso_faltas")

        if st.button("Generar PDF de Faltas"):
            buffer = io.BytesIO()
            c = canvas.Canvas(buffer, pagesize=landscape(A4))
            page_width, page_height = landscape(A4)

            # Filtrar cursos
            if curso_f_nombre == "Todos los cursos":
                cursos_a_procesar = df_cursos[df_cursos["nombre"].str.lower() != "ninguno"].to_dict(orient="records")
            else:
                cursos_a_procesar = df_cursos[df_cursos["nombre"] == curso_f_nombre].to_dict(orient="records")

            dias_mes = calendar.monthrange(año_f, mes_f)[1]
            y_offset = page_height - 120
            cursos_en_pagina = 0

            for i, curso in enumerate(cursos_a_procesar):

                if cursos_en_pagina == 2:
                    add_page_number(c)
                    c.showPage()
                    draw_logo_centered(c, page_width, page_height - 200)
                    y_offset = page_height - 120
                    cursos_en_pagina = 0

                if cursos_en_pagina == 0:
                    draw_logo_centered(c, page_width, page_height - 200)
                    c.setFont("Helvetica-Bold", 16)
                    c.drawCentredString(page_width/2, page_height - 90, f"Informe de Faltas - {mes_f}/{año_f}")

                c.setFont("Helvetica-Bold", 12)
                c.drawString(30, y_offset, f"Curso: {curso['nombre']}")
                y_offset -= 15

                # CABECERA CON TOTAL
                tabla_data = [["Alumno"] + [str(d) for d in range(1, dias_mes+1)] + ["Total"]]

                alumnos_curso = df_alumnos[df_alumnos["curso_id"] == curso["id"]]

                estilos_celdas = [
                    ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
                    ("GRID", (0,0), (-1,-1), 0.25, colors.grey),
                    ("ALIGN", (0,0), (-1,-1), "CENTER"),
                    ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                    ("FONTSIZE", (0,0), (-1,-1), 8),
                    ("LEFTPADDING", (0,0), (-1,-1), 1),
                    ("RIGHTPADDING", (0,0), (-1,-1), 1),
                ]

                # RELLENAR DATOS
                for fila_idx, (_, alumno) in enumerate(alumnos_curso.iterrows()):
                    fila = [alumno["nombre"]]
                    faltas_alumno = 0

                    for dia in range(1, dias_mes+1):
                        fecha = f"{año_f}-{mes_f:02d}-{dia:02d}"
                        asistencia = df_asistencia[
                            (df_asistencia["alumno_id"] == alumno["id"]) & 
                            (df_asistencia["fecha"] == fecha)
                        ]

                        if not asistencia.empty and not asistencia.iloc[0]["asiste"]:
                            fila.append("F")
                            faltas_alumno += 1
                            col_idx = dia
                            estilos_celdas.append(('TEXTCOLOR', (col_idx, fila_idx + 1), (col_idx, fila_idx + 1), colors.red))
                            estilos_celdas.append(('FONTNAME', (col_idx, fila_idx + 1), (col_idx, fila_idx + 1), "Helvetica-Bold"))
                        else:
                            fila.append("")

                    # AÑADIR TOTAL DE FALTAS
                    fila.append(faltas_alumno)
                    tabla_data.append(fila)
                    
                # Crear la tabla
                # Ajustamos anchos: nombre 120px, días 18px cada uno + total
                tabla = Table(tabla_data, colWidths=[120] + [18.5]*dias_mes + [30])

                # Estilos base
                tabla.setStyle(TableStyle(estilos_celdas))

                # ============================
                # SOMBREADO ALTERNADO DE FILAS
                # ============================
                for fila_idx in range(1, len(tabla_data)):  # desde 1 para no afectar a la cabecera
                    if fila_idx % 2 == 0:  # filas pares
                        tabla.setStyle(TableStyle([
                            ("BACKGROUND", (0, fila_idx), (-1, fila_idx), colors.whitesmoke)
                        ]))

                # # TABLA CON COLUMNA EXTRA
                # tabla = Table(tabla_data, colWidths=[120] + [18.5]*dias_mes + [30])
                # tabla.setStyle(TableStyle(estilos_celdas))

                w, h = tabla.wrap(0, 0)

                if y_offset - h < 50:
                    add_page_number(c)
                    c.showPage()
                    draw_logo_centered(c, page_width, page_height - 200)
                    y_offset = page_height - 120
                    cursos_en_pagina = 0

                tabla.drawOn(c, 30, y_offset - h)
                y_offset -= (h + 40)
                cursos_en_pagina += 1

            add_page_number(c)
            c.save()

            st.download_button(
                label="Descargar Informe de Faltas",
                data=buffer.getvalue(),
                file_name=f"faltas_{curso_f_nombre}_{mes_f}_{año_f}.pdf",
                mime="application/pdf"
            )


        # # =========================
        # # INFORME INDIVIDUAL (FACTURA)
        # # =========================
        # st.subheader("Informe Individual (Factura)")
        # opciones_alumnos = ["Todos los alumnos"] + [a["nombre"] for _, a in df_alumnos.iterrows()]
        # alumno_sel = st.selectbox("Selecciona alumno", opciones_alumnos, key="alumno_pdf")

        # precio_menu = st.number_input("Precio del menú (€)", min_value=0.0, step=0.1)

        # col1, col2 = st.columns(2)

        # with col1:
            # mes_sel = st.selectbox(
                # "Selecciona mes",
                # list(range(1, 13)),
                # index=datetime.now().month - 1,
                # key="mes_factura"
            # )

        # with col2:
            # año_sel = st.number_input(
                # "Año",
                # min_value=2020,
                # max_value=2035,
                # value=datetime.now().year,
                # key="año_factura"
            # )

        # if st.button("Generar Factura"):

            # buffer = io.BytesIO()
            # c = canvas.Canvas(buffer, pagesize=A4)
            # page_width, page_height = A4

            # # Determinar si es uno o todos
            # if alumno_sel == "Todos los alumnos":
                # lista_alumnos = df_alumnos.to_dict(orient="records")
            # else:
                # lista_alumnos = df_alumnos[df_alumnos["nombre"] == alumno_sel].to_dict(orient="records")

            # mes_actual = mes_sel
            # año_actual = año_sel


            # primera_pagina = True

            # for alumno in lista_alumnos:

                # if not primera_pagina:
                    # c.showPage()
                # primera_pagina = False

                # draw_logo_centered(c, page_width, page_height - 200)

                # nombre = alumno["nombre"]
                # curso = df_cursos[df_cursos["id"] == alumno["curso_id"]]["nombre"].iloc[0]

                # c.setFont("Helvetica-Bold", 18)
                # c.drawCentredString(page_width/2, 720, f"Factura Comedor - {nombre}")
                # c.setFont("Helvetica", 12)
                # c.drawCentredString(page_width/2, 700, f"Curso: {curso}")
                # c.drawCentredString(page_width/2, 680, f"Fecha: {datetime.now().strftime('%d/%m/%Y')}")

                # df_mes = df_asistencia[
                    # (df_asistencia["alumno_id"] == alumno["id"]) &
                    # (df_asistencia["fecha"].str.startswith(f"{año_actual}-{mes_actual:02d}"))
                # ]

                # tabla_data = [["Fecha", "Come", "Motivo"]]
                # for _, row in df_mes.iterrows():
                    # tabla_data.append([row["fecha"], "Sí" if row["asiste"] else "No", row["motivo"] or ""])

                # tabla = Table(tabla_data, colWidths=[120, 60, 250])
                # tabla.setStyle(TableStyle([
                    # ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
                    # ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
                    # ("ALIGN", (0,0), (-1,-1), "CENTER"),
                    # ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                    # ("FONTSIZE", (0,0), (-1,-1), 11),
                # ]))

                # w, h = tabla.wrap(page_width, page_height)
                # y_tabla = 650 - h
                # tabla.drawOn(c, 50, y_tabla)

                # dias_comidos = df_mes["asiste"].sum()
                # total_pagar = dias_comidos * precio_menu

                # y_texto = y_tabla - 40
                # c.setFont("Helvetica-Bold", 14)
                # c.drawString(50, y_texto, f"Días asistidos: {dias_comidos}")
                # c.drawString(50, y_texto - 20, f"Precio por menú: {precio_menu:.2f} €")
                # c.setFont("Helvetica-Bold", 16)
                # c.drawString(50, y_texto - 50, f"TOTAL A PAGAR: {total_pagar:.2f} €")

                # add_page_number(c)

            # c.save()

            # st.download_button(
                # label="Descargar Facturas",
                # data=buffer.getvalue(),
                # file_name=f"facturas_{mes_actual}_{año_actual}.pdf",
                # mime="application/pdf"
            # )

     
        # =========================================================
        # CUADRANTE MAESTROS CON SALTO DE PÁGINA AUTOMÁTICO
        # =========================================================
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet

        st.subheader("Cuadrante de Maestros (Optimizado y Multipage)")

        rango_m = st.date_input(
            "Selecciona el intervalo de fechas",
            value=[datetime.now().date(), datetime.now().date()],
            key="rango_maestros_multipage"
        )

        if isinstance(rango_m, (list, tuple)) and len(rango_m) == 2:
            fecha_inicio, fecha_fin = rango_m
            f_ini_str = fecha_inicio.strftime("%Y-%m-%d")
            f_fin_str = fecha_fin.strftime("%Y-%m-%d")

            if st.button("Generar Informe Multipágina"):
                df_profes = db_select("profesores")
                df_comidas_raw = db_select("maestros_comidas")
                df_agua_raw = db_select("maestros_agua")

                # 1. Filtrar actividad
                comidas_rango = df_comidas_raw[(df_comidas_raw["fecha"] >= f_ini_str) & (df_comidas_raw["fecha"] <= f_fin_str)]
                agua_rango = df_agua_raw[(df_agua_raw["fecha"] >= f_ini_str) & (df_agua_raw["fecha"] <= f_fin_str)]

                # 2. Días activos
                fechas_activas = sorted(list(set(comidas_rango["fecha"].unique()) | set(agua_rango["fecha"].unique())))
                dias_datos = [datetime.strptime(f, "%Y-%m-%d").date() for f in fechas_activas]
                num_dias = len(dias_datos)

                if num_dias == 0:
                    st.warning("No hay actividad en las fechas seleccionadas.")
                else:
                    ids_activos = set(comidas_rango["maestro_id"].unique()) | set(agua_rango["maestro_id"].unique())
                    profes_activos = df_profes[df_profes["id"].isin(ids_activos)]

                    buffer = io.BytesIO()
                    # Usamos SimpleDocTemplate para gestionar las páginas automáticamente
                    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), 
                                            rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
            
                    elementos = [] # Lista donde guardaremos todo lo que va al PDF
                    estilos = getSampleStyleSheet()
            
                    # Título
                    titulo = f"Informe de Maestros: {fecha_inicio.strftime('%d/%m/%y')} al {fecha_fin.strftime('%d/%m/%y')}"
                    elementos.append(Paragraph(f"<b>{titulo}</b>", estilos['Title']))
                    elementos.append(Spacer(1, 20))

                    # --- TABLA COMIDAS ---
                    elementos.append(Paragraph("<b>Asistencia a Comedor:</b>", estilos['Normal']))
                    elementos.append(Spacer(1, 10))
            
                    header_c = ["Maestro"] + [d.strftime('%d/%m') for d in dias_datos] + ["Total"]
                    data_c = [header_c]
            
                    for _, p in profes_activos.iterrows():
                        fila = [p["usuario"]]
                        tot = 0
                        for d in dias_datos:
                            f_s = d.strftime("%Y-%m-%d")
                            check = not comidas_rango[(comidas_rango["maestro_id"] == p["id"]) & (comidas_rango["fecha"] == f_s)].empty
                            fila.append("X" if check else "")
                            if check: tot += 1
                        fila.append(tot)
                        data_c.append(fila)

                    ancho_col = 30 if num_dias < 15 else 20
                    t1 = Table(data_c, colWidths=[100] + [ancho_col]*num_dias + [40], repeatRows=1)
                    t1.setStyle(TableStyle([
                        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
                        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
                        ("ALIGN", (1,0), (-1,-1), "CENTER"),
                        ("FONTSIZE", (0,0), (-1,-1), 8),
                    ]))
                    elementos.append(t1)
                    elementos.append(Spacer(1, 30))

                    # --- TABLA AGUA ---
                    elementos.append(Paragraph("<b>Consumo de Agua (0.25 | 0.60):</b>", estilos['Normal']))
                    elementos.append(Spacer(1, 10))

                    data_a = [["Maestro"] + [d.strftime('%d/%m') for d in dias_datos]]
                    for _, p in profes_activos.iterrows():
                        fila = [p["usuario"]]
                        for d in dias_datos:
                            f_s = d.strftime("%Y-%m-%d")
                            reg = agua_rango[(agua_rango["maestro_id"] == p["id"]) & (agua_rango["fecha"] == f_s)]
                            if not reg.empty:
                                a25, a60 = reg.iloc[0].get("agua_025", 0), reg.iloc[0].get("agua_060", 0)
                                fila.append(f"{int(a25)}|{int(a60)}" if (a25 > 0 or a60 > 0) else "")
                            else:
                                fila.append("")
                        data_a.append(fila)

                    t2 = Table(data_a, colWidths=[100] + [ancho_col]*num_dias, repeatRows=1)
                    t2.setStyle(TableStyle([
                        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
                        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
                        ("ALIGN", (1,0), (-1,-1), "CENTER"),
                        ("FONTSIZE", (0,0), (-1,-1), 7),
                    ]))
                    elementos.append(t2)
            
                    # Nota final
                    elementos.append(Spacer(1, 20))
                    elementos.append(Paragraph("<font size=8><i>* Solo se muestran días con actividad. Formato agua: (Bot. 0.25€ | Bot. 0.60€)</i></font>", estilos['Normal']))

                    # Construir PDF
                    doc.build(elementos)
            
                    st.success("Informe generado con éxito.")
                    st.download_button(
                        "Descargar Informe (Multipágina)", 
                        data=buffer.getvalue(), 
                        file_name=f"informe_maestros_{f_ini_str}.pdf"
                    )
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
        def dibujar_factura_maestro(canvas_obj, maestro, f_ini, f_fin, p_m, p_a25, p_a60):
            page_width, page_height = A4

            # Obtener datos de la base de datos
            df_c = db_select("maestros_comidas")
            df_a = db_select("maestros_agua")
        
            # Filtrado por rango de fechas (usando las variables f_ini y f_fin)
            mask_c = (df_c["maestro_id"] == maestro["id"]) & (df_c["fecha"] >= f_ini) & (df_c["fecha"] <= f_fin)
            mask_a = (df_a["maestro_id"] == maestro["id"]) & (df_a["fecha"] >= f_ini) & (df_a["fecha"] <= f_fin)
    
            # Cálculo de totales basados en el filtrado por rango
            total_comidas = len(df_c[mask_c])
            reg_agua = df_a[mask_a]
    
            total_a25 = reg_agua["agua_025"].sum() if not reg_agua.empty else 0
            total_a60 = reg_agua["agua_060"].sum() if not reg_agua.empty else 0
    
            # Si no hay ningún consumo, no generamos la página
            if total_comidas == 0 and total_a25 == 0 and total_a60 == 0:
                return False 

            # Encabezado y Logo
            draw_logo_centered(canvas_obj, page_width, page_height - 180)
            canvas_obj.setFont("Helvetica-Bold", 20)
            canvas_obj.drawCentredString(page_width/2, 700, "RECIBO DE COMEDOR")
    
            # Datos del Maestro
            canvas_obj.setFont("Helvetica-Bold", 12)
            canvas_obj.drawString(70, 650, f"MAESTRO/A: {maestro['usuario']}")
            canvas_obj.setFont("Helvetica", 12)
    
            # Formateamos las fechas para que el recibo se vea más profesional (DD/MM/YYYY)
            f_ini_dt = datetime.strptime(f_ini, "%Y-%m-%d").strftime("%d/%m/%Y")
            f_fin_dt = datetime.strptime(f_fin, "%Y-%m-%d").strftime("%d/%m/%Y")
    
            canvas_obj.drawString(70, 635, f"Periodo: del {f_ini_dt} al {f_fin_dt}")
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
    
            return True
        # --- Interfaz de Botones Actualizada ---
        df_p = db_select("profesores")

        # Extraemos las fechas del selector de rango (rango_m es el st.date_input que pusimos antes)
        if isinstance(rango_m, (list, tuple)) and len(rango_m) == 2:
            f_ini_str = rango_m[0].strftime("%Y-%m-%d")
            f_fin_str = rango_m[1].strftime("%Y-%m-%d")
    
            col_b1, col_b2 = st.columns(2)
    
            with col_b1:
                maestro_u = st.selectbox("Seleccionar Maestro para factura individual", 
                                        df_p.to_dict(orient="records"), format_func=lambda x: x["usuario"])
        
                if st.button("Generar Factura Individual"):
                    buffer = io.BytesIO()
                    c = canvas.Canvas(buffer, pagesize=A4)
                    # Pasamos f_ini_str y f_fin_str en lugar de mes/año
                    if dibujar_factura_maestro(c, maestro_u, f_ini_str, f_fin_str, p_menu, p_agua_025, p_agua_060):
                        c.save()
                        st.download_button(
                            label=f"Descargar Factura {maestro_u['usuario']}", 
                            data=buffer.getvalue(), 
                            file_name=f"factura_{maestro_u['usuario']}_{f_ini_str}.pdf"
                        )
                    else:
                        st.warning("Este maestro no tiene consumos en el periodo seleccionado.")

            with col_b2:
                st.write("Generar todas las facturas del periodo:")
                if st.button("Generar TODAS las Facturas (PDF Masivo)"):
                    buffer = io.BytesIO()
                    c = canvas.Canvas(buffer, pagesize=A4)
                    facturas_generadas = 0
    
                    for _, prof in df_p.iterrows():
                        # Intentamos dibujar la factura del maestro con el rango
                        if dibujar_factura_maestro(c, prof, f_ini_str, f_fin_str, p_menu, p_agua_025, p_agua_060):
                            c.showPage() 
                            facturas_generadas += 1
    
                    if facturas_generadas > 0:
                        c.save()
                        st.success(f"Se han generado {facturas_generadas} facturas.")
                        st.download_button(
                            label="Descargar PDF Masivo", 
                            data=buffer.getvalue(), 
                            file_name=f"facturas_maestros_{f_ini_str}_al_{f_fin_str}.pdf"
                        )
                    else:
                        st.error("No hay consumos registrados para ningún maestro en este periodo.")
        else:
            st.info("Por favor, selecciona un rango de fechas (Inicio y Fin) en el calendario de arriba para habilitar la facturación.")
            
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
