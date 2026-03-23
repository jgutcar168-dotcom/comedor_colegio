from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
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
st.cache_data.clear()
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

        elif rol == "cocina":
            opciones_diario = ["🍽️ Panel cocina"]

        else:  # profesor
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
    # GRUPO: INFORMES (admin + cocina)
    # ---------------------------
    if rol in ["admin", "cocina"]:
        with st.expander("📄 Informes", expanded=False):

            if rol == "admin":
                opciones_informes = ["📝 Informes PDF"]

            elif rol == "cocina":
                opciones_informes = ["📊 Informe de situación en mesa"]

            informes = st.radio(
                "   ",
                opciones_informes,
                label_visibility="collapsed",
                index=None,
                key="informes",
                on_change=set_nav,
                args=(st.session_state.get("informes"), "informes")
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
# INFORME PARA COCINA (solo rol cocina)
# ---------------------------------------------------------
if rol == "cocina" and st.session_state.informes == "📊 Informe de situación en mesa":

    st.header("Informe de situación en mesa")

    # Cargar datos
    df_asistencia = db_select("asistencia")
    df_alumnos = db_select("alumnos")
    df_cursos = db_select("cursos")

    # Cargar configuración de mesas (creada por admin)
    try:
        df_config = db_select("config_mesas")
    except:
        df_config = pd.DataFrame()

    if df_config.empty:
        st.warning("No hay configuración de mesas guardada por el administrador.")
        st.stop()

    # Fecha de hoy
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")

    # Filtrar asistencia de hoy
    df_hoy = df_asistencia[
        (df_asistencia["fecha"] == fecha_hoy) &
        (df_asistencia["asiste"] == True)
    ]

    if df_hoy.empty:
        st.warning("No hay alumnos registrados hoy en el comedor.")
        st.stop()

    # IDs de alumnos que asisten hoy
    ids_hoy = df_hoy["alumno_id"].astype(int).tolist()

    # Unir alumnos con cursos
    df_cursos_ren = df_cursos.rename(columns={"nombre": "nombre_curso"})
    df_alumnos_full = df_alumnos.merge(
        df_cursos_ren[["id", "nombre_curso"]],
        left_on="curso_id",
        right_on="id",
        suffixes=("", "_c")
    )

    # Filtrar solo alumnos que asisten hoy
    df_alumnos_hoy = df_alumnos_full[df_alumnos_full["id"].isin(ids_hoy)]

    # Preparar listas por fila
    m1 = df_alumnos_hoy[df_alumnos_hoy["id"].isin(df_config[df_config["fila"] == 1]["id_alumno"])]
    m2 = df_alumnos_hoy[df_alumnos_hoy["id"].isin(df_config[df_config["fila"] == 2]["id_alumno"])]
    m3 = df_alumnos_hoy[df_alumnos_hoy["id"].isin(df_config[df_config["fila"] == 3]["id_alumno"])]

    # Ordenar por curso
    m1 = m1.sort_values("curso_id")
    m2 = m2.sort_values("curso_id")
    m3 = m3.sort_values("curso_id")

    # Botón para generar PDF
    if st.button("📄 Descargar PDF de situación en mesa", type="primary", use_container_width=True):

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            rightMargin=30, leftMargin=30, topMargin=40, bottomMargin=30
        )

        elementos = []
        estilos = getSampleStyleSheet()

        # Título
        titulo = f"SITUACIÓN EN MESA - {datetime.now().strftime('%d/%m/%Y')}"
        elementos.append(Paragraph(f"<b>{titulo}</b>", estilos['Title']))
        elementos.append(Spacer(1, 15))

        # Preparar tabla
        tabla_data = [["INFANTIL", "MEDIANOS", "GRANDES"]]

        # Estilos base de la tabla (cabecera, grid, alineación…)
        estilos_tabla = [
            ("BACKGROUND", (0,0), (-1,0), colors.black),
            ("TEXTCOLOR", (0,0), (-1,0), colors.white),
            ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("FONTSIZE", (0,0), (-1,-1), 9),
        ]

        max_filas = max(len(m1), len(m2), len(m3))

        for i in range(max_filas):
            fila = []
            for col_idx, lista in enumerate([m1, m2, m3]):
                if i < len(lista):
                    alu = lista.iloc[i]
                    fila.append(f"{alu['nombre']}\n({alu['nombre_curso']})")

                    # Obtener color según etapa
                    _, color_f = obtener_info_etapa(alu['nombre_curso'])

                    # Aplicar color a la celda
                    estilos_tabla.append(
                        ("BACKGROUND", (col_idx, i+1), (col_idx, i+1), color_f)
                    )
                else:
                    fila.append("")
            tabla_data.append(fila)

        # Totales por columna
        tabla_data.append([
            f"Total: {len(m1)}",
            f"Total: {len(m2)}",
            f"Total: {len(m3)}"
        ])

        # Resaltar fila de totales
        estilos_tabla.append(
            ("BACKGROUND", (0, len(tabla_data)-1), (-1, len(tabla_data)-1), colors.lightgrey)
        )
        estilos_tabla.append(
            ("FONTNAME", (0, len(tabla_data)-1), (-1, len(tabla_data)-1), "Helvetica-Bold")
        )

        # Crear tabla
        ancho_util = landscape(A4)[0] - 60
        tabla = Table(tabla_data, colWidths=[ancho_util/3]*3, repeatRows=1)
        tabla.setStyle(TableStyle(estilos_tabla))

        elementos.append(tabla)

        # -----------------------------
        # TOTAL GENERAL DE COMENSALES
        # -----------------------------
        total_general = len(m1) + len(m2) + len(m3)

        elementos.append(Spacer(1, 20))
        elementos.append(Paragraph(
            f"<para align='right' size='14'><b>TOTAL COMENSALES HOY: {total_general}</b></para>",
            estilos['Normal']
        ))

        # Construir PDF
        doc.build(elementos)

        st.download_button(
            "📥 Descargar PDF",
            buffer.getvalue(),
            f"situacion_mesa_{fecha_hoy}.pdf",
            "application/pdf",
            use_container_width=True
        )


# ---------------------------------------------------------
# NAVEGACIÓN PRINCIPAL SEGÚN EL MENÚ PREMIUM
# ---------------------------------------------------------

# =========================================================
# 📅 DIARIO
# =========================================================

