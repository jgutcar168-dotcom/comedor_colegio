import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client

# ---------------------------------------------------------
# CONFIGURACIÓN SUPABASE
# ---------------------------------------------------------
SUPABASE_URL = st.secrets["https://supabase.com/dashboard/project/faeoxyimhhoeiuuphbnv"]
SUPABASE_KEY = st.secrets["n3s+*24NkR#t!bA"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------------------------------------------------
# FUNCIONES DE BASE DE DATOS
# ---------------------------------------------------------
def db_select(table):
    """Devuelve una tabla completa como DataFrame."""
    data = supabase.table(table).select("*").execute().data
    return pd.DataFrame(data)

def db_insert(table, rows):
    """Inserta una o varias filas."""
    supabase.table(table).insert(rows).execute()

def db_upsert(table, rows):
    """Inserta o actualiza según clave primaria."""
    supabase.table(table).upsert(rows).execute()

def db_delete(table, conditions):
    """Elimina filas según condiciones."""
    supabase.table(table).delete().match(conditions).execute()

# ---------------------------------------------------------
# CONFIGURACIÓN DE PÁGINA
# ---------------------------------------------------------
st.set_page_config(page_title="Gestión Comedor Escolar", layout="wide")
CONTRASEÑA_ADMIN = "pinkipinki"

if "admin_autenticado" not in st.session_state:
    st.session_state.admin_autenticado = False

# ---------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------
st.sidebar.title("Menú Comedor")
opcion = st.sidebar.radio(
    "Ir a:",
    ["Pasar Lista (Profesores)", "Resumen Diario", "Panel de Administración", "Informes y PDF"]
)

# ---------------------------------------------------------
# PASAR LISTA
# ---------------------------------------------------------
if opcion == "Pasar Lista (Profesores)":
    st.header("Control de Asistencia Diario")

    df_cursos = db_select("cursos")
    df_alumnos = db_select("alumnos")
    df_asistencia = db_select("asistencia")

    fecha_hoy = datetime.now().strftime("%Y-%m-%d")

    cursos = df_cursos.sort_values(by=["orden", "letra"]).to_dict(orient="records")

    if cursos:
        curso_sel = st.selectbox("Selecciona tu curso:", cursos, format_func=lambda x: x["nombre"])

        if curso_sel:
            alumnos = df_alumnos[df_alumnos["curso_id"] == curso_sel["id"]].sort_values("nombre")
            asist_hoy = df_asistencia[df_asistencia["fecha"] == fecha_hoy]

            datos_previos = asist_hoy.set_index("alumno_id").to_dict(orient="index")

            with st.form("form_asistencia"):
                st.subheader(f"Lista de {curso_sel['nombre']} - {datetime.now().strftime('%d/%m/%Y')}")
                nuevos = []

                for _, al in alumnos.iterrows():
                    col1, col2, col3 = st.columns([2, 1, 3])

                    prev = datos_previos.get(al["id"], {})
                    default_asiste = prev.get("asiste", True)
                    default_motivo = prev.get("motivo", "")

                    col1.write(f"**{al['nombre']}**")
                    asiste = col2.checkbox("Come", value=bool(default_asiste), key=f"chk_{al['id']}")
                    motivo = col3.text_input("Obs", value=str(default_motivo), key=f"mot_{al['id']}", label_visibility="collapsed")

                    nuevos.append({
                        "fecha": fecha_hoy,
                        "alumno_id": al["id"],
                        "asiste": asiste,
                        "motivo": motivo
                    })

                if st.form_submit_button("Guardar Asistencia"):
                    # Borrar registros previos del día para ese curso
                    ids = alumnos["id"].tolist()
                    for id_al in ids:
                        db_delete("asistencia", {"fecha": fecha_hoy, "alumno_id": id_al})

                    # Insertar nuevos
                    db_insert("asistencia", nuevos)

                    st.success("¡Asistencia guardada!")
                    st.rerun()

# ---------------------------------------------------------
# PANEL ADMINISTRACIÓN
# ---------------------------------------------------------
elif opcion == "Panel de Administración":
    if not st.session_state.admin_autenticado:
        with st.form("login"):
            pw = st.text_input("Password", type="password")
            if st.form_submit_button("Entrar"):
                if pw == CONTRASEÑA_ADMIN:
                    st.session_state.admin_autenticado = True
                    st.rerun()
    else:
        st.header("Panel de Administración")

        df_cursos = db_select("cursos")
        df_alumnos = db_select("alumnos")

        tab1, tab2 = st.tabs(["Gestionar Alumnos", "Configuración"])

        with tab1:
            with st.form("nuevo_al"):
                nombre = st.text_input("Nombre Alumno")
                curso = st.selectbox("Curso", df_cursos.to_dict(orient="records"), format_func=lambda x: x["nombre"])

                if st.form_submit_button("Añadir"):
                    db_insert("alumnos", [{
                        "nombre": nombre,
                        "curso_id": curso["id"]
                    }])
                    st.success("Alumno añadido")
                    st.rerun()

# ---------------------------------------------------------
# INFORMES Y PDF
# ---------------------------------------------------------
elif opcion == "Informes y PDF":
    st.header("Generación de Informes")

    df_asistencia = db_select("asistencia")
    df_alumnos = db_select("alumnos")
    df_cursos = db_select("cursos")

    col1, col2, col3 = st.columns(3)
    mes_sel = col1.selectbox("Mes", list(range(1, 13)), index=datetime.now().month - 1)
    anio_sel = col2.selectbox("Año", [2024, 2025, 2026], index=1)
    precio_menu = col3.number_input("Precio Menú (€)", value=4.50, step=0.10)

    df_asistencia["fecha_dt"] = pd.to_datetime(df_asistencia["fecha"])
    df_mes = df_asistencia[
        (df_asistencia["fecha_dt"].dt.month == mes_sel) &
        (df_asistencia["fecha_dt"].dt.year == anio_sel) &
        (df_asistencia["asiste"] == True)
    ]

    tab_al, tab_cu, tab_ce = st.tabs(["Por Alumno", "Por Curso", "Total Centro"])

    with tab_al:
        st.subheader("Recibo Individual")
        alumnos_lista = df_alumnos.sort_values("nombre").to_dict(orient="records")
        al_sel = st.selectbox("Selecciona Alumno", alumnos_lista, format_func=lambda x: x["nombre"])

        if al_sel:
            dias = len(df_mes[df_mes["alumno_id"] == al_sel["id"]])
            total = dias * precio_menu

            st.info(f"El alumno **{al_sel['nombre']}** ha comido **{dias}** días.")
            st.write(f"### Total a pagar: {total:.2f} €")

    with tab_cu:
        st.subheader("Informe por Curso")
        curso_sel = st.selectbox("Selecciona Curso", df_cursos.to_dict(orient="records"), format_func=lambda x: x["nombre"])

        if curso_sel:
            alumnos_curso = df_alumnos[df_alumnos["curso_id"] == curso_sel["id"]]
            asist_curso = df_mes[df_mes["alumno_id"].isin(alumnos_curso["id"])]

            resumen = asist_curso.groupby("alumno_id").size().reset_index(name="Dias")
            resumen = resumen.merge(df_alumnos, left_on="alumno_id", right_on="id")
            resumen["Total €"] = resumen["Dias"] * precio_menu

            st.dataframe(resumen[["nombre", "Dias", "Total €"]], hide_index=True)

    with tab_ce:
        st.subheader("Resumen Total Centro")
        total_dias = len(df_mes)
        total_recaudado = total_dias * precio_menu

        st.metric("Total Comidas del Mes", total_dias)
        st.metric("Total Recaudación Estimada", f"{total_recaudado:.2f} €")

        if not df_mes.empty:
            st.bar_chart(df_mes.groupby("fecha").size())

# ---------------------------------------------------------
# RESUMEN DIARIO
# ---------------------------------------------------------
elif opcion == "Resumen Diario":
    st.header("Resumen de Comedor para Cocina")

    df_asistencia = db_select("asistencia")
    df_alumnos = db_select("alumnos")
    df_cursos = db_select("cursos")

    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    st.subheader(f"Día: {datetime.now().strftime('%d/%m/%Y')}")

    df_hoy = df_asistencia[df_asistencia["fecha"] == fecha_hoy]
    comen = df_hoy[df_hoy["asiste"] == True]

    if not comen.empty:
        resumen = comen.merge(df_alumnos, left_on="alumno_id", right_on="id")
        resumen = resumen.merge(df_cursos, left_on="curso_id", right_on="id", suffixes=("", "_curso"))

        st.metric("TOTAL COMENSALES", len(resumen))

        col1, col2 = st.columns(2)

        with col1:
            st.write("### Por Curso")
            conteo = resumen.groupby("nombre_curso").size().reset_index(name="Cant.")
            st.table(conteo)

        with col2:
            st.write("### Observaciones")
            obs = resumen[resumen["motivo"].fillna("") != ""][["nombre", "motivo"]]
            if not obs.empty:
                st.dataframe(obs, hide_index=True)
            else:
                st.write("No hay observaciones para hoy.")
    else:
        st.warning("Aún no se ha pasado lista hoy.")
