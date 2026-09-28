"""Interface do MAX — Motor de Análise de Exposição.

Execucao:
    streamlit run src/app.py
"""

from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import audit, config  # noqa: E402
from src.agent import AgenteMax, mensagem_de_abertura  # noqa: E402
from src.data_engine import formatar_data, formatar_reais  # noqa: E402
from src.knowledge_base import obter_base  # noqa: E402

st.set_page_config(
    page_title="MAX | Motor de Análise de Exposição",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Paleta console de operação ───────────────────────
# bg0 #090B0D  fundo global — preto quente
# bg1 #0E1114  painel superior e sidebar
# bg2 #131720  cards e blocos internos
# bg3 #1A1F26  cabeçalhos de card
# ln  #1E252C  divisórias
# ln2 #26303A  divisórias mais visíveis
# txt #C2D0D8  texto principal
# tx2 #445A68  texto secundário / rótulos
# grn #3EC9A7  acento positivo
# red #D95F52  crítico
# amb #C8A03A  alerta / atenção
# wht #DDE8EC  branco suave
# acc #1A6E88  azul-petróleo estrutural
# ──────────────────────────────────────────────────────

ESTILO = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inconsolata:wght@500;700;800&display=swap');

:root {
    --bg0: #090B0D;
    --bg1: #0E1114;
    --bg2: #131720;
    --bg3: #1A1F26;
    --ln:  #1E252C;
    --ln2: #26303A;
    --txt: #C2D0D8;
    --tx2: #445A68;
    --grn: #3EC9A7;
    --red: #D95F52;
    --amb: #C8A03A;
    --wht: #DDE8EC;
    --acc: #1A6E88;
}

html, body, .stApp { background: var(--bg0) !important; }
html, body, .stApp, .stMarkdown, .stText {
    font-family: 'Space Grotesk', sans-serif;
    color: var(--txt);
}
[data-testid="stIconMaterial"],
.material-symbols-rounded, .material-symbols-outlined,
.material-icons, .material-icons-outlined {
    font-family: 'Material Symbols Rounded', 'Material Icons' !important;
    font-feature-settings: 'liga';
    letter-spacing: normal !important;
}

#MainMenu, header, footer { visibility: hidden; }
.block-container { padding-top: 0 !important; padding-bottom: 1.5rem; max-width: 1480px; }

/* TOPBAR */
.topbar {
    display: flex; align-items: stretch;
    background: var(--bg1); border-bottom: 2px solid var(--acc);
    margin: -1rem -1rem 1.4rem -1rem;
}
.topbar-logo {
    background: var(--acc); padding: 10px 20px;
    display: flex; align-items: center; gap: 10px;
}
.topbar-logo span {
    font-family: 'Inconsolata', monospace;
    font-size: 22px; font-weight: 800; color: #DDE8EC; letter-spacing: .08em;
}
.topbar-logo sub {
    font-size: 9px; letter-spacing: .18em; text-transform: uppercase;
    color: #8AB8C8; font-family: 'Space Grotesk', sans-serif; font-weight: 500;
}
.topbar-nome {
    flex: 1; display: flex; align-items: center; padding: 0 18px;
    font-size: 10px; letter-spacing: .18em; text-transform: uppercase; color: var(--tx2);
    border-right: 1px solid var(--ln2);
}
.topbar-pill {
    display: flex; align-items: center; padding: 0 14px;
    border-right: 1px solid var(--ln2);
    font-family: 'Inconsolata', monospace; font-size: 10px; letter-spacing: .1em;
}
.topbar-pill.ok   { color: var(--grn); }
.topbar-pill.off  { color: var(--tx2); }
.topbar-pill.crit { background: #200E0C; color: var(--red); font-weight: 700; border-right: none; }

/* INDICADORES */
.ind-strip {
    display: grid; grid-template-columns: repeat(4, 1fr);
    border-bottom: 1px solid var(--ln2);
}
.ind-bloco { padding: 14px 18px; border-right: 1px solid var(--ln2); }
.ind-bloco:last-child { border-right: none; }
.ind-bloco.crit { background: #120806; }
.ind-bloco.amb  { background: #0E0E06; }
.ind-bloco.pos  { background: #060E0C; }
.ind-label {
    font-size: 9px; letter-spacing: .18em; text-transform: uppercase;
    font-weight: 700; color: var(--tx2); margin-bottom: 8px;
}
.ind-val {
    font-family: 'Inconsolata', monospace; font-variant-numeric: tabular-nums;
    font-size: 1.65rem; font-weight: 800; line-height: 1; color: var(--wht);
}
.ind-val.neg { color: var(--red); }
.ind-val.pos { color: var(--grn); }
.ind-val.amb { color: var(--amb); }
.ind-note    { font-size: 11px; color: var(--tx2); margin-top: 6px; }

/* BARRA DE COMPOSIÇÃO */
.comp-bar { display: flex; height: 3px; gap: 1px; margin: 10px 0 4px; }
.comp-bar .liq { background: var(--grn); opacity: .75; border-radius: 1px; }
.comp-bar .fra { background: var(--red); opacity: .85; border-radius: 1px; }
.comp-labels { display: flex; justify-content: space-between; }
.comp-liq { font-family: 'Inconsolata', monospace; font-size: 9px; color: var(--grn); letter-spacing: .08em; }
.comp-fra { font-family: 'Inconsolata', monospace; font-size: 9px; color: var(--red); letter-spacing: .08em; }

/* GRÁFICO */
.chart-header {
    display: flex; justify-content: space-between; align-items: center;
    padding: 10px 18px 6px; border-bottom: 1px solid var(--ln); background: var(--bg1);
}
.chart-title { font-size: 9px; letter-spacing: .18em; text-transform: uppercase; color: var(--tx2); font-weight: 700; }

/* AGENDA */
.agenda-wrap { border-top: 1px solid var(--ln2); }
.agenda-head { display: flex; padding: 6px 18px; background: var(--bg1); border-bottom: 1px solid var(--ln2); }
.agenda-row {
    display: flex; align-items: center;
    padding: 7px 18px; border-bottom: 1px solid var(--ln); font-size: 13px;
}
.agenda-row:last-child { border-bottom: none; }
.agenda-row:hover { background: var(--bg2); }
.agenda-data  { font-family: 'Inconsolata', monospace; font-size: 11px; color: var(--tx2); flex: 0 0 72px; }
.agenda-desc  { flex: 1; color: var(--txt); }
.agenda-cat   { flex: 0 0 106px; font-size: 11px; color: var(--tx2); }
.agenda-val   { font-family: 'Inconsolata', monospace; font-size: 13px; font-weight: 700; flex: 0 0 100px; text-align: right; }
.agenda-val.neg   { color: var(--red); }
.agenda-val.pos   { color: var(--grn); }
.agenda-saldo { font-family: 'Inconsolata', monospace; font-size: 11px; flex: 0 0 94px; text-align: right; color: var(--tx2); }
.agenda-saldo.neg { color: var(--red); }
.col-head { font-size: 9px; letter-spacing: .15em; text-transform: uppercase; color: var(--tx2); font-weight: 700; }

/* COBERTURA */
.cob-header {
    display: flex; justify-content: space-between; align-items: flex-start;
    padding: 12px 16px; border-bottom: 1px solid var(--ln2); background: var(--bg3);
}
.cob-nome { font-size: 14px; font-weight: 700; color: var(--wht); }
.cob-sub  { font-size: 11px; color: var(--tx2); margin-top: 2px; }
.cob-taxa { font-family: 'Inconsolata', monospace; font-size: 20px; font-weight: 800; color: var(--grn); text-align: right; }
.cob-taxa sub { font-size: 10px; display: block; color: var(--tx2); font-weight: 500; margin-top: 1px; }
.cob-linha {
    display: flex; justify-content: space-between; align-items: baseline;
    padding: 7px 16px; border-bottom: 1px solid var(--ln);
}
.cob-linha:last-child { border-bottom: none; }
.cob-rot { font-size: 12px; color: var(--tx2); }
.cob-val { font-family: 'Inconsolata', monospace; font-size: 14px; font-weight: 700; color: var(--wht); }
.eco-strip {
    display: flex; justify-content: space-between; align-items: center;
    padding: 10px 16px; background: #081A13; border-top: 1px solid #1A3A2A;
}
.eco-rot { font-size: 9px; color: #2E7A5A; letter-spacing: .16em; text-transform: uppercase; }
.eco-val { font-family: 'Inconsolata', monospace; font-size: 22px; font-weight: 800; color: var(--grn); }

/* CATÁLOGO */
.cat-linha {
    display: flex; justify-content: space-between; align-items: center;
    padding: 7px 16px; border-bottom: 1px solid var(--ln);
}
.cat-linha:last-child { border-bottom: none; }
.cat-nome { font-size: 12px; color: var(--txt); }
.cat-taxa { font-family: 'Inconsolata', monospace; font-size: 13px; font-weight: 700; color: var(--wht); }
.cat-taxa.best { color: var(--grn); }

/* BANNER DE SEÇÃO */
.sec-banner {
    display: flex; justify-content: space-between; align-items: center;
    padding: 6px 18px; background: var(--bg1);
    border-top: 1px solid var(--ln2); border-bottom: 1px solid var(--ln2); margin-bottom: 0;
}
.sec-banner-title { font-size: 9px; letter-spacing: .18em; text-transform: uppercase; font-weight: 700; color: var(--tx2); }
.sec-banner-info  { font-family: 'Inconsolata', monospace; font-size: 10px; color: var(--tx2); letter-spacing: .06em; }

/* FRAUDE */
.fraud-card { border-radius: 2px; overflow: hidden; border: 1px solid var(--ln2); margin-bottom: 10px; }
.fraud-card.crit  { border-color: #4A1A14; border-left: 4px solid var(--red); }
.fraud-card.alto  { border-color: #4A3010; border-left: 4px solid var(--amb); }
.fraud-card.medio { border-color: #2E3018; border-left: 4px solid #6A7820; }
.fraud-header { display: flex; justify-content: space-between; align-items: center; padding: 9px 14px; border-bottom: 1px solid; }
.fraud-header.crit  { background: #160A08; border-color: #4A1A14; }
.fraud-header.alto  { background: #120E06; border-color: #4A3010; }
.fraud-header.medio { background: #111306; border-color: #2E3018; }
.fraud-id { font-family: 'Inconsolata', monospace; font-size: 11px; font-weight: 700; letter-spacing: .06em; }
.fraud-id.crit  { color: #C89090; }
.fraud-id.alto  { color: #C8A870; }
.fraud-id.medio { color: #A8B060; }
.badge { font-family: 'Inconsolata', monospace; font-size: 9px; font-weight: 800; padding: 2px 8px; border-radius: 1px; letter-spacing: .08em; }
.badge.crit  { background: var(--red); color: #fff; }
.badge.alto  { background: var(--amb); color: #100800; }
.badge.medio { background: #6A7820; color: #fff; }
.fraud-body { padding: 12px 14px; }
.fraud-valor { font-family: 'Inconsolata', monospace; font-variant-numeric: tabular-nums; font-size: 26px; font-weight: 800; letter-spacing: -.02em; line-height: 1; }
.fraud-valor.crit  { color: var(--red); }
.fraud-valor.alto  { color: var(--amb); }
.fraud-valor.medio { color: #8A9840; }
.regra-pill { display: inline-block; font-family: 'Inconsolata', monospace; font-size: 10px; padding: 2px 7px; letter-spacing: .06em; margin: 3px 4px 0 0; border-radius: 1px; border: 1px solid; }
.regra-pill.crit  { border-color: #4A1A14; color: #A87070; }
.regra-pill.alto  { border-color: #4A3010; color: #A88848; }
.regra-pill.medio { border-color: #2E3018; color: #889040; }
.fraud-orient { margin-top: 10px; font-size: 12px; color: var(--tx2); line-height: 1.5; padding-top: 9px; border-top: 1px solid var(--ln); }

/* AUDITORIA */
.audit-card { background: var(--bg2); border: 1px solid var(--ln2); border-radius: 2px; padding: 12px 14px; height: 100%; }
.audit-label { font-size: 9px; letter-spacing: .18em; text-transform: uppercase; color: var(--tx2); margin-bottom: 6px; font-weight: 700; }
.audit-val { font-family: 'Inconsolata', monospace; font-size: 24px; font-weight: 800; color: var(--wht); }
.audit-val.neg { color: var(--red); }
.audit-val.amb { color: var(--amb); }

/* SELOS */
.selo { display: inline-block; padding: .14rem .5rem; border-radius: 2px; font-family: 'Inconsolata', monospace; font-size: .68rem; font-weight: 700; letter-spacing: .06em; }
.selo-critico { background: rgba(217,95,82,.15); color: var(--red); border: 1px solid rgba(217,95,82,.4); }
.selo-alto    { background: rgba(200,160,58,.12); color: var(--amb); border: 1px solid rgba(200,160,58,.35); }
.selo-medio   { background: rgba(106,120,32,.15); color: #8A9840; border: 1px solid rgba(106,120,32,.35); }
.selo-baixo   { background: rgba(62,201,167,.10); color: var(--grn); border: 1px solid rgba(62,201,167,.30); }

/* CHAT */
.motivo { border-left: 2px solid var(--ln2); padding: .1rem 0 .1rem .7rem; margin: .3rem 0; font-size: .85rem; color: var(--tx2); }
.codigo-regra { font-family: 'Inconsolata', monospace; font-size: .72rem; color: var(--grn); font-weight: 700; margin-right: .4rem; }
.orientacao { background: #081A13; border: 1px solid #1A3A2A; border-radius: 2px; padding: .6rem .8rem; font-size: .85rem; margin-top: .6rem; color: var(--txt); }

/* SIDEBAR */
.lat-item { display: flex; justify-content: space-between; align-items: baseline; padding: 6px 0; border-bottom: 1px solid var(--ln); }
.lat-rot { font-size: 12px; color: var(--tx2); }
.lat-val { font-family: 'Inconsolata', monospace; font-size: 13px; font-weight: 700; color: var(--wht); }

/* RODAPÉ */
.rodape { font-size: 11px; color: var(--ln2); border-top: 1px solid var(--ln2); padding-top: .8rem; margin-top: 2rem; font-style: italic; }
</style>
"""

st.markdown(ESTILO, unsafe_allow_html=True)

SUGESTOES = [
    "Tenho caixa para pagar a folha?",
    "Tem algum pagamento suspeito?",
    "Qual a linha de crédito mais barata?",
    "Como identificar um boleto adulterado?",
]
PROVEDORES = ["offline", "ollama", "groq", "gemini"]
CLASSE_SELO = {
    "CRITICO": "selo-critico", "ALTO": "selo-alto",
    "MEDIO": "selo-medio", "BAIXO": "selo-baixo",
}


# ─── Utilitários ──────────────────────────────────────────────────────────────

def md(texto: str) -> str:
    """Escapa cifrão para evitar interpretação LaTeX."""
    return texto.replace("$", r"\$")


@st.cache_resource(show_spinner=False)
def obter_agente(provider: str, modelo: str = "") -> AgenteMax:
    return AgenteMax(provider_nome=provider, modelo=modelo or None)


@st.cache_data(show_spinner=False, ttl=300)
def listar_modelos(provider: str) -> list[str]:
    return obter_agente(provider).provider.listar_modelos()


def topbar(provider: str, modelo: str, ativo: bool, critico: bool) -> None:
    pill_status = (
        f'<div class="topbar-pill ok">● {provider.upper()} · {modelo}</div>'
        if ativo
        else f'<div class="topbar-pill off">○ {provider.upper()} · {modelo}</div>'
    )
    pill_risco = (
        '<div class="topbar-pill crit">▲ RISCO CRÍTICO</div>'
        if critico
        else '<div class="topbar-pill off">◉ MONITORANDO</div>'
    )
    st.markdown(
        f'<div class="topbar">'
        f'<div class="topbar-logo"><span>MAX</span><sub>Motor de análise de exposição</sub></div>'
        f'<div class="topbar-nome">TechIndustrial Peças · Exercício 09/2026</div>'
        f'{pill_status}{pill_risco}'
        f"</div>",
        unsafe_allow_html=True,
    )
def ind_card(rotulo: str, valor: str, nota: str = "", classe: str = "") -> str:
    return (
        f'<div class="ind-card">'
        f'<div class="ind-label">{rotulo}</div>'
        f'<div class="ind-val {classe}">{valor}</div>'
        f'<div class="ind-note">{nota}</div>'
        f"</div>"
    )


def serie_diaria(contexto) -> pd.DataFrame:
    projecao = contexto.projecao_sem_suspeitos
    inicio = contexto.base.referencia
    if not projecao.eventos:
        return pd.DataFrame({"Data": [pd.Timestamp(inicio)], "Saldo": [projecao.saldo_inicial]})
    fim = projecao.eventos[-1].data
    por_dia = {ev.data: ev.saldo_apos for ev in projecao.eventos}
    linhas, saldo, dia = [], projecao.saldo_inicial, inicio
    while dia <= fim:
        if dia in por_dia:
            saldo = por_dia[dia]
        linhas.append({"Data": pd.Timestamp(dia), "Saldo": saldo})
        dia += timedelta(days=1)
    return pd.DataFrame(linhas)


def grafico_trajetoria(contexto):
    dados = serie_diaria(contexto)
    dados["Pos"] = dados["Saldo"].clip(lower=0)
    dados["Neg"] = dados["Saldo"].clip(upper=0)

    ax = alt.X("Data:T", title=None, axis=alt.Axis(
        format="%d/%m", labelColor="#4E6370", grid=False, tickColor="#232A2E",
    ))

    area_pos = (
        alt.Chart(dados).mark_area(opacity=0.20, color="#44C9AA", interpolate="step-after")
        .encode(x=ax, y=alt.Y("Pos:Q", title=None))
    )
    area_neg = (
        alt.Chart(dados).mark_area(opacity=0.20, color="#DC6355", interpolate="step-after")
        .encode(x=ax, y=alt.Y("Neg:Q", title=None))
    )
    linha = (
        alt.Chart(dados).mark_line(color="#44C9AA", strokeWidth=2.2, interpolate="step-after")
        .encode(
            x=ax,
            y=alt.Y("Saldo:Q", title=None, axis=alt.Axis(
                labelColor="#4E6370", gridColor="#1C2124", format="~s",
            )),
            tooltip=[
                alt.Tooltip("Data:T", title="Data", format="%d/%m/%Y"),
                alt.Tooltip("Saldo:Q", title="Saldo", format=",.2f"),
            ],
        )
    )
    zero = (
        alt.Chart(pd.DataFrame({"y": [0]}))
        .mark_rule(color="#232A2E", strokeDash=[4, 4], strokeWidth=1)
        .encode(y="y:Q")
    )
    return (area_pos + area_neg + zero + linha).properties(height=200)


# ─── Abas ─────────────────────────────────────────────────────────────────────

def aba_caixa(contexto) -> None:
    projecao = contexto.projecao_sem_suspeitos
    risco = contexto.risco

    liq = projecao.necessidade_caixa
    fra = risco["valor_em_risco"]
    total = liq + fra
    pct_liq = int(liq / total * 100) if total else 50
    pct_fra = 100 - pct_liq

    cls_pior = "neg" if projecao.pior_saldo < 0 else "pos"
    cls_liq  = "amb" if liq else "pos"
    cls_fra  = "neg" if fra else "pos"
    nota_pior = formatar_data(projecao.data_pior_saldo) if projecao.data_pior_saldo else "sem déficit"

    blocos = [
        ("",                                      "SALDO EM CONTA",        formatar_reais(projecao.saldo_inicial), "posição de hoje", ""),
        ("crit" if projecao.pior_saldo < 0 else "","PIOR SALDO PROJETADO", formatar_reais(projecao.pior_saldo),   nota_pior,         cls_pior),
        ("amb" if liq else "pos",                 "EXPOSIÇÃO DE LIQUIDEZ", formatar_reais(liq),                   "valor a cobrir",  cls_liq),
        ("crit" if fra else "pos",                "EXPOSIÇÃO A FRAUDE",    formatar_reais(fra),                   f"{risco['criticos']} crítico(s), {risco['altos']} alto(s)", cls_fra),
    ]
    html_blocos = "".join(
        f'<div class="ind-bloco {bg}">'
        f'<div class="ind-label">{lb}</div>'
        f'<div class="ind-val {cls}">{val}</div>'
        f'<div class="ind-note">{nota}</div>'
        f"</div>"
        for bg, lb, val, nota, cls in blocos
    )
    st.markdown(f'<div class="ind-strip">{html_blocos}</div>', unsafe_allow_html=True)

    if total:
        st.markdown(
            f'<div style="padding:8px 18px 2px;background:var(--bg0)">'
            f'<div class="comp-bar">'
            f'<div class="liq" style="width:{pct_liq}%"></div>'
            f'<div class="fra" style="width:{pct_fra}%"></div>'
            f'</div>'
            f'<div class="comp-labels">'
            f'<span class="comp-liq">LIQUIDEZ {formatar_reais(liq)}</span>'
            f'<span class="comp-fra">FRAUDE {formatar_reais(fra)}</span>'
            f'</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div class="chart-header"><span class="chart-title">Trajetória do saldo · 21 dias</span></div>',
        unsafe_allow_html=True,
    )
    st.altair_chart(grafico_trajetoria(contexto), width="stretch")

    if projecao.primeira_data_negativa:
        dias = (projecao.primeira_data_negativa - contexto.base.referencia).days
        st.warning(md(
            f"O saldo fica negativo em {dias} dia(s), a partir de "
            f"{formatar_data(projecao.primeira_data_negativa)}. "
            f"Cenário já considera a retenção dos suspeitos. "
            f"Sem a retenção, o pior saldo seria {formatar_reais(contexto.projecao.pior_saldo)}."
        ))

    st.write("")
    col_ag, col_cob = st.columns([1.6, 1], gap="large")

    with col_ag:
        st.markdown('<div class="sec-banner"><span class="sec-banner-title">Agenda do período</span></div>', unsafe_allow_html=True)
        cab = (
            '<div class="agenda-head">'
            '<span class="col-head" style="flex:0 0 72px">Data</span>'
            '<span class="col-head" style="flex:1">Lançamento</span>'
            '<span class="col-head" style="flex:0 0 106px">Centro</span>'
            '<span class="col-head" style="flex:0 0 100px;text-align:right">Valor</span>'
            '<span class="col-head" style="flex:0 0 94px;text-align:right">Saldo após</span>'
            '</div>'
        )
        linhas = []
        for ev in projecao.eventos:
            v = ev.valor if ev.tipo == "entrada" else -ev.valor
            cv = "pos" if v >= 0 else "neg"
            cs = "neg" if ev.saldo_apos < 0 else ""
            linhas.append(
                f'<div class="agenda-row">'
                f'<span class="agenda-data">{formatar_data(ev.data)}</span>'
                f'<span class="agenda-desc">{ev.descricao}</span>'
                f'<span class="agenda-cat">{ev.categoria}</span>'
                f'<span class="agenda-val {cv}">{formatar_reais(v)}</span>'
                f'<span class="agenda-saldo {cs}">{formatar_reais(ev.saldo_apos)}</span>'
                f"</div>"
            )
        st.markdown(f'<div class="agenda-wrap">{cab}{"".join(linhas)}</div>', unsafe_allow_html=True)

    with col_cob:
        st.markdown('<div class="sec-banner"><span class="sec-banner-title">Cobertura recomendada</span></div>', unsafe_allow_html=True)
        rec = contexto.recomendacao
        if not rec:
            st.success("Nenhuma contratação necessária no horizonte analisado.")
        else:
            itens_cob = [
                ("Valor sugerido",                        formatar_reais(rec["valor_sugerido"])),
                ("Custo em 30 dias",                      formatar_reais(rec["custo_mensal"])),
                (f"Custo pela {rec['alternativa_cara']}", formatar_reais(rec["custo_alternativa"])),
            ]
            linhas_cob = "".join(
                f'<div class="cob-linha"><span class="cob-rot">{r}</span><span class="cob-val">{v}</span></div>'
                for r, v in itens_cob
            )
            st.markdown(
                f'<div style="background:var(--bg2);border:1px solid var(--ln2);border-radius:2px;overflow:hidden">'
                f'<div class="cob-header">'
                f'<div><div class="cob-nome">{rec["nome"]}</div>'
                f'<div class="cob-sub">Liberação {rec["prazo_liberacao"]}</div></div>'
                f'<div class="cob-taxa">{rec["taxa_mensal"] * 100:.2f}%<sub>ao mês</sub></div>'
                f'</div>'
                f'{linhas_cob}'
                f'<div class="eco-strip">'
                f'<span class="eco-rot">Economia ao escolher certo</span>'
                f'<span class="eco-val">{formatar_reais(rec["economia_estimada"])}</span>'
                f'</div></div>',
                unsafe_allow_html=True,
            )

        st.write("")
        st.markdown('<div class="sec-banner"><span class="sec-banner-title">Catálogo de linhas</span></div>', unsafe_allow_html=True)
        linhas_cat = sorted(contexto.base.linhas_credito, key=lambda x: x["taxa_mensal"])
        html_cat = "".join(
            f'<div class="cat-linha">'
            f'<span class="cat-nome">{l["nome"]}</span>'
            f'<span class="cat-taxa {"best" if i == 0 else ""}">{float(l["taxa_mensal"]) * 100:.2f}%</span>'
            f"</div>"
            for i, l in enumerate(linhas_cat)
        )
        st.markdown(
            f'<div style="background:var(--bg2);border:1px solid var(--ln2);border-radius:2px">{html_cat}</div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div class="rodape">MAX · protótipo consultivo · não executa movimentação financeira · não fornece dados identificáveis</div>',
        unsafe_allow_html=True,
    )
def _renderizar_meta(meta: dict) -> None:
    if not meta:
        return
    if meta.get("bloqueado"):
        st.error(
            f"Solicitação interrompida pelo guardrail. "
            f"Categoria `{meta['categoria']}`, regra `{meta['regra']}`. "
            "Registrado na trilha de auditoria."
        )
    elif meta.get("substituiu"):
        st.warning(md("Resposta produzida pelo motor determinístico. " + meta.get("motivo", "")))
    elif meta.get("provider"):
        partes = [f"`{meta['provider']}` · `{meta['modelo']}` · {meta['latencia']} ms"]
        if meta.get("violacoes"):
            partes.append("verificações: " + "; ".join(meta["violacoes"]))
        st.caption(" | ".join(partes))


def _renderizar_mensagem(mensagem: dict) -> None:
    with st.chat_message(mensagem["role"]):
        st.markdown(md(mensagem["content"]))
        _renderizar_meta(mensagem.get("meta", {}))


def aba_conversa(agente: AgenteMax, contexto) -> None:
    if "mensagens" not in st.session_state:
        st.session_state.mensagens = [
            {"role": "assistant", "content": mensagem_de_abertura(contexto)}
        ]

    historico_box = st.container()

    st.caption("Sugestões")
    cols = st.columns(len(SUGESTOES))
    escolhida = None
    for col, sug in zip(cols, SUGESTOES):
        if col.button(sug, width="stretch", key=f"sug_{sug}"):
            escolhida = sug

    digitada = st.chat_input("Pergunte sobre caixa, crédito ou segurança")
    pergunta = escolhida or digitada

    with historico_box:
        for mensagem in st.session_state.mensagens:
            _renderizar_mensagem(mensagem)

        if not pergunta:
            return

        st.session_state.mensagens.append({"role": "user", "content": pergunta})
        _renderizar_mensagem(st.session_state.mensagens[-1])

        historico = [
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state.mensagens[:-1]
        ]

        with st.chat_message("assistant"):
            rotulo = (
                "Consultando o modelo. Em modelo local isso pode levar minutos"
                if agente.provider.nome != "offline"
                else "Analisando"
            )
            with st.spinner(rotulo):
                resposta = agente.responder(pergunta, historico)

            meta = {
                "bloqueado": resposta.bloqueado,
                "categoria": resposta.categoria,
                "regra": resposta.regra,
                "substituiu": resposta.substituiu_por_deterministico,
                "motivo": resposta.motivo_substituicao,
                "provider": resposta.provider,
                "modelo": resposta.modelo,
                "latencia": resposta.latencia_ms,
                "violacoes": resposta.violacoes,
            }
            st.markdown(md(resposta.texto))
            _renderizar_meta(meta)

    st.session_state.mensagens.append(
        {"role": "assistant", "content": resposta.texto, "meta": meta}
    )


def aba_seguranca(contexto) -> None:
    st.markdown('<div class="sec-title">Pagamentos pendentes sob análise</div>', unsafe_allow_html=True)
    st.caption(
        "Pontuação determinística calculada em código. "
        "Cada alerta carrega a regra que o originou, permitindo auditoria sem depender do modelo."
    )

    for analise in contexto.analises:
        cls = analise.classificacao.lower()
        cabecalho = (
            f"{analise.transacao_id} · {analise.descricao} · "
            f"{formatar_reais(analise.valor)} · {formatar_data(analise.data)}"
        )
        with st.expander(cabecalho, expanded=analise.suspeito):
            st.markdown(
                f'<span class="selo {CLASSE_SELO[analise.classificacao]}">'
                f"{analise.classificacao} · {analise.pontuacao}/100</span>",
                unsafe_allow_html=True,
            )
            st.markdown(f"**Beneficiário:** {analise.beneficiario}")
            if not analise.alertas:
                st.markdown('<div class="motivo">Nenhum sinal de risco identificado.</div>', unsafe_allow_html=True)
            for alerta in analise.alertas:
                st.markdown(
                    f'<div class="motivo">'
                    f'<span class="codigo-regra">{alerta.regra}</span>'
                    f"<strong>{alerta.titulo}</strong> · +{alerta.peso} pontos<br>{alerta.detalhe}"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            if analise.orientacao:
                st.markdown(f'<div class="orientacao">{analise.orientacao}</div>', unsafe_allow_html=True)

    st.write("")
    st.markdown('<div class="sec-title">Base de conhecimento sobre golpes</div>', unsafe_allow_html=True)
    kb = obter_base()
    st.caption(
        f"{len(kb.documentos())} documentos indexados em {len(kb.trechos)} trechos, "
        "recuperados por TF-IDF com similaridade de cosseno."
    )
    st.markdown("\n".join(f"- {n.replace('-', ' ').capitalize()}" for n in kb.documentos()))


def aba_auditoria() -> None:
    est = audit.estatisticas()
    cols = st.columns(5, gap="small")
    indicadores = [
        ("Interações",      str(est["total"]),               ""),
        ("Bloqueios",       str(est["bloqueios"]),           "neg"),
        ("Prompt injection",str(est["injecoes"]),            "neg"),
        ("Dados mascarados",str(est["mascaramentos"]),       "amb"),
        ("Latência média",  f"{est['latencia_media_ms']} ms",""),
    ]
    for col, (rot, val, cls) in zip(cols, indicadores):
        with col:
            st.markdown(
                f'<div class="audit-card">'
                f'<div class="audit-label">{rot}</div>'
                f'<div class="audit-val {cls}">{val}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )

    st.write("")
    st.markdown('<div class="sec-title">Trilha de auditoria</div>', unsafe_allow_html=True)
    st.caption(
        "Cada interação é registrada em logs/auditoria.jsonl após o mascaramento de dados identificáveis. "
        "Nenhum dado pessoal é gravado em texto puro."
    )

    registros = audit.ler_registros(limite=100)
    if not registros:
        st.info("Sem registros nesta sessão. Faça uma pergunta na aba Consultoria.")
        return

    tabela = pd.DataFrame([
        {
            "Momento":      r["momento"].replace("T", " "),
            "Categoria":    r["categoria"],
            "Regra":        r["regra"] or "—",
            "Bloqueado":    "sim" if r["bloqueado"] else "não",
            "Ancoragem":    "ok" if r["ancoragem_ok"] else "falhou",
            "Latência (ms)":r["latencia_ms"],
            "Mensagem":     r["mensagem"],
        }
        for r in registros
    ])
    st.dataframe(tabela, hide_index=True, width="stretch", height=380)

    if st.button("Limpar trilha de auditoria"):
        audit.limpar()
        st.rerun()


def barra_lateral():
    with st.sidebar:
        st.markdown("#### Execução")
        indice = PROVEDORES.index(config.PROVIDER) if config.PROVIDER in PROVEDORES else 0
        provider = st.selectbox(
            "Provedor de modelo", options=PROVEDORES, index=indice,
            help="O modo offline usa o motor determinístico e não exige chave de API.",
        )

        agente = obter_agente(provider)
        modelo_escolhido = ""

        if provider != "offline":
            disponiveis = listar_modelos(provider)
            if disponiveis:
                padrao = agente.provider.modelo
                idx = disponiveis.index(padrao) if padrao in disponiveis else 0
                modelo_escolhido = st.selectbox(
                    "Modelo", options=disponiveis, index=idx,
                    help="Lista obtida do provedor em tempo real.",
                )
                agente = obter_agente(provider, modelo_escolhido)
            else:
                st.caption(f"Não foi possível listar os modelos. Usando `{agente.provider.modelo}`.")

        if provider == "offline":
            st.info("Motor determinístico. Nenhuma chamada externa.")
        elif agente.provider.disponivel():
            st.success(f"`{agente.provider.nome}` · `{agente.provider.modelo}`")
            st.caption(f"Tempo limite de {config.TIMEOUT_LLM}s por resposta.")
        else:
            st.warning(
                f"`{agente.provider.nome}` indisponível. "
                "As respostas usarão o motor determinístico e o motivo aparecerá no chat."
            )

        if provider != "offline" and st.button("Testar o provedor", width="stretch"):
            with st.spinner("Enviando uma requisição de teste"):
                teste = agente.provider.gerar("Responda apenas com a palavra ok.", "", "teste de conexao", [])
            if teste.texto:
                st.success(f"Resposta em {teste.latencia_ms} ms: {teste.texto[:80]}")
            else:
                st.error(teste.erro or "O provedor não retornou conteúdo.")

        contexto = agente.preparar_contexto()
        perfil = contexto.base.perfil

        st.divider()
        st.markdown("#### Cliente")
        st.markdown(f"**{perfil['razao_social']}**  \n{perfil['setor']} · {perfil['porte']}")

        itens = [
            ("Perfil de risco",     perfil["perfil_risco"]),
            ("Faturamento mensal",  formatar_reais(perfil["faturamento_medio_mensal"])),
            ("Custo fixo mensal",   formatar_reais(perfil["custo_fixo_mensal"])),
            ("Alçada de aprovação", formatar_reais(perfil["alcada_aprovacao_pagamento"])),
            ("Horizonte de análise",f"{config.HORIZONTE_DIAS} dias"),
        ]
        st.markdown(
            "".join(
                f'<div class="lat-item">'
                f'<span class="lat-rot">{r}</span>'
                f'<span class="lat-val">{v}</span>'
                f"</div>"
                for r, v in itens
            ),
            unsafe_allow_html=True,
        )

        st.divider()
        st.caption(
            "Dados fictícios criados para o desafio DIO e Bradesco. "
            "Nenhuma informação real de cliente é utilizada."
        )

    return agente, contexto


def main() -> None:
    agente, contexto = barra_lateral()

    critico = contexto.risco.get("criticos", 0) > 0 or contexto.risco.get("altos", 0) > 0
    topbar(
        agente.provider.nome,
        agente.provider.modelo,
        agente.provider.disponivel(),
        critico,
    )

    caixa, conversa, seguranca, auditoria = st.tabs(
        ["Caixa", "Consultoria", "Segurança", "Auditoria"]
    )
    with caixa:
        aba_caixa(contexto)
    with conversa:
        aba_conversa(agente, contexto)
    with seguranca:
        aba_seguranca(contexto)
    with auditoria:
        aba_auditoria()


main()
