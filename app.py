import json
import numpy as np
import pandas as pd
import requests
import scipy.stats as stats
import streamlit as st
from openai import OpenAI

# Configuración de la página
st.set_page_config(
    page_title="Quant Betting AI Engine | Institutional Pro",
    page_icon="📈",
    layout="wide",
)

# --- 1. SEGURIDAD Y AUTENTICACIÓN ---
if "authenticated" not in st.session_state:
  st.session_state.authenticated = False

if not st.session_state.authenticated:
  st.title("🔒 Acceso Restringido - Sistema Quant Master")
  password_input = st.text_input("Introduce la contraseña:", type="password")
  if st.button("Ingresar"):
    if password_input == st.secrets.get("APP_PASSWORD", "admin123"):
      st.session_state.authenticated = True
      st.rerun()
    else:
      st.error("Contraseña incorrecta.")
  st.stop()


# --- 2. FUNCIONES MATEMÁTICAS Y DE MODELADO (PYTHON PURITO) ---
def calcular_probabilidad_poisson(lambda_local, lambda_visitante, max_goles=6):
  """Calcula la matriz de probabilidades de goles usando la distribución de Poisson."""
  matriz_goles = np.outer(
      stats.poisson.pmf(np.arange(max_goles + 1), lambda_local),
      stats.poisson.pmf(np.arange(max_goles + 1), lambda_visitante),
  )

  prob_local_win = np.sum(np.tril(matriz_goles, -1))
  prob_empate = np.sum(np.diag(matriz_goles))
  prob_visita_win = np.sum(np.triu(matriz_goles, 1))

  prob_over_25 = np.sum(
      [
          matriz_goles[i, j]
          for i in range(max_goles + 1)
          for j in range(max_goles + 1)
          if i + j > 2.5
      ]
  )
  prob_btts = 1.0 - (
      np.sum(matriz_goles[0, :])
      + np.sum(matriz_goles[:, 0])
      - matriz_goles[0, 0]
  )

  return {
      "1": prob_local_win * 100,
      "X": prob_empate * 100,
      "2": prob_visita_win * 100,
      "over_25": prob_over_25 * 100,
      "btts": prob_btts * 100,
  }


def devig_probabilidades(cuota_1, cuota_x, cuota_2):
  """Elimina el margen de la casa (vig) para calcular probabilidades reales de mercado."""
  inv_1 = 1.0 / cuota_1
  inv_x = 1.0 / cuota_x
  inv_2 = 1.0 / cuota_2
  suma_inv = inv_1 + inv_x + inv_2
  return (inv_1 / suma_inv) * 100, (inv_x / suma_inv) * 100, (inv_2 / suma_inv) * 100


def calcular_ev(prob_real_pct, cuota):
  """Calcula el Valor Esperado Positivo (+EV) matemático."""
  p = prob_real_pct / 100.0
  ev = ((p * cuota) - 1.0) * 100.0
  return round(ev, 2)


# --- 3. INTERFAZ DE USUARIO ---
st.title("📈 Motor Cuantitativo de Apuestas Deportivas (Institutional Grade)")
st.markdown(
    "Sistema impulsado por **Modelos Matemáticos Deterministas (Poisson /"
    " De-vig)** y validación cognitiva por IA."
)

st.subheader("📂 1. Carga tu Plantilla Maestra Excel (.xlsx)")
uploaded_excel = st.file_uploader(
    "Sube el archivo Excel con los datos consolidados del partido:",
    type=["xlsx"],
)

datos_excel_resumen = ""
if uploaded_excel is not None:
  try:
    xls = pd.ExcelFile(uploaded_excel)
    resumen_partido = []
    for sheet in xls.sheet_names:
      df = pd.read_excel(xls, sheet_name=sheet)
      resumen_partido.append(f"--- PESTAÑA: {sheet} ---")
      for _, row in df.iterrows():
        row_str = " | ".join([str(v) for v in row.values if pd.notna(v)])
        if row_str.strip():
          resumen_partido.append(row_str)
    datos_excel_resumen = "\n".join(resumen_partido)
    st.success(
        f"✅ Plantilla leída correctamente ({len(xls.sheet_names)} pestañas"
        " procesadas)."
    )
  except Exception as e:
    st.error(f"Error al procesar el Excel: {e}")

# Parámetros configurables por el usuario para el modelo matemático
st.subheader("⚙️ 2. Calibración del Modelo xG (Poisson)")
col_p1, col_p2, col_p3 = st.columns(3)
x_local = col_p1.number_input(
    "xG Esperado Local", min_value=0.1, max_value=5.0, value=1.49, step=0.05
)
x_visitante = col_p2.number_input(
    "xG Esperado Visitante", min_value=0.1, max_value=5.0, value=1.11, step=0.05
)
bankroll = col_p3.number_input(
    "Bankroll Total ($)", min_value=10, max_value=100000, value=1000, step=50
)

# Ejecución de cálculos deterministas en Python
prob_poisson = calcular_probabilidad_poisson(x_local, x_visitante)

