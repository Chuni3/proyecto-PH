import streamlit as st
import os
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEndpoint
from langchain_core.prompts import PromptTemplate
from langchain_huggingface import ChatHuggingFace
from langchain_core.output_parsers import StrOutputParser

# 1. Cargar las variables de entorno (tu API Key secreta)
load_dotenv()

# 2. Configurar la interfaz de Streamlit
st.title("Diseñador de Muebles Inteligente")
st.write("Contame qué tipo de mueble estás buscando y con qué características.")

# 3. Inicializar la "Memoria" (Requisito C del Trabajo Final)
# Usamos session_state para que la memoria no se borre al recargar la página
if "memoria_diseno" not in st.session_state:
    st.session_state.memoria_diseno = {
        "Tipo_Mueble": None,
        "Material": None,
        "Color": None,
        "Dimensiones": None
    }

if "historial_chat" not in st.session_state:
    st.session_state.historial_chat = []

# 4. Mostrar el estado actual de la memoria en la barra lateral (para la demostración)
with st.sidebar:
    st.header("Memoria del Bot (Estado del Diseño)")
    st.json(st.session_state.memoria_diseno)
    
if st.sidebar.button("🔄 Reiniciar Diseño"):
    st.session_state.memoria_diseno = {"Tipo_Mueble": None, "Material": None, "Color": None, "Dimensiones": None}
    st.session_state.historial_chat = []
    st.rerun()
    
# 5. Configurar el LLM gratuito en modo Chat
repo_id = "Qwen/Qwen2.5-7B-Instruct"
llm_endpoint = HuggingFaceEndpoint(
    repo_id=repo_id,
    temperature=0.1,
    max_new_tokens=128
)

# Envolvemos el modelo para que LangChain use la ruta "conversacional"
llm = ChatHuggingFace(llm=llm_endpoint)

st.set_page_config(page_title="Diseñador de Muebles", page_icon="🪑")
st.markdown("<h1 style='color: #8B4513;'>🪑 El Diseñador de Carpintería</h1>", unsafe_allow_html=True)

# --- A PARTIR DE ACÁ VA LA LÓGICA DEL CHAT ---
# (Capturar el input del usuario, enviarlo al LLM y actualizar la memoria)

#-----------------------------------------------------------------------------------------------------------

import json

# --- 6. El Prompt (Las instrucciones del sistema) ---
template = """
Sos un asistente virtual. Tu única tarea es extraer la información del mensaje del usuario y clasificar su intención en base al ESTADO ACTUAL DEL DISEÑO. No debes redactar respuestas largas ni dar precios.

ESTADO ACTUAL DEL DISEÑO:
{memoria_actual}

Mensaje del usuario: "{mensaje}"

Intenciones posibles: "Iniciar_Diseño", "Configurar_Atributo", "Solicitar_Cotizacion".

Respondé ÚNICAMENTE con un objeto JSON válido con este formato exacto, en una sola línea y sin saltos de línea:
{{
  "intencion": "[Escribir Iniciar_Diseño, Configurar_Atributo o Solicitar_Cotizacion]",
  "entidades": {{
    "Tipo_Mueble": "[Escribir el dato o null]",
    "Material": "[Escribir el dato o null]",
    "Color": "[Escribir el dato o null]",
    "Dimensiones": "[Escribir el dato o null]"
  }}
}}
"""

prompt = PromptTemplate(template=template, input_variables=["mensaje", "memoria_actual"])

# 7. Renderizar el historial del chat en la pantalla
for msg in st.session_state.historial_chat:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# 8. Capturar el mensaje del usuario
if prompt_usuario := st.chat_input("Escribí acá (ej: Hola, quiero una mesa de pino negra...)"):
    
    # Mostrar el mensaje del usuario
    with st.chat_message("user"):
        st.write(prompt_usuario)
    
    # Guardar en el historial
    st.session_state.historial_chat.append({"role": "user", "content": prompt_usuario})
    
    # Pensando...
    with st.spinner('El bot está pensando...'):
        try:
            # Mandar el mensaje y la memoria al modelo
            cadena = prompt | llm | StrOutputParser()
            respuesta_llm = cadena.invoke({
                "mensaje": prompt_usuario,
                "memoria_actual": json.dumps(st.session_state.memoria_diseno)
            })
            
            # Limpiar la respuesta para asegurar que sea JSON
            texto_json = respuesta_llm.strip().replace('```json', '').replace('```', '')
            datos_extraidos = json.loads(texto_json)
            
            # 9. Actualizar la Memoria (st.session_state)
            entidades_nuevas = datos_extraidos.get("entidades", {})
            for clave, valor in entidades_nuevas.items():
                if valor and str(valor).lower() != "null":
                    st.session_state.memoria_diseno[clave] = valor
            
            # 10. Generar la respuesta del bot desde Python
            intencion = datos_extraidos.get("intencion", "")
            memoria = st.session_state.memoria_diseno
            respuesta_bot = ""

            # Verificamos si la memoria ya tiene al menos un dato guardado
            tiene_datos = any(v is not None and str(v).lower() != "null" for v in memoria.values())

            if intencion == "Iniciar_Diseño" and not tiene_datos:
                # Solo saluda si la memoria está 100% vacía
                respuesta_bot = "¡Hola! Para empezar, ¿qué tipo de mueble te gustaría diseñar (mesa, silla, cama, placard, etc.)?"
            
            elif intencion == "Solicitar_Cotizacion" or all(v is not None and str(v).lower() != "null" for v in memoria.values()):
                # Cotización final armada por Python
                respuesta_bot = f"¡Perfecto! Aquí tienes el detalle de tu diseño:\n\n- Tipo: {memoria.get('Tipo_Mueble')}\n- Material: {memoria.get('Material')}\n- Color: {memoria.get('Color')}\n- Medidas: {memoria.get('Dimensiones')}\n\n*Nota: El precio estimado te será enviado por un asesor de ventas a la brevedad.* ¡Gracias por elegirnos!"
                
            else:
                # Preguntar qué falta
                faltantes = [k for k, v in memoria.items() if v is None or str(v).lower() == "null"]
                if faltantes:
                    respuesta_bot = f"¡Entendido! Ya anoté esa preferencia. Para seguir, ¿podrías indicarme el detalle de: {faltantes[0]}?"
                else:
                    respuesta_bot = "¡Perfecto! ¿Necesitás cotizar el mueble o modificar algún dato?"

            st.session_state.historial_chat.append({"role": "assistant", "content": respuesta_bot})
            
            # Recargar la página para que la interfaz muestre el mensaje y actualice la memoria
            st.rerun()

        except Exception as e:
            st.error(f"Hubo un error de formato con el LLM: {e}")