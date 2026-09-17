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
# ESTILO — DASHBOARD VERDE, PRETO E BRANCO
# ============================================================
def apply_custom_style():
    st.markdown(
        """
        <style>

        /* ==================================================
           BASE
        ================================================== */

        .stApp {
            background:
                radial-gradient(
                    circle at 15% 5%,
                    rgba(31, 107, 74, 0.10),
                    transparent 28%
                ),
                linear-gradient(
                    135deg,
                    #f7faf8 0%,
                    #eef4f0 100%
                );
        }

        .main {
            background: transparent;
        }

        .block-container {
            max-width: 1250px;
            padding-top: 2rem;
            padding-bottom: 4rem;
        }

        /* ==================================================
           ESCONDER ELEMENTOS DESNECESSÁRIOS
        ================================================== */

        #MainMenu {
            visibility: hidden;
        }

        footer {
            visibility: hidden;
        }

        header {
            background: transparent !important;
        }

        /* ==================================================
           SIDEBAR
        ================================================== */

        section[data-testid="stSidebar"] {
            background:
                linear-gradient(
                    180deg,
                    #07130e 0%,
                    #0d2118 100%
                );
            border-right: 1px solid #183c2b;
        }

        section[data-testid="stSidebar"] > div {
            padding-top: 1.8rem;
        }

        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3 {
            color: #ffffff !important;
            font-weight: 750;
        }

        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] span {
            color: #d9e8df !important;
        }

        section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] {
            gap: 7px;
        }

        section[data-testid="stSidebar"] .stRadio label {
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 9px;
            padding: 9px 12px;
            transition: 0.2s;
        }

        section[data-testid="stSidebar"] .stRadio label:hover {
            background: rgba(46, 139, 93, 0.18);
            border-color: #2e8b5d;
        }

        /* ==================================================
           CABEÇALHO PRINCIPAL
        ================================================== */

        .hero {
            background:
                linear-gradient(
                    135deg,
                    #07130e 0%,
                    #102c1f 58%,
                    #174f37 100%
                );
            border-radius: 24px;
            padding: 34px 38px;
            margin-bottom: 28px;
            box-shadow:
                0 15px 40px rgba(7, 28, 18, 0.16);
            position: relative;
            overflow: hidden;
        }

        .hero:after {
            content: "";
            position: absolute;
            width: 240px;
            height: 240px;
            right: -80px;
            top: -100px;
            border-radius: 50%;
            background: rgba(255,255,255,0.06);
        }

        .hero-title {
            color: #ffffff;
            font-size: 2.45rem;
            font-weight: 800;
            line-height: 1.1;
            margin-bottom: 9px;
            letter-spacing: -1px;
        }

        .hero-subtitle {
            color: #cfe2d7;
            font-size: 1rem;
            margin: 0;
        }

        .hero-badge {
            display: inline-block;
            margin-bottom: 14px;
            padding: 6px 12px;
            border-radius: 30px;
            background: rgba(255,255,255,0.09);
            border: 1px solid rgba(255,255,255,0.13);
            color: #d9f1e3;
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.5px;
        }

        /* ==================================================
           TÍTULOS
        ================================================== */

        h1 {
            color: #071d13 !important;
            font-weight: 800 !important;
            letter-spacing: -0.8px;
        }

        h2,
        h3,
        h4 {
            color: #103d29 !important;
            font-weight: 750 !important;
        }

        p {
            color: #53655c;
        }

        /* ==================================================
           ÁREA DE FOTO
        ================================================== */

        .photo-section {
            background: #ffffff;
            border: 1px solid #dbe7df;
            border-radius: 22px;
            padding: 24px;
            box-shadow:
                0 10px 30px rgba(16, 61, 41, 0.07);
            margin-bottom: 24px;
        }

        .section-label {
            color: #123d2b;
            font-size: 0.82rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 7px;
        }

        .section-description {
            color: #718078;
            font-size: 0.92rem;
            margin-bottom: 18px;
        }

        /* ==================================================
           TABS
        ================================================== */

        .stTabs [data-baseweb="tab-list"] {
            background: #f0f5f2;
            padding: 5px;
            border-radius: 13px;
            gap: 5px;
            border: 1px solid #dce7e1;
        }

        .stTabs [data-baseweb="tab"] {
            color: #53675c;
            border-radius: 9px;
            padding: 9px 18px;
            font-weight: 650;
        }

        .stTabs [aria-selected="true"] {
            color: #ffffff !important;
            background: #103d29 !important;
        }

        .stTabs [data-baseweb="tab-highlight"] {
            background: transparent;
        }

        /* ==================================================
           UPLOAD
        ================================================== */

        [data-testid="stFileUploader"] {
            background: #ffffff;
            border-radius: 15px;
            padding: 7px;
            border: 1px solid #d7e5dc;
        }

        [data-testid="stFileUploaderDropzone"] {
            background: #f8fbf9;
            border: 1px dashed #8bb39e;
            border-radius: 11px;
        }

        [data-testid="stFileUploaderDropzone"]:hover {
            background: #f0f8f3;
            border-color: #24764f;
        }

        /* ==================================================
           CÂMERA
        ================================================== */

        [data-testid="stCameraInput"] {
            background: #ffffff;
            border: 1px solid #d7e5dc;
            border-radius: 15px;
            padding: 7px;
        }

        /* ==================================================
           IMAGEM DE PRÉ-VISUALIZAÇÃO
        ================================================== */

        [data-testid="stImage"] {
            background: #ffffff;
            border-radius: 20px;
        }

        [data-testid="stImage"] img {
            border-radius: 18px;
            box-shadow:
                0 12px 30px rgba(0,0,0,0.10);
        }

        /* ==================================================
           BOTÃO PRINCIPAL
        ================================================== */

        .stButton > button {
            width: 100%;
            min-height: 50px;
            background:
                linear-gradient(
                    135deg,
                    #123d2b,
                    #1f6b4a
                );
            color: #ffffff;
            border: none;
            border-radius: 12px;
            font-weight: 750;
            font-size: 0.98rem;
            box-shadow:
                0 7px 18px rgba(18,61,43,0.20);
            transition: all 0.2s ease;
        }

        .stButton > button:hover {
            background:
                linear-gradient(
                    135deg,
                    #0b2d1e,
                    #185b3e
                );
            color: #ffffff;
            transform: translateY(-2px);
            box-shadow:
                0 10px 24px rgba(18,61,43,0.25);
        }

        .stButton > button:focus {
            color: #ffffff;
            border: none;
        }

        /* ==================================================
           RESULTADO
        ================================================== */

        .result-card {
            background: #ffffff;
            border-radius: 22px;
            border: 1px solid #dbe7df;
            padding: 26px;
            margin-top: 25px;
            box-shadow:
                0 12px 35px rgba(16,61,41,0.08);
        }

        .result-title {
            color: #0c291c;
            font-size: 1.05rem;
            font-weight: 800;
            margin-bottom: 8px;
        }

        .dish-description {
            color: #40564b;
            font-size: 1rem;
            line-height: 1.55;
            margin-bottom: 20px;
        }

        /* ==================================================
           CARDS NUTRICIONAIS
        ================================================== */

        [data-testid="stMetric"] {
            background:
                linear-gradient(
                    145deg,
                    #ffffff,
                    #f5faf7
                );
            border: 1px solid #d8e7de;
            border-radius: 17px;
            padding: 18px 16px;
            min-height: 120px;
            box-shadow:
                0 7px 20px rgba(18,61,43,0.06);
        }

        [data-testid="stMetricLabel"] {
            color: #65786e !important;
            font-size: 0.82rem !important;
            font-weight: 650 !important;
        }

        [data-testid="stMetricValue"] {
            color: #123d2b !important;
            font-size: 1.7rem !important;
            font-weight: 800 !important;
        }

        /* ==================================================
           STATUS MINEIRO
        ================================================== */

        [data-testid="stAlert"] {
            border-radius: 13px;
            border: 1px solid #d4e5db;
        }

        [data-testid="stAlert"][kind="success"] {
            background: #eaf6ee;
            color: #164d32;
        }

        [data-testid="stAlert"][kind="info"] {
            background: #f1f5f3;
            color: #40574c;
        }

        /* ==================================================
           HISTÓRICO
        ================================================== */

        [data-testid="stVerticalBlockBorderWrapper"] {
            background: #ffffff;
            border: 1px solid #dbe7df;
            border-radius: 19px;
            padding: 10px;
            margin-bottom: 18px;
            box-shadow:
                0 7px 24px rgba(16,61,41,0.06);
        }

        /* ==================================================
           CAMPO API
        ================================================== */

        .stTextInput input {
            background: #ffffff;
            color: #18382a;
            border: 1px solid #bcd1c5;
            border-radius: 10px;
        }

        .stTextInput input:focus {
            border-color: #2a7650;
            box-shadow: 0 0 0 1px #2a7650;
        }

        /* ==================================================
           SPINNER
        ================================================== */

        .stSpinner > div {
            border-top-color: #1f6b4a !important;
        }

        /* ==================================================
           DIVISORES
        ================================================== */

        hr {
            border-color: #dce8e1 !important;
        }

        /* ==================================================
           MOBILE
        ================================================== */

        @media (max-width: 768px) {

            .block-container {
                padding-left: 1rem;
                padding-right: 1rem;
                padding-top: 1rem;
            }

            .hero {
                padding: 25px 22px;
                border-radius: 18px;
            }

            .hero-title {
                font-size: 1.8rem;
            }

            .photo-section {
                padding: 17px;
                border-radius: 17px;
            }

            [data-testid="stMetric"] {
                min-height: 105px;
                padding: 13px;
            }

            [data-testid="stMetricValue"] {
                font-size: 1.35rem !important;
            }

            .stTabs [data-baseweb="tab"] {
                padding: 8px 10px;
            }
        }

        </style>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# UTILIDADES
# ============================================================
def image_to_base64_jpeg(image: Image.Image, size=(800, 600)) -> str:
    resized = image.convert("RGB").resize(size)

    buffer = io.BytesIO()

    resized.save(
        buffer,
        format="JPEG"
    )

    return base64.b64encode(
        buffer.getvalue()
    ).decode("utf-8")


def analyze_dish(client: OpenAI, image: Image.Image) -> dict:

    base64_image = image_to_base64_jpeg(image)

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": INSTRUCTIONS
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        },
                    },
                ],
            }
        ],
        response_format={
            "type": "json_object"
        },
        reasoning_effort="minimal",
        max_completion_tokens=800,
    )

    choice = response.choices[0]

    raw = (
        choice.message.content or ""
    ).strip()

    if not raw:

        reason = (
            "a resposta foi cortada por limite de tokens antes de terminar"
            if choice.finish_reason == "length"
            else "a API retornou uma resposta vazia"
        )

        raise ValueError(
            f"Não foi possível ler o resultado: {reason}. "
            "Tente novamente."
        )

    clean = (
        raw
        .replace("```json", "")
        .replace("```", "")
        .strip()
    )

    return json.loads(clean)


# ============================================================
# RESULTADO
# ============================================================
def render_result(dish: dict):

    if dish.get("erro"):

        st.error(
            dish["erro"]
        )

        return

    st.markdown(
        '<div class="result-card">',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="result-title">Resultado da análise</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        f'<div class="dish-description">{dish["descricao"]}</div>',
        unsafe_allow_html=True
    )

    if dish.get("culinaria_mineira"):

        label = "Culinária mineira"

        if dish.get("prato_tipico"):
            label += f" — {dish['prato_tipico']}"

        st.success(label)

    else:

        st.info(
            "Não identificado como prato mineiro"
        )

    if dish.get("justificativa_classificacao"):

        st.caption(
            dish["justificativa_classificacao"]
        )

    st.markdown(
        "#### Informação nutricional"
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Calorias",
        f"{round(dish['calorias'])}"
    )

    col2.metric(
        "Carboidratos",
        f"{dish['carboidratos_g']} g"
    )

    col3.metric(
        "Proteínas",
        f"{dish['proteinas_g']} g"
    )

    col4.metric(
        "Gorduras",
        f"{dish['gorduras_g']} g"
    )

    st.caption(
        "Valores estimados por IA a partir da imagem. "
        "Podem variar em relação à composição real do prato."
    )

    st.markdown(
        "</div>",
        unsafe_allow_html=True
    )


# ============================================================
# NOVO PRATO
# ============================================================
def show_new_dish_page(api_key: str):

    st.markdown(
        """
        <div class="hero">

            <div class="hero-badge">
                ANÁLISE NUTRICIONAL COM IA
            </div>

            <div class="hero-title">
                Descubra o que há<br>
                no seu prato
            </div>

            <p class="hero-subtitle">
                Envie uma foto e receba uma estimativa nutricional
                inteligente da sua refeição.
            </p>

        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="photo-section">

            <div class="section-label">
                Analisar refeição
            </div>

            <div class="section-description">
                Escolha uma imagem do prato ou tire uma foto diretamente.
                Para melhores resultados, fotografe de cima e com boa iluminação.
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_upload, tab_camera = st.tabs(
        [
            "Enviar imagem",
            "Tirar foto"
        ]
    )

    image = None

    with tab_upload:

        uploaded = st.file_uploader(
            "Escolha uma imagem",
            type=[
                "jpg",
                "jpeg",
                "png"
            ]
        )

        if uploaded:

            image = Image.open(
                uploaded
            )

    with tab_camera:

        captured = st.camera_input(
            "Tirar foto do prato"
        )

        if captured:

            image = Image.open(
                captured
            )

    if image is not None:

        st.markdown(
            "### Pré-visualização"
        )

        st.image(
            image,
            caption="Imagem selecionada",
            width=420
        )

        st.markdown("")

        if st.button(
            "Analisar prato",
            type="primary"
        ):

            if not api_key:

                st.error(
                    "Informe sua chave da API OpenAI na barra lateral."
                )

                return

            with st.spinner(
                "A IA está analisando sua refeição..."
            ):

                try:

                    client = OpenAI(
                        api_key=api_key
                    )

                    dish = analyze_dish(
                        client,
                        image
                    )

                except Exception as exc:

                    st.error(
                        f"Erro ao chamar a API: {exc}"
                    )

                    return

            if dish.get("erro"):

                st.error(
                    dish["erro"]
                )

                return

            render_result(
                dish
            )

            st.session_state.history.insert(
                0,
                {
                    "dish": dish,
                    "image": image,
                    "timestamp": datetime.now()
                }
            )


# ============================================================
# HISTÓRICO
# ============================================================
def show_history_page():

    st.markdown(
        """
        <div class="hero">

            <div class="hero-badge">
                SEU HISTÓRICO
            </div>

            <div class="hero-title">
                Análises realizadas
            </div>

            <p class="hero-subtitle">
                Consulte as refeições analisadas nesta sessão.
            </p>

        </div>
        """,
        unsafe_allow_html=True,
    )

    if not st.session_state.history:

        st.info(
            "Nenhuma análise ainda."
        )

        return

    for item in st.session_state.history:

        with st.container(
            border=True
        ):

            col_img, col_info = st.columns(
                [1, 4]
            )

            with col_img:

                st.image(
                    item["image"],
                    width=130
                )

            with col_info:

                st.caption(
                    item["timestamp"].strftime(
                        "%d/%m/%Y • %H:%M"
                    )
                )

                render_result(
                    item["dish"]
                )


# ============================================================
# APP
# ============================================================
def main():

    st.set_page_config(
        page_title=APP_TITLE,
        page_icon="🍽️",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    apply_custom_style()

    if "history" not in st.session_state:

        st.session_state.history = []

    with st.sidebar:

        st.markdown(
            """
            <div style="
                padding: 5px 0 18px 0;
                border-bottom: 1px solid #214333;
                margin-bottom: 18px;
            ">
                <div style="
                    font-size: 1.35rem;
                    font-weight: 800;
                    color: white;
                ">
                    Identificador
                </div>

                <div style="
                    font-size: 0.82rem;
                    color: #9fc2ad;
                    margin-top: 3px;
                ">
                    Nutrição inteligente
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        api_key = st.text_input(
            "Chave da API",
            value=os.environ.get(
                "OPENAI_API_KEY",
                ""
            ),
            type="password",
            help=(
                "Ou defina a variável de ambiente "
                "OPENAI_API_KEY antes de rodar."
            ),
        )

        st.markdown("")

        page = st.radio(
            "Navegação",
            [
                "Novo prato",
                "Histórico"
            ]
        )

        if st.session_state.history:

            st.markdown("---")

            st.caption(
                "ANÁLISES RECENTES"
            )

            for item in st.session_state.history[:5]:

                st.write(
                    f"{item['dish']['descricao'][:28]}…"
                )

                st.caption(
                    f"{round(item['dish']['calorias'])} kcal"
                )

    if page == "Novo prato":

        show_new_dish_page(
            api_key
        )

    else:

        show_history_page()


if __name__ == "__main__":
    main()