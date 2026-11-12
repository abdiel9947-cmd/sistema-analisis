import streamlit as st
import PyPDF2
import requests

# ==============================================================================
# 1. CONFIGURACIÓN DE LA INTERFAZ
# ==============================================================================
st.set_page_config(page_title="Sistema Interno de Análisis Cuantitativo", page_icon="📊", layout="centered")

# Pantalla de bloqueo
st.sidebar.title("🔒 Acceso Restringido")
access_code = st.sidebar.text_input("Ingrese código de operador:", type="password")

if access_code != "CLAVE123":  # <--- CAMBIA ESTA CLAVE POR LA QUE TÚ QUIERAS
    st.warning("Acceso denegado. Sistema reservado para personal autorizado.")
    st.stop()

st.title("📊 Panel de Procesamiento de Datos Deportivos")
st.markdown("**Instrucciones:** Suba los PDFs de estadísticas y los PDFs de cuotas de las casas de apuestas. El sistema extraerá y analizará toda la información automáticamente.")
st.markdown("---")

# ==============================================================================
# 2. EL CEREBRO OCULTO (PROMPT)
# ==============================================================================
SYSTEM_PROMPT = """
Actúa como un Analista Cuantitativo Profesional de Apuestas Deportivas (Quant). Tu único objetivo es preservar el capital y encontrar Valor Esperado Positivo (+EV) matemáticamente demostrable. Tu tolerancia al riesgo es extremadamente baja.

Analizarás EXCLUSIVAMENTE los datos numéricos de los archivos PDF adjuntos. PROHIBIDO usar conocimiento general, narrativas de "motivación", o inventar datos. Si un dato no está en los PDFs, el mercado correspondiente se descarta inmediatamente.

IMPORTANTE: Uno de los PDFs contiene las cuotas de las casas de apuestas. Debes extraer automáticamente las cuotas relevantes de ese documento y usarlas para tus cálculos de +EV.

Aplica el siguiente ALGORITMO DE 5 PASOS de forma estricta y genera la respuesta exactamente en este formato:

🛑 PASO 1: AUDITORÍA DE LAS 9 CATEGORÍAS (Filtro de Sufficiencia de Datos)
Escanea los PDFs y evalúa rápidamente si hay datos suficientes para las siguientes categorías. Si NO hay datos, escríbelo literalmente: "Categoría X: DATOS INSUFICIENTES EN PDF. MERCADO DESCARTADO".
1. Principales: (1X2, Hándicap, Doble Oportunidad, DNB).
2. Goles: (Over/Under, BTTS, Goles por equipo/mitad).
3. Jugadores: (Goleador, Tiros a puerta del jugador, Tarjetas del jugador).
4. Disciplina: (Tarjetas totales, Faltas cometidas por equipo/jugador).
5. Córners: (Totales, por equipo, hándicap).
6. Mitades/Intervalos: (Resultado HT, Goles HT/2T).
7. Stats Avanzadas: (Tiros totales, Tiros a puerta, xG, xGA, Fueras de juego).
8. Asiáticos: (Hándicap Asiático, Totales Asiáticos).
9. Especiales: (Primer gol, Win to Nil, Gana al menos una parte).

📊 PASO 2: CÁLCULO DE +EV (Solo para mercados con datos completos)
De las categorías que PASARON el Paso 1, selecciona las 1, 2 o 3 oportunidades más sólidas. Para cada una, muestra el cálculo:
• Mercado: [Ej: Villarreal Más de 5.5 Tiros a Puerta]
• Cuota Implícita (extraída del PDF de cuotas): [Ej: 1.50 = 66.6%]
• Probabilidad Real (basada en PDFs de estadísticas): [Ej: El PDF muestra "Team Shots On Target 5.5+ 60%", pero ajustado por el rival con 0% de clean sheets fuera, la probabilidad real se estima en 75%].
• Margen +EV: [Ej: 75% - 66.6% = +8.4% de valor]. Si el margen es menor al 5%, descarta el mercado como "-EV / Trampa".

⚖️ PASO 3: VEREDICTO BINARIO Y STAKE (La única recomendación)
Elige UNA SOLA opción de máxima confianza para minimizar la varianza.
• Opción A (Recomendada): 1 mercado único de alta probabilidad.
• Opción B (Alternativa): 1 Combinada Correlacionada de MÁXIMO 2 selecciones. Nunca 3 o más.
• Stake: Indica "Stake Fijo: 1% del Bankroll".

📈 PASO 4: EVIDENCIA CON DATOS DUROS (Citas Textuales)
Proporciona exactamente 3 citas numéricas de los PDFs que blinden la recomendación del Paso 3.
• Formato: "📄 Dato PDF: [Cifra exacta]. Esto valida la apuesta porque..."

⚠️ PASO 5: REGLA DE LA HORA (Kill Switch Pre-Partido)
Define la condición exacta que VALIDA o CANCELARÁ la apuesta 60 minutos antes del inicio.
• VALIDAR si: [Ej: "El titular confirmado incluye a X"].
• CANCELAR INMEDIATAMENTE si: [Ej: "La cuota baja más de un 15%"].

REGLAS INQUEBRANTABLES:
1. Cero Alucinaciones: Si el PDF dice "DATA FOR PREMIUM MEMBERS ONLY", asume que el dato es NO DISPONIBLE y descarta esos mercados.
2. Matemáticas sobre Narrativa: Ignora frases como "necesitan ganar".
3. Prioridad de Seguridad: Si no hay ningún mercado con un +EV claro (>5%), tu respuesta final debe ser: "⛔ NO APOSTAR. Ningún mercado presenta un +EV matemático suficiente basado en los datos de los PDFs. Preservar capital."
4. Extracción de Cuotas: Si no puedes identificar claramente las cuotas en los PDFs de casas de apuestas, indica "⚠️ ERROR: No se pudieron extraer las cuotas de los PDFs proporcionados."
"""

