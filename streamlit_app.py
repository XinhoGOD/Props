import streamlit as st
import time
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import plotly.express as px
import base64
from datetime import datetime

# Configuración de la página
st.set_page_config(
    page_title="Fantasy Sports Ownership",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Funciones de scraping adaptadas para Streamlit
@st.cache_data(ttl=3600)  # Cache por 1 hora
def scrape_ownership_data(sport="mlb", _progress_bar=None):
    """
    Función general para hacer scraping de datos de propiedad tanto para MLB como NBA
    """
    try:
        url = f"https://fantasyteamadvice.com/dfs/{sport}/ownership"
        
        # Configuración para usar Chrome en modo headless
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Ejecutar sin interfaz gráfica
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--start-maximized")
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        if _progress_bar:
            _progress_bar.progress(10)
            _progress_bar.text("Abriendo navegador y cargando la página...")
        
        driver.get(url)
        time.sleep(5)
        
        if progress_bar:
            progress_bar.progress(20)
            progress_bar.text("Esperando que se cargue el contenedor de datos...")
        
        wait = WebDriverWait(driver, 20)
        
        # Buscar el contenedor de la tabla de ownership
        try:
            ownership_container = wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, f"div[data-testid='ownershipTable{sport}']")
            ))
            if progress_bar:
                progress_bar.progress(30)
                progress_bar.text("Contenedor de datos encontrado! Iniciando extracción...")
        except Exception as e:
            if progress_bar:
                progress_bar.error(f"Error al esperar el contenedor: {e}")
            driver.quit()
            return None
        
        # Buscar el contenedor donde se debe hacer scroll
        scroll_container = ownership_container.find_element(By.XPATH, './div')
        
        # Crear lista para guardar los datos de todos los jugadores
        all_players_data = []
        
        # Conjunto para llevar un registro de los jugadores ya procesados (para evitar duplicados)
        processed_players = set()
        
        # Proceso de scroll y captura de datos con scroll incremental
        same_count_iterations = 0
        max_same_count = 5
        total_scrolls = 0
        max_scrolls = 100
        scroll_increment = 300
        current_scroll_position = 0
        
        while total_scrolls < max_scrolls:
            # Actualizar la barra de progreso
            if progress_bar:
                # Calcular progreso basado en número de scrolls y máximo estimado
                estimated_progress = min(30 + (total_scrolls / 30) * 60, 90)
                progress_bar.progress(int(estimated_progress))
                progress_bar.text(f"Scroll #{total_scrolls+1}... Jugadores encontrados: {len(processed_players)}")
            
            # Hacer scroll incremental
            current_scroll_position += scroll_increment
            driver.execute_script(
                f"arguments[0].scrollTop = {current_scroll_position};", 
                scroll_container
            )
            
            # Esperar que se carguen nuevos elementos
            time.sleep(2)
            
            # Contar filas actuales y obtener datos
            player_rows = driver.find_elements(By.CSS_SELECTOR, "div[data-testid='ownershipPlayerRow']")
            current_count = len(player_rows)
            
            # Contador de nuevos jugadores en este scroll
            new_players_in_this_scroll = 0
            
            # Procesar solo jugadores nuevos en cada iteración
            for row in player_rows:
                try:
                    # Obtener nombre del jugador para identificación única
                    player_name = row.find_element(By.CSS_SELECTOR, "div[data-testid='ownershipPlayer']").text
                    
                    # Verificar si ya procesamos este jugador
                    player_key = player_name.strip()
                    if player_key in processed_players:
                        continue
                    
                    # Marcar como procesado
                    processed_players.add(player_key)
                    new_players_in_this_scroll += 1
                    
                    # Obtener equipo
                    team_div = row.find_element(By.CSS_SELECTOR, "div[data-testid='ownershipPlayerTeam']")
                    team_img = team_div.find_element(By.TAG_NAME, "img")
                    team = team_img.get_attribute("alt").replace(" logo", "")
                    
                    # Obtener precios y ownership
                    dk_price = row.find_element(By.CSS_SELECTOR, "div[data-testid='ownershipPlayerDkPrice']").text
                    dk_ownership = row.find_element(By.CSS_SELECTOR, "div[data-testid='ownershipPlayerDkOwnership']").text
                    fd_price = row.find_element(By.CSS_SELECTOR, "div[data-testid='ownershipPlayerFdPrice']").text
                    fd_ownership = row.find_element(By.CSS_SELECTOR, "div[data-testid='ownershipPlayerFdOwnership']").text
                    
                    # Agregar datos a la lista
                    all_players_data.append({
                        'Team': team,
                        'Player': player_name,
                        'DK Price': dk_price,
                        'DK Ownership': dk_ownership,
                        'FD Price': fd_price,
                        'FD Ownership': fd_ownership
                    })
                    
                except Exception as e:
                    st.warning(f"Error procesando jugador: {e}")
                    continue
            
            total_scrolls += 1
            
            # Verificar si estamos encontrando nuevos jugadores
            if new_players_in_this_scroll == 0:
                same_count_iterations += 1
                if same_count_iterations >= max_same_count:
                    # Probar con un scroll grande
                    current_scroll_position += 1000
                    driver.execute_script(
                        f"arguments[0].scrollTop = {current_scroll_position};", 
                        scroll_container
                    )
                    time.sleep(3)
                    
                    # Verificar si encontramos nuevos jugadores 
                    player_rows_after_big_scroll = driver.find_elements(By.CSS_SELECTOR, "div[data-testid='ownershipPlayerRow']")
                    if len(player_rows_after_big_scroll) > current_count:
                        same_count_iterations = 0
                    else:
                        # Intento final: scroll al final
                        driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scroll_container)
                        time.sleep(3)
                        
                        # Verificación final
                        final_player_rows = driver.find_elements(By.CSS_SELECTOR, "div[data-testid='ownershipPlayerRow']")
                        final_new_players = 0
                        
                        for row in final_player_rows:
                            try:
                                player_name = row.find_element(By.CSS_SELECTOR, "div[data-testid='ownershipPlayer']").text
                                if player_name.strip() not in processed_players:
                                    final_new_players += 1
                            except:
                                pass
                        
                        if final_new_players == 0:
                            break
                        else:
                            same_count_iterations = 0
            else:
                same_count_iterations = 0
        
        # Finalizar y cerrar navegador
        driver.quit()
        
        # Crear DataFrame y formatear datos
        df = pd.DataFrame(all_players_data)
        
        # Limpiar y convertir las columnas de ownership
        df['DK Ownership'] = df['DK Ownership'].str.replace('%', '').astype(float)
        df['FD Ownership'] = df['FD Ownership'].str.replace('%', '').astype(float)
        
        # Guardar a CSV
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = f'{sport}_ownership_{timestamp}.csv'
        df.to_csv(csv_path, index=False)
        
        if progress_bar:
            progress_bar.progress(100)
            progress_bar.text(f"Proceso completado. Total de {len(df)} jugadores extraídos.")
        
        return df
        
    except Exception as e:
        if progress_bar:
            progress_bar.error(f"Error en el scraping: {e}")
        if 'driver' in locals():
            driver.quit()
        return None

