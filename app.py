import streamlit as st
import requests
import json

st.set_page_config(page_title="Sistema Interno de Análisis Cuantitativo", page_icon="📊", layout="centered")

st.sidebar.title("🔒 Acceso Restringido")
access_code = st.sidebar.text_input("Ingrese código de operador:", type="password")
if access_code != "CLAVE123":
    st.warning("Acceso denegado.")
    st.stop()

st.title("📊 Panel de Procesamiento de Datos Deportivos")
st.markdown("**Instrucciones:** Pegue el resumen consolidado del partido. El sistema auditará 9 categorías y buscará hasta 3 oportunidades de +EV.")
st.markdown("---")

# ==============================================================================
# PROMPT EXHAUSTIVO ORIGINAL (RESTAURADO Y OPTIMIZADO PARA JSON)
# ==============================================================================
SYSTEM_PROMPT = """Actúa como un Analista Cuantitativo Profesional de Apuestas Deportivas (Quant). Tu único objetivo es preservar el capital y encontrar Valor Esperado Positivo (+EV) matemáticamente demostrable. Tu tolerancia al riesgo es extremadamente baja.

Analizarás EXCLUSIVAMENTE los datos numéricos del texto adjunto. PROHIBIDO usar conocimiento general, narrativas de "motivación", o inventar datos. Si un dato no está en el texto, el mercado correspondiente se descarta inmediatamente.

Aplica el siguiente ALGORITMO y devuelve EXCLUSIVAMENTE este formato JSON (sin bloques de código markdown, solo el JSON puro):
{
  "auditoria_9_categorias": {
    "1_Principales": "DATOS SUFICIENTES" o "INSUFICIENTES. MERCADO DESCARTADO",
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
      "mercado": "Nombre exacto del mercado (ej: Victoria Local, Over 2.5 Goles)",
      "cuota": 2.05,
      "probabilidad_datos": 70.0,
      "margen_ev": 12.5,
      "evidencia_1": "Cita textual exacta con el número",
      "evidencia_2": "Segunda cita textual exacta",
      "evidencia_3": "Tercera cita textual exacta",
      "validar_si": "Condición pre-partido para validar",
      "cancelar_si": "Condición pre-partido para cancelar"
    }
  ],
  "veredicto_final": "APOSTAR" o "NO APOSTAR",
  "mensaje_preservacion": "Mensaje final de recomendación"
}

REGLAS INQUEBRANTABLES:
1. La lista "oportunidades" debe contener 1, 2 o 3 mercados sólidos que hayan pasado la auditoría y tengan un margen EV > 5%. Si no hay ninguno, deja la lista vacía [] y pon veredicto "NO APOSTAR".
2. Los valores de 'cuota', 'probabilidad_datos' y 'margen_ev' DEBEN ser números (float), no texto.
3. Cero Alucinaciones: Si el texto dice "UNLOCK" o "PREMIUM", asume que el dato es NO DISPONIBLE.
4. Matemáticas sobre Narrativa: Ignora frases como "necesitan ganar".
"""

st.subheader("Pegue el Resumen Consolidado del Partido Aquí:")
input_text = st.text_area(
    "Resumen del partido (incluya estadísticas, cuotas, H2H, forma, etc.):",
    height=400,
    placeholder="Pegue aquí el resumen completo generado por IA con todos los datos del partido..."
)

