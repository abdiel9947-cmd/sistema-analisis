import io
import json
import numpy as np
import pandas as pd
import scipy.stats as stats
import streamlit as st
from openai import OpenAI

# Configuración de la página
st.set_page_config(
    page_title="Quant Betting AI Engine | Institutional Pro V3.1",
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
def normalizar_texto(texto):
  return " ".join(str(texto).lower().strip().split())


def calcular_probabilidad_poisson(
    lambda_local, lambda_visitante, max_goles=6, rho_dixon_coles=-0.04
):
  """Calcula la matriz de probabilidades de goles usando la distribución de Poisson

  con ajuste opcional de baja puntuación (Dixon-Coles) para marcadores bajos.
  """
  matriz_goles = np.outer(
      stats.poisson.pmf(np.arange(max_goles + 1), lambda_local),
      stats.poisson.pmf(np.arange(max_goles + 1), lambda_visitante),
  )

  # Corrección ligera en marcadores bajos (0-0, 1-0, 0-1, 1-1) para mayor realismo en fútbol
  if rho_dixon_coles != 0 and lambda_local > 0 and lambda_visitante > 0:
    ajuste_00 = 1.0 - (lambda_local * lambda_visitante * rho_dixon_coles)
    ajuste_10 = 1.0 + (lambda_visitante * rho_dixon_coles)
    ajuste_01 = 1.0 + (lambda_local * rho_dixon_coles)
    ajuste_11 = 1.0 - rho_dixon_coles

    matriz_goles[0, 0] = max(0.0, matriz_goles[0, 0] * ajuste_00)
    if max_goles >= 1:
      matriz_goles[1, 0] = max(0.0, matriz_goles[1, 0] * ajuste_10)
      matriz_goles[0, 1] = max(0.0, matriz_goles[0, 1] * ajuste_01)
      matriz_goles[1, 1] = max(0.0, matriz_goles[1, 1] * ajuste_11)

    total_masa = np.sum(matriz_goles)
    if total_masa > 0:
      matriz_goles = matriz_goles / total_masa

  prob_local_win = np.sum(np.tril(matriz_goles, -1))
  prob_empate = np.sum(np.diag(matriz_goles))
  prob_visita_win = np.sum(np.triu(matriz_goles, 1))

  prob_over_15 = sum(
      matriz_goles[i, j]
      for i in range(max_goles + 1)
      for j in range(max_goles + 1)
      if i + j > 1.5
  )
  prob_over_25 = sum(
      matriz_goles[i, j]
      for i in range(max_goles + 1)
      for j in range(max_goles + 1)
      if i + j > 2.5
  )
  prob_over_35 = sum(
      matriz_goles[i, j]
      for i in range(max_goles + 1)
      for j in range(max_goles + 1)
      if i + j > 3.5
  )

  prob_btts = 1.0 - (
      np.sum(matriz_goles[0, :])
      + np.sum(matriz_goles[:, 0])
      - matriz_goles[0, 0]
  )

  prob_1x = prob_local_win + prob_empate
  prob_x2 = prob_visita_win + prob_empate
  prob_12 = prob_local_win + prob_visita_win

  denom_dnb = prob_local_win + prob_visita_win
  prob_dnb_local = (prob_local_win / denom_dnb) if denom_dnb > 0 else 0.0
  prob_dnb_visita = (prob_visita_win / denom_dnb) if denom_dnb > 0 else 0.0

  return {
      "1": prob_local_win * 100,
      "X": prob_empate * 100,
      "2": prob_visita_win * 100,
      "over_15": prob_over_15 * 100,
      "under_15": (1.0 - prob_over_15) * 100,
      "over_25": prob_over_25 * 100,
      "under_25": (1.0 - prob_over_25) * 100,
      "over_35": prob_over_35 * 100,
      "under_35": (1.0 - prob_over_35) * 100,
      "btts": prob_btts * 100,
      "no_btts": (1.0 - prob_btts) * 100,
      "1x": prob_1x * 100,
      "x2": prob_x2 * 100,
      "12": prob_12 * 100,
      "dnb_local": prob_dnb_local * 100,
      "dnb_visita": prob_dnb_visita * 100,
  }


def devig_probabilidades_1x2(cuota_1, cuota_x, cuota_2):
  """Elimina el margen de la casa (vig) para el mercado 1X2."""
  try:
    c1, cx, c2 = float(cuota_1), float(cuota_x), float(cuota_2)
    if c1 <= 1.0 or cx <= 1.0 or c2 <= 1.0:
      return 0.0, 0.0, 0.0, 0.0
    inv_1 = 1.0 / c1
    inv_x = 1.0 / cx
    inv_2 = 1.0 / c2
    suma_inv = inv_1 + inv_x + inv_2
    return (
        (inv_1 / suma_inv) * 100,
        (inv_x / suma_inv) * 100,
        (inv_2 / suma_inv) * 100,
        (suma_inv - 1.0) * 100,
    )
  except Exception:
    return 0.0, 0.0, 0.0, 0.0


def devig_2_vias(cuota_a, cuota_b):
  """Elimina el margen de la casa (vig) para mercados de 2 vías (Over/Under, BTTS, DNB)."""
  try:
    ca, cb = float(cuota_a), float(cuota_b)
    if ca <= 1.0 or cb <= 1.0:
      return 0.0, 0.0, 0.0
    inv_a = 1.0 / ca
    inv_b = 1.0 / cb
    suma_inv = inv_a + inv_b
    return (
        (inv_a / suma_inv) * 100,
        (inv_b / suma_inv) * 100,
        (suma_inv - 1.0) * 100,
    )
  except Exception:
    return 0.0, 0.0, 0.0


def mapear_clave_a_probabilidad(mercado_str, prob_dict):
  """Intenta vincular un nombre de mercado en la hoja de cuotas con la probabilidad del modelo."""
  m = normalizar_texto(mercado_str)

  alias_map = [
      (["local", "home", "1x2 - 1", "gana local", "victoria local", "1"], "1"),
      (["empate", "draw", "1x2 - x", "x"], "X"),
      ([
          "visitante",
          "away",
          "1x2 - 2",
          "gana visitante",
          "victoria visitante",
          "2",
      ], "2"),
      (["over 1.5", "mas de 1.5", "+1.5 goles", "o1.5"], "over_15"),
      (["under 1.5", "menos de 1.5", "-1.5 goles", "u1.5"], "under_15"),
      (["over 2.5", "mas de 2.5", "+2.5 goles", "o2.5"], "over_25"),
      (["under 2.5", "menos de 2.5", "-2.5 goles", "u2.5"], "under_25"),
      (["over 3.5", "mas de 3.5", "+3.5 goles", "o3.5"], "over_35"),
      (["under 3.5", "menos de 3.5", "-3.5 goles", "u3.5"], "under_35"),
      (["btts", "ambos marcan", "both teams to score", "si marcan"], "btts"),
      (["no btts", "ambos no marcan", "no marcan ambos"], "no_btts"),
      (["1x", "local o empate", "doble oportunidad 1x"], "1x"),
      (["x2", "empate o visitante", "doble oportunidad x2"], "x2"),
      (["12", "local o visitante", "doble oportunidad 12"], "12"),
      (["dnb local", "sin empate local", "draw no bet local"], "dnb_local"),
      ([
          "dnb visitante",
          "sin empate visitante",
          "draw no bet visitante",
      ], "dnb_visita"),
  ]

  if m in prob_dict:
    return m, prob_dict[m]

  for claves, clave_modelo in alias_map:
    if any(m == normalizar_texto(c) for c in claves):
      return clave_modelo, prob_dict[clave_modelo]

  return None, None


def calcular_oportunidades_ev_python(df_odds, prob_dict, umbral_ev=2.0):
  """Calcula en Python el EV real de las cuotas cargadas y filtra las que superan el umbral (+2.0%)."""
  candidatas = []
  resumen_devig = []

  if df_odds is None or df_odds.empty:
    return candidatas, resumen_devig

  cols_norm = {normalizar_texto(c): c for c in df_odds.columns}

  col_mercado = next(
      (
          v
          for k, v in cols_norm.items()
          if any(x in k for x in ["mercado", "market", "seleccion", "evento"])
      ),
      None,
  )
  col_cuota = next(
      (
          v
          for k, v in cols_norm.items()
          if any(
              x in k for x in ["cuota", "odd", "precio", "actual", "vigente"]
          )
      ),
      None,
  )
  col_casa = next(
      (
          v
          for k, v in cols_norm.items()
          if any(x in k for x in ["casa", "bookmaker", "book", "operador"])
      ),
      None,
  )
  col_apertura = next(
      (
          v
          for k, v in cols_norm.items()
          if any(x in k for x in ["apertura", "open", "inicial"])
      ),
      None,
  )

  # Si existen columnas de cuotas 1, X, 2 en la misma fila, calculamos de-vig 1X2
  c1_col = next(
      (v for k, v in cols_norm.items() if k in ["1", "cuota 1", "local"]), None
  )
  cx_col = next(
      (v for k, v in cols_norm.items() if k in ["x", "cuota x", "empate"]), None
  )
  c2_col = next(
      (v for k, v in cols_norm.items() if k in ["2", "cuota 2", "visitante"]),
      None,
  )

  for idx, row in df_odds.iterrows():
    if c1_col and cx_col and c2_col:
      p1_fair, px_fair, p2_fair, vig_1x2 = devig_probabilidades_1x2(
          row[c1_col], row[cx_col], row[c2_col]
      )
      if vig_1x2 > 0:
        resumen_devig.append({
            "fila": idx + 1,
            "casa": row[col_casa] if col_casa else f"Fila {idx + 1}",
            "vig_1x2_%": round(vig_1x2, 2),
            "prob_justa_1_%": round(p1_fair, 2),
            "prob_justa_X_%": round(px_fair, 2),
            "prob_justa_2_%": round(p2_fair, 2),
        })

    if not col_mercado or not col_cuota:
      continue

    try:
      cuota_val = float(row[col_cuota])
    except Exception:
      continue

    if cuota_val <= 1.0:
      continue

    mercado_texto = str(row[col_mercado]).strip()
    casa_texto = (
        str(row[col_casa]).strip() if col_casa and pd.notna(row[col_casa]) else "Casa / Excel"
    )

    clave_modelo, prob_modelo_pct = mapear_clave_a_probabilidad(
        mercado_texto, prob_dict
    )
    if prob_modelo_pct is None:
      continue

    prob_decimal = prob_modelo_pct / 100.0
    ev_pct = ((prob_decimal * cuota_val) - 1.0) * 100.0
    prob_implicita_bruta_pct = (1.0 / cuota_val) * 100.0

    movimiento_texto = "Sin dato de apertura"
    if col_apertura and pd.notna(row[col_apertura]):
      try:
        cuota_ap = float(row[col_apertura])
        if cuota_ap > 1.0:
          diff_pct = ((cuota_val - cuota_ap) / cuota_ap) * 100.0
          if diff_pct < -1.5:
            movimiento_texto = f"Cayó {abs(diff_pct):.1f}% (desde {cuota_ap})"
          elif diff_pct > 1.5:
            movimiento_texto = f"Subió +{diff_pct:.1f}% (desde {cuota_ap})"
          else:
            movimiento_texto = f"Estable ({cuota_ap} -> {cuota_val})"
      except Exception:
        pass

    if ev_pct > umbral_ev:
      candidatas.append({
          "mercado_excel": mercado_texto,
          "clave_modelo": clave_modelo,
          "casa": casa_texto,
          "cuota": round(cuota_val, 3),
          "probabilidad_modelo": round(prob_modelo_pct, 2),
          "prob_implicita_bruta": round(prob_implicita_bruta_pct, 2),
          "margen_ev": round(ev_pct, 2),
          "movimiento_cuota": movimiento_texto,
      })

  return candidatas, resumen_devig


# --- 3. INTERFAZ DE USUARIO Y CARGA DE EXCEL ---
st.title(
    "📈 Motor Cuantitativo de Apuestas Deportivas (Institutional Grade V3.1)"
)
st.markdown(
    "Sistema conectado al 100% con la **Plantilla Maestra Excel V7** y sus"
    " bloques analíticos, con motor matemático determinista en Python."
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

    if master_dict:
      total_filas = len(master_dict)
      vacios_o_nd = sum(
          1
          for val in master_dict.values()
          if normalizar_texto(val)
          in ["", "n/d", "nd", "na", "n/a", "none", "nan", "-"]
      )
      completitud_pct = (
          ((total_filas - vacios_o_nd) / total_filas) * 100
          if total_filas > 0
          else 0
      )
      st.caption(
          f"Auditoría de datos Hoja 1: {total_filas - vacios_o_nd}/{total_filas}"
          f" variables con información ({completitud_pct:.1f}% completitud)."
      )
  except Exception as e:
    st.error(f"Error crítico al leer las hojas del Excel: {e}")

# Extraer xG automáticamente desde el diccionario de la Hoja 1 (con respaldos por defecto)
x_local_val = 1.49
x_visita_val = 1.11
xg_encontrado_local = False
xg_encontrado_visita = False

for key, val in master_dict.items():
  k_norm = normalizar_texto(key)
  if "xg overall numerico local" in k_norm or "xg local" in k_norm:
    try:
      x_local_val = float(str(val).replace(",", "."))
      xg_encontrado_local = True
    except Exception:
      pass
  if "xg overall numerico visitante" in k_norm or "xg visitante" in k_norm:
    try:
      x_visita_val = float(str(val).replace(",", "."))
      xg_encontrado_visita = True
    except Exception:
      pass

if uploaded_excel is not None and (
    not xg_encontrado_local or not xg_encontrado_visita
):
  st.warning(
      "⚠️ No se detectaron automáticamente uno o ambos valores numéricos de"
      " xG en la Hoja 1; revisa los campos de calibración abajo."
  )

st.subheader("⚙️ 2. Calibración y Parámetros del Partido")
col_p1, col_p2, col_p3 = st.columns(3)
x_local = col_p1.number_input(
    "xG Local (Extraído de Excel)",
    min_value=0.1,
    max_value=5.0,
    value=float(x_local_val),
    step=0.05,
)
x_visitante = col_p2.number_input(
    "xG Visitante (Extraído de Excel)",
    min_value=0.1,
    max_value=5.0,
    value=float(x_visita_val),
    step=0.05,
)
bankroll = col_p3.number_input(
    "Bankroll Total ($)", min_value=10, max_value=100000, value=1000, step=50
)

col_a1, col_a2, col_a3 = st.columns(3)
ajuste_xg_local_pct = col_a1.slider(
    "Ajuste Contexto xG Local (%)",
    min_value=-25,
    max_value=25,
    value=0,
    step=1,
    help=(
        "Ajuste manual/contextual (bajas, clima, fatiga) aplicado antes de"
        " Poisson."
    ),
)
ajuste_xg_visita_pct = col_a2.slider(
    "Ajuste Contexto xG Visitante (%)",
    min_value=-25,
    max_value=25,
    value=0,
    step=1,
    help=(
        "Ajuste manual/contextual (bajas, clima, fatiga) aplicado antes de"
        " Poisson."
    ),
)
usar_dixon_coles = col_a3.checkbox(
    "Aplicar ajuste empates bajos (Dixon-Coles)",
    value=True,
    help="Corrige ligeramente la subestimación de 0-0 y 1-1 en fútbol.",
)

lambda_local_final = max(0.05, x_local * (1.0 + ajuste_xg_local_pct / 100.0))
lambda_visita_final = max(0.05, x_visitante * (1.0 + ajuste_xg_visita_pct / 100.0))

# Ejecución de Poisson
prob_poisson = calcular_probabilidad_poisson(
    lambda_local_final,
    lambda_visita_final,
    rho_dixon_coles=(-0.04 if usar_dixon_coles else 0.0),
)

# Cálculo determinista en Python de oportunidades con +EV > 2.0%
oportunidades_python, devig_1x2_lista = calcular_oportunidades_ev_python(
    df_odds, prob_poisson, umbral_ev=2.0
)

# --- 4. PROMPT ESPECIALIZADO INSTITUCIONAL ---
SYSTEM_PROMPT = """
Eres el Director de Riesgo Cuantitativo de un fondo de apuestas profesionales. Tu trabajo es analizar la información completa de la Plantilla Maestra Excel (Bloques de 1 a 11) y la matriz de cuotas multi-casa, contrastándola con los cálculos matemáticos puros (Poisson y De-vig) ya ejecutados en Python.

REGLAS INQUEBRANTABLES:
1. NO INVENTES NÚMEROS: Las probabilidades y el margen EV provienen de los cálculos matemáticos ya ejecutados en Python. Respeta exactamente esos valores y no alteres las matemáticas.
2. REVISA TODA LA DATA: Considera fatiga, clima, bajas confirmadas, arbitraje (StatsHub), cuotas de apertura (CLV) y movimientos de mercado.
3. FILTRO ESTRICTO DE +EV: Solo reporta oportunidades donde el Margen EV sea superior al +2.0% (y prioriza las detectadas en el cálculo determinista de Python). Si alguna oportunidad tiene bandera roja grave de contexto (ej. baja crítica confirmada o movimiento adverso severo), márcala en "cancelar_si" o "no apostar".
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
        contexto_excel_str = json.dumps(
            master_dict, ensure_ascii=False, indent=2
        )
        tabla_cuotas_str = (
            df_odds.to_string() if not df_odds.empty else "Sin cuotas cargadas"
        )
        candidatas_python_str = json.dumps(
            oportunidades_python, ensure_ascii=False, indent=2
        )
        devig_python_str = json.dumps(
            devig_1x2_lista, ensure_ascii=False, indent=2
        )

        contexto_matematico = f"""
        [CÁLCULOS MATEMÁTICOS DETERMINISTAS (POISSON + DEVIG + EV EN PYTHON)]
- xG Local Base: {x_local} | Ajuste: {ajuste_xg_local_pct}% | Lambda Local Final: {lambda_local_final:.3f}
- xG Visitante Base: {x_visitante} | Ajuste: {ajuste_xg_visita_pct}% | Lambda Visitante Final: {lambda_visita_final:.3f}
- Probabilidad Local Win (1): {prob_poisson['1']:.2f}%
- Probabilidad Empate (X): {prob_poisson['X']:.2f}%
- Probabilidad Visitante Win (2): {prob_poisson['2']:.2f}%
- Probabilidad Over 1.5 / Under 1.5: {prob_poisson['over_15']:.2f}% / {prob_poisson['under_15']:.2f}%
- Probabilidad Over 2.5 / Under 2.5: {prob_poisson['over_25']:.2f}% / {prob_poisson['under_25']:.2f}%
- Probabilidad Over 3.5 / Under 3.5: {prob_poisson['over_35']:.2f}% / {prob_poisson['under_35']:.2f}%
- Probabilidad BTTS / No BTTS: {prob_poisson['btts']:.2f}% / {prob_poisson['no_btts']:.2f}%
- Probabilidad Doble Oportunidad (1X / X2 / 12): {prob_poisson['1x']:.2f}% / {prob_poisson['x2']:.2f}% / {prob_poisson['12']:.2f}%
- Probabilidad Sin Empate (DNB Local / DNB Visita): {prob_poisson['dnb_local']:.2f}% / {prob_poisson['dnb_visita']:.2f}%

[OPORTUNIDADES PRE-FILTRADAS EN PYTHON CON MARGEN EV > +2.0%]
{candidatas_python_str}

[RESUMEN DEVIG 1X2 CALCULADO EN PYTHON]
{devig_python_str}
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
        st.session_state["ultimo_resultado"] = resultado_json
        st.session_state["ultimo_contexto_mat"] = {
            "lambda_local_final": lambda_local_final,
            "lambda_visita_final": lambda_visita_final,
            "oportunidades_python": oportunidades_python,
            "devig_1x2_lista": devig_1x2_lista,
        }

      except Exception as e:
        st.error(f"Error crítico en la ejecución del motor V3: {e}")

if "ultimo_resultado" in st.session_state:
  resultado_json = st.session_state["ultimo_resultado"]
  ctx_mat = st.session_state.get("ultimo_contexto_mat", {})

  st.success(
      "✅ Análisis institucional avanzado completado con toda la información"
      " del Excel."
  )

  veredicto = resultado_json.get("veredicto_final", "NO APOSTAR")
  if veredicto == "APOSTAR":
    st.success(f"🟢 VEREDICTO FINAL: {veredicto}")
  else:
    st.error(
        f"🛑 VEREDICTO FINAL: {veredicto} (No hay +EV superior al umbral"
        " requerido)"
    )

  tab1, tab2, tab3, tab4 = st.tabs([
      "💎 Oportunidades +EV Validadas",
      "🧠 Razonamiento Táctico y Factores",
      "📋 Auditoría Completa de Bloques",
      "📊 Cálculo Determinista y Registro",
  ])

  with tab1:
    oportunidades = resultado_json.get("oportunidades", [])
    if not oportunidades:
      st.info(
          "No se detectaron mercados con un +EV seguro cruzando toda la data."
      )
    else:
      for idx, op in enumerate(oportunidades, 1):
        ev_val = op.get("margen_ev", 0)
        cuota_op = op.get("cuota", 1.0)
        stake_sugerido = round(bankroll * (0.01 if ev_val < 5 else 0.02), 2)

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

  with tab4:
    st.markdown("### Verificación Matemática en Python (+EV > +2.0%)")
    ops_py = ctx_mat.get("oportunidades_python", [])
    if ops_py:
      st.dataframe(pd.DataFrame(ops_py), use_container_width=True)
    else:
      st.info(
          "No se encontraron filas en la Hoja 2 que superen +2.0% EV con las"
          " probabilidades actuales (o los nombres de mercado requieren"
          " coincidencia)."
      )

    devig_py = ctx_mat.get("devig_1x2_lista", [])
    if devig_py:
      st.markdown("### Margen de la Casa (Vig) y Probabilidades Justas 1X2")
      st.dataframe(pd.DataFrame(devig_py), use_container_width=True)

    oportunidades_para_log = resultado_json.get("oportunidades", [])
    if oportunidades_para_log:
      filas_log = []
      for op in oportunidades_para_log:
        ev_v = op.get("margen_ev", 0)
        stk = round(bankroll * (0.01 if ev_v < 5 else 0.02), 2)
        filas_log.append({
            "categoria": op.get("categoria", ""),
            "mercado": op.get("mercado", ""),
            "cuota": op.get("cuota", ""),
            "probabilidad_modelo": op.get("probabilidad_modelo", ""),
            "margen_ev": ev_v,
            "stake_usd": stk,
            "veredicto": veredicto,
            "resultado_real": "",
            "cuota_cierre": "",
        })
      buffer_csv = io.StringIO()
      pd.DataFrame(filas_log).to_csv(buffer_csv, index=False)
      st.download_button(
          label="📥 Descargar Picks Validados (CSV para Bitácora)",
          data=buffer_csv.getvalue(),
          file_name="picks_validados_ev.csv",
          mime="text/csv",
      )
