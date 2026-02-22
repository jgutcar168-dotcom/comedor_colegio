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

# --- PANTALLA 1: CONSULTA DE ASISTENCIA (CON FILTRO DUAL) ---
if opcion == "📋 Alumnos en Comedor Hoy":
    st.title("Control de Presencia PT/AL")
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    
    df_asistencia = db_select("asistencia")
    if not df_asistencia.empty:
        df_hoy = df_asistencia[df_asistencia["fecha"] == fecha_hoy]
        ids_asisten = df_hoy[df_hoy["asiste"] == True]["alumno_id"].tolist()
        
        if not ids_asisten:
            st.warning("No hay registros de asistencia para hoy todavía.")
        else:
            # FILTRO: Que estén presentes hoy Y sean PT/AL (ya sean comedor o solo apoyo)
            df_presentes = df_alumnos[
                (df_alumnos["id"].isin(ids_asisten)) & 
                (df_alumnos["es_pt_al"] == True)
            ]
            
            if df_presentes.empty:
                st.info("Ningún alumno del programa PT/AL ha asistido hoy al centro.")
            else:
                df_presentes = df_presentes.merge(df_cursos, left_on="curso_id", right_on="id")
                df_presentes = df_presentes.rename(columns={"nombre_x": "Alumno", "nombre_y": "Curso"}).sort_values(["Curso", "Alumno"])
                
                for curso in df_presentes["Curso"].unique():
                    color = obtener_color_etapa(curso)
                    st.markdown(f"""<div style='background-color:{color}; padding:10px; border-radius:10px; margin-top:15px; border-left: 8px solid #555;'>
                                <h3>{curso}</h3></div>""", unsafe_allow_html=True)
                    
                    # Separamos visualmente dentro del curso
                    df_curso_actual = df_presentes[df_presentes["Curso"] == curso]
                    
                    # 1. Bloque Comedor
                    comedor = df_curso_actual[df_curso_actual["solo_pt_al"] == False]
                    if not comedor.empty:
                        st.markdown("🍴 **En Comedor:**")
                        cols = st.columns(4)
                        for i, (_, alu) in enumerate(comedor.iterrows()):
                            cols[i % 4].markdown(f"<div class='alumno-card'>{alu['Alumno']}</div>", unsafe_allow_html=True)
                    
                    # 2. Bloque Solo Apoyo
                    solo_apoyo = df_curso_actual[df_curso_actual["solo_pt_al"] == True]
                    if not solo_apoyo.empty:
                        st.markdown("📘 **Solo Apoyo (No Comedor):**")
                        cols_ap = st.columns(4)
                        for i, (_, alu) in enumerate(solo_apoyo.iterrows()):
                            cols_ap[i % 4].markdown(f"<div class='alumno-card' style='border-color: #3498db;'>{alu['Alumno']}</div>", unsafe_allow_html=True)

# --- PANTALLA 2: GESTIÓN DE ALUMNOS (SOLO LECTURA DE CATEGORÍA) ---
elif opcion == "👥 Gestión de Alumnos":
    st.title("Configuración de Alumnos PT/AL")
    st.info("Seleccione los alumnos que pertenecen a su programa. El tipo de asistencia (Comedor/Apoyo) solo puede ser modificado por el Administrador.")

    if not df_alumnos.empty:
        df_merge = df_alumnos.merge(df_cursos, left_on="curso_id", right_on="id")
        
        buscar = st.text_input("Buscar alumno por nombre...")
        if buscar:
            df_merge = df_merge[df_merge["nombre_x"].str.contains(buscar, case=False)]

        st.markdown("---")
        # Encabezados de tabla
        h1, h2, h3 = st.columns([2, 1, 1])
        h1.write("**Alumno (Curso)**")
        h2.write("**¿Pertenece a PT/AL?**")
        h3.write("**Categoría actual**")

        for _, fila in df_merge.sort_values(["nombre_y", "nombre_x"]).iterrows():
            c1, c2, c3 = st.columns([2, 1, 1])
            
            with c1:
                st.write(f"{fila['nombre_x']} ({fila['nombre_y']})")
            
            with c2:
                # Ellas solo marcan si el niño es de su cupo o no
                check_pt = st.checkbox("En mi programa", value=fila['es_pt_al'], key=f"pt_{fila['id_x']}")
                if check_pt != fila['es_pt_al']:
                    supabase.table("alumnos").update({"es_pt_al": check_pt}).eq("id", fila['id_x']).execute()
                    st.rerun()

            with c3:
                # SOLO LECTURA: No pueden cambiarlo, solo ven lo que el admin ha puesto
                tipo = "📘 Solo Apoyo" if fila['solo_pt_al'] else "🍴 Comedor"
                st.markdown(f"*{tipo}*")