import streamlit as st
import PyPDF2
import requests
import json

# ==============================================================================
# 1. INTERFAZ
# ==============================================================================
st.set_page_config(page_title="Sistema Interno de Análisis Cuantitativo", page_icon="📊", layout="centered")

st.sidebar.title("🔒 Acceso Restringido")
access_code = st.sidebar.text_input("Ingrese código de operador:", type="password")

if access_code != "CLAVE123":
    st.warning("Acceso denegado. Sistema reservado para personal autorizado.")
    st.stop()

st.title("📊 Panel de Procesamiento de Datos Deportivos")
st.markdown("**Instrucciones:** Suba los PDFs de estadísticas y los PDFs de cuotas. El sistema extraerá y analizará toda la información automáticamente.")
st.markdown("---")

# ==============================================================================
# 2. PROMPT
# ==============================================================================
SYSTEM_PROMPT = """
Actúa como un Analista Cuantitativo Profesional de Apuestas Deportivas (Quant). Tu único objetivo es preservar el capital y encontrar Valor Esperado Positivo (+EV) matemáticamente demostrable. Tu tolerancia al riesgo es extremadamente baja.

Analizarás EXCLUSIVAMENTE los datos numéricos de los archivos PDF adjuntos. PROHIBIDO usar conocimiento general, narrativas de "motivación", o inventar datos. Si un dato no está en los PDFs, el mercado correspondiente se descarta inmediatamente.

IMPORTANTE: Uno de los PDFs contiene las cuotas de las casas de apuestas. Debes extraer automáticamente las cuotas relevantes de ese documento y usarlas para tus cálculos de +EV.

Aplica el siguiente ALGORITMO DE 5 PASOS de forma estricta y genera la respuesta exactamente en este formato:

🛑 PASO 1: AUDITORÍA DE LAS 9 CATEGORÍAS (Filtro de Suficiencia de Datos)
Escanea los PDFs y evalúa si hay datos suficientes para las siguientes categorías. Si NO hay datos, escríbelo literalmente: "Categoría X: DATOS INSUFICIENTES EN PDF. MERCADO DESCARTADO".
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
Selecciona las 1, 2 o 3 oportunidades más sólidas. Para cada una:
• Mercado: [Ej: Villarreal Más de 5.5 Tiros a Puerta]
• Cuota Implícita (extraída del PDF de cuotas): [Ej: 1.50 = 66.6%]
• Probabilidad Real (basada en PDFs de estadísticas): [justifica con cifras del PDF]
• Margen +EV: [Ej: 75% - 66.6% = +8.4%]. Si es menor al 5%, descarta como "-EV / Trampa".

⚖️ PASO 3: VEREDICTO BINARIO Y STAKE
Elige UNA SOLA opción de máxima confianza.
• Opción A: 1 mercado único de alta probabilidad.
• Opción B: 1 Combinada Correlacionada de MÁXIMO 2 selecciones. Nunca 3 o más.
• Stake: "Stake Fijo: 1% del Bankroll".

📈 PASO 4: EVIDENCIA CON DATOS DUROS
Exactamente 3 citas numéricas de los PDFs.
• Formato: "📄 Dato PDF: [Cifra exacta]. Esto valida la apuesta porque..."

⚠️ PASO 5: REGLA DE LA HORA (Kill Switch Pre-Partido)
• VALIDAR si: [condición exacta].
• CANCELAR INMEDIATAMENTE si: [condición exacta].

REGLAS INQUEBRANTABLES:
1. Cero Alucinaciones: Si el PDF dice "DATA FOR PREMIUM MEMBERS ONLY" o "UNLOCK", el dato es NO DISPONIBLE y se descarta ese mercado.
2. Matemáticas sobre Narrativa: Ignora frases como "necesitan ganar".
3. Si no hay +EV claro (>5%), responde: "⛔ NO APOSTAR. Ningún mercado presenta un +EV matemático suficiente basado en los datos de los PDFs. Preservar capital."
4. Si no puedes extraer cuotas, responde: "⚠️ ERROR: No se pudieron extraer las cuotas de los PDFs proporcionados."

IMPORTANTE: Entrega SIEMPRE el informe final completo en texto visible. No respondas vacío.
"""

# ==============================================================================
# 3. ENTRADA DE DATOS
# ==============================================================================
st.subheader("1. PDFs de Estadísticas del Partido")
stats_files = st.file_uploader("Seleccionar PDFs de Estadísticas", type="pdf", accept_multiple_files=True, key="stats")

st.markdown("---")

st.subheader("2. PDFs de Cuotas (Casas de Apuestas)")
odds_files = st.file_uploader("Seleccionar PDFs de Cuotas", type="pdf", accept_multiple_files=True, key="odds")

# ==============================================================================
# 4. PROCESAMIENTO CON RESPALDO AUTOMÁTICO
# ==============================================================================

def extraer_texto(files):
    texto = ""
    for f in files:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            t = page.extract_text()
            if t:
                texto += t + "\n"
    return texto


def consultar_motor(api_key, mensajes):
    """Consulta la lista de modelos gratuitos en orden hasta obtener texto real."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://sistema-interno.local",
        "X-Title": "SistemaInterno"
    }

    # 1) Descubrir en vivo qué modelos gratuitos existen HOY
    candidatos = []
    try:
        cat = requests.get("https://openrouter.ai/api/v1/models", headers=headers, timeout=30)
        if cat.status_code == 200:
            for m in cat.json().get("data", []):
                precio = m.get("pricing", {})
                es_gratis = str(precio.get("prompt", "1")) in ("0", "0.0") and str(precio.get("completion", "1")) in ("0", "0.0")
                if es_gratis or m.get("id", "").endswith(":free"):
                    candidatos.append(m["id"])
    except Exception:
        pass

    # 2) Lista de respaldo fija por si el catálogo falla
    respaldo = [
        "openrouter/free",
        "deepseek/deepseek-r1:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "google/gemini-2.0-flash-exp:free",
        "mistralai/mistral-small-3.1-24b-instruct:free",
    ]
    for r in respaldo:
        if r not in candidatos:
            candidatos.append(r)

    # Priorizar modelos potentes known-good si están disponibles
    preferidos = [c for c in candidatos if any(k in c.lower() for k in ["deepseek", "llama", "qwen", "gemini", "nemotron", "mistral"])]
    otros = [c for c in candidatos if c not in preferidos]
    orden = preferidos + otros

    registro = []
    for modelo in orden[:12]:  # intenta hasta 12 modelos
        try:
            payload = {
                "model": modelo,
                "messages": mensajes,
                "temperature": 0.1,
                "max_tokens": 4000
            }
            r = requests.post(url, headers=headers, json=payload, timeout=180)

            if r.status_code != 200:
                registro.append(f"{modelo} → HTTP {r.status_code}")
                continue

            data = r.json()
            if "choices" not in data or not data["choices"]:
                registro.append(f"{modelo} → sin 'choices'")
                continue

            msg = data["choices"][0].get("message", {}) or {}
            contenido = msg.get("content")

            # Algunos modelos ponen el texto en 'reasoning'
            if not contenido:
                contenido = msg.get("reasoning") or data["choices"][0].get("text")

            if contenido and str(contenido).strip():
                return str(contenido), modelo, registro

            registro.append(f"{modelo} → respuesta vacía")
        except Exception as e:
            registro.append(f"{modelo} → {type(e).__name__}")
            continue

    return None, None, registro


if st.button("⚙️ EJECUTAR ANÁLISIS CUANTITATIVO", type="primary"):
    if not stats_files or not odds_files:
        st.error("⚠️ Error: Debe subir al menos un PDF de estadísticas y al menos un PDF de cuotas.")
    else:
        with st.spinner("Procesando datos y calculando probabilidades..."):
            try:
                stats_text = extraer_texto(stats_files)
                odds_text = extraer_texto(odds_files)

                if len(stats_text.strip()) < 50 or len(odds_text.strip()) < 20:
                    st.error("⚠️ Los PDFs no contienen texto legible. Es probable que se hayan guardado como imagen. Vuelva a imprimir la página usando 'Guardar como PDF' (no captura de pantalla).")
                    st.stop()

                # Recorte de seguridad para no exceder límites gratuitos
                stats_text = stats_text[:30000]
                odds_text = odds_text[:15000]

                mensajes = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"--- DATOS DE ESTADÍSTICAS ---\n{stats_text}\n\n--- DATOS DE CUOTAS ---\n{odds_text}"}
                ]

                resultado, modelo_usado, registro = consultar_motor(st.secrets["OR_API_KEY"], mensajes)

                if resultado:
                    st.success("✅ Análisis completado exitosamente.")
                    st.markdown("---")
                    st.markdown(resultado)
                    st.markdown("---")
                    st.caption("Sistema Interno de Análisis Cuantitativo v1.0 | Uso exclusivo.")
                else:
                    st.error("⛔ Ningún motor gratuito disponible respondió en este momento.")
                    with st.expander("Ver diagnóstico técnico"):
                        st.write(registro)

            except Exception as e:
                st.error(f"Error en el sistema: {type(e).__name__}: {str(e)}")
