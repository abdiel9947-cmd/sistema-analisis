import json
import numpy as np
import pandas as pd
import scipy.stats as stats
import streamlit as st
from openai import OpenAI

# Configuración de la página
st.set_page_config(
    page_title="Quant Betting AI Engine | Institutional Pro V3",
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


# --- 2. FUNCIONES MATEMÁTICAS Y DE MODELADO INSTITUCIONAL ---
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


def devig_probabilidades_1x2(cuota_1, cuota_x, cuota_2):
  """Elimina el margen de la casa (vig) para el mercado 1X2."""
  try:
    inv_1 = 1.0 / float(cuota_1)
    inv_x = 1.0 / float(cuota_x)
    inv_2 = 1.0 / float(cuota_2)
    suma_inv = inv_1 + inv_x + inv_2
    return (
        (inv_1 / suma_inv) * 100,
        (inv_x / suma_inv) * 100,
        (inv_2 / suma_inv) * 100,
        (suma_inv - 1.0) * 100,
    )  # Retorna probabilidades reales y el Payout/Vig
  except:
    return 0.0, 0.0, 0.0, 0.0


# --- 3. INTERFAZ DE USUARIO Y CARGA DE EXCEL ---
st.title(
    "📈 Motor Cuantitativo de Apuestas Deportivas (Institutional Grade V3)"
)
st.markdown(
    "Sistema conectado al 100% con la **Plantilla Maestra Excel V7** y sus"
    " bloques analíticos."
)

st.subheader("📂 1. Carga tu Plantilla Maestra Excel (.xlsx)")
uploaded_excel = st.file_uploader(
    "Sube el archivo Excel con las dos hojas estructuradas:", type=["xlsx"]
)

master_dict = {}
df_odds = pd.DataFrame()

if uploaded_excel is not None:
  try:
    xls = pd.ExcelFile(uploaded_excel)

    # Procesar Hoja 1: Analisis_Cuantitativo_Master
    if "Analisis_Cuantitativo_Master" in xls.sheet_names:
      df_master = pd.read_excel(xls, sheet_name="Analisis_Cuantitativo_Master")
      # Mapear Columna 0 (Variable) a Columna 1 (Valor)
      for _, row in df_master.iterrows():
        k = str(row.iloc[0]).strip()
        v = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else "N/D"
        if k and k != "nan":
          master_dict[k] = v

    # Procesar Hoja 2: Comparativa_Cuotas_Casas
    if "Comparativa_Cuotas_Casas" in xls.sheet_names:
      df_odds = pd.read_excel(xls, sheet_name="Comparativa_Cuotas_Casas")

    st.success(
        "✅ Plantilla leída con éxito: Hojas procesadas y mapeadas"
        " perfectamente."
    )
  except Exception as e:
    st.error(f"Error crítico al leer las hojas del Excel: {e}")

# Extraer xG automáticamente desde el diccionario de la Hoja 1 (con respaldos por defecto)
x_local_val = 1.49
x_visita_val = 1.11

for key, val in master_dict.items():
  if "xG Overall Numérico Local" in key:
    try:
      x_local_val = float(val)
    except:
      pass
  if "xG Overall Numérico Visitante" in key:
    try:
      x_visita_val = float(val)
    except:
      pass

st.subheader("⚙️ 2. Calibración y Parámetros del Partido")
col_p1, col_p2, col_p3 = st.columns(3)
x_local = col_p1.number_input(
    "xG Local (Extraído de Excel)",
    min_value=0.1,
    max_value=5.0,
    value=x_local_val,
    step=0.05,
)
x_visitante = col_p2.number_input(
    "xG Visitante (Extraído de Excel)",
    min_value=0.1,
    max_value=5.0,
    value=x_visita_val,
    step=0.05,
)
bankroll = col_p3.number_input(
    "Bankroll Total ($)", min_value=10, max_value=100000, value=1000, step=50
)

# Ejecución de Poisson
prob_poisson = calcular_probabilidad_poisson(x_local, x_visitante)

# --- 4. PROMPT ESPECIALIZADO INSTITUCIONAL ---
SYSTEM_PROMPT = """
Eres el Director de Riesgo Cuantitativo de un fondo de apuestas profesionales. Tu trabajo es analizar la información completa de la Plantilla Maestra Excel (Bloques de 1 a 11) y la matriz de cuotas multi-casa, contrastándola con los cálculos matemáticos puros (Poisson y De-vig).

REGLAS INQUEBRANTABLES:
1. NO INVENTES NÚMEROS: Las probabilidades base provienen de modelos matemáticos exactos incrustados en el software.
2. REVISA TODA LA DATA: Considera fatiga, clima, bajas confirmadas, arbitraje (StatsHub) y cuotas de apertura (CLV).
3. FILTRO ESTRICTO DE +EV: Solo reporta oportunidades donde el Margen EV sea superior al +2.0%.
4. FORMATO ESTRICTO JSON: Devuelve exclusivamente un objeto JSON válido con la estructura solicitada.

ESTRUCTURA JSON OBLIGATORIA:
{
  "analisis_previo": "Razonamiento táctico y macro cruzando xG, clima, árbitro, bajas y fatiga.",
  "auditoria_bloques": {
    "contexto_y_clima": "Evaluación...",
    "disciplina_arbitro": "Evaluación...",
    "rendimiento_y_h2h": "Evaluación..."
  },
  "oportunidades": [
    {
      "categoria": "Goles / Córners / 1X2 / etc.",
      "mercado": "Nombre exacto del mercado y casa",
      "cuota": 1.94,
      "probabilidad_modelo": 54.5,
      "margen_ev": 5.73,
      "evidencia_1": "Dato duro del Excel (ej. xG o Stats de arbitraje)",
      "evidencia_2": "Dato duro del Excel (ej. Bajas o fatiga)",
      "validar_si": "Condición pre-partido",
      "cancelar_si": "Kill switch"
    }
  ],
  "veredicto_final": "APOSTAR" o "NO APOSTAR",
  "recomendacion_stake": "1% al 2% del Bankroll."
}
"""

if st.button("🚀 Ejecutar Motor Cuantitativo Institucional V3"):
  if not uploaded_excel or not master_dict:
    st.warning("Por favor, sube tu archivo Excel maestro V7.")
  else:
    with st.spinner(
        "Procesando las 150 filas del Excel, matrices de cuotas y modelos con"
        " gpt-4o..."
    ):
      try:
        # Serializar todo el diccionario de la Hoja 1 y la tabla de la Hoja 2 en texto estructurado
        contexto_excel_str = json.dumps(master_dict, ensure_ascii=False, indent=2)
        tabla_cuotas_str = (
            df_odds.to_string() if not df_odds.empty else "Sin cuotas cargadas"
        )

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
                        + "\n\n[HOJA 1: ANALISIS_CUANTITATIVO_MASTER]\n"
                        + contexto_excel_str
                        + "\n\n[HOJA 2: COMPARATIVA_CUOTAS_CASAS]\n"
                        + tabla_cuotas_str
                    ),
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        resultado_json = json.loads(response.choices[0].message.content)
        st.success(
            "✅ Análisis institucional avanzado completado con toda la"
            " información del Excel."
        )

        veredicto = resultado_json.get("veredicto_final", "NO APOSTAR")
        if veredicto == "APOSTAR":
          st.success(f"🟢 VEREDICTO FINAL: {veredicto}")
        else:
          st.error(
              f"🛑 VEREDICTO FINAL: {veredicto} (No hay +EV superior al umbral"
              " requerido)"
          )

        tab1, tab2, tab3 = st.tabs([
            "💎 Oportunidades +EV Validadas",
            "🧠 Razonamiento Táctico y Factores",
            "📋 Auditoría Completa de Bloques",
        ])

        with tab1:
          oportunidades = resultado_json.get("oportunidades", [])
          if not oportunidades:
            st.info(
                "No se detectaron mercados con un +EV seguro cruzando toda la"
                " data."
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
          st.json(resultado_json.get("auditoria_bloques", {}))

      except Exception as e:
        st.error(f"Error crítico en la ejecución del motor V3: {e}")
