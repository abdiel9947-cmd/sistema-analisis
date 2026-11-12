import streamlit as st
import google.generativeai as genai
import json

# ==============================================================================
# 1. INTERFAZ
# ==============================================================================
st.set_page_config(page_title="Sistema Interno de Análisis Cuantitativo", page_icon="📊", layout="centered")

st.sidebar.title("🔒 Acceso Restringido")
access_code = st.sidebar.text_input("Ingrese código de operador:", type="password")

if access_code != "CLAVE123":
    st.warning("Acceso denegado.")
    st.stop()

st.title("📊 Panel de Procesamiento de Datos Deportivos")
st.markdown("**Instrucciones:** Copie el texto de las páginas web de estadísticas y cuotas, y péguelo en los campos correspondientes. El sistema calculará el Valor Esperado (+EV) de forma automática.")
st.markdown("---")

# ==============================================================================
# 2. PROMPT (SOLO EXTRACCIÓN, SIN CÁLCULOS)
# ==============================================================================
SYSTEM_PROMPT = """Eres un extractor de datos cuantitativos. Tu ÚNICA tarea es leer los textos adjuntos y devolver un objeto JSON válido. NO calcules nada, NO inventes datos, NO agregues texto fuera del JSON.

Busca en los datos de estadísticas la probabilidad histórica o frecuencia de un evento (ej: "Over 2.5 goles: 65%").
Busca en los datos de cuotas la cuota decimal de ese mismo mercado (ej: "1.85").

Devuelve EXCLUSIVAMENTE este formato JSON (sin bloques de código markdown, solo el JSON puro):
{
  "mercado": "Nombre exacto del mercado",
  "cuota": 1.85,
  "probabilidad_pdf": 65.0,
  "evidencia_1": "Cita textual exacta del texto de estadísticas con el número",
  "evidencia_2": "Segunda cita textual exacta",
  "evidencia_3": "Tercera cita textual exacta",
  "validar_si": "Condición pre-partido para validar",
  "cancelar_si": "Condición pre-partido para cancelar"
}

REGLAS ABSOLUTAS:
1. Si no encuentras una cuota clara, devuelve: {"error": "No se encontraron cuotas válidas en los datos."}
2. Si no encuentras datos estadísticos, devuelve: {"error": "Datos estadísticos insuficientes."}
3. Los valores de 'cuota' y 'probabilidad_pdf' DEBEN ser números (float), no texto.
"""

# ==============================================================================
# 3. FORMULARIO DE TEXTO (SIN PDFs)
# ==============================================================================
st.subheader("1. Datos de Estadísticas del Partido")
st.markdown("Copie el texto de la página web (Flashscore, Sofascore, etc.) y péguelo aquí:")
stats_text = st.text_area("Texto de estadísticas:", height=200, placeholder="Ej: Real Madrid vs Barcelona\nOver 2.5 Goles: 72%\nBTTS: 68%\nTiros a puerta promedio: 5.8...")

st.markdown("---")

st.subheader("2. Datos de Cuotas (Casas de Apuestas)")
st.markdown("Copie el texto de la página web de la casa de apuestas y péguelo aquí:")
odds_text = st.text_area("Texto de cuotas:", height=200, placeholder="Ej: Over 2.5 Goles: 1.85\nUnder 2.5 Goles: 1.95\nBTTS Sí: 1.72\nBTTS No: 2.10")

