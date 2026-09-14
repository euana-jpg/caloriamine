
import base64
import io
import json
import os
from datetime import datetime

import streamlit as st
from openai import OpenAI
from PIL import Image

APP_TITLE = "Identificador de Calorias"
MODEL = "gpt-5-mini"

INSTRUCTIONS = """
Você é um assistente que analisa fotos de pratos de comida para um aplicativo de estimativa nutricional.

Passo 1 — Verifique se a imagem contém um prato de comida.
Se NÃO contiver, responda apenas:
{ "erro": "A imagem não parece conter um prato de comida." }

Passo 2 — Se contiver, descreva em uma frase os itens visíveis no prato
(ingredientes principais, forma de preparo aparente, acompanhamentos).

Passo 3 — Avalie se o prato é característico da culinária mineira (Minas Gerais, Brasil).
Considere ingredientes e preparos típicos como: tutu de feijão, feijão tropeiro, couve
refogada, torresmo, linguiça artesanal, frango com quiabo, angu, pão de queijo, doce de
leite, queijo minas, arroz com pequi, entre outros. Não classifique como mineiro só por
ser um prato brasileiro genérico (ex.: arroz com feijão simples, salada comum) — a
classificação positiva exige ao menos um elemento claramente típico dessa culinária.

Passo 4 — Estime os valores nutricionais aproximados para a refeição completa.

Responda SOMENTE em JSON, sem markdown, no formato:
{
  "descricao": "string",
  "culinaria_mineira": boolean,
  "prato_tipico": "nome do prato típico identificado, ou null se não aplicável",
  "justificativa_classificacao": "uma frase curta explicando por que é ou não é considerado mineiro",
  "calorias": number,
  "carboidratos_g": number,
  "proteinas_g": number,
  "gorduras_g": number
}
"""


# ============================================================
# Utilidades
# ============================================================
def image_to_base64_jpeg(image: Image.Image, size=(800, 600)) -> str:
    """Redimensiona a imagem e retorna como base64 JPEG (sem o cabeçalho data:...)."""
    resized = image.convert("RGB").resize(size)
    buffer = io.BytesIO()
    resized.save(buffer, format="JPEG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def analyze_dish(client: OpenAI, image: Image.Image) -> dict:
    base64_image = image_to_base64_jpeg(image)

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": INSTRUCTIONS},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                    },
                ],
            }
        ],
        response_format={"type": "json_object"},
        reasoning_effort="minimal",
        max_completion_tokens=800,
    )

    choice = response.choices[0]
    raw = (choice.message.content or "").strip()

    if not raw:
        reason = (
            "a resposta foi cortada por limite de tokens antes de terminar"
            if choice.finish_reason == "length"
            else "a API retornou uma resposta vazia"
        )
        raise ValueError(f"Não foi possível ler o resultado: {reason}. Tente novamente.")

    clean = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(clean)


# ============================================================
# Renderização
# ============================================================
def render_result(dish: dict):
    if dish.get("erro"):
        st.error(dish["erro"])
        return

    st.markdown(f"**{dish['descricao']}**")

    if dish.get("culinaria_mineira"):
        label = "🟧 Culinária mineira"
        if dish.get("prato_tipico"):
            label += f" — {dish['prato_tipico']}"
        st.success(label)
    else:
        st.info("Não identificado como prato mineiro")

    if dish.get("justificativa_classificacao"):
        st.caption(dish["justificativa_classificacao"])

    st.markdown("#### Informação nutricional")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Calorias", f"{round(dish['calorias'])}")
    col2.metric("Carboidratos", f"{dish['carboidratos_g']} g")
    col3.metric("Proteínas", f"{dish['proteinas_g']} g")
    col4.metric("Gorduras", f"{dish['gorduras_g']} g")
    st.caption("Valores estimados por IA a partir da imagem. Podem variar em relação à composição real do prato.")


# ============================================================
# App
# ============================================================
def main():
    st.set_page_config(page_title=APP_TITLE, page_icon="🍽️", layout="wide")

    if "history" not in st.session_state:
        st.session_state.history = []  # cada item: {dish, image, timestamp}

    with st.sidebar:
        st.header(APP_TITLE)
        api_key = st.text_input(
            "Digite sua chave API_Key aqui:",
            value=os.environ.get("OPENAI_API_KEY", ""),
            type="password",
            help="Ou defina a variável de ambiente OPENAI_API_KEY antes de rodar.",
        )
        page = st.radio("Navegação", ["Novo prato", "Histórico"])

        if st.session_state.history:
            st.markdown("---")
            st.caption("Análises recentes")
            for item in st.session_state.history[:5]:
                st.write(f"{item['dish']['descricao'][:28]}… — **{round(item['dish']['calorias'])} kcal**")

    if page == "Novo prato":
        show_new_dish_page(api_key)
    else:
        show_history_page()


def show_new_dish_page(api_key: str):
    st.title("Envie ou tire uma foto do prato")
    st.caption("Uma foto de cima, com boa luz, gera a estimativa mais precisa.")

    tab_upload, tab_camera = st.tabs(["📁 Enviar arquivo", "📷 Tirar foto"])

    image = None
    with tab_upload:
        uploaded = st.file_uploader("Escolha uma imagem", type=["jpg", "jpeg", "png"])
        if uploaded:
            image = Image.open(uploaded)

    with tab_camera:
        captured = st.camera_input("Tirar foto do prato")
        if captured:
            image = Image.open(captured)

    if image is not None:
        st.image(image, caption="Pré-visualização", width=320)

        if st.button("Analisar prato", type="primary"):
            if not api_key:
                st.error("Informe sua chave da API OpenAI na barra lateral.")
                return
            with st.spinner("Analisando o prato…"):
                try:
                    client = OpenAI(api_key=api_key)
                    dish = analyze_dish(client, image)
                except Exception as exc:
                    st.error(f"Erro ao chamar a API: {exc}")
                    return

            if dish.get("erro"):
                st.error(dish["erro"])
                return

            render_result(dish)
            st.session_state.history.insert(
                0, {"dish": dish, "image": image, "timestamp": datetime.now()}
            )


def show_history_page():
    st.title("Histórico da sessão")
    st.caption("Todas as análises feitas desde que você abriu esta página.")

    if not st.session_state.history:
        st.info("Nenhuma análise ainda.")
        return

    for item in st.session_state.history:
        with st.container(border=True):
            col_img, col_info = st.columns([1, 4])
            with col_img:
                st.image(item["image"], width=100)
            with col_info:
                st.write(item["timestamp"].strftime("%H:%M"))
                render_result(item["dish"])


if __name__ == "__main__":
    main()