# ---------------------------------------------------------
# PASAR LISTA (VERSIÓN SIN CACHÉ)
# ---------------------------------------------------------
if diario == "📋 Pasar lista":
    st.header("📋 Pasar Lista")

    # Forzamos la carga fresca de datos de Supabase SIN USAR db_select si tiene caché
    df_alumnos = supabase.table("alumnos").select("*").execute().data
    df_alumnos = pd.DataFrame(df_alumnos)
    df_cursos = supabase.table("cursos").select("*").execute().data
    df_cursos = pd.DataFrame(df_cursos)
    
    # IMPORTANTE: Cargamos asistencia de hoy directamente de Supabase, sin pasar por filtros de Streamlit
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    res_asist = supabase.table("asistencia").select("*").eq("fecha", fecha_hoy).execute()
    df_asistencia = pd.DataFrame(res_asist.data)

    if rol == "admin":
        cursos_disponibles = df_cursos.to_dict(orient="records")
    else:
        ids_profe = str(prof["curso_id"]).split(",")
        cursos_disponibles = df_cursos[df_cursos["id"].astype(str).isin(ids_profe)].to_dict(orient="records")

    if not cursos_disponibles:
        st.warning("No tienes cursos asignados.")
    else:
        curso_sel = st.selectbox("Selecciona curso:", cursos_disponibles, format_func=lambda x: x["nombre"], key="sel_v4")
        c_id = int(curso_sel["id"])

        alumnos_curso = df_alumnos[df_alumnos["curso_id"] == c_id].copy().sort_values(by="nombre")
        
        # Filtramos la asistencia que acabamos de bajar de Supabase
        asist_actual = df_asistencia[df_asistencia["curso_id"] == c_id] if not df_asistencia.empty else pd.DataFrame()

        estado_checks = {}
        for _, alu in alumnos_curso.iterrows():
            reg = asist_actual[asist_actual["alumno_id"] == alu["id"]]
            valor_db = True if reg.empty else bool(reg["asiste"].iloc[0])

            # Usamos una key que depende del curso y de la fecha para que no se hereden valores
            estado_checks[alu["id"]] = st.checkbox(alu["nombre"], value=valor_db, key=f"v4_{c_id}_{alu['id']}")

        if st.button("💾 GUARDAR AHORA", type="primary"):
            registros = [{"fecha": fecha_hoy, "alumno_id": int(a_id), "curso_id": c_id, "asiste": bool(v), "motivo": ""} for a_id, v in estado_checks.items()]
            
            # Borramos e insertamos (Fuerza bruta)
            supabase.table("asistencia").delete().eq("fecha", fecha_hoy).eq("curso_id", c_id).execute()
            supabase.table("asistencia").insert(registros).execute()
            
            st.success("¡Datos enviados a la nube!")
            st.cache_data.clear() # Limpiamos toda la caché de la app
            st.rerun()
                    
# ---------------------------------------------------------
# PANEL DE COCINA (VERSIÓN TIEMPO REAL)
# ---------------------------------------------------------
elif diario == "🍽️ Panel cocina":
    st.header("🍽️ Panel para Cocina")
    st.cache_data.clear() # Limpieza total al entrar

    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    
    # Consultas directas a Supabase (Saltándonos tu función db_select por si tiene caché)
    asist_data = supabase.table("asistencia").select("*").eq("fecha", fecha_hoy).eq("asiste", True).execute().data
    cursos_data = supabase.table("cursos").select("*").execute().data
    
    if not asist_data:
        st.warning(f"No hay comensales registrados para hoy ({fecha_hoy}).")
    else:
        df_asist = pd.DataFrame(asist_data)
        df_curs = pd.DataFrame(cursos_data)
        
        df_asist["curso_id"] = df_asist["curso_id"].astype(int)
        df_curs["id"] = df_curs["id"].astype(int)

        # Merge directo
        resumen = df_asist.merge(df_curs, left_on="curso_id", right_on="id")
        
        st.metric("TOTAL COMENSALES", len(resumen))
        conteo = resumen.groupby("nombre").size().reset_index(name="Alumnos")
        st.table(conteo.rename(columns={"nombre": "Curso"}))
# ---------------------------------------------------------
# CONTROL DE ASISTENCIA (VERSIÓN TIEMPO REAL)
# ---------------------------------------------------------
elif diario == "✔️ Control de asistencia" and rol == "admin":
    st.header("✔️ Control de Asistencia")
    st.cache_data.clear() # Limpieza total

    fecha_hoy = datetime.now().strftime("%Y-%m-%d")

    # CONSULTA DIRECTA (Sin db_select)
    asist_data = supabase.table("asistencia").select("curso_id").eq("fecha", fecha_hoy).execute().data
    cursos_data = supabase.table("cursos").select("id, nombre").execute().data
    
    df_cursos_raw = pd.DataFrame(cursos_data)
    # Excluimos "Ninguno"
    df_cursos = df_cursos_raw[df_cursos_raw["nombre"].str.lower() != "ninguno"].copy()
    df_cursos["id"] = df_cursos["id"].astype(int)

    # IDs de cursos que han pasado lista hoy
    if asist_data:
        cursos_con_lista = pd.DataFrame(asist_data)["curso_id"].unique().astype(int).tolist()
    else:
        cursos_con_lista = []

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("✅ Han pasado lista")
        df_ok = df_cursos[df_cursos["id"].isin(cursos_con_lista)]
        if df_ok.empty:
            st.info("Nadie todavía.")
        else:
            st.table(df_ok[["nombre"]].rename(columns={"nombre": "Curso"}))

    with col2:
        st.subheader("❌ Pendientes")
        df_pend = df_cursos[~df_cursos["id"].isin(cursos_con_lista)]
        if df_pend.empty:
            st.success("¡Todos los cursos al día!")
        else:
            st.table(df_pend[["nombre"]].rename(columns={"nombre": "Curso"}))
            
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
    # GESTIÓN DE ASISTENCIAS (ORDENADO ALFABÉTICAMENTE)
    # ---------------------------------------------------------
    elif gestion == "📊 Gestión de asistencias":
        st.header("Gestión de asistencias por día")

        df_asistencia = db_select("asistencia")
        df_alumnos = db_select("alumnos")

        fecha_sel = st.date_input("Selecciona un día", datetime.now())
        fecha_str = fecha_sel.strftime("%Y-%m-%d")

        # 1. Filtrar asistencias del día
        datos = df_asistencia[df_asistencia["fecha"] == fecha_str].copy()

        if datos.empty:
            st.info("No hay registros de asistencia para este día.")
            st.stop()

        # 2. Unir con alumnos para obtener los nombres
        datos = datos.merge(df_alumnos, left_on="alumno_id", right_on="id", suffixes=("", "_alumno"))

        # --- CAMBIO CLAVE: ORDENADO ALFABÉTICO ---
        # Ordenamos los datos por el nombre del alumno antes de mostrarlos en el editor
        datos = datos.sort_values(by="nombre")

        st.subheader(f"Asistencias del {fecha_sel.strftime('%d/%m/%Y')}")

        # 3. Selección segura de columnas
        columnas_disponibles = datos.columns.tolist()
        columnas_a_mostrar = ["alumno_id", "nombre", "asiste", "curso_id"]
        
        if "curso_academico" in columnas_disponibles:
            columnas_a_mostrar.append("curso_academico")

        # 4. Mostrar el editor de datos (ya ordenado)
        editable = st.data_editor(
            datos[columnas_a_mostrar],
            num_rows="fixed",
            hide_index=True,
            key="editor_gest_asistencia_ordenado"
        )

        # --- BOTÓN GUARDAR CAMBIOS ---
        if st.button("Guardar cambios"):
            try:
                registros_update = []
                for _, row in editable.iterrows():
                    reg = {
                        "alumno_id": int(row["alumno_id"]),
                        "fecha": fecha_str,
                        "curso_id": int(row["curso_id"]),
                        "asiste": bool(row["asiste"]),
                        "motivo": str(row["motivo"])
                    }
                    if "curso_academico" in row:
                        reg["curso_academico"] = row["curso_academico"]
                    
                    registros_update.append(reg)

                supabase.table("asistencia").upsert(
                    registros_update, 
                    on_conflict="alumno_id,fecha"
                ).execute()

                st.success("✅ Cambios guardados y ordenados correctamente.")
                st.cache_data.clear()
            except Exception as e:
                st.error(f"Error al guardar: {e}")

        st.divider()

        # --- ELIMINAR REGISTRO (Las opciones también saldrán ordenadas) ---
        st.subheader("Eliminar registro de asistencia")
        
        opciones_borrar = editable[["alumno_id", "nombre"]].copy()
        opciones_borrar["opcion"] = opciones_borrar["alumno_id"].astype(str) + " - " + opciones_borrar["nombre"]

        seleccion = st.selectbox("Selecciona el registro a eliminar", options=opciones_borrar["opcion"])
    
   
    # ---------------------------------------------------------
