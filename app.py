import streamlit as st
import pandas as pd
import requests
import json

st.set_page_config(page_title="Sistema Interno de Análisis Cuantitativo", page_icon="📊", layout="centered")

st.sidebar.title("🔒 Acceso Restringido")
access_code = st.sidebar.text_input("Ingrese código de operador:", type="password")
if access_code != "CLAVE123":
    st.warning("Acceso denegado.")
    st.stop()

st.title("📊 Panel de Procesamiento de Datos Deportivos")
st.markdown("**Instrucciones:** Pegue el resumen consolidado del partido en el cuadro de abajo. El sistema calculará el +EV automáticamente.")
st.markdown("---")

SYSTEM_PROMPT = """Eres un extractor de datos cuantitativos. Tu ÚNICA tarea es leer el texto y devolver un objeto JSON válido. NO calcules nada, NO inventes datos.

Busca en el texto la probabilidad/frecuencia de un evento y la cuota decimal de ese mismo mercado.
Devuelve EXCLUSIVAMENTE este formato JSON (sin bloques de código markdown):
{
  "mercado": "Nombre del mercado (ej: Victoria Local, Over 2.5 Goles)",
  "cuota": 2.05,
  "probabilidad_datos": 70.0,
  "evidencia_1": "Cita textual con el número",
  "evidencia_2": "Segunda cita textual",
  "evidencia_3": "Tercera cita textual",
  "validar_si": "Condición para validar",
  "cancelar_si": "Condición para cancelar"
}
REGLAS:
1. Si no hay cuota clara, devuelve: {"error": "No se encontraron cuotas válidas."}
2. Si no hay datos estadísticos, devuelve: {"error": "Datos estadísticos insuficientes."}
3. 'cuota' y 'probabilidad_datos' DEBEN ser números (float).
"""

st.subheader("Pegue el Resumen Consolidado del Partido Aquí:")
input_text = st.text_area(
    "Resumen del partido:",
    height=400,
    placeholder="Pegue aquí el resumen completo con estadísticas, cuotas, H2H, forma reciente..."
)

if st.button("⚙️ EJECUTAR ANÁLISIS CUANTITATIVO", type="primary"):
    if not input_text.strip():
        st.error("⚠️ Debe pegar el texto del resumen.")
    else:
        with st.spinner("Extrayendo datos y calculando +EV..."):
            try:
                # LLAMADA A POLLINATIONS.AI (SIN API KEY, SIN REGISTRO)
                url = "https://text.pollinations.ai/openai"
                
                payload = {
                    "model": "openai",
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f"--- TEXTO A ANALIZAR ---\n{input_text[:40000]}"}
                    ],
                    "temperature": 0.0,
                    "max_tokens": 1000,
                    "seed": 42
                }
                
                headers = {"Content-Type": "application/json"}
                response = requests.post(url, headers=headers, json=payload, timeout=120)
                
                if response.status_code != 200:
                    st.error(f"⚠️ Error de conexión (código {response.status_code}). Reintente en 30 segundos.")
                    st.stop()

                raw_text = response.json()["choices"][0]["message"]["content"]
                
                if not raw_text or not raw_text.strip():
                    st.error("⚠️ El motor no devolvió datos. Reintente.")
                    st.stop()

                clean_json = raw_text.replace("```json", "").replace("```", "").strip()
                
                try:
                    data = json.loads(clean_json)
                except json.JSONDecodeError:
                    st.error("⚠️ No se pudo estructurar el JSON. Verifique que el texto tenga cuotas y estadísticas claras.")
                    st.stop()

                if "error" in data:
                    st.warning(f"⛔ NO APOSTAR. {data['error']} Preservar capital.")
                    st.stop()

                # CÁLCULO MATEMÁTICO REAL (Python puro)
                cuota = float(data.get("cuota", 0))
                prob_real = float(data.get("probabilidad_datos", 0))

                if cuota <= 1.0 or prob_real <= 0:
                    st.error("⚠️ Datos de cuota o probabilidad inválidos.")
                    st.stop()

                prob_implicada = (1 / cuota) * 100
                ev_porcentaje = ((prob_real / 100.0) * cuota - 1.0) * 100

                st.success("✅ Análisis Completado")
                st.markdown("---")
                st.markdown(f"### 📌 Mercado: **{data.get('mercado', 'No especificado')}**")
                st.markdown(f"💰 **Cuota:** {cuota} | 📊 **Prob. Implícita:** {prob_implicada:.1f}%")
                st.markdown(f"🧠 **Prob. Real:** {prob_real}%")
                
                if ev_porcentaje > 5.0:
                    st.markdown(f"### 🟢 **+EV: +{ev_porcentaje:.2f}%** *(Oportunidad)*")
                    st.markdown("⚖️ **Veredicto:** APOSTAR. Stake: 1%.")
                elif ev_porcentaje >= 0:
                    st.markdown(f"### 🟡 **+EV: +{ev_porcentaje:.2f}%** *(Margen bajo)*")
                    st.markdown("⚖️ **Veredicto:** NO APOSTAR.")
                else:
                    st.markdown(f"### 🔴 **-EV: {ev_porcentaje:.2f}%** *(Trampa)*")
                    st.markdown("⚖️ **Veredicto:** NO APOSTAR.")

                st.markdown("---")
                st.markdown("#### 📈 Evidencia:")
                st.markdown(f"1. 📄 *\"{data.get('evidencia_1', 'N/A')}\"*")
                st.markdown(f"2. 📄 *\"{data.get('evidencia_2', 'N/A')}\"*")
                st.markdown(f"3. 📄 *\"{data.get('evidencia_3', 'N/A')}\"*")
                
                st.markdown("---")
                st.markdown(f"• ✅ **VALIDAR si:** {data.get('validar_si', 'N/A')}")
                st.markdown(f"• ❌ **CANCELAR si:** {data.get('cancelar_si', 'N/A')}")
                st.caption("Sistema v10.0 | Motor Pollinations | Cálculos verificados por Python.")

            except Exception as e:
                st.error(f"⚠️ Error: {type(e).__name__}: {str(e)}")
