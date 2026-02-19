import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime
import io

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Consulta PT/AL - Comedor", layout="wide", page_icon="🏫")

# --- ESTILOS CSS PERSONALIZADOS ---
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; }
    .alumno-card {
        padding: 10px;
        border-radius: 8px;
        margin: 5px;
        border: 1px solid #ddd;
        text-align: center;
        font-weight: bold;
        color: #333;
    }
    </style>
    """, unsafe_allow_html=True)

# --- CONEXIÓN SUPABASE ---
# Asegúrate de configurar estos Secrets en Streamlit Cloud
URL = st.secrets["SUPABASE_URL"]
KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(URL, KEY)

def db_select(tabla):
    try:
        response = supabase.table(tabla).select("*").execute()
        return pd.DataFrame(response.data)
    except Exception:
        return pd.DataFrame()

# --- LÓGICA DE COLORES ---
def obtener_color_etapa(nombre_curso):
    nombre = str(nombre_curso).upper()
    if any(x in nombre for x in ["INF", "3 AÑOS", "4 AÑOS", "5 AÑOS"]):
        return "#D1E9FF" # Azul
    if any(x in nombre for x in ["1º", "2º"]):
        return "#D1FFD1" # Verde
    if any(x in nombre for x in ["3º", "4º"]):
        return "#FFFFD1" # Amarillo
    if any(x in nombre for x in ["5º", "6º"]):
        return "#FFD1D1" # Salmón
    return "#F0F2F6"

# --- LOGIN ---
if 'pt_autenticado' not in st.session_state:
    st.session_state.pt_autenticado = False

if not st.session_state.pt_autenticado:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🔐 Acceso Equipo PT/AL")
        st.info("Utilice sus credenciales de profesor del centro")
        user = st.text_input("Usuario / Email")
        password = st.text_input("Contraseña", type="password")
        if st.button("Iniciar Sesión"):
            df_profes = db_select("profesores")
            if not df_profes.empty:
                auth = df_profes[(df_profes["usuario"] == user) & (df_profes["password"] == password)]
                if not auth.empty:
                    st.session_state.pt_autenticado = True
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos")
            else:
                st.error("Error al conectar con la base de datos de profesores")
    st.stop()

# --- CARGA DE DATOS ---
df_cursos = db_select("cursos")
df_alumnos = db_select("alumnos")

# --- MENÚ LATERAL ---
with st.sidebar:
    st.title("Menú PT/AL")
    opcion = st.radio("Ir a:", ["📋 Alumnos en Comedor Hoy", "👥 Gestión de Alumnos"])
    if st.button("Cerrar Sesión"):
        st.session_state.pt_autenticado = False
        st.rerun()

# --- PANTALLA 1: CONSULTA DE ASISTENCIA ---
if opcion == "📋 Alumnos en Comedor Hoy":
    st.title("Alumnos que asisten hoy")
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    
    # 1. Obtener asistencia del día
    df_asistencia = db_select("asistencia")
    if not df_asistencia.empty:
        df_hoy = df_asistencia[df_asistencia["fecha"] == fecha_hoy]
        ids_asisten = df_hoy[df_hoy["asiste"] == True]["alumno_id"].tolist()
        
        if not ids_asisten:
            st.warning("No hay alumnos registrados para hoy todavía.")
        else:
            # 2. Unir datos para mostrar
            df_presentes = df_alumnos[df_alumnos["id"].isin(ids_asisten)]
            df_presentes = df_presentes.merge(df_cursos, left_on="curso_id", right_on="id")
            df_presentes = df_presentes.rename(columns={"nombre_x": "Alumno", "nombre_y": "Curso"}).sort_values(["Curso", "Alumno"])
            
            # 3. Mostrar por bloques de cursos
            cursos_en_lista = df_presentes["Curso"].unique()
            
            for curso in cursos_en_lista:
                color = obtener_color_etapa(curso)
                st.markdown(f"""<div style='background-color:{color}; padding:10px; border-radius:10px; margin-top:20px; border-left: 10px solid rgba(0,0,0,0.2)'>
                            <h2 style='margin:0; color:black;'>{curso}</h2></div>""", unsafe_allow_html=True)
                
                alumnos_curso = df_presentes[df_presentes["Curso"] == curso]["Alumno"].tolist()
                
                # Mostrar nombres en columnas
                cols = st.columns(4)
                for i, nombre in enumerate(alumnos_curso):
                    with cols[i % 4]:
                        st.markdown(f"<div class='alumno-card'>{nombre}</div>", unsafe_allow_html=True)
    else:
        st.error("No se pudo acceder a la tabla de asistencia.")

# --- PANTALLA 2: GESTIÓN DE ALUMNOS ---
elif opcion == "👥 Gestión de Alumnos":
    st.title("Gestión de Alumnos (Altas y Bajas)")
    
    tab1, tab2 = st.tabs(["➕ Nuevo Alumno", "🗑️ Listado / Borrar"])
    
    with tab1:
        with st.form("nuevo_alumno"):
            nombre_n = st.text_input("Nombre completo del alumno")
            curso_n = st.selectbox("Asignar a Curso", df_cursos["nombre"].tolist() if not df_cursos.empty else [])
            enviar = st.form_submit_button("Guardar en Base de Datos")
            
            if enviar and nombre_n:
                c_id = int(df_cursos[df_cursos["nombre"] == curso_n]["id"].iloc[0])
                try:
                    supabase.table("alumnos").insert({"nombre": nombre_n, "curso_id": c_id}).execute()
                    st.success(f"Alumno {nombre_n} guardado correctamente.")
                except Exception as e:
                    st.error(f"Error al guardar: {e}")

    with tab2:
        if not df_alumnos.empty:
            df_lista = df_alumnos.merge(df_cursos, left_on="curso_id", right_on="id", suffixes=("_a", "_c"))
            df_lista = df_lista[["id_a", "nombre_a", "nombre_c"]].rename(columns={"id_a":"ID", "nombre_a":"Nombre", "nombre_c":"Curso"})
            
            # Buscador básico
            busqueda = st.text_input("Buscar alumno por nombre...")
            if busqueda:
                df_lista = df_lista[df_lista["Nombre"].str.contains(busqueda, case=False)]
            
            st.dataframe(df_lista, use_container_width=True, hide_index=True)
            
            # Opción de borrado (con precaución)
            with st.expander("Sección de borrado"):
                id_borrar = st.number_input("Introduzca el ID del alumno a eliminar", step=1)
                if st.button("Eliminar permanentemente", type="secondary"):
                    try:
                        supabase.table("alumnos").delete().eq("id", id_borrar).execute()
                        st.success("Alumno eliminado.")
                        st.rerun()
                    except Exception as e:
                        st.error("No se pudo eliminar el alumno.")