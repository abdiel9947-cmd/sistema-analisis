import json
import re
import requests
import streamlit as st
from openai import OpenAI

# Configuración de la página
st.set_page_config(
    page_title="Quant Betting AI System +EV", page_icon="📈", layout="wide"
)

# --- 1. PROTECCIÓN POR CONTRASEÑA ---
if "authenticated" not in st.session_state:
  st.session_state.authenticated = False

if not st.session_state.authenticated:
  st.title("🔒 Acceso Restringido - Comunidad Suscriptores")
  password_input = st.text_input("Introduce la contraseña:", type="password")
  if st.button("Ingresar"):
    if password_input == st.secrets.get("APP_PASSWORD", "admin123"):
      st.session_state.authenticated = True
      st.rerun()
    else:
      st.error("Contraseña incorrecta.")
  st.stop()


# --- FUNCIÓN DE CLIMA AUTOMÁTICO (Open-Meteo API - Sin API Key) ---
def obtener_clima_estadio(nombre_estadio):
  try:
    # Geocodificación usando el nombre del estadio o ciudad extraído del texto
    geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={requests.utils.quote(nombre_estadio)}&count=1&language=es&format=json"
    geo_resp = requests.get(geo_url, timeout=5).json()

    if "results" not in geo_resp or not geo_resp["results"]:
      return f"Clima: No se pudo geolocalizar automáticamente el estadio '{nombre_estadio}'."

    lat = geo_resp["results"][0]["latitude"]
    lon = geo_resp["results"][0]["longitude"]
    nombre_lugar = geo_resp["results"][0].get("name", nombre_estadio)
    pais = geo_resp["results"][0].get("country", "")

    # Obtener pronóstico actual y condiciones meteorológicas
    weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m&timezone=auto"
    w_resp = requests.get(weather_url, timeout=5).json()

    if "current" in w_resp:
      curr = w_resp["current"]
      temp = curr.get("temperature_2m", "N/D")
      hum = curr.get("relative_humidity_2m", "N/D")
      prec = curr.get("precipitation", "N/D")
      wind = curr.get("wind_speed_10m", "N/D")

      return (
          f"Ubicación Detectada Automáticamente: {nombre_lugar}, {pais} (Lat:"
          f" {lat}, Lon: {lon}) | Temperatura: {temp}°C | Humedad: {hum}% |"
          f" Precipitación: {prec} mm | Viento: {wind} km/h"
      )
    else:
      return "Clima: Datos meteorológicos no disponibles temporalmente."
  except Exception as e:
    return f"Clima: Error al consultar el servicio meteorológico ({e})."


# --- 2. INTERFAZ PRINCIPAL ---
st.title("📈 Sistema Cuantitativo de Apuestas Deportivas (+EV)")
st.markdown(
    "Pega el consolidado completo del partido. El sistema detectará"
    " automáticamente el estadio, consultará el clima y ejecutará la auditoría"
    " cuantitativa."
)

texto_partido = st.text_area(
    "Pega aquí todo el consolidado de datos (FootyStats, Flashscore, Árbitro,"
    " etc.):",
    height=320,
    placeholder=(
        "Pega aquí los bloques de texto generados por tus prompts maestros..."
    ),
)

SYSTEM_PROMPT = """
Actúa como un Analista Cuantitativo Profesional de Apuestas Deportivas (Quant). Tu objetivo absoluto es preservar el capital y detectar Valor Esperado Positivo (+EV) matemáticamente demostrable (> 5%). Tu tolerancia al riesgo es extremadamente baja.

Analiza EXCLUSIVAMENTE los datos numéricos y estructurados del texto proporcionado, incluyendo:
1. Datos meteorológicos automáticos integrados en el entorno.
2. Estadísticas macro de FootyStats (xG, xGA, PPG, tendencias All/Home/Away).
3. Cuotas de mercado de Flashscore para los 10 apartados (1X2, Más/Menos, Ambos Marcan, Hándicap Asiático/Europeo, Doble Oportunidad, Apuesta sin Empate, Marcador Correcto, Descanso/Final, Par/Impar).
4. Perfil institucional y disciplinario del árbitro en StatsHub (amarillas, rojas, penaltis).
5. Alineaciones, ratings y eventos minuto a minuto.

REGLAS DE ORO INQUEBRANTABLES:
1. Cero Alucinaciones / Temperatura 0.1: Si un dato dice "N/D", está bloqueado o no aparece, descarta el mercado correspondiente de inmediato. Nunca inventes cuotas ni estimes porcentajes.
2. Formato Estricto: Devuelve la respuesta ÚNICAMENTE en formato JSON válido con la estructura exacta solicitada.
3. Validación de Probabilidades: Compara la probabilidad implícita de las cuotas vigentes con la probabilidad estadística calculada de las fuentes. Si el margen +EV es estrictamente menor al 5%, no lo incluyas en oportunidades.

ESTRUCTURA JSON OBLIGATORIA:
{
  "auditoria_9_categorias": {
    "1_Principales": "ESTADO Y DATOS SUFICIENTES/INSUFICIENTES",
    "2_Goles": "...",
    "3_Jugadores": "...",
    "4_Disciplina": "...",
    "5_Corners": "...",
    "6_Mitades": "...",
    "7_Stats_Avanzadas": "...",
    "8_Asiaticos": "...",
    "9_Especiales": "..."
  },
  "oportunidades": [
    {
      "mercado": "Nombre exacto del mercado con +EV > 5%",
      "cuota": 0.0,
      "probabilidad_datos": 0.0,
      "margen_ev": 0.0,
      "evidencia_1": "Cita textual 1 con datos duros del texto",
      "evidencia_2": "Cita textual 2 con datos duros del texto",
      "evidencia_3": "Cita textual 3 con datos duros del texto",
      "validar_si": "Condición pre-partido exacta",
      "cancelar_si": "Condición exacta para cancelar apuesta"
    }
  ],
  "veredicto_final": "APOSTAR" o "NO APOSTAR",
  "mensaje_preservacion": "Stake Fijo: 1% del Bankroll o directriz de preservación."
}
"""