# ==============================================================================
# 3. FORMULARIO DE ENTRADA (SOLO PDFs)
# ==============================================================================
st.subheader("1. PDFs de Estadísticas del Partido")
st.markdown("Suba los PDFs de sitios como Flashscore, Sofascore, etc. (máx. 3 archivos)")
stats_files = st.file_uploader("Seleccionar PDFs de Estadísticas", type="pdf", accept_multiple_files=True, key="stats")

st.markdown("---")

st.subheader("2. PDFs de Cuotas (Casas de Apuestas)")
st.markdown("Suba los PDFs de casas de apuestas como Bet365, Pinnacle, etc. (máx. 3 archivos)")
odds_files = st.file_uploader("Seleccionar PDFs de Cuotas", type="pdf", accept_multiple_files=True, key="odds")

# ==============================================================================
# 4. PROCESAMIENTO
# ==============================================================================
if st.button("⚙️ EJECUTAR ANÁLISIS CUANTITATIVO", type="primary"):
    if not stats_files or not odds_files:
        st.error("⚠️ Error: Debe subir al menos un PDF de estadísticas y al menos un PDF de cuotas.")
    else:
        with st.spinner("Procesando datos y calculando probabilidades (esto puede tomar 5-10 segundos)..."):
            try:
                # A. Leer el texto de los PDFs de estadísticas
                stats_text = ""
                for file in stats_files:
                    reader = PyPDF2.PdfReader(file)
                    for page in reader.pages:
                        stats_text += page.extract_text() + "\n"
                
                # B. Leer el texto de los PDFs de cuotas
                odds_text = ""
                for file in odds_files:
                    reader = PyPDF2.PdfReader(file)
                    for page in reader.pages:
                        odds_text += page.extract_text() + "\n"
                
                # C. CONFIGURACIÓN DE LA API GROQ
                GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
                API_URL = "https://api.groq.com/openai/v1/chat/completions"
                
                headers = {
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "model": "llama3-70b-8192",
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f"--- DATOS DE ESTADÍSTICAS ---\n{stats_text}\n\n--- DATOS DE CUOTAS ---\n{odds_text}"}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 2000
                }
                
                # D. Enviar solicitud
                response = requests.post(API_URL, headers=headers, json=payload)
                
                if response.status_code == 200:
                    resultado = response.json()["choices"][0]["message"]["content"]
                    st.success("✅ Análisis completado exitosamente.")
                    st.markdown("---")
                    st.markdown(resultado)
                    st.markdown("---")
                    st.caption("Sistema Interno de Análisis Cuantitativo v1.0 | Uso exclusivo.")
                else:
                    st.error(f"Error del servidor: {response.status_code}. Detalles: {response.text}")

            except Exception as e:
                st.error(f"Error en el sistema: {str(e)}.")
