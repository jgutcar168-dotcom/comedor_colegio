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

# --- PANTALLA 1: CONSULTA DE ASISTENCIA (FILTRADA) ---
if opcion == "📋 Alumnos en Comedor Hoy":
    st.title("Alumnos PT/AL en Comedor Hoy")
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    
    df_asistencia = db_select("asistencia")
    if not df_asistencia.empty:
        df_hoy = df_asistencia[df_asistencia["fecha"] == fecha_hoy]
        ids_asisten = df_hoy[df_hoy["asiste"] == True]["alumno_id"].tolist()
        
        if not ids_asisten:
            st.warning("No hay registros de asistencia para hoy.")
        else:
            # FILTRO CRÍTICO: Que asistan hoy Y que tengan la marca 'es_pt_al'
            df_presentes = df_alumnos[
                (df_alumnos["id"].isin(ids_asisten)) & 
                (df_alumnos["es_pt_al"] == True)
            ]
            
            if df_presentes.empty:
                st.info("Ningún alumno de PT/AL ha asistido al comedor hoy.")
            else:
                df_presentes = df_presentes.merge(df_cursos, left_on="curso_id", right_on="id")
                df_presentes = df_presentes.rename(columns={"nombre_x": "Alumno", "nombre_y": "Curso"}).sort_values(["Curso", "Alumno"])
                
                for curso in df_presentes["Curso"].unique():
                    color = obtener_color_etapa(curso)
                    st.markdown(f"<div style='background-color:{color}; padding:10px; border-radius:10px; margin-top:15px;'><h3>{curso}</h3></div>", unsafe_allow_html=True)
                    
                    alumnos_curso = df_presentes[df_presentes["Curso"] == curso]["Alumno"].tolist()
                    cols = st.columns(4)
                    for i, nombre in enumerate(alumnos_curso):
                        cols[i % 4].markdown(f"<div class='alumno-card'>{nombre}</div>", unsafe_allow_html=True)

# --- PANTALLA 2: GESTIÓN DE ALUMNOS (ASIGNAR PT/AL) ---
elif opcion == "👥 Gestión de Alumnos":
    st.title("Configuración de Alumnos PT/AL")
    st.info("Marca los alumnos que pertenecen al programa PT/AL para que aparezcan en tu lista diaria.")

    if not df_alumnos.empty:
        df_merge = df_alumnos.merge(df_cursos, left_on="curso_id", right_on="id")
        
        # Buscador para facilitar el trabajo
        buscar = st.text_input("Buscar alumno para marcar/desmarcar...")
        if buscar:
            df_merge = df_merge[df_merge["nombre_x"].str.contains(buscar, case=False)]

        # Creamos una lista de checkboxes
        for _, fila in df_merge.sort_values("nombre_x").iterrows():
            col_alu, col_check = st.columns([3, 1])
            with col_alu:
                st.write(f"{fila['nombre_x']} ({fila['nombre_y']})")
            with col_check:
                # El checkbox refleja el estado actual en la DB
                nuevo_estado = st.checkbox("Es PT/AL", value=fila['es_pt_al'], key=f"chk_{fila['id_x']}")
                
                # Si el usuario cambia el checkbox, actualizamos Supabase al instante
                if nuevo_estado != fila['es_pt_al']:
                    supabase.table("alumnos").update({"es_pt_al": nuevo_estado}).eq("id", fila['id_x']).execute()
                    st.toast(f"Actualizado: {fila['nombre_x']}")