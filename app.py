import json
import streamlit as st
from google import genai

# Configuración de la página
st.set_page_config(
    page_title="Quant Betting AI System", page_icon="📈", layout="wide"
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

# --- 2. INTERFAZ PRINCIPAL ---
st.title("📈 Sistema Cuantitativo de Apuestas Deportivas (+EV)")
st.markdown(
    "Pega el resumen consolidado del partido para realizar la auditoría matemática y de 9 categorías."
)

texto_partido = st.text_area(
    "Pega aquí los datos del partido (Estadísticas, H2H, Cuotas, etc.):",
    height=250,
    placeholder="Pega el texto aquí...",
)

# Prompt Maestro integrado como System Instructions para la IA
SYSTEM_PROMPT = """
Actúa como un Analista Cuantitativo Profesional de Apuestas Deportivas (Quant). Tu único objetivo es preservar el capital y encontrar Valor Esperado Positivo (+EV) matemáticamente demostrable. Tu tolerancia al riesgo es extremadamente baja.

Analiza EXCLUSIVAMENTE los datos numéricos del texto proporcionado. PROHIBIDO usar conocimiento general, narrativas de "motivación", o inventar datos. Si un dato no está en el texto, el mercado correspondiente se descarta inmediatamente.

Debes devolver la respuesta ÚNICAMENTE en formato JSON válido (sin bloques de texto extra markdown fuera del JSON si es posible, o asegúrate de que sea un JSON parseable) con esta estructura exacta:

{
  "auditoria_9_categorias": {
    "1_Principales": "DATOS SUFICIENTES" o "DATOS INSUFICIENTES EN PDF. MERCADO DESCARTADO",
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
      "mercado": "Nombre del mercado con +EV > 5%",
      "cuota": 0.0,
      "probabilidad_datos": 0.0,
      "margen_ev": 0.0,
      "evidencia_1": "Cita textual 1 con datos duros",
      "evidencia_2": "Cita textual 2 con datos duros",
      "evidencia_3": "Cita textual 3 con datos duros",
      "validar_si": "Condición exacta pre-partido",
      "cancelar_si": "Condición exacta para cancelar"
    }
  ],
  "veredicto_final": "APOSTAR" o "NO APOSTAR",
  "mensaje_preservacion": "Stake Fijo: 1% del Bankroll o mensaje de preservación si no hay valor."
}

REGLAS INQUEBRANTABLES:
1. Cero Alucinaciones: Si dice "PREMIUM" o "UNLOCK", asume que el dato NO ESTÁ DISPONIBLE y descártalo.
2. Si no hay ningún mercado con +EV > 5%, la lista 'oportunidades' debe ser [] y 'veredicto_final' debe ser "NO APOSTAR".
3. Todos los valores numéricos de cuota, probabilidad y margen DEBEN ser float (números), no texto.
"""

if st.button("Ejecutar Análisis Cuantitativo"):
  if not texto_partido.strip():
    st.warning("Por favor, pega los datos del partido antes de analizar.")
  else:
    with st.spinner(
        "Analizando datos numéricos y calculando Valor Esperado..."
    ):
      try:
        # Inicializar el cliente oficial de Google GenAI usando la API key de los secretos
        client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

        # Llamada al modelo más estable y rápido para texto y JSON estructurado
        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=f"Analiza el siguiente texto de un partido:\n\n{texto_partido}",
            config={
                "system_instruction": SYSTEM_PROMPT,
                "response_mime_type": "application/json",
            },
        )

        # Parsear el JSON devuelto
        resultado_json = json.loads(response.text)

        st.success("¡Análisis completado con éxito!")

        # Mostrar Veredicto Final
        veredicto = resultado_json.get("veredicto_final", "NO APOSTAR")
        if veredicto == "APOSTAR":
          st.error(f"🟢 VEREDICTO: {veredicto}")
        else:
          st.warning(f"🛑 VEREDICTO: {veredicto}")

        st.info(
            f"**Gestión de Bankroll / Mensaje:** {resultado_json.get('mensaje_preservacion', '')}"
        )

        # Pestañas para organizar la visualización
        tab1, tab2 = st.tabs(
            ["📊 Oportunidades +EV", "📋 Auditoría de 9 Categorías"]
        )

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
                  f"Oportunidad {idx}: {op.get('mercado')} (+{op.get('margen_ev')}%"
                  " EV)"
              ):
                col1, col2, col3 = st.columns(3)
                col1.metric("Cuota", op.get("cuota"))
                col2.metric("Probabilidad Real", f"{op.get('probabilidad_datos')}%")
                col3.metric("Margen +EV", f"+{op.get('margen_ev')}%")

                st.markdown("##### 📄 Evidencias (Datos Duros)")
                st.markdown(f"- {op.get('evidencia_1')}")
                st.markdown(f"- {op.get('evidencia_2')}")
                st.markdown(f"- {op.get('evidencia_3')}")

                st.markdown("##### ⚠️ Regla Pre-Partido (Kill Switch)")
                st.markdown(f"* **Validar si:** {op.get('validar_si')}")
                st.markdown(f"* **Cancelar si:** {op.get('cancelar_si')}")

        with tab2:
          st.json(resultado_json.get("auditoria_9_categorias", {}))

      except Exception as e:
        st.error(f"Ocurrió un error al procesar con la IA: {e}")