# ==============================================================================
# 4. PROCESAMIENTO CON GEMINI (ESTABLE Y GRATUITO)
# ==============================================================================
if st.button("⚙️ EJECUTAR ANÁLISIS CUANTITATIVO", type="primary"):
    if not stats_text.strip() or not odds_text.strip():
        st.error("⚠️ Debe ingresar texto en ambos campos.")
    else:
        with st.spinner("Extrayendo datos y calculando Valor Esperado (+EV)..."):
            try:
                # Recorte de seguridad
                stats_text_clean = stats_text[:30000]
                odds_text_clean = odds_text[:15000]

                # Configurar Gemini
                genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                model = genai.GenerativeModel("gemini-2.0-flash")
                
                prompt_completo = f"{SYSTEM_PROMPT}\n\n--- ESTADÍSTICAS ---\n{stats_text_clean}\n\n--- CUOTAS ---\n{odds_text_clean}"
                
                response = model.generate_content(
                    prompt_completo,
                    generation_config=genai.GenerationConfig(
                        temperature=0.0,
                        max_output_tokens=1000,
                        response_mime_type="application/json"
                    )
                )

                raw_text = response.text
                
                if not raw_text or not raw_text.strip():
                    st.error("⚠️ El motor no devolvió datos. Reintente en unos segundos.")
                    st.stop()

                # Limpieza y parseo
                clean_json = raw_text.replace("```json", "").replace("```", "").strip()
                
                try:
                    data = json.loads(clean_json)
                except json.JSONDecodeError:
                    st.error("⚠️ Los datos no pudieron estructurarse. Verifique que los textos contengan números y cuotas claros.")
                    st.stop()

                if "error" in data:
                    st.warning(f"⛔ NO APOSTAR. {data['error']} Preservar capital.")
                    st.stop()

                # CÁLCULO MATEMÁTICO REAL (Python puro, cero alucinación)
                try:
                    cuota = float(data.get("cuota", 0))
                    prob_real = float(data.get("probabilidad_pdf", 0))
                except (ValueError, TypeError):
                    st.error("⚠️ Los datos extraídos no son números válidos.")
                    st.stop()

                if cuota <= 1.0 or prob_real <= 0:
                    st.error("⚠️ Datos de cuota o probabilidad inválidos.")
                    st.stop()

                prob_implicada = (1 / cuota) * 100
                prob_real_decimal = prob_real / 100.0
                ev = (prob_real_decimal * cuota) - 1.0
                ev_porcentaje = ev * 100

                # Informe Final
                st.success("✅ Análisis Cuantitativo Completado")
                st.markdown("---")
                
                st.markdown(f"### 📌 Mercado Analizado: **{data.get('mercado', 'No especificado')}**")
                st.markdown(f"💰 **Cuota de Mercado:** {cuota}  |  📊 **Probabilidad Implícita:** {prob_implicada:.1f}%")
                st.markdown(f"🧠 **Probabilidad Real (de los datos):** {prob_real}%")
                
                if ev_porcentaje > 5.0:
                    st.markdown(f"### 🟢 **VALOR ESPERADO (+EV): +{ev_porcentaje:.2f}%** *(Oportunidad Matemática Detectada)*")
                    st.markdown("⚖️ **Veredicto:** APOSTAR. Stake Fijo: 1% del Bankroll.")
                elif ev_porcentaje >= 0:
                    st.markdown(f"### 🟡 **VALOR ESPERADO (+EV): +{ev_porcentaje:.2f}%** *(Margen insuficiente)*")
                    st.markdown("⚖️ **Veredicto:** NO APOSTAR. El margen es menor al 5% mínimo requerido.")
                else:
                    st.markdown(f"### 🔴 **VALOR ESPERADO (-EV): {ev_porcentaje:.2f}%** *(Trampa de la casa)*")
                    st.markdown("⚖️ **Veredicto:** NO APOSTAR. Valor negativo.")

                st.markdown("---")
                st.markdown("#### 📈 Evidencia con Datos Duros (Citas):")
                st.markdown(f"1. 📄 *\"{data.get('evidencia_1', 'No disponible')}\"*")
                st.markdown(f"2. 📄 *\"{data.get('evidencia_2', 'No disponible')}\"*")
                st.markdown(f"3. 📄 *\"{data.get('evidencia_3', 'No disponible')}\"*")
                
                st.markdown("---")
                st.markdown("#### ⚠️ Regla de la Hora (Kill Switch Pre-Partido):")
                st.markdown(f"• ✅ **VALIDAR si:** {data.get('validar_si', 'Condiciones normales')}")
                st.markdown(f"• ❌ **CANCELAR INMEDIATAMENTE si:** {data.get('cancelar_si', 'Movimiento brusco de cuota')}")
                
                st.markdown("---")
                st.caption("Sistema Interno de Análisis Cuantitativo v4.0 | Motor Gemini | Cálculos verificados por Python.")

            except Exception as e:
                st.error(f"⚠️ Error en el sistema: {type(e).__name__}: {str(e)}")