# INFORMES PDF (VERSIÓN CON NORMALIZACIÓN DE DATOS)
# ---------------------------------------------------------
    if st.session_state.informes == "📝 Informes PDF":

        st.header("Generación de Informes PDF")
    
        # 1. CARGA DIRECTA Y LIMPIEZA DE CACHÉ
        st.cache_data.clear()

        with st.spinner("Sincronizando con la base de datos..."):
            # Asistencia
            res_asist = supabase.table("asistencia").select("*").execute()
            df_asistencia = pd.DataFrame(res_asist.data)
        
            # Alumnos
            res_alu = supabase.table("alumnos").select("*").execute()
            df_alumnos = pd.DataFrame(res_alu.data)
        
            # Cursos
            res_cur = supabase.table("cursos").select("*").execute()
            df_cursos = pd.DataFrame(res_cur.data)

            # Maestros (puedes dejarlos como estaban o directos)
            df_comidas = db_select("maestros_comidas")
            df_agua = db_select("maestros_agua")

        # 2. CRÍTICO: NORMALIZACIÓN DE TIPOS (Evita fallos en el Merge)
        # Esto asegura que los IDs sean siempre números y no den error al comparar
        if not df_asistencia.empty:
            df_asistencia["alumno_id"] = pd.to_numeric(df_asistencia["alumno_id"], errors='coerce')
            df_asistencia["curso_id"] = pd.to_numeric(df_asistencia["curso_id"], errors='coerce')
    
        if not df_alumnos.empty:
            df_alumnos["id"] = pd.to_numeric(df_alumnos["id"], errors='coerce')
            df_alumnos["curso_id"] = pd.to_numeric(df_alumnos["curso_id"], errors='coerce')
            
        if not df_cursos.empty:
            df_cursos["id"] = pd.to_numeric(df_cursos["id"], errors='coerce')

        fecha_hoy = datetime.now().strftime("%Y-%m-%d")

      
        # =========================
        # INFORME DIARIO PARA COCINA (CONEXIÓN DIRECTA SIN CACHÉ)
        # =========================
        st.subheader("Informe Diario para Cocina")

        fecha_diario = st.date_input(
            "Selecciona la fecha del informe",
            value=datetime.now().date(),
            key="fecha_informe_diario"
        )
        fecha_diario_str = fecha_diario.strftime("%Y-%m-%d")

        if st.button("Generar PDF Diario", type="primary"):
            # --- PASO 1: LIMPIEZA DE CACHÉ Y CARGA FRESCA ---
            # Forzamos a que Streamlit olvide los datos viejos
            st.cache_data.clear()
            
            with st.spinner("Obteniendo datos actualizados de Supabase..."):
                # Cargamos directamente sin pasar por funciones previas
                r_asis = supabase.table("asistencia").select("*").eq("fecha", fecha_diario_str).execute()
                df_asis_fresco = pd.DataFrame(r_asis.data)
                
                r_alu = supabase.table("alumnos").select("*").execute()
                df_alu_fresco = pd.DataFrame(r_alu.data)
                
                r_cur = supabase.table("cursos").select("*").execute()
                df_cur_fresco = pd.DataFrame(r_cur.data)

            if df_asis_fresco.empty:
                st.warning(f"No hay registros de asistencia para el día {fecha_diario.strftime('%d/%m/%Y')}")
            else:
                # --- PASO 2: MAPEO DE NOMBRES ---
                # Creamos diccionarios con los datos RECIÉN TRAÍDOS
                dict_cursos = {str(row['id']): str(row['nombre']) for _, row in df_cur_fresco.iterrows()}
                dict_alu_nombre = {str(row['id']): str(row['nombre']) for _, row in df_alu_fresco.iterrows()}
                dict_alu_curso = {str(row['id']): str(row['curso_id']) for _, row in df_alu_fresco.iterrows()}

                # Solo los que asisten
                comensales_hoy = df_asis_fresco[df_asis_fresco["asiste"] == True].copy()
                
                lista_nombres_cursos = []
                for _, fila in comensales_hoy.iterrows():
                    id_alumno = str(fila["alumno_id"])
                    id_curso_del_alumno = dict_alu_curso.get(id_alumno, "Sin ID")
                    
                    # Buscamos el nombre del curso. Si no existe el ID, usamos el valor que tenga (por si ya es un nombre)
                    nombre_final = dict_cursos.get(id_curso_del_alumno, id_curso_del_alumno)
                    lista_nombres_cursos.append(nombre_final)

                df_pdf = pd.DataFrame({"curso": lista_nombres_cursos})
                conteo = df_pdf.groupby("curso").size().reset_index(name="Total")
                conteo = conteo.sort_values("curso")

                # --- PASO 3: CONSTRUCCIÓN DEL PDF ---
                buffer = io.BytesIO()
                c = canvas.Canvas(buffer, pagesize=A4)
                page_width, page_height = A4

                draw_logo_centered(c, page_width, page_height - 190)
                c.setFont("Helvetica-Bold", 18)
                c.drawCentredString(page_width/2, 750, f"Informe Diario - {fecha_diario.strftime('%d/%m/%Y')}")

                tabla_data = [["Curso", "Comensales"]]
                for _, row in conteo.iterrows():
                    tabla_data.append([str(row["curso"]), row["Total"]])
                
                tabla_data.append(["TOTAL GENERAL", conteo["Total"].sum()])

                tabla = Table(tabla_data, colWidths=[250, 100])
                tabla.setStyle(TableStyle([
                    ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
                    ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
                    ("ALIGN", (0,0), (-1,-1), "CENTER"),
                    ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                    ("FONTNAME", (0,-1), (-1,-1), "Helvetica-Bold"),
                    ("BACKGROUND", (0,-1), (-1,-1), colors.whitesmoke),
                ]))

                w, h = tabla.wrap(page_width, page_height)
                y_pos = 700 - h
                tabla.drawOn(c, 50, y_pos)

                # Observaciones
                y_pos -= 40
                c.setFont("Helvetica-Bold", 14)
                c.drawString(50, y_pos, "Observaciones:")
                y_pos -= 20
                c.setFont("Helvetica", 10)
                
                obs_hoy = df_asis_fresco[df_asis_fresco["motivo"].fillna("") != ""]
                if obs_hoy.empty:
                    c.drawString(60, y_pos, "Sin observaciones.")
                else:
                    for _, row in obs_hoy.iterrows():
                        nombre_a = dict_alu_nombre.get(str(row["alumno_id"]), "Alumno")
                        c.drawString(60, y_pos, f"• {nombre_a}: {row['motivo']}")
                        y_pos -= 15

                add_page_number(c)
                c.save()

                st.success("PDF generado con datos frescos de la base de datos.")
                st.download_button(
                    label="📥 Descargar Informe Diario",
                    data=buffer.getvalue(),
                    file_name=f"informe_diario_{fecha_diario_str}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
        # =========================================================
        # INFORME DE SITUACIÓN EN MESA (VERSIÓN CORREGIDA)
        # =========================================================
        st.write("---")
        st.subheader("📍 Informe de Situación en Mesa")
        st.info("Configura la distribución de los alumnos. Esta configuración se guarda permanentemente.")

        # 1. CARGA DE DATOS FRESCOS
        st.cache_data.clear() # Limpiamos para asegurar datos reales
        df_cursos = db_select("cursos")
        df_alumnos = db_select("alumnos")
        
        try:
            df_config_prev = db_select("config_mesas")
        except:
            df_config_prev = pd.DataFrame()

        # --- MAPEO ROBUSTO (SIN MERGES) ---
        # Creamos diccionarios para evitar el error de columnas inexistentes
        dict_nombres_curso = {str(k): str(v) for k, v in zip(df_cursos["id"], df_cursos["nombre"])}
        
        # Preparamos la lista de alumnos con su nombre de curso ya integrado
        lista_alumnos_procesada = []
        for _, alu in df_alumnos.iterrows():
            id_cur = str(alu["curso_id"])
            nombre_c = dict_nombres_curso.get(id_cur, id_cur) # Si no hay ID, usa el valor (por si ya es nombre)
            lista_alumnos_procesada.append({
                "id": alu["id"],
                "nombre": alu["nombre"],
                "nombre_curso": nombre_c,
                "curso_id": alu["curso_id"]
            })
        
        df_alumnos_full = pd.DataFrame(lista_alumnos_procesada)
        df_alumnos_full = df_alumnos_full.sort_values(by="nombre_curso")

        # --- FUNCIÓN DE DEFAULTS ---
        def obtener_defaults(fila_num):
            if df_config_prev is not None and not df_config_prev.empty:
                if "fila" in df_config_prev.columns and "id_alumno" in df_config_prev.columns:
                    ids_en_fila = df_config_prev[df_config_prev["fila"] == fila_num]["id_alumno"].tolist()
                    seleccionados = df_alumnos_full[df_alumnos_full["id"].isin(ids_en_fila)]
                    return seleccionados.to_dict('records')
            return []
            
        # 2. INTERFAZ DE EDICIÓN
        col_m1, col_m2, col_m3 = st.columns(3)

        with col_m1:
            st.markdown("### 🪑 INFANTIL")
            m1_sel = st.multiselect("Fila 1", df_alumnos_full.to_dict('records'), 
                                   default=obtener_defaults(1), 
                                   format_func=lambda x: f"{x['nombre']} ({x['nombre_curso']})", 
                                   key="m1_final")
        with col_m2:
            st.markdown("### 🪑 MEDIANOS")
            m2_sel = st.multiselect("Fila 2", df_alumnos_full.to_dict('records'), 
                                   default=obtener_defaults(2), 
                                   format_func=lambda x: f"{x['nombre']} ({x['nombre_curso']})", 
                                   key="m2_final")
        with col_m3:
            st.markdown("### 🪑 GRANDES")
            m3_sel = st.multiselect("Fila 3", df_alumnos_full.to_dict('records'), 
                                   default=obtener_defaults(3), 
                                   format_func=lambda x: f"{x['nombre']} ({x['nombre_curso']})", 
                                   key="m3_final")

        # 3. ACCIONES
        c_btn1, c_btn2 = st.columns(2)

        with c_btn1:
            if st.button("💾 Guardar Cambios de Mesa", use_container_width=True):
                try:
                    supabase.table("config_mesas").delete().neq("id", -1).execute() 
                    nuevos_reg = []
                    for a in m1_sel: nuevos_reg.append({"id_alumno": a["id"], "fila": 1})
                    for a in m2_sel: nuevos_reg.append({"id_alumno": a["id"], "fila": 2})
                    for a in m3_sel: nuevos_reg.append({"id_alumno": a["id"], "fila": 3})
                    
                    if nuevos_reg:
                        db_insert("config_mesas", nuevos_reg)
                        st.success("Configuración guardada.")
                        st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")

        with c_btn2:
            if st.button("🖨️ Generar PDF de Situación", type="primary", use_container_width=True):
                # OBTENER ASISTENCIA REAL DE HOY (CARGA DIRECTA)
                fecha_hoy_str = datetime.now().strftime("%Y-%m-%d")
                res_asis = supabase.table("asistencia").select("alumno_id").eq("fecha", fecha_hoy_str).eq("asiste", True).execute()
                ids_asisten_hoy = [r["alumno_id"] for r in res_asis.data]

                if not any([m1_sel, m2_sel, m3_sel]):
                    st.error("Asigna alumnos a las mesas primero.")
                else:
                    # Si no hay nadie marcado hoy, por cortesía mostramos todos los asignados
                    if not ids_asisten_hoy:
                        st.warning("No hay asistencia marcada hoy. Mostrando todos los asignados.")
                        ids_asisten_hoy = [a["id"] for a in (m1_sel + m2_sel + m3_sel)] 

                    # Filtrar listas para el PDF
                    m1_pdf = [a for a in m1_sel if a["id"] in ids_asisten_hoy]
                    m2_pdf = [a for a in m2_sel if a["id"] in ids_asisten_hoy]
                    m3_pdf = [a for a in m3_sel if a["id"] in ids_asisten_hoy]

                    buffer = io.BytesIO()
                    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=30, leftMargin=30, topMargin=40, bottomMargin=30)
                    elementos = []
                    estilos_p = getSampleStyleSheet()

                    # Título
                    titulo = f"SITUACIÓN EN MESA - {datetime.now().strftime('%d/%m/%Y')}"
                    elementos.append(Paragraph(f"<b>{titulo}</b>", estilos_p['Title']))
                    elementos.append(Spacer(1, 15))

                    # Tabla
                    max_filas = max(len(m1_pdf), len(m2_pdf), len(m3_pdf))
                    tabla_data = [["INFANTIL", "MEDIANOS", "GRANDES"]]
                    
                    estilos_tabla = [
                        ("BACKGROUND", (0,0), (-1,0), colors.black),
                        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
                        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
                        ("ALIGN", (0,0), (-1,-1), "CENTER"),
                        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                        ("FONTSIZE", (0,0), (-1,-1), 10),
                    ]

                    alertas_gluten = ["Ceballos Ruíz, Lucía", "García Ruíz, Lucía"]

                    for i in range(max_filas):
                        fila_cont = []
                        for col_idx, lista in enumerate([m1_pdf, m2_pdf, m3_pdf]):
                            if i < len(lista):
                                alu = lista[i]
                                nombre = alu['nombre']
                                curso = alu['nombre_curso']
                                
                                # Color por etapa (Infantil, Primaria...)
                                _, color_base = obtener_info_etapa(curso)
                                
                                # Alerta Alergia
                                if nombre in alertas_gluten:
                                    color_base = colors.orange
                                
                                fila_cont.append(f"{nombre}\n({curso})")
                                estilos_tabla.append(("BACKGROUND", (col_idx, i+1), (col_idx, i+1), color_base))
                            else:
                                fila_cont.append("")
                        tabla_data.append(fila_cont)

                    # Subtotales
                    tabla_data.append([f"Total: {len(m1_pdf)}", f"Total: {len(m2_pdf)}", f"Total: {len(m3_pdf)}"])
                    idx_last = len(tabla_data) - 1
                    estilos_tabla.append(("BACKGROUND", (0, idx_last), (-1, idx_last), colors.lightgrey))
                    estilos_tabla.append(("FONTNAME", (0, idx_last), (-1, idx_last), "Helvetica-Bold"))

                    ancho_util = landscape(A4)[0] - 60
                    t_mesas = Table(tabla_data, colWidths=[ancho_util/3]*3)
                    t_mesas.setStyle(TableStyle(estilos_tabla))
                    elementos.append(t_mesas)

                    # Total Final
                    elementos.append(Spacer(1, 20))
                    total_hoy = len(m1_pdf) + len(m2_pdf) + len(m3_pdf)
                    elementos.append(Paragraph(f"<para align='right' size='14'><b>TOTAL COMENSALES: <font color='blue'>{total_hoy}</font></b></para>", estilos_p['Normal']))

                    def add_page_number(canvas, doc):
                        canvas.setFont("Helvetica", 9)
                        canvas.drawRightString(landscape(A4)[0] - 30, 20, f"Página {canvas.getPageNumber()}")

                    doc.build(elementos, onFirstPage=add_page_number, onLaterPages=add_page_number)
                    
                    st.download_button(
                        "📩 Descargar PDF de Situación", 
                        buffer.getvalue(), 
                        f"situacion_mesas_{fecha_hoy_str}.pdf", 
                        "application/pdf", 
                        use_container_width=True
                    )
        # =========================
        # INFORME POR CURSO (CARGA FRESCA FORZADA)
        # =========================
        st.subheader("Informe por Curso")

        opciones_cursos = ["Todos los cursos"] + df_cursos[df_cursos["nombre"].str.lower() != "ninguno"]["nombre"].tolist()
        curso_sel = st.selectbox("Selecciona curso", opciones_cursos, key="curso_pdf")

        fecha_curso = st.date_input(
            "Selecciona la fecha",
            value=datetime.now().date(),
            key="fecha_informe_curso"
        )
        fecha_curso_str = fecha_curso.strftime("%Y-%m-%d")

        if st.button("Generar PDF por Curso", type="primary"):
            with st.spinner("Actualizando datos..."):
                # PASO 1: Forzamos lectura fresca de la DB
                df_alumnos_fresco = db_select("alumnos")
                df_cursos_fresco = db_select("cursos")
                # Traemos la asistencia de ese día específico directamente
                res_asis = supabase.table("asistencia").select("*").eq("fecha", fecha_curso_str).execute()
                df_dia_fresco = pd.DataFrame(res_asis.data)

            if df_dia_fresco.empty:
                st.warning(f"No hay registros de asistencia para el día {fecha_curso.strftime('%d/%m/%Y')}")
            else:
                # PASO 2: Preparar mapeos con datos frescos
                # Usamos diccionarios para que la búsqueda sea instantánea
                dict_alu_curso = {str(k): str(v) for k, v in zip(df_alumnos_fresco["id"], df_alumnos_fresco["curso_id"])}
                dict_nombres_alu = {str(k): str(v) for k, v in zip(df_alumnos_fresco["id"], df_alumnos_fresco["nombre"])}
                
                # Definir qué cursos procesar
                if curso_sel == "Todos los cursos":
                    cursos_a_procesar = df_cursos_fresco[df_cursos_fresco["nombre"].str.lower() != "ninguno"].to_dict(orient="records")
                else:
                    cursos_a_procesar = df_cursos_fresco[df_cursos_fresco["nombre"] == curso_sel].to_dict(orient="records")

                buffer = io.BytesIO()
                c = canvas.Canvas(buffer, pagesize=A4)
                page_width, page_height = A4
                primera_pagina = True 
                
                for curso in cursos_a_procesar:
                    nombre_curso = curso["nombre"]
                    id_curso_target = str(curso["id"])

                    # Filtrar alumnos de este curso en la asistencia de hoy
                    filas_curso = []
                    for _, row in df_dia_fresco.iterrows():
                        id_alu = str(row["alumno_id"])
                        # Verificamos si el alumno de esta fila de asistencia pertenece al curso actual
                        if dict_alu_curso.get(id_alu) == id_curso_target:
                            filas_curso.append([
                                dict_nombres_alu.get(id_alu, "Desconocido"),
                                "Sí" if row["asiste"] else "No"
                            ])
                    
                    # Si el curso no tiene alumnos hoy, y seleccionamos "Todos", saltamos página vacía
                    if not filas_curso and curso_sel == "Todos los cursos":
                        continue

                    if not primera_pagina: 
                        c.showPage() 
                    primera_pagina = False

                    draw_logo_centered(c, page_width, page_height - 190)

                    c.setFont("Helvetica-Bold", 18)
                    c.drawCentredString(page_width/2, 750, f"Informe por Curso - {nombre_curso}")
                    c.setFont("Helvetica", 12)
                    c.drawCentredString(page_width/2, 720, f"Fecha: {fecha_curso.strftime('%d/%m/%Y')}")

                    # Tabla
                    tabla_data = [["Alumno", "Asiste"]]
                    filas_curso.sort(key=lambda x: x[0]) # Orden alfabético
                    tabla_data.extend(filas_curso if filas_curso else [["Sin alumnos registrados", "-"]])

                    anchos = [300, 100]
                    x_centrada = (page_width - sum(anchos)) / 2
                    tabla = Table(tabla_data, colWidths=anchos)
                    tabla.setStyle(TableStyle([
                        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
                        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
                        ("ALIGN", (0,0), (-1,-1), "CENTER"),
                        ("ALIGN", (0,0), (0,-1), "LEFT"),
                        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                        ("LEFTPADDING", (0,0), (0,-1), 15),
                        ("FONTSIZE", (0,0), (-1,-1), 11),
                    ]))

                    w, h = tabla.wrap(page_width, page_height)
                    tabla.drawOn(c, x_centrada, 680 - h)
                    add_page_number(c)

                c.save()
                st.success("PDF generado con datos actualizados.")
                st.download_button(
                    label="📥 Descargar PDF por Curso",
                    data=buffer.getvalue(),
                    file_name=f"informe_{curso_sel}_{fecha_curso_str}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
    
        # =========================
        # INFORME MENSUAL (CARGA TOTAL FORZADA)
        # =========================
        st.subheader("Informe Mensual")
        col_m, col_a = st.columns(2)
        with col_m:
            mes = st.selectbox("Selecciona mes", list(range(1, 13)), index=datetime.now().month - 1, key="mes_pdf")
        with col_a:
            año = st.number_input("Año", min_value=2024, max_value=2030, value=datetime.now().year, key="año_pdf_input")

        if st.button("Generar PDF Mensual", type="primary"):
            with st.spinner("Recopilando datos mensuales..."):
                # 1. CARGA FRESCA DE DATOS BÁSICOS
                df_alumnos_fresco = db_select("alumnos")
                df_cursos_fresco = db_select("cursos")
                
                # 2. CARGA DE ASISTENCIA DEL MES DIRECTAMENTE DESDE SUPABASE
                dias_mes = calendar.monthrange(año, mes)[1]
                fecha_inicio = f"{año}-{mes:02d}-01"
                fecha_fin = f"{año}-{mes:02d}-{dias_mes:02d}"
                
                res_asis = supabase.table("asistencia")\
                    .select("alumno_id, fecha, asiste")\
                    .gte("fecha", fecha_inicio)\
                    .lte("fecha", fecha_fin)\
                    .eq("asiste", True)\
                    .execute()
                
                df_asis_mes = pd.DataFrame(res_asis.data)

            if df_asis_mes.empty:
                st.warning(f"No hay registros de asistencia para el mes {mes}/{año}")
            else:
                # 3. PREPARAR MAPEOS
                # Diccionario Alumno -> Curso ID
                dict_alu_curso = {str(k): str(v) for k, v in zip(df_alumnos_fresco["id"], df_alumnos_fresco["curso_id"])}
                # Cursos válidos (excluyendo 'ninguno')
                df_cur_filt = df_cursos_fresco[df_cursos_fresco["nombre"].str.lower() != "ninguno"].copy()
                df_cur_filt = df_cur_filt.sort_values("nombre")

                # 4. CONSTRUIR MATRIZ (Curso x Días)
                tabla_data = [["Curso"] + [str(d) for d in range(1, dias_mes+1)] + ["Total"]]
                totales_diarios = [0] * dias_mes

                for _, curso in df_cur_filt.iterrows():
                    id_curso_str = str(curso["id"])
                    fila = [curso["nombre"]]
                    total_curso = 0

                    for d in range(1, dias_mes+1):
                        f_busqueda = f"{año}-{mes:02d}-{d:02d}"
                        # Buscamos en los datos del mes
                        asis_dia = df_asis_mes[df_asis_mes["fecha"] == f_busqueda]
                        
                        # Contamos cuántos alumnos de este curso aparecen en la asistencia de ese día
                        count = 0
                        for alu_id in asis_dia["alumno_id"]:
                            if dict_alu_curso.get(str(alu_id)) == id_curso_str:
                                count += 1
                        
                        fila.append(count if count > 0 else "")
                        total_curso += count
                        totales_diarios[d-1] += count
                    
                    fila.append(total_curso)
                    tabla_data.append(fila)

                # Fila de Totales Verticales
                fila_totales = ["TOTAL DÍA"] + [str(t) if t > 0 else "0" for t in totales_diarios] + [sum(totales_diarios)]
                tabla_data.append(fila_totales)

                # 5. GENERAR EL PDF (Landscape A4)
                buffer = io.BytesIO()
                c = canvas.Canvas(buffer, pagesize=landscape(A4))
                page_width, page_height = landscape(A4)

                draw_logo_centered(c, page_width, page_height - 200)
                c.setFont("Helvetica-Bold", 18)
                c.drawCentredString(page_width/2, page_height - 110, f"INFORME MENSUAL DE COMENSALES - {mes}/{año}")

                # Ajuste de tamaño de fuente
                fontSize = 8 if dias_mes > 30 else 9
                
                # Calculamos anchos: Nombre curso (80), días (20 aprox), total (40)
                anchos_dias = (page_width - 150) / dias_mes
                tabla = Table(tabla_data, colWidths=[85] + [anchos_dias]*dias_mes + [45])
                
                estilo = [
                    ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
                    ("BACKGROUND", (0,-1), (-1,-1), colors.lightgrey),
                    ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
                    ("ALIGN", (0,0), (-1,-1), "CENTER"),
                    ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                    ("FONTNAME", (0,-1), (-1,-1), "Helvetica-Bold"),
                    ("FONTSIZE", (0,0), (-1,-1), fontSize),
                    ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                ]
                
                # Sombreado alterno para las filas de cursos
                for i in range(1, len(tabla_data)-1):
                    if i % 2 == 0:
                        estilo.append(("BACKGROUND", (0,i), (-1,i), colors.whitesmoke))
                
                tabla.setStyle(TableStyle(estilo))
                
                w, h = tabla.wrap(0, 0)
                # Centramos la tabla en la página
                tabla.drawOn(c, (page_width - w)/2, page_height - 160 - h)

                add_page_number(c)
                c.save()

                st.success(f"Informe de {mes}/{año} generado correctamente.")
                st.download_button(
                    label="📥 Descargar Informe Mensual",
                    data=buffer.getvalue(),
                    file_name=f"mensual_{año}_{mes:02d}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
        # =========================================================
        # INFORME DE FALTAS (OPTIMIZADO Y SIN ERRORES)
        # =========================================================
        st.subheader("Informe de Faltas")

        col1, col2 = st.columns(2)
        with col1:
            mes_f = st.selectbox("Selecciona mes", list(range(1, 13)), key="mes_faltas", index=datetime.now().month - 1)
            año_f = st.number_input("Año", min_value=2024, max_value=2030, value=datetime.now().year, key="año_faltas")
        with col2:
            opciones_curso = ["Todos los cursos"] + df_cursos[df_cursos["nombre"].str.lower() != "ninguno"]["nombre"].tolist()
            curso_f_nombre = st.selectbox("Selecciona curso", opciones_curso, key="curso_faltas")

        if st.button("Generar PDF de Faltas", type="primary"):
            with st.spinner("Procesando faltas mensuales..."):
                # 1. Carga fresca de datos
                df_alu_f = db_select("alumnos")
                df_cur_f = db_select("cursos")
                
                # 2. Obtener solo las FALTAS (asiste = False) de todo el mes
                dias_mes = calendar.monthrange(año_f, mes_f)[1]
                f_inicio = f"{año_f}-{mes_f:02d}-01"
                f_fin = f"{año_f}-{mes_f:02d}-{dias_mes:02d}"
                
                res_faltas = supabase.table("asistencia")\
                    .select("alumno_id, fecha")\
                    .gte("fecha", f_inicio)\
                    .lte("fecha", f_fin)\
                    .eq("asiste", False)\
                    .execute()
                
                # Crear un set de búsqueda rápida: {(alumno_id, fecha), ...}
                faltas_set = {(str(r['alumno_id']), r['fecha']) for r in res_faltas.data}

            # 3. Filtrar cursos a procesar
            if curso_f_nombre == "Todos los cursos":
                cursos_a_procesar = df_cur_f[df_cur_f["nombre"].str.lower() != "ninguno"].to_dict(orient="records")
            else:
                cursos_a_procesar = df_cur_f[df_cur_f["nombre"] == curso_f_nombre].to_dict(orient="records")

            buffer = io.BytesIO()
            c = canvas.Canvas(buffer, pagesize=landscape(A4))
            page_width, page_height = landscape(A4)

            for i, curso in enumerate(cursos_a_procesar):
                # Filtrar alumnos de este curso
                alumnos_este_curso = df_alu_f[df_alu_f["curso_id"] == curso["id"]].sort_values("nombre")
                
                if alumnos_este_curso.empty and curso_f_nombre == "Todos los cursos":
                    continue

                if i > 0: c.showPage()

                draw_logo_centered(c, page_width, page_height - 180)
                
                c.setFont("Helvetica-Bold", 16)
                c.drawCentredString(page_width/2, page_height - 110, f"Control Mensual de Faltas - {mes_f}/{año_f}")
                c.setFont("Helvetica-Bold", 13)
                c.drawString(40, page_height - 140, f"Curso: {curso['nombre']}")

                # Cabecera de tabla
                tabla_data = [["Alumno"] + [str(d) for d in range(1, dias_mes+1)] + ["Total"]]
                
                # Estilos base
                estilos = [
                    ("BACKGROUND", (0,0), (-1,0), colors.black),
                    ("TEXTCOLOR", (0,0), (-1,0), colors.white),
                    ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
                    ("ALIGN", (0,0), (-1,-1), "CENTER"),
                    ("ALIGN", (0,0), (0,-1), "LEFT"),
                    ("FONTSIZE", (0,0), (-1,-1), 7),
                    ("LEFTPADDING", (0,0), (-1,-1), 1),
                    ("RIGHTPADDING", (0,0), (-1,-1), 1),
                ]

                # Rellenar filas de alumnos
                total_faltas_curso = 0
                for fila_idx, (_, alu) in enumerate(alumnos_este_curso.iterrows()):
                    id_alu_str = str(alu["id"])
                    fila = [alu["nombre"]]
                    faltas_alu = 0
                    
                    for d in range(1, dias_mes+1):
                        f_check = f"{año_f}-{mes_f:02d}-{d:02d}"
                        if (id_alu_str, f_check) in faltas_set:
                            fila.append("F")
                            faltas_alu += 1
                            # Color rojo para la 'F'
                            estilos.append(('TEXTCOLOR', (d, fila_idx + 1), (d, fila_idx + 1), colors.red))
                            estilos.append(('FONTNAME', (d, fila_idx + 1), (d, fila_idx + 1), "Helvetica-Bold"))
                        else:
                            fila.append("")
                    
                    fila.append(faltas_alu)
                    total_faltas_curso += faltas_alu
                    tabla_data.append(fila)
                    
                    if (fila_idx + 1) % 2 == 0:
                        estilos.append(("BACKGROUND", (0, fila_idx + 1), (-1, fila_idx + 1), colors.whitesmoke))

                # Fila de total inferior
                idx_total = len(tabla_data)
                fila_total = ["TOTAL FALTAS DEL CURSO"] + [""] * dias_mes + [total_faltas_curso]
                tabla_data.append(fila_total)
                
                estilos.append(("BACKGROUND", (0, -1), (-1, -1), colors.lightgrey))
                estilos.append(("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"))
                estilos.append(("SPAN", (0, -1), (dias_mes, -1)))
                estilos.append(("ALIGN", (0, -1), (0, -1), "RIGHT"))

                # Dibujar tabla
                # Ajuste de anchos para que no se salga del papel
                anchos_dias = (page_width - 200) / dias_mes
                tabla = Table(tabla_data, colWidths=[120] + [anchos_dias]*dias_mes + [25])
                tabla.setStyle(TableStyle(estilos))
                
                # --- BUSCA LA LÍNEA tabla.drawOn Y CÁMBIALA POR ESTA ---
                w, h = tabla.wrap(0, 0)
                x_centered = (page_width - w) / 2  # Calcula el centro exacto
                tabla.drawOn(c, x_centered, page_height - 160 - h)
                add_page_number(c)

            c.save()
            st.success("Informe de faltas generado correctamente.")
            st.download_button(
                label="📥 Descargar Informe de Faltas",
                data=buffer.getvalue(),
                file_name=f"faltas_{curso_f_nombre}_{mes_f}_{año_f}.pdf",
                mime="application/pdf",
                use_container_width=True
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
        # CUADRANTE MAESTROS CON SALTO DE PÁGINA AUTOMÁTICO (CORREGIDO)
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
                # CARGA DE DATOS CON PROTECCIÓN DE COLUMNAS
                df_profes = db_select("profesores")
        
                # Leemos comidas
                df_comidas_raw = db_select("maestros_comidas")
                if df_comidas_raw is None or df_comidas_raw.empty:
                    df_comidas_raw = pd.DataFrame(columns=["fecha", "maestro_id"])
            
                # Leemos agua
                df_agua_raw = db_select("maestros_agua")
                if df_agua_raw is None or df_agua_raw.empty:
                    df_agua_raw = pd.DataFrame(columns=["fecha", "maestro_id", "agua_025", "agua_060"])

                # 1. Filtrar actividad por rango de fechas
                comidas_rango = df_comidas_raw[(df_comidas_raw["fecha"] >= f_ini_str) & (df_comidas_raw["fecha"] <= f_fin_str)]
                agua_rango = df_agua_raw[(df_agua_raw["fecha"] >= f_ini_str) & (df_agua_raw["fecha"] <= f_fin_str)]

                # 2. Días activos (Evitamos errores si unique() devuelve vacío)
                set_comidas = set(comidas_rango["fecha"].unique()) if "fecha" in comidas_rango.columns else set()
                set_agua = set(agua_rango["fecha"].unique()) if "fecha" in agua_rango.columns else set()
        
                fechas_activas = sorted(list(set_comidas | set_agua))
                dias_datos = [datetime.strptime(f, "%Y-%m-%d").date() for f in fechas_activas]
                num_dias = len(dias_datos)

                if num_dias == 0:
                    st.warning("No hay actividad (comidas ni agua) registrada para los maestros en estas fechas.")
                else:
                    # Obtener IDs de maestros con actividad
                    ids_comidas = set(comidas_rango["maestro_id"].unique()) if not comidas_rango.empty else set()
                    ids_agua = set(agua_rango["maestro_id"].unique()) if not agua_rango.empty else set()
                    ids_activos = ids_comidas | ids_agua
            
                    profes_activos = df_profes[df_profes["id"].isin(ids_activos)]

                    buffer = io.BytesIO()
                    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), 
                                            rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
            
                    elementos = [] 
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

                    ancho_col = 35 if num_dias < 10 else 25
                    t1 = Table(data_c, colWidths=[110] + [ancho_col]*num_dias + [40], repeatRows=1)
                    t1.setStyle(TableStyle([
                        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
                        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
                        ("ALIGN", (1,0), (-1,-1), "CENTER"),
                        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
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
                                a25 = reg.iloc[0].get("agua_025", 0) or 0
                                a60 = reg.iloc[0].get("agua_060", 0) or 0
                                fila.append(f"{int(a25)}|{int(a60)}" if (a25 > 0 or a60 > 0) else "")
                            else:
                                fila.append("")
                        data_a.append(fila)

                    t2 = Table(data_a, colWidths=[110] + [ancho_col]*num_dias, repeatRows=1)
                    t2.setStyle(TableStyle([
                        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
                        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
                        ("ALIGN", (1,0), (-1,-1), "CENTER"),
                        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
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
                        "📩 Descargar Informe de Maestros", 
                        data=buffer.getvalue(), 
                        file_name=f"maestros_{f_ini_str}_al_{f_fin_str}.pdf",
                        mime="application/pdf",
                        use_container_width=True
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
