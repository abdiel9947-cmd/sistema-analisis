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


# --- FUNCIÓN DE CLIMA AUTOMÁTICO (Con Diccionario de Estadios y Fallback) ---
def obtener_clima_estadio(nombre_estadio):
  try:
    # Diccionario de respaldo para estadios clave en Colombia y evitar confusiones geográficas
    diccionario_estadios = {
        "alfonso lópez": "Bucaramanga",
        "atanasio girardot": "Medellin",
        "el campín": "Bogota",
        "metropolitano": "Barranquilla",
        "pascual guerrero": "Cali",
        "palogrande": "Manizales",
        "centenario": "Armenia",
        "manuel murillo toro": "Ibagué",
        "romelio martínez": "Barranquilla",
    }

    nombre_lower = nombre_estadio.lower().strip()
    lugar_busqueda = None

    for est, ciudad in diccionario_estadios.items():
      if est in nombre_lower:
        lugar_busqueda = ciudad
        break

    if not lugar_busqueda:
      # Limpieza estándar si no está en el diccionario
      lugar_busqueda = (
          nombre_estadio.replace("Estadio", "")
          .replace("Stadium", "")
          .split("(")[0]
          .strip()
      )
      if not lugar_busqueda:
        lugar_busqueda = "Medellin"

    geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={requests.utils.quote(lugar_busqueda)}&count=1&language=es&format=json"
    geo_resp = requests.get(geo_url, timeout=5).json()

    if "results" not in geo_resp or not geo_resp["results"]:
      # Fallback de seguridad definitivo
      geo_url_alt = (
          "https://geocoding-api.open-meteo.com/v1/search?name=Bucaramanga&count=1&language=es&format=json"
      )
      geo_resp = requests.get(geo_url_alt, timeout=5).json()

    if "results" not in geo_resp or not geo_resp["results"]:
      return f"Clima: No se pudo geolocalizar automáticamente la ubicación de '{nombre_estadio}'."

    lat = geo_resp["results"][0]["latitude"]
    lon = geo_resp["results"][0]["longitude"]
    nombre_lugar = geo_resp["results"][0].get("name", lugar_busqueda)
    pais = geo_resp["results"][0].get("country", "")

    weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m&timezone=auto"
    w_resp = requests.get(weather_url, timeout=5).json()

    if "current" in w_resp:
      curr = w_resp["current"]
      temp = curr.get("temperature_2m", "N/D")
      hum = curr.get("relative_humidity_2m", "N/D")
      prec = curr.get("precipitation", "N/D")
      wind = curr.get("wind_speed_10m", "N/D")

      return (
          f"Ubicación Geolocalizada: {nombre_lugar}, {pais} (Lat: {lat},"
          f" Lon: {lon}) | Temperatura: {temp}°C | Humedad: {hum}% | Precipitación:"
          f" {prec} mm | Viento: {wind} km/h"
      )
    else:
      return "Clima: Datos meteorológicos no disponibles temporalmente."
  except Exception as e:
    return f"Clima: Error al consultar el servicio meteorológico ({e})."


# --- 2. INTERFAZ PRINCIPAL ---
st.title("📈 Sistema Cuantitativo de Apuestas Deportivas (+EV Blindado)")
st.markdown(
    "Motor cuantitativo optimizado con **gpt-4o** (Temperatura 0.1) y validación"
    " matemática estricta."
)

texto_partido = st.text_area(
    "Pega aquí todo el consolidado de datos (FootyStats, StatsHub y cuotas de"
    " casas de apuestas):",
    height=360,
    placeholder=(
        "Pega aquí las estadísticas macro, el árbitro y los bloques de cuotas..."
    ),
)

SYSTEM_PROMPT = """
Actúa como un Analista Cuantitativo Profesional de Apuestas Deportivas (Quant) de nivel institucional. Tu objetivo es cruzar rigurosamente las estadísticas macro con las cuotas reales de múltiples casas de apuestas para detectar ineficiencias matemáticas reales de Valor Esperado Positivo (+EV).

Analiza estrictamente:
1. Datos meteorológicos automáticos integrados en el entorno.
2. Estadísticas macro de FootyStats (xG, xGA, PPG, tendencias All/Home/Away).
3. Perfil disciplinario y arbitral de StatsHub.
4. Cuotas detalladas de las casas de apuestas provistas en el texto.

REGLAS DE ORO INQUEBRANTABLES:
1. Cero Alucinaciones / Temperatura 0.1: Utiliza exclusivamente los datos provistos. Si un dato no aparece, descártalo.
2. Fórmula Matemática Obligatoria de +EV: NO adivines ni estimes porcentajes. Tienes la obligación matemática de calcular el margen de valor usando la fórmula exacta:
   [Margen +EV (%)] = ((Probabilidad Calculada * Cuota Vigente) - 1) * 100
   Ejemplo: Si la probabilidad calculada es 0.60 (60%) y la cuota es 1.80: (0.60 * 1.80 - 1) * 100 = +8.0% de EV.
3. Coherencia Cruzada de Apuestas: Bajo ninguna circunstancia recomiendes mercados mutuamente contradictorios en el mismo análisis (por ejemplo, no puedes recomendar un hándicap pesado como -1.5 y al mismo tiempo un 'Menos de 2.5 goles' a menos que el perfil exacto del partido lo justifique matemáticamente de forma impecable).
4. Filtro de Umbral: 
   - Valor Moderado: +EV del 2.0% al 4.9%.
   - Valor Alto: +EV > 5.0%.
   - Si ningún mercado supera el 2.0% real aplicando la fórmula, la lista 'oportunidades' debe ser obligatoriamente [] y el veredicto final "NO APOSTAR".
5. Formato Estricto: Devuelve la respuesta ÚNICAMENTE en formato JSON válido con la estructura exacta solicitada.

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
      "mercado": "Nombre exacto del mercado y casa (ej. Atlético Bucaramanga Más de 1.5 Goles - Betano @1.72)",
      "cuota": 0.0,
      "probabilidad_datos": 0.0,
      "margen_ev": 0.0,
      "evidencia_1": "Cita textual 1 con datos duros",
      "evidencia_2": "Cita textual 2 con datos duros",
      "evidencia_3": "Cita textual 3 con datos duros",
      "validar_si": "Condición pre-partido exacta",
      "cancelar_si": "Condición exacta para cancelar apuesta"
    }
  ],
  "veredicto_final": "APOSTAR" o "NO APOSTAR",
  "mensaje_preservacion": "Stake Fijo: 1% al 2% del Bankroll según nivel de +EV."
}
"""

if st.button("Ejecutar Análisis Cuantitativo Blindado (GPT-4o)"):
  if not texto_partido.strip():
    st.warning("Por favor, pega los datos consolidados del partido.")
  else:
    with st.spinner(
        "Extrayendo estadio, consultando clima exacto y procesando con"
        " fórmulas matemáticas (gpt-4o)..."
    ):
      try:
        estadio_detectado = ""
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
              " en el texto pegado.\n"
          )

        input_total = (
            info_clima
            + "\n\n[DATOS CONSOLIDADOS Y CUOTAS MULTI-CASA]\n"
            + texto_partido
        )

        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": input_total},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
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
            "📊 Oportunidades +EV Detectadas",
            "📋 Auditoría de 9 Categorías",
            "🌦️ Clima Detectado",
        ])

        with tab1:
          oportunidades = resultado_json.get("oportunidades", [])
          if not oportunidades:
            st.info(
                "No se encontraron mercados con un +EV superior al 2%. Se"
                " recomienda preservar el capital."
            )
          else:
            for idx, op in enumerate(oportunidades, 1):
              with st.expander(
                  f"Oportunidad {idx}: {op.get('mercado')} (+{op.get('margen_ev')}%"
                  " EV)"
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

      except Exception as e:
        st.error(f"Ocurrió un error al procesar el análisis cuantitativo: {e}")