def analyze_highest_ownership(df, sport=""):
    """
    Analiza los datos para encontrar los jugadores con mayor ownership
    """
    # Crear una copia para no modificar el dataframe original
    df_analysis = df.copy()
    
    # Calcular métricas adicionales
    df_analysis['Combined Ownership'] = df_analysis['DK Ownership'] + df_analysis['FD Ownership']
    df_analysis['Min Ownership'] = df_analysis[['DK Ownership', 'FD Ownership']].min(axis=1)
    
    # Crear diccionario con los resultados
    results = {
        'max_dk': df_analysis.loc[df_analysis['DK Ownership'].idxmax()].to_dict(),
        'max_fd': df_analysis.loc[df_analysis['FD Ownership'].idxmax()].to_dict(),
        'max_combined': df_analysis.loc[df_analysis['Combined Ownership'].idxmax()].to_dict(),
        'max_min': df_analysis.loc[df_analysis['Min Ownership'].idxmax()].to_dict()
    }
    
    return results, df_analysis

def get_top_players(df, n=10):
    """Obtener top N jugadores por diferentes métricas"""
    df_top = df.copy()
    
    # Crear diferentes clasificaciones
    top_dk = df_top.nlargest(n, 'DK Ownership')[['Player', 'Team', 'DK Price', 'DK Ownership']]
    top_fd = df_top.nlargest(n, 'FD Ownership')[['Player', 'Team', 'FD Price', 'FD Ownership']]
    top_combined = df_top.nlargest(n, 'Combined Ownership')[['Player', 'Team', 'DK Ownership', 'FD Ownership', 'Combined Ownership']]
    top_min = df_top.nlargest(n, 'Min Ownership')[['Player', 'Team', 'DK Ownership', 'FD Ownership', 'Min Ownership']]
    
    return {
        'top_dk': top_dk,
        'top_fd': top_fd,
        'top_combined': top_combined,
        'top_min': top_min
    }

