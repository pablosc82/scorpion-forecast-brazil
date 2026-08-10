"""Dashboard institucional Streamlit — lê artefatos; nunca treina modelos."""

from __future__ import annotations

import base64
import copy
import hashlib
import html
import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


ROOT_DIR = Path(__file__).resolve().parent
INPUT_CSV = ROOT_DIR / "incidencia_total.csv"
FORECASTS_CSV = ROOT_DIR / "artifacts" / "latest_forecasts.csv"
METADATA_JSON = ROOT_DIR / "artifacts" / "latest_run.json"
GEOJSON_PATH = ROOT_DIR / "assets" / "br_states.geojson"
LOGOS_DIR = ROOT_DIR / "assets" / "logos"

UNIT_LABEL = "Incidência mensal por 100.000 habitantes"
ARTICLE_URL = "https://www.nature.com/articles/s44528-026-00002-9"

# Envelope do GeoJSON local em longitude/latitude WGS84, com pequena folga para
# as fronteiras. O enquadramento explícito evita escala global no coroplético.
BRAZIL_LON_RANGE = (-75.0, -33.8)
BRAZIL_LAT_RANGE = (-35.0, 6.3)

STATE_NAMES = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas",
    "BA": "Bahia", "CE": "Ceará", "DF": "Distrito Federal", "ES": "Espírito Santo",
    "GO": "Goiás", "MA": "Maranhão", "MT": "Mato Grosso", "MS": "Mato Grosso do Sul",
    "MG": "Minas Gerais", "PA": "Pará", "PB": "Paraíba", "PR": "Paraná",
    "PE": "Pernambuco", "PI": "Piauí", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte",
    "RS": "Rio Grande do Sul", "RO": "Rondônia", "RR": "Roraima", "SC": "Santa Catarina",
    "SP": "São Paulo", "SE": "Sergipe", "TO": "Tocantins",
}
MONTH_NAMES = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)
MONTH_ABBREVIATIONS = (
    "JAN", "FEV", "MAR", "ABR", "MAI", "JUN",
    "JUL", "AGO", "SET", "OUT", "NOV", "DEZ",
)
LOGO_SPECS = (
    ("inct_conexao", "INCT-CONEXAO"),
    ("ufs", "Universidade Federal de Sergipe"),
    ("martes", "MarTeS"),
)


