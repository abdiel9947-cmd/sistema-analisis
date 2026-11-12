import streamlit as st
import PyPDF2
import requests
import json
import re

# ==============================================================================
# 1. CONFIGURACIÓN DE LA INTERFAZ
# ==============================================================================
st.set_page_config(page_title="Sistema Interno de Análisis Cuantitativo", page_icon="📊", layout="centered")

st.sidebar.title("🔒 Acceso Restringido")
access_code = st.sidebar.text_input("Ingrese código de operador:", type="password")

if access_code != "CLAVE123":
    st.warning("Acceso denegado. Sistema reservado para personal autorizado.")
    st.stop()

st.title("📊 Panel de Procesamiento de Datos Deportivos")
st.markdown("**Instrucciones:** Suba los PDFs de estadísticas y los PDFs de cuotas. El sistema extraerá los datos y calculará el Valor Esperado (+EV) de forma automática.")
st.markdown("---")

# ==============================================================================
# 2. EL CEREBRO OCULTO (SOLO EXTRACCIÓN DE DATOS)
# ==============================================================================
SYSTEM_PROMPT = """
Eres un extractor de datos cuantitativos. Tu ÚNICA tarea es leer los PDFs adjuntos y devolver un objeto JSON válido. NO calcules nada, NO inventes datos, NO agregues texto fuera del JSON.

Busca en los PDFs de estadísticas la probabilidad histórica o frecuencia de un evento (ej: "Over 2.5 goles: 65%").
Busca en los PDFs de cuotas la cuota decimal de ese mismo mercado (ej: "1.85").

Devuelve EXCLUSIVAMENTE este formato JSON (sin bloques de código markdown, solo el JSON puro):
{
  "mercado": "Nombre exacto del mercado",
  "cuota": 1.85,
  "probabilidad_pdf": 65.0,
  "evidencia_1": "Cita textual exacta del PDF de estadísticas con el número",
  "evidencia_2": "Segunda cita textual exacta del PDF que respalde el dato",
  "evidencia_3": "Tercera cita textual exacta",
  "validar_si": "Condición pre-partido para validar",
  "cancelar_si": "Condición pre-partido para cancelar"
}

REGLAS ABSOLUTAS:
1. Si no encuentras una cuota clara, devuelve: {"error": "No se encontraron cuotas válidas en los PDFs."}
2. Si no encuentras datos estadísticos, devuelve: {"error": "Datos estadísticos insuficientes en el PDF."}
3. Los valores de 'cuota' y 'probabilidad_pdf' DEBEN ser números (float), no texto.
"""

# ==============================================================================
# 3. FORMULARIO DE ENTRADA
# ==============================================================================
st.subheader("1. PDFs de Estadísticas del Partido")
stats_files = st.file_uploader("Seleccionar PDFs de Estadísticas", type="pdf", accept_multiple_files=True, key="stats")

st.markdown("---")

st.subheader("2. PDFs de Cuotas (Casas de Apuestas)")
odds_files = st.file_uploader("Seleccionar PDFs de Cuotas", type="pdf", accept_multiple_files=True, key="odds")

# ==============================================================================
# 4. PROCESAMIENTO Y CÁLCULO MATEMÁTICO REAL
# ==============================================================================
def extraer_texto(files):
    texto = ""
    for f in files:
        try:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    texto += t + "\n"
        except Exception:
            continue
    return texto