if st.button("Ejecutar Análisis Cuantitativo Avanzado"):
  if not texto_partido.strip():
    st.warning("Por favor, pega los datos consolidados del partido.")
  else:
    with st.spinner(
        "Extrayendo estadio, consultando clima y procesando con OpenAI"
        " (Temperatura 0.1)..."
    ):
      try:
        # Extracción automática del estadio usando Expresiones Regulares (Regex)
        estadio_detectado = ""
        # Busca patrones como "Estadio: [Nombre]" o "Stadium: [Nombre]" en el texto pegado
        match_estadio = re.search(
            r"(?:Estadio|Stadium):\s*([^\n\r]+)", texto_partido, re.IGNORECASE
        )
        if match_estadio:
          estadio_detectado = match_estadio.group(1).strip()

        info_clima = ""
        if estadio_detectado:
          clima_resultado = obtener_clima_estadio(estadio_detectado)
          info_clima = (
              f"\n[DATOS METEOROLÓGICOS AUTOMÁTICOS (Extraídos del"
              f" texto)]\n- Estadio Detectado: {estadio_detectado}\n-"
              f" {clima_resultado}\n"
          )
        else:
          info_clima = (
              "\n[DATOS METEOROLÓGICOS]: No se encontró una línea de 'Estadio:'"
              " en el texto pegado para geolocalizar automáticamente.\n"
          )

        # Consolidar texto completo para la IA
        input_total = (
            info_clima + "\n\n[DATOS CONSOLIDADOS DEL PARTIDO]\n" + texto_partido
        )

        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": input_total},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,  # Cero creatividad, máxima precisión matemática
        )

        resultado_json = json.loads(response.choices[0].message.content)

        st.success("¡Análisis cuantitativo completado con éxito!")

        veredicto = resultado_json.get("veredicto_final", "NO APOSTAR")
        if veredicto == "APOSTAR":
          st.error(f"🟢 VEREDICTO: {veredicto}")
        else:
          st.warning(f"🛑 VEREDICTO: {veredicto}")

        st.info(
            f"**Gestión de Bankroll / Preservación:**"
            f" {resultado_json.get('mensaje_preservacion', '')}"
        )

        tab1, tab2, tab3 = st.tabs([
            "📊 Oportunidades +EV",
            "📋 Auditoría de 9 Categorías",
            "🌦️ Clima Detectado",
        ])

        with tab1:
          oportunidades = resultado_json.get("oportunidades", [])
          if not oportunidades:
            st.info(
                "No se encontraron mercados con un +EV > 5%. Se recomienda"
                " preservar el capital."
            )
          else:
            for idx, op in enumerate(oportunidades, 1):
              with st.expander(
                  f"Oportunidad {idx}: {op.get('mercado')} (+{op.get('margen_ev')}% EV)"
              ):
                col1, col2, col3 = st.columns(3)
                col1.metric("Cuota Vigente", op.get("cuota"))
                col2.metric(
                    "Probabilidad Calculada",
                    f"{op.get('probabilidad_datos')}%",
                )
                col3.metric("Margen +EV", f"+{op.get('margen_ev')}%")

                st.markdown("##### 📄 Evidencias (Datos Duros)")
                st.markdown(f"- {op.get('evidencia_1')}")
                st.markdown(f"- {op.get('evidencia_2')}")
                st.markdown(f"- {op.get('evidencia_3')}")

                st.markdown("##### ⚠️ Protocolo Pre-Partido (Kill Switch)")
                st.markdown(f"* **Validar si:** {op.get('validar_si')}")
                st.markdown(f"* **Cancelar si:** {op.get('cancelar_si')}")

        with tab2:
          st.json(resultado_json.get("auditoria_9_categorias", {}))

        with tab3:
          st.markdown("### Resumen del Entorno Climático Extraído")
          st.code(info_clima, language="text")
          st.info(
              "El script buscó automáticamente la línea 'Estadio:' dentro del"
              " bloque de texto que pegaste, consultó las coordenadas y"
              " descargó el clima en tiempo real sin requerir ningún campo"
              " manual."
          )

      except Exception as e:
        st.error(f"Ocurrió un error al procesar el análisis cuantitativo: {e}")