def download_link(df, filename, text):
    """Genera un enlace para descargar un DataFrame como archivo CSV"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">{text}</a>'
    return href

# Interfaz de usuario con Streamlit
st.title("🏆 Fantasy Sports Ownership Dashboard")
st.markdown("Herramienta para analizar datos de propiedad (ownership) en Fantasy Sports")

# Crear pestañas para diferentes deportes
tab_mlb, tab_nba, tab_about = st.tabs(["⚾ MLB Ownership", "🏀 NBA Ownership", "ℹ️ Acerca de"])

with tab_mlb:
    st.header("⚾ MLB Ownership Data")
    
    # Botón para iniciar el scraping
    col1, col2 = st.columns([1, 2])
    with col1:
        if st.button("Extraer datos de MLB", type="primary", use_container_width=True):
            # Crear barra de progreso
            progress_bar = st.progress(0)
            status_text = st.empty()
            progress_bar.text("Iniciando...")
            
            # Ejecutar scraping
            mlb_data = scrape_ownership_data("mlb", progress_bar)
            
            # Guardar en session state
            if mlb_data is not None:
                st.session_state.mlb_data = mlb_data
                st.session_state.mlb_analyzed = analyze_highest_ownership(mlb_data, "MLB")
                st.session_state.mlb_top = get_top_players(st.session_state.mlb_analyzed[1])
                st.success(f"✅ Datos extraídos correctamente: {len(mlb_data)} jugadores")
            else:
                st.error("❌ Error al extraer los datos")
    
    with col2:
        if 'mlb_data' in st.session_state:
            st.success(f"✅ Datos disponibles: {len(st.session_state.mlb_data)} jugadores")
            st.markdown(
                download_link(
                    st.session_state.mlb_data, 
                    'mlb_ownership.csv', 
                    '⬇️ Descargar datos en formato CSV'
                ), 
                unsafe_allow_html=True
            )
    
    # Mostrar datos si están disponibles
    if 'mlb_data' in st.session_state:
        # Sección de análisis destacado
        st.header("🔍 Análisis Destacado")
        
        # Obtener resultados del análisis
        analysis_results = st.session_state.mlb_analyzed[0]
        
        # Mostrar tarjetas con los jugadores destacados
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Mayor Ownership en DraftKings")
            max_dk = analysis_results['max_dk']
            st.markdown(f"""
            ### 👑 {max_dk['Player']} ({max_dk['Team']})
            - **DK Ownership**: {max_dk['DK Ownership']:.2f}%
            - **Precio DK**: {max_dk['DK Price']}
            - **FD Ownership**: {max_dk['FD Ownership']:.2f}%
            """)
        
        with col2:
            st.subheader("Mayor Ownership en FanDuel")
            max_fd = analysis_results['max_fd']
            st.markdown(f"""
            ### 👑 {max_fd['Player']} ({max_fd['Team']})
            - **FD Ownership**: {max_fd['FD Ownership']:.2f}%
            - **Precio FD**: {max_fd['FD Price']}
            - **DK Ownership**: {max_fd['DK Ownership']:.2f}%
            """)
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Mayor Ownership Combinado")
            max_combined = analysis_results['max_combined']
            st.markdown(f"""
            ### 👑 {max_combined['Player']} ({max_combined['Team']})
            - **Total**: {max_combined['Combined Ownership']:.2f}%
            - **DK**: {max_combined['DK Ownership']:.2f}%
            - **FD**: {max_combined['FD Ownership']:.2f}%
            """)
        
        with col2:
            st.subheader("Mayor Ownership en Ambas")
            max_min = analysis_results['max_min']
            st.markdown(f"""
            ### 👑 {max_min['Player']} ({max_min['Team']})
            - **Mínimo**: {max_min['Min Ownership']:.2f}%
            - **DK**: {max_min['DK Ownership']:.2f}%
            - **FD**: {max_min['FD Ownership']:.2f}%
            """)
        
        # Pestañas para tops y tablas
        tab_top, tab_table, tab_viz = st.tabs(["Top Jugadores", "Tabla Completa", "Visualizaciones"])
        
        with tab_top:
            # Mostrar top 10 jugadores en diferentes categorías
            st.subheader("Top 10 Jugadores por Categoría")
            top_data = st.session_state.mlb_top
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### Top 10 DraftKings Ownership")
                st.dataframe(top_data['top_dk'], use_container_width=True)
            
            with col2:
                st.markdown("#### Top 10 FanDuel Ownership")
                st.dataframe(top_data['top_fd'], use_container_width=True)
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### Top 10 Ownership Combinado")
                st.dataframe(top_data['top_combined'], use_container_width=True)
            
            with col2:
                st.markdown("#### Top 10 Ownership en Ambas Plataformas")
                st.dataframe(top_data['top_min'], use_container_width=True)
        
        with tab_table:
            # Mostrar tabla completa con filtrado
            st.subheader("Datos Completos")
            st.dataframe(st.session_state.mlb_data, use_container_width=True)
        
        with tab_viz:
            # Visualizaciones
            st.subheader("Visualizaciones")
            
            # Seleccionar top N jugadores para gráfico
            n_players = st.slider("Número de jugadores a mostrar", 5, 30, 15)
            
            # Obtener datos para visualización
            top_players_viz = st.session_state.mlb_analyzed[1].nlargest(n_players, 'Min Ownership')
            
            # Crear gráfico de barras comparativas
            fig = px.bar(
                top_players_viz,
                x='Player',
                y=['DK Ownership', 'FD Ownership'],
                title=f'Top {n_players} Jugadores por Ownership',
                labels={'value': 'Ownership (%)', 'Player': 'Jugador', 'variable': 'Plataforma'},
                barmode='group',
                color_discrete_sequence=['#1E88E5', '#FFC107']
            )
            fig.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)
            
            # Gráfico de dispersión: DK vs FD ownership
            fig2 = px.scatter(
                st.session_state.mlb_analyzed[1],
                x='DK Ownership',
                y='FD Ownership',
                hover_name='Player',
                hover_data=['Team', 'DK Price', 'FD Price'],
                title='Comparación de Ownership entre DraftKings y FanDuel',
                labels={'DK Ownership': 'DraftKings Ownership (%)', 'FD Ownership': 'FanDuel Ownership (%)'}
            )
            fig2.update_layout(
                xaxis_title="DraftKings Ownership (%)",
                yaxis_title="FanDuel Ownership (%)"
            )
            # Añadir línea de 45 grados para referencia
            max_val = max(
                st.session_state.mlb_analyzed[1]['DK Ownership'].max(),
                st.session_state.mlb_analyzed[1]['FD Ownership'].max()
            )
            fig2.add_shape(
                type='line',
                x0=0,
                y0=0,
                x1=max_val,
                y1=max_val,
                line=dict(color='red', dash='dash')
            )
            st.plotly_chart(fig2, use_container_width=True)

with tab_nba:
    st.header("🏀 NBA Ownership Data")
    
    # Botón para iniciar el scraping
    col1, col2 = st.columns([1, 2])
    with col1:
        if st.button("Extraer datos de NBA", type="primary", use_container_width=True):
            # Crear barra de progreso
            progress_bar = st.progress(0)
            status_text = st.empty()
            progress_bar.text("Iniciando...")
            
            # Ejecutar scraping
            nba_data = scrape_ownership_data("nba", progress_bar)
            
            # Guardar en session state
            if nba_data is not None:
                st.session_state.nba_data = nba_data
                st.session_state.nba_analyzed = analyze_highest_ownership(nba_data, "NBA")
                st.session_state.nba_top = get_top_players(st.session_state.nba_analyzed[1])
                st.success(f"✅ Datos extraídos correctamente: {len(nba_data)} jugadores")
            else:
                st.error("❌ Error al extraer los datos")
    
    with col2:
        if 'nba_data' in st.session_state:
            st.success(f"✅ Datos disponibles: {len(st.session_state.nba_data)} jugadores")
            st.markdown(
                download_link(
                    st.session_state.nba_data, 
                    'nba_ownership.csv', 
                    '⬇️ Descargar datos en formato CSV'
                ), 
                unsafe_allow_html=True
            )
    
    # Mostrar datos si están disponibles (mismo código que MLB pero con nba_data)
    if 'nba_data' in st.session_state:
        # Sección de análisis destacado
        st.header("🔍 Análisis Destacado")
        
        # Obtener resultados del análisis
        analysis_results = st.session_state.nba_analyzed[0]
        
        # Mostrar tarjetas con los jugadores destacados
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Mayor Ownership en DraftKings")
            max_dk = analysis_results['max_dk']
            st.markdown(f"""
            ### 👑 {max_dk['Player']} ({max_dk['Team']})
            - **DK Ownership**: {max_dk['DK Ownership']:.2f}%
            - **Precio DK**: {max_dk['DK Price']}
            - **FD Ownership**: {max_dk['FD Ownership']:.2f}%
            """)
        
        with col2:
            st.subheader("Mayor Ownership en FanDuel")
            max_fd = analysis_results['max_fd']
            st.markdown(f"""
            ### 👑 {max_fd['Player']} ({max_fd['Team']})
            - **FD Ownership**: {max_fd['FD Ownership']:.2f}%
            - **Precio FD**: {max_fd['FD Price']}
            - **DK Ownership**: {max_fd['DK Ownership']:.2f}%
            """)
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Mayor Ownership Combinado")
            max_combined = analysis_results['max_combined']
            st.markdown(f"""
            ### 👑 {max_combined['Player']} ({max_combined['Team']})
            - **Total**: {max_combined['Combined Ownership']:.2f}%
            - **DK**: {max_combined['DK Ownership']:.2f}%
            - **FD**: {max_combined['FD Ownership']:.2f}%
            """)
        
        with col2:
            st.subheader("Mayor Ownership en Ambas")
            max_min = analysis_results['max_min']
            st.markdown(f"""
            ### 👑 {max_min['Player']} ({max_min['Team']})
            - **Mínimo**: {max_min['Min Ownership']:.2f}%
            - **DK**: {max_min['DK Ownership']:.2f}%
            - **FD**: {max_min['FD Ownership']:.2f}%
            """)
        
        # Pestañas para tops y tablas
        tab_top, tab_table, tab_viz = st.tabs(["Top Jugadores", "Tabla Completa", "Visualizaciones"])
        
        with tab_top:
            # Mostrar top 10 jugadores en diferentes categorías
            st.subheader("Top 10 Jugadores por Categoría")
            top_data = st.session_state.nba_top
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### Top 10 DraftKings Ownership")
                st.dataframe(top_data['top_dk'], use_container_width=True)
            
            with col2:
                st.markdown("#### Top 10 FanDuel Ownership")
                st.dataframe(top_data['top_fd'], use_container_width=True)
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### Top 10 Ownership Combinado")
                st.dataframe(top_data['top_combined'], use_container_width=True)
            
            with col2:
                st.markdown("#### Top 10 Ownership en Ambas Plataformas")
                st.dataframe(top_data['top_min'], use_container_width=True)
        
        with tab_table:
            # Mostrar tabla completa con filtrado
            st.subheader("Datos Completos")
            st.dataframe(st.session_state.nba_data, use_container_width=True)
        
        with tab_viz:
            # Visualizaciones
            st.subheader("Visualizaciones")
            
            # Seleccionar top N jugadores para gráfico
            n_players = st.slider("Número de jugadores a mostrar", 5, 30, 15, key="nba_slider")
            
            # Obtener datos para visualización
            top_players_viz = st.session_state.nba_analyzed[1].nlargest(n_players, 'Min Ownership')
            
            # Crear gráfico de barras comparativas
            fig = px.bar(
                top_players_viz,
                x='Player',
                y=['DK Ownership', 'FD Ownership'],
                title=f'Top {n_players} Jugadores por Ownership',
                labels={'value': 'Ownership (%)', 'Player': 'Jugador', 'variable': 'Plataforma'},
                barmode='group',
                color_discrete_sequence=['#1E88E5', '#FFC107']
            )
            fig.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)
            
            # Gráfico de dispersión: DK vs FD ownership
            fig2 = px.scatter(
                st.session_state.nba_analyzed[1],
                x='DK Ownership',
                y='FD Ownership',
                hover_name='Player',
                hover_data=['Team', 'DK Price', 'FD Price'],
                title='Comparación de Ownership entre DraftKings y FanDuel',
                labels={'DK Ownership': 'DraftKings Ownership (%)', 'FD Ownership': 'FanDuel Ownership (%)'}
            )
            fig2.update_layout(
                xaxis_title="DraftKings Ownership (%)",
                yaxis_title="FanDuel Ownership (%)"
            )
            # Añadir línea de 45 grados para referencia
            max_val = max(
                st.session_state.nba_analyzed[1]['DK Ownership'].max(),
                st.session_state.nba_analyzed[1]['FD Ownership'].max()
            )
            fig2.add_shape(
                type='line',
                x0=0,
                y0=0,
                x1=max_val,
                y1=max_val,
                line=dict(color='red', dash='dash')
            )
            st.plotly_chart(fig2, use_container_width=True)

with tab_about:
    st.header("ℹ️ Acerca de esta Aplicación")
    
    st.markdown("""
    ### 🏆 Fantasy Sports Ownership Dashboard
    
    Esta aplicación te permite extraer y analizar datos de propiedad (ownership) para Fantasy Sports de MLB y NBA desde FantasyTeamAdvice.com.
    
    #### Características:
    
    - **Extracción de Datos**: Web scraping automatizado que captura todos los jugadores disponibles.
    - **Análisis Detallado**: Identifica jugadores con mayor ownership en diferentes categorías.
    - **Visualizaciones**: Gráficos interactivos para comparar ownership entre plataformas.
    - **Exportación**: Descarga los datos en formato CSV para análisis adicional.
    
    #### ¿Cómo usar la aplicación?
    
    1. Selecciona la pestaña del deporte que te interesa (MLB o NBA).
    2. Haz clic en el botón "Extraer datos".
    3. Espera a que se complete el proceso de scraping.
    4. Explora los diferentes análisis y visualizaciones disponibles.
    
    #### Requisitos adicionales
    
    Para ejecutar esta aplicación en tu entorno local, necesitas instalar:
    
    ```
    pip install streamlit pandas selenium webdriver-manager plotly
    ```
    
    **Nota**: El scraping puede tardar varios minutos dependiendo de la cantidad de jugadores disponibles.
    """)

    st.info("Esta aplicación es solo para fines educativos y de análisis personal. No está afiliada oficialmente a FantasyTeamAdvice, DraftKings o FanDuel.")