if st.button("⚙️ EJECUTAR ANÁLISIS CUANTITATIVO", type="primary"):
    if not stats_files or not odds_files:
        st.error("⚠️ Error: Debe subir al menos un PDF de estadísticas y al menos un PDF de cuotas.")
    else:
        with st.spinner("Extrayendo datos y calculando Valor Esperado (+EV)..."):
            try:
                stats_text = extraer_texto(stats_files)[:40000]
                odds_text = extraer_texto(odds_files)[:20000]

                if len(stats_text.strip()) < 50 or len(odds_text.strip()) < 20:
                    st.error("⚠️ Los PDFs no contienen texto legible. Asegúrese de usar 'Guardar como PDF' desde el navegador, no una captura de pantalla.")
                    st.stop()

                # 1. Llamar a la API
                url = "https://openrouter.ai/api/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {st.secrets['OR_API_KEY']}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://sistema-interno.local",
                    "X-Title": "SistemaInterno"
                }
                
                payload = {
                    "model": "openrouter/free",
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f"--- ESTADÍSTICAS ---\n{stats_text}\n\n--- CUOTAS ---\n{odds_text}"}
                    ],
                    "temperature": 0.0,
                    "max_tokens": 1000
                }
                
                response = requests.post(url, headers=headers, json=payload, timeout=60)
                
                if response.status_code != 200:
                    st.error(f"⚠️ Error de conexión con el motor (Código {response.status_code}). Por favor, intente nuevamente en 30 segundos.")
                    st.stop()

                # 2. Extracción segura del texto (Blindado contra NoneType)
                respuesta_json = response.json()
                choices = respuesta_json.get("choices", [])
                
                if not choices:
                    st.error("⚠️ El motor devolvió una respuesta vacía. Esto ocurre a veces en la capa gratuita. Por favor, haga clic en 'Ejecutar' una segunda vez.")
                    st.stop()
                
                raw_text = choices[0].get("message", {}).get("content")
                
                # BLINDAJE CONTRA NONE: Si raw_text es None, lo manejamos sin que el sistema se caiga
                if not raw_text or not isinstance(raw_text, str):
                    st.error("⚠️ El motor no generó texto legible. Intente subir PDFs con texto más claro o reintente la operación.")
                    st.stop()

                # 3. Limpieza y parseo del JSON
                clean_json = raw_text.replace("```json", "").replace("```", "").strip()
                
                try:
                    data = json.loads(clean_json)
                except json.JSONDecodeError:
                    st.error("⚠️ El motor no pudo estructurar los datos. Asegúrese de que los PDFs contengan números y cuotas claros.")
                    st.stop()

                # 4. Manejo de errores lógicos del prompt
                if "error" in data:
                    st.warning(f"⛔ NO APOSTAR. {data['error']} Preservar capital.")
                    st.stop()

                # 5. CÁLCULO MATEMÁTICO REAL (Python puro, cero alucinación)
                try:
                    cuota = float(data.get("cuota", 0))
                    prob_real = float(data.get("probabilidad_pdf", 0))
                except (ValueError, TypeError):
                    st.error("⚠️ Los datos extraídos no son números válidos. Verifique que el PDF de cuotas tenga formato decimal (ej: 1.85).")
                    st.stop()

                if cuota <= 1.0 or prob_real <= 0:
                    st.error("⚠️ Datos de cuota o probabilidad inválidos extraídos del PDF.")
                    st.stop()

                prob_implicada = (1 / cuota) * 100
                prob_real_decimal = prob_real / 100.0
                ev = (prob_real_decimal * cuota) - 1.0
                ev_porcentaje = ev * 100

                # 6. Generar el Informe Final
                st.success("✅ Análisis Cuantitativo Completado")
                st.markdown("---")
                
                st.markdown(f"### 📌 Mercado Analizado: **{data.get('mercado', 'No especificado')}**")
                st.markdown(f"💰 **Cuota de Mercado:** {cuota}  |  📊 **Probabilidad Implícita:** {prob_implicada:.1f}%")
                st.markdown(f"🧠 **Probabilidad Real (del PDF):** {prob_real}%")
                
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
                st.markdown("#### 📈 Evidencia con Datos Duros (Citas del PDF):")
                st.markdown(f"1. 📄 *\"{data.get('evidencia_1', 'No disponible')}\"*")
                st.markdown(f"2. 📄 *\"{data.get('evidencia_2', 'No disponible')}\"*")
                st.markdown(f"3. 📄 *\"{data.get('evidencia_3', 'No disponible')}\"*")
                
                st.markdown("---")
                st.markdown("#### ⚠️ Regla de la Hora (Kill Switch Pre-Partido):")
                st.markdown(f"• ✅ **VALIDAR si:** {data.get('validar_si', 'Condiciones normales')}")
                st.markdown(f"• ❌ **CANCELAR INMEDIATAMENTE si:** {data.get('cancelar_si', 'Movimiento brusco de cuota')}")
                
                st.markdown("---")
                st.caption("Sistema Interno de Análisis Cuantitativo v2.1 | Cálculos verificados por motor matemático.")

            except Exception as e:
                st.error(f"⚠️ Error inesperado en el sistema. Por favor, reintente la operación. (Detalle: {type(e).__name__})")