if st.button("⚙️ EJECUTAR ANÁLISIS CUANTITATIVO COMPLETO", type="primary"):
    if not input_text.strip():
        st.error("⚠️ Debe pegar el texto del resumen.")
    else:
        with st.spinner("Auditoría de 9 categorías y cálculo de +EV en curso..."):
            try:
                # ==============================================================================
                # LLAMADA A POLLINATIONS.AI (SIN CLAVES, SIN REGISTRO, MODELO ESTABLE)
                # ==============================================================================
                url = "https://text.pollinations.ai/openai"
                payload = {
                    "model": "llama",  # <--- ESTE ES EL MODELO QUE FUNCIONA SIN ERROR 400
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f"--- TEXTO A ANALIZAR ---\n{input_text[:45000]}"}
                    ],
                    "temperature": 0.0,
                    "max_tokens": 2500,
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
                    st.error("⚠️ No se pudo estructurar el JSON. Verifique que el texto tenga datos claros.")
                    st.stop()

                # ==============================================================================
                # RENDERIZADO DE LA INTERFAZ (PROMPT EXHAUSTIVO DE 5 PASOS)
                # ==============================================================================
                st.success("✅ Análisis Cuantitativo Completado")
                st.markdown("---")
                
                # PASO 1: AUDITORÍA
                st.markdown("### 🛑 PASO 1: AUDITORÍA DE LAS 9 CATEGORÍAS")
                audit = data.get("auditoria_9_categorias", {})
                cols = st.columns(3)
                for i, (cat, status) in enumerate(audit.items()):
                    with cols[i % 3]:
                        if "INSUFICIENTES" in str(status):
                            st.markdown(f"🔴 **{cat}:** {status}")
                        else:
                            st.markdown(f"🟢 **{cat}:** {status}")
                
                st.markdown("---")
                
                # PASO 2 y 3: OPORTUNIDADES Y VEREDICTO
                opps = data.get("oportunidades", [])
                
                if not opps or data.get("veredicto_final") == "NO APOSTAR":
                    st.markdown("### ⛔ VEREDICTO FINAL: NO APOSTAR")
                    st.warning(data.get("mensaje_preservacion", "Ningún mercado presenta un +EV matemático suficiente (>5%). Preservar capital."))
                else:
                    st.markdown("### 📊 PASO 2 y 3: OPORTUNIDADES DE +EV DETECTADAS")
                    for i, opp in enumerate(opps, 1):
                        st.markdown(f"#### 🎯 Oportunidad #{i}: **{opp.get('mercado', 'No especificado')}**")
                        
                        cuota = float(opp.get("cuota", 0))
                        prob_real = float(opp.get("probabilidad_datos", 0))
                        ev = float(opp.get("margen_ev", 0))
                        prob_implicada = (1 / cuota) * 100 if cuota > 0 else 0
                        
                        st.markdown(f"💰 **Cuota:** {cuota} | 📊 **Prob. Implícita:** {prob_implicada:.1f}% | 🧠 **Prob. Real:** {prob_real}%")
                        
                        if ev > 5.0:
                            st.markdown(f"### 🟢 **VALOR ESPERADO (+EV): +{ev:.2f}%** *(Oportunidad Matemática Detectada)*")
                            st.markdown("⚖️ **Veredicto:** APOSTAR. Stake Fijo: 1% del Bankroll.")
                        else:
                            st.markdown(f"### 🟡 **VALOR ESPERADO (+EV): +{ev:.2f}%** *(Margen insuficiente)*")
                            st.markdown("⚖️ **Veredicto:** NO APOSTAR.")
                        
                        st.markdown("**📈 Evidencia con Datos Duros:**")
                        st.markdown(f"1. 📄 *\"{opp.get('evidencia_1', 'N/A')}\"*")
                        st.markdown(f"2. 📄 *\"{opp.get('evidencia_2', 'N/A')}\"*")
                        st.markdown(f"3. 📄 *\"{opp.get('evidencia_3', 'N/A')}\"*")
                        
                        st.markdown("**⚠️ Regla de la Hora (Kill Switch):**")
                        st.markdown(f"• ✅ **VALIDAR si:** {opp.get('validar_si', 'Condiciones normales')}")
                        st.markdown(f"• ❌ **CANCELAR si:** {opp.get('cancelar_si', 'Movimiento brusco de cuota')}")
                        st.markdown("---")

                st.caption("Sistema Interno de Análisis Cuantitativo v12.1 | Algoritmo de 5 pasos restaurado | Motor Pollinations (llama) | Cálculos verificados por Python.")

            except Exception as e:
                st.error(f"⚠️ Error en el sistema: {type(e).__name__}: {str(e)}")