def _sha256_file(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _month_label(month: str) -> str:
    timestamp = pd.Timestamp(f"{month}-01")
    return f"{MONTH_NAMES[timestamp.month - 1]} de {timestamp.year}"


def _month_short_label(month: str) -> str:
    timestamp = pd.Timestamp(f"{month}-01")
    return f"{MONTH_ABBREVIATIONS[timestamp.month - 1]}/{timestamp.year}"


def _logo_path(stem: str) -> Path | None:
    """Encontra um logo fornecido pelo usuário, sem gerar substitutos."""
    for extension in (".svg", ".png", ".jpg", ".jpeg", ".webp"):
        candidate = LOGOS_DIR / f"{stem}{extension}"
        if candidate.is_file():
            return candidate
    return None


def _logo_markup(stem: str, label: str) -> str:
    path = _logo_path(stem)
    if path is None:
        return f'<span class="logo-pending">{html.escape(label)}</span>'

    mime_types = {
        ".svg": "image/svg+xml",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    mime_type = mime_types[path.suffix.lower()]
    return (
        f'<img class="institution-logo" alt="{html.escape(label)}" '
        f'src="data:{mime_type};base64,{encoded}">'
    )


def _inject_styles() -> None:
    """Define a camada visual institucional sem alterar a lógica da aplicação."""
    st.markdown(
        """
        <style>
            :root {
                --ink: #15354b;
                --muted: #5f7180;
                --line: #dce5e8;
                --paper: #f7faf9;
                --blue: #1f5a8a;
                --teal: #117d7a;
                --teal-soft: #e8f3f1;
            }
            #MainMenu, footer, [data-testid="stHeader"] { display: none !important; }
            [data-testid="stAppViewContainer"] { background: #ffffff; }
            .block-container {
                max-width: 1450px;
                padding: 2.1rem 3.3rem 3.8rem !important;
            }
            @media (max-width: 780px) {
                .block-container { padding: 1.25rem 1rem 2.5rem !important; }
            }
            .institution-header {
                border-bottom: 1px solid var(--line);
                margin: 0 0 1.7rem;
                padding: 0 0 1.25rem;
            }
            .institution-logos {
                align-items: center;
                display: flex;
                gap: 1.25rem;
                min-height: 49px;
                margin-bottom: 1rem;
            }
            .institution-logo {
                display: block;
                max-height: 45px;
                max-width: 155px;
                object-fit: contain;
                width: auto;
            }
            .logo-pending {
                border-left: 2px solid #8aa9a7;
                color: #416b71;
                font-size: 0.72rem;
                font-weight: 650;
                letter-spacing: 0.06em;
                padding-left: 0.55rem;
                text-transform: uppercase;
            }
            .eyebrow {
                color: var(--teal);
                font-size: 0.74rem;
                font-weight: 700;
                letter-spacing: 0.12em;
                margin-bottom: 0.32rem;
                text-transform: uppercase;
            }
            .institution-title {
                color: var(--ink);
                font-family: Georgia, "Times New Roman", serif;
                font-size: clamp(2rem, 3.1vw, 3.15rem);
                font-weight: 600;
                letter-spacing: -0.028em;
                line-height: 1.07;
                margin: 0;
            }
            .institution-subtitle {
                color: var(--muted);
                font-size: 1.04rem;
                margin: 0.42rem 0 0;
            }
            .metadata-strip {
                display: flex;
                flex-wrap: wrap;
                gap: 0.5rem 1.55rem;
                margin-top: 1rem;
            }
            .metadata-item {
                color: var(--muted);
                font-size: 0.82rem;
            }
            .metadata-item strong { color: var(--ink); font-weight: 650; }
            .article-line {
                color: var(--muted);
                font-size: 0.78rem;
                margin: 0.88rem 0 0;
            }
            .article-line a, .model-copy a, .footer-copy a {
                color: var(--blue);
                text-decoration: none;
            }
            .article-line a:hover, .model-copy a:hover, .footer-copy a:hover {
                text-decoration: underline;
            }
            .mock-notice {
                background: #f7fbfa;
                border-left: 3px solid #75a5a0;
                color: #42646a;
                font-size: 0.82rem;
                margin: 0 0 1.2rem;
                padding: 0.6rem 0.78rem;
            }
            .section-kicker {
                color: var(--teal);
                font-size: 0.72rem;
                font-weight: 700;
                letter-spacing: 0.1em;
                margin: 0 0 0.25rem;
                text-transform: uppercase;
            }
            .section-heading {
                color: var(--ink);
                font-family: Georgia, "Times New Roman", serif;
                font-size: 1.3rem;
                font-weight: 600;
                margin: 0 0 0.78rem;
            }
            .map-instruction {
                color: var(--muted);
                font-size: 0.78rem;
                margin: 0.15rem 0 0.7rem;
            }
            .state-heading {
                color: var(--ink);
                font-family: Georgia, "Times New Roman", serif;
                font-size: 1.7rem;
                font-weight: 600;
                line-height: 1.12;
                margin: 0.15rem 0 0.7rem;
            }
            .state-heading span { color: var(--teal); font-family: inherit; }
            div[data-testid="stSelectbox"] label, div[data-testid="stToggle"] label {
                color: var(--muted) !important;
                font-size: 0.78rem !important;
                font-weight: 650 !important;
            }
            div[data-testid="stSelectbox"] [data-baseweb="select"] > div {
                border-color: var(--line);
                box-shadow: none;
            }
            div[data-testid="stButton"] > button {
                background: #ffffff;
                border: 1px solid var(--line);
                border-radius: 3px;
                color: var(--blue);
                font-size: 0.78rem;
                font-weight: 700;
                letter-spacing: 0.06em;
                min-height: 2.25rem;
                padding: 0.35rem 0.25rem;
            }
            div[data-testid="stButton"] > button[kind="primary"] {
                background: var(--blue);
                border-color: var(--blue);
                color: #ffffff;
            }
            div[data-testid="stButton"] > button:hover { border-color: var(--teal); color: var(--teal); }
            div[data-testid="stButton"] > button[kind="primary"]:hover { color: #ffffff; }
            .forecast-heading {
                border-top: 1px solid var(--line);
                margin-top: 1.35rem;
                padding-top: 1.15rem;
            }
            .forecast-card {
                border-top: 2px solid #8eb7b2;
                min-height: 112px;
                padding: 0.65rem 0.1rem 0.1rem;
            }
            .forecast-card-month {
                color: var(--muted);
                font-size: 0.71rem;
                font-weight: 700;
                letter-spacing: 0.07em;
            }
            .forecast-card-value {
                color: var(--ink);
                font-size: 1.36rem;
                font-weight: 650;
                letter-spacing: -0.025em;
                line-height: 1.25;
                margin: 0.22rem 0;
            }
            .forecast-card-range { color: var(--muted); font-size: 0.72rem; line-height: 1.35; }
            .forecast-card-range strong { color: #42646a; font-weight: 650; }
            [data-testid="stExpander"] {
                border: 1px solid var(--line);
                border-radius: 3px;
                margin-top: 1.3rem;
            }
            [data-testid="stExpander"] summary { color: var(--blue); font-size: 0.85rem; font-weight: 650; }
            .about-model {
                border-top: 1px solid var(--line);
                margin-top: 2.5rem;
                padding-top: 1.55rem;
            }
            .model-copy, .footer-copy {
                color: var(--muted);
                font-size: 0.88rem;
                line-height: 1.62;
                margin: 0;
                max-width: 900px;
            }
            .footer-copy { font-size: 0.8rem; margin-top: 1rem; }
            .footer-copy strong { color: var(--ink); }
            .stPlotlyChart { border: 1px solid #edf1f2; border-radius: 2px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False)
def load_dashboard_data() -> tuple[pd.DataFrame, pd.DataFrame, dict, dict]:
    history = pd.read_csv(INPUT_CSV)
    history["data"] = pd.to_datetime(history["data"], format="%Y-%m")
    forecasts = pd.read_csv(FORECASTS_CSV)
    with METADATA_JSON.open(encoding="utf-8") as source:
        metadata = json.load(source)
    with GEOJSON_PATH.open(encoding="utf-8") as source:
        geojson = json.load(source)
    return history, forecasts, metadata, geojson


def _geojson_for_plotly(geojson: dict) -> dict:
    """Converte somente em memória a orientação dos anéis para Plotly Geo."""
    rendered_geojson = copy.deepcopy(geojson)
    for feature in rendered_geojson["features"]:
        geometry = feature["geometry"]
        if geometry["type"] == "Polygon":
            geometry["coordinates"] = [
                list(reversed(ring)) for ring in geometry["coordinates"]
            ]
        elif geometry["type"] == "MultiPolygon":
            geometry["coordinates"] = [
                [list(reversed(ring)) for ring in polygon]
                for polygon in geometry["coordinates"]
            ]
    return rendered_geojson


def build_map(month_rows: pd.DataFrame, geojson: dict, selected_month: str) -> go.Figure:
    """Monta um coroplético estadual local, com hover e clique preservados."""
    map_data = month_rows.set_index("uf").reindex(STATE_NAMES).reset_index()
    map_data["nome_uf"] = map_data["uf"].map(STATE_NAMES)
    figure = go.Figure(
        go.Choropleth(
            geojson=_geojson_for_plotly(geojson),
            locations=map_data["uf"],
            z=map_data["media"],
            featureidkey="properties.sigla",
            colorscale=[[0.0, "#f7fbf9"], [0.45, "#a8d1c7"], [0.75, "#3a8c88"], [1.0, "#153f66"]],
            marker_line_color="white",
            marker_line_width=0.75,
            colorbar={
                "title": {"text": "Incidência mensal<br>por 100 mil hab.", "side": "top"},
                "x": 0.93,
                "y": 0.5,
                "len": 0.86,
                "thickness": 12,
                "tickfont": {"size": 10, "color": "#5f7180"},
            },
            customdata=map_data[
                ["uf", "nome_uf", "media", "limite_inferior_95", "limite_superior_95"]
            ].to_numpy(),
            hovertemplate=(
                "<b>%{customdata[1]} (%{customdata[0]})</b><br>"
                "Previsão: %{customdata[2]:.2f}<br>"
                "IC 95%: %{customdata[3]:.2f} a %{customdata[4]:.2f}"
                "<extra></extra>"
            ),
        )
    )
    figure.update_geos(
        visible=False,
        projection_type="mercator",
        center={"lon": -54.4, "lat": -14.2},
        lonaxis_range=BRAZIL_LON_RANGE,
        lataxis_range=BRAZIL_LAT_RANGE,
        showcoastlines=False,
        showcountries=False,
        showland=False,
        showlakes=False,
        showframe=False,
        bgcolor="rgba(0,0,0,0)",
    )
    figure.update_layout(
        height=540,
        margin={"l": 0, "r": 0, "t": 42, "b": 0},
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        title={
            "text": f"Incidência prevista — {_month_label(selected_month)}",
            "font": {"color": "#15354b", "family": "Arial, sans-serif", "size": 15},
            "x": 0.0,
            "xanchor": "left",
        },
        geo={"domain": {"x": [0.0, 0.88], "y": [0.0, 1.0]}},
    )
    return figure


def build_state_chart(
    history: pd.DataFrame,
    state_forecasts: pd.DataFrame,
    uf: str,
    show_full_series: bool,
) -> go.Figure:
    """Exibe cinco anos observados por padrão, mantendo a série completa opcional."""
    observed = history[["data", uf]].rename(columns={uf: "incidencia"})
    if not show_full_series:
        five_years_ago = observed["data"].iloc[-1] - pd.DateOffset(years=5)
        observed = observed.loc[observed["data"] >= five_years_ago]

    forecast_dates = pd.to_datetime(state_forecasts["data_previsao"], format="%Y-%m")
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=observed["data"], y=observed["incidencia"], mode="lines",
            name="Observado", line={"color": "#1f5a8a", "width": 2.2},
        )
    )
    figure.add_trace(
        go.Scatter(
            x=forecast_dates, y=state_forecasts["limite_inferior_95"], mode="lines",
            line={"width": 0, "color": "rgba(17,125,122,0)"},
            hoverinfo="skip", showlegend=False,
        )
    )
    figure.add_trace(
        go.Scatter(
            x=forecast_dates, y=state_forecasts["limite_superior_95"], mode="lines",
            fill="tonexty", fillcolor="rgba(17,125,122,0.17)",
            line={"width": 0, "color": "rgba(17,125,122,0)"},
            name="Intervalo de 95%", hoverinfo="skip",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=forecast_dates, y=state_forecasts["media"], mode="lines+markers",
            name="Previsão", line={"color": "#117d7a", "width": 2.5, "dash": "dash"},
            marker={"size": 6},
        )
    )
    figure.add_vline(
        x=observed["data"].iloc[-1], line_dash="dot", line_color="#6d7b84",
        annotation_text="Início da previsão", annotation_position="top left",
        annotation_font={"size": 10, "color": "#5f7180"},
    )
    figure.update_layout(
        height=470,
        margin={"l": 8, "r": 8, "t": 20, "b": 52},
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        xaxis={
            "title": None,
            "showgrid": False,
            "linecolor": "#dce5e8",
            "tickfont": {"color": "#5f7180", "size": 11},
        },
        yaxis={
            "title": {"text": UNIT_LABEL, "font": {"color": "#5f7180", "size": 11}},
            "gridcolor": "#edf1f2",
            "zeroline": False,
            "tickfont": {"color": "#5f7180", "size": 11},
        },
        hovermode="x unified",
        legend={
            "orientation": "h",
            "x": 0,
            "y": -0.2,
            "font": {"color": "#5f7180", "size": 11},
        },
    )
    return figure


def _render_header(metadata: dict, forecasts: pd.DataFrame) -> None:
    first_month = min(forecasts["data_previsao"])
    last_month = max(forecasts["data_previsao"])
    logos = "".join(
        f'<div class="logo-container">{_logo_markup(stem, label)}</div>'
        for stem, label in LOGO_SPECS
    )
    st.markdown(
        f"""
        <header class="institution-header">
            <div class="institution-logos">{logos}</div>
            <div class="eyebrow">Vigilância e alerta precoce em saúde pública</div>
            <h1 class="institution-title">Previsão de acidentes escorpiônicos no Brasil</h1>
            <p class="institution-subtitle">Sistema de previsão de curto prazo baseado em modelos N-BEATS</p>
            <div class="metadata-strip">
                <span class="metadata-item"><strong>Último mês observado:</strong> {_month_label(metadata['observed_end'])}</span>
                <span class="metadata-item"><strong>Horizonte previsto:</strong> {_month_label(first_month)} — {_month_label(last_month)}</span>
                <span class="metadata-item"><strong>Unidades federativas:</strong> 27 UFs</span>
                <span class="metadata-item"><strong>Horizonte:</strong> 6 meses</span>
            </div>
            <p class="article-line">Modelo baseado em <a href="{ARTICLE_URL}" target="_blank">Martinez et al. (2026), Communications Health</a>.</p>
        </header>
        """,
        unsafe_allow_html=True,
    )


def _render_month_selector(forecast_months: list[str]) -> str:
    if st.session_state.get("mes_previsao") not in forecast_months:
        st.session_state.mes_previsao = forecast_months[0]

    st.markdown('<p class="section-kicker">Mês de referência</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-heading">Previsão espacial</p>', unsafe_allow_html=True)
    month_columns = st.columns(len(forecast_months), gap="small")
    for column, month in zip(month_columns, forecast_months, strict=True):
        with column:
            is_selected = month == st.session_state.mes_previsao
            if st.button(
                MONTH_ABBREVIATIONS[pd.Timestamp(f"{month}-01").month - 1],
                key=f"mes_{month}",
                type="primary" if is_selected else "secondary",
                use_container_width=True,
            ):
                st.session_state.mes_previsao = month
                st.rerun()
    return st.session_state.mes_previsao


def _render_forecast_cards(state_forecasts: pd.DataFrame, uf: str) -> None:
    st.markdown('<div class="forecast-heading">', unsafe_allow_html=True)
    st.markdown('<p class="section-kicker">Síntese operacional</p>', unsafe_allow_html=True)
    st.markdown(
        f'<p class="section-heading">Previsão — {STATE_NAMES[uf]} ({uf})</p>',
        unsafe_allow_html=True,
    )
    st.markdown('</div>', unsafe_allow_html=True)
    card_columns = st.columns(6, gap="small")
    for column, (_, row) in zip(card_columns, state_forecasts.iterrows(), strict=True):
        with column:
            st.markdown(
                f"""
                <div class="forecast-card">
                    <div class="forecast-card-month">{_month_short_label(row['data_previsao'])}</div>
                    <div class="forecast-card-value">{row['media']:.2f}</div>
                    <div class="forecast-card-range"><strong>IC 95%</strong><br>{row['limite_inferior_95']:.2f} — {row['limite_superior_95']:.2f}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _render_about_model() -> None:
    st.markdown('<section class="about-model">', unsafe_allow_html=True)
    st.markdown('<p class="section-kicker">Fundamentação científica</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-heading">Sobre o modelo</p>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <p class="model-copy">
            A previsão utiliza cinco modelos globais N-BEATS independentes, um para cada
            macrorregião brasileira, produzindo previsões mensais para as 27 UFs.
        </p>
        <p class="model-copy" style="margin-top:0.7rem;">
            Martinez et al. (2026). <em>Deep learning forecasting of scorpion envenoming incidence in Brazil to support early warning and prevention.</em>
            Communications Health 1, Article 2. <a href="{ARTICLE_URL}" target="_blank">Consultar publicação</a>.
        </p>
        <p class="footer-copy">
            <strong>Desenvolvido no âmbito do INCT-CONEXAO</strong><br>
            Instagram: <a href="https://www.instagram.com/inct_conexao/" target="_blank" rel="noopener noreferrer">@inct_conexao</a><br>
            Universidade Federal de Sergipe — UFS<br>
            MarTeS — <a href="https://www.instagram.com/projeto.martes/" target="_blank" rel="noopener noreferrer">@projeto.martes</a>
        </p>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('</section>', unsafe_allow_html=True)


def main() -> None:
    st.set_page_config(
        page_title="Previsão de acidentes escorpiônicos",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    _inject_styles()

    missing_files = [path for path in (FORECASTS_CSV, METADATA_JSON, GEOJSON_PATH) if not path.exists()]
    if missing_files:
        st.info(
            "Inclua os arquivos de dados do dashboard antes de publicá-lo: "
            "incidencia_total.csv, os dois artefatos em artifacts/ e o mapa estadual em assets/."
        )
        return

    history, forecasts, metadata, geojson = load_dashboard_data()
    _render_header(metadata, forecasts)

    if metadata.get("is_mock"):
        st.markdown(
            '<div class="mock-notice">Modo de demonstração: os valores exibidos são dados sintéticos para validação visual e não constituem previsão N-BEATS.</div>',
            unsafe_allow_html=True,
        )
    if _sha256_file(INPUT_CSV) != metadata.get("input_sha256"):
        st.warning(
            "O CSV histórico foi alterado depois da última previsão. Execute novamente "
            "o pipeline antes de interpretar este dashboard."
        )

    forecast_months = sorted(forecasts["data_previsao"].unique().tolist())
    selected_month = _render_month_selector(forecast_months)

    if "uf_selecionada" not in st.session_state:
        st.session_state.uf_selecionada = "SP"
    if "uf_selectbox" not in st.session_state:
        st.session_state.uf_selectbox = st.session_state.uf_selecionada
    if st.session_state.pop("atualizar_uf_pelo_mapa", False):
        st.session_state.uf_selectbox = st.session_state.uf_selecionada

    map_column, chart_column = st.columns((0.45, 0.55), gap="large")
    with chart_column:
        selected_uf = st.selectbox(
            "Unidade federativa", list(STATE_NAMES), key="uf_selectbox",
            format_func=lambda uf: f"{STATE_NAMES[uf]} ({uf})",
        )
        st.session_state.uf_selecionada = selected_uf
        st.markdown(
            f'<div class="state-heading">{STATE_NAMES[selected_uf]} <span>({selected_uf})</span></div>',
            unsafe_allow_html=True,
        )
        show_full_series = st.toggle(
            "Ver série completa", value=False, key="mostrar_serie_completa"
        )

    with map_column:
        month_rows = forecasts.loc[forecasts["data_previsao"] == selected_month].copy()
        st.markdown('<p class="map-instruction">Clique em uma UF para atualizar a série temporal.</p>', unsafe_allow_html=True)
        event = st.plotly_chart(
            build_map(month_rows, geojson, selected_month),
            use_container_width=True,
            on_select="rerun",
            selection_mode="points",
            key="mapa_brasil",
        )
        selected_points = event.selection.get("points", []) if event else []
        if selected_points:
            clicked_uf = selected_points[0].get("location")
            if clicked_uf in STATE_NAMES and clicked_uf != st.session_state.uf_selecionada:
                st.session_state.uf_selecionada = clicked_uf
                st.session_state.atualizar_uf_pelo_mapa = True
                st.rerun()

    state_forecasts = forecasts.loc[forecasts["uf"] == selected_uf].sort_values("data_previsao")
    with chart_column:
        st.plotly_chart(
            build_state_chart(history, state_forecasts, selected_uf, show_full_series),
            use_container_width=True,
        )

    _render_forecast_cards(state_forecasts, selected_uf)

    table = state_forecasts[
        ["data_previsao", "media", "limite_inferior_95", "limite_superior_95"]
    ].copy()
    table["data_previsao"] = table["data_previsao"].map(_month_label)
    table.columns = [
        "Mês", "Previsão média", "Limite inferior (95%)", "Limite superior (95%)"
    ]
    with st.expander("Ver dados detalhados"):
        st.caption(UNIT_LABEL)
        st.dataframe(table, hide_index=True, use_container_width=True)

    _render_about_model()


if __name__ == "__main__":
    main()