# --- 4. PROMPT INSTITUCIONAL RIGUROSO PARA LA IA ---
SYSTEM_PROMPT = """
Eres el Director de Riesgo Cuantitativo de un fondo de apuestas profesionales. Tu trabajo es analizar el informe tabular generado de la Plantilla Maestra Excel y contrastarlo con los cálculos matemáticos puros (Poisson y De-vig) proporcionados en el sistema.

REGLAS INQUEBRANTABLES:
1. NO INVENTES NÚMEROS: Las probabilidades base provienen de modelos matemáticos exactos incrustados en el software.
2. ESCANEA LAS 9 CATEGORÍAS: Principales, Goles, Jugadores, Disciplina, Corners, Mitades, Stats Avanzadas, Asiáticos y Especiales.
3. FILTRO ESTRICTO DE +EV: Solo reporta oportunidades donde el Margen EV sea superior al +2.0%. Si no hay valor, indícalo claramente.
4. FORMATO ESTRICTO JSON: Devuelve exclusivamente un objeto JSON válido con la estructura solicitada.

ESTRUCTURA JSON OBLIGATORIA:
{
  "analisis_previo": "Razonamiento táctico y macro de 4 líneas cruzando xG, árbitro y clima.",
  "auditoria_9_categorias": {
    "1_Principales": "Evaluación analítica...",
    "2_Goles": "Evaluación analítica...",
    "3_Jugadores": "Evaluación analítica...",
    "4_Disciplina": "Evaluación analítica...",
    "5_Corners": "Evaluación analítica...",
    "6_Mitades": "Evaluación analítica...",
    "7_Stats_Avanzadas": "Evaluación analítica...",
    "8_Asiaticos": "Evaluación analítica...",
    "9_Especiales": "Evaluación analítica..."
  },
  "oportunidades": [
    {
      "categoria": "Goles / Corners / etc.",
      "mercado": "Nombre exacto del mercado y casa",
      "cuota": 1.94,
      "probabilidad_modelo": 54.5,
      "margen_ev": 5.73,
      "evidencia_1": "Dato duro de la plantilla Excel",
      "evidencia_2": "Dato duro de la plantilla Excel",
      "validar_si": "Condición pre-partido",
      "cancelar_si": "Kill switch"
    }
  ],
  "veredicto_final": "APOSTAR" o "NO APOSTAR",
  "recomendacion_stake": "1% al 2% del Bankroll."
}
"""

if st.button("🚀 Ejecutar Motor Cuantitativo Institucional"):
  if not uploaded_excel or not datos_excel_resumen.strip():
    st.warning("Por favor, sube tu archivo Excel maestro.")
  else:
    with st.spinner(
        "Calculando matrices de Poisson, des-margen de cuotas y escaneando"
        " mercados con gpt-4o..."
    ):
      try:
        # Inyectar resultados matemáticos duros al contexto de la IA
        contexto_matematico = f"""
        [CÁLCULOS MATEMÁTICOS DETERMINISTAS (POISSON)]
        - xG Local: {x_local} | xG Visitante: {x_visitante}
        - Probabilidad Local Win (Poisson): {prob_poisson['1']:.2f}%
        - Probabilidad Empate (Poisson): {prob_poisson['X']:.2f}%
        - Probabilidad Visitante Win (Poisson): {prob_poisson['2']:.2f}%
        - Probabilidad Over 2.5 Goles (Poisson): {prob_poisson['over_25']:.2f}%
        - Probabilidad BTTS (Poisson): {prob_poisson['btts']:.2f}%
        """

        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        contexto_matematico
                        + "\n\n[DATOS DE LA PLANTILLA MAESTRA EXCEL]\n"
                        + datos_excel_resumen
                    ),
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        resultado_json = json.loads(response.choices[0].message.content)
        st.success("✅ Análisis institucional completado con éxito.")

        veredicto = resultado_json.get("veredicto_final", "NO APOSTAR")
        if veredicto == "APOSTAR":
          st.success(f"🟢 VEREDICTO FINAL: {veredicto}")
        else:
          st.error(
              f"🛑 VEREDICTO FINAL: {veredicto} (No hay +EV superior al umbral"
              " requerido)"
          )

        # Mostrar Pestañas de Resultados
        tab1, tab2, tab3 = st.tabs([
            "💎 Oportunidades +EV Validadas",
            "🧠 Razonamiento Táctico (IA)",
            "📋 Auditoría de 9 Categorías",
        ])

        with tab1:
          oportunidades = resultado_json.get("oportunidades", [])
          if not oportunidades:
            st.info(
                "No se detectaron mercados con un +EV seguro. Proteger el capital"
                " es la jugada óptima."
            )
          else:
            for idx, op in enumerate(oportunidades, 1):
              ev_val = op.get("margen_ev", 0)
              cuota_op = op.get("cuota", 1.0)
              stake_sugerido = round(
                  bankroll * (0.01 if ev_val < 5 else 0.02), 2
              )

              with st.expander(
                  f"Oportunidad {idx}: {op.get('mercado')} (+{ev_val}% EV)"
              ):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Cuota Vigente", cuota_op)
                c2.metric("Prob. Modelo", f"{op.get('probabilidad_modelo')}%")
                c3.metric("Margen +EV", f"+{ev_val}%")
                c4.metric(
                    "Stake Sugerido",
                    f"${stake_sugerido} ({1 if ev_val < 5 else 2}%)",
                )

                st.markdown("##### 📄 Evidencias del Excel")
                st.markdown(f"- 1️⃣ {op.get('evidencia_1')}")
                st.markdown(f"- 2️⃣ {op.get('evidencia_2')}")

                st.markdown("##### ⚠️ Protocolo Pre-Partido (Kill Switch)")
                st.markdown(f"* **Validar:** {op.get('validar_si')}")
                st.markdown(f"* **Cancelar si:** {op.get('cancelar_si')}")

        with tab2:
          st.markdown("### Razonamiento Institucional")
          st.markdown(resultado_json.get("analisis_previo", ""))

        with tab3:
          st.json(resultado_json.get("auditoria_9_categorias", {}))

      except Exception as e:
        st.error(f"Error crítico en la ejecución del motor: {e}")
