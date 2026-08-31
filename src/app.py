"""Interface do MAX.

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

ESTILO = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@500;700&display=swap');

:root {
    --aco-800: #18222E;
    --aco-700: #22303F;
    --borda: #2A3847;
    --texto: #E6EDF5;
    --texto-fraco: #8A9BAE;
    --seguro: #35C39A;
    --atencao: #F5A524;
    --alerta: #E5484D;
    --dado: #4C8DFF;
}

html, body, .stApp, .stMarkdown, .stText { font-family: 'Inter', sans-serif; }

[data-testid="stIconMaterial"],
.material-icons, .material-icons-outlined,
.material-symbols-rounded, .material-symbols-outlined {
    font-family: 'Material Symbols Rounded', 'Material Icons' !important;
    font-feature-settings: 'liga';
    letter-spacing: normal !important;
}
h1, h2, h3 { font-family: 'Space Grotesk', sans-serif; letter-spacing: -0.02em; }
h3 { font-size: 1.05rem !important; margin-bottom: .5rem !important; }

#MainMenu, header, footer { visibility: hidden; }
.block-container { padding-top: 2.2rem; padding-bottom: 2rem; max-width: 1440px; }

.marca {
    display: flex; align-items: baseline; gap: .8rem;
    border-bottom: 1px solid var(--borda); padding-bottom: .9rem; margin-bottom: 1.4rem;
}
.marca-sigla {
    font-family: 'Space Grotesk', sans-serif; font-size: 2.1rem; font-weight: 700;
    letter-spacing: -0.04em; color: var(--texto);
}
.marca-nome {
    font-size: .82rem; color: var(--texto-fraco);
    letter-spacing: .09em; text-transform: uppercase;
}

.painel {
    background: var(--aco-800); border: 1px solid var(--borda);
    border-radius: 10px; padding: 1rem 1.15rem; height: 100%;
}
.painel-rotulo {
    font-size: .68rem; letter-spacing: .11em; text-transform: uppercase;
    color: var(--texto-fraco); margin-bottom: .4rem;
}
.painel-valor {
    font-family: 'JetBrains Mono', monospace; font-size: 1.42rem; font-weight: 700;
    line-height: 1.15; color: var(--texto);
}
.painel-nota { font-size: .75rem; color: var(--texto-fraco); margin-top: .3rem; }
.negativo { color: var(--alerta); }
.positivo { color: var(--seguro); }
.aviso { color: var(--atencao); }

.lateral-item {
    display: flex; justify-content: space-between; align-items: baseline;
    padding: .34rem 0; border-bottom: 1px solid rgba(42,56,71,.55);
}
.lateral-rotulo { font-size: .76rem; color: var(--texto-fraco); }
.lateral-valor {
    font-family: 'JetBrains Mono', monospace; font-size: .84rem;
    font-weight: 700; color: var(--texto);
}

.selo {
    display: inline-block; padding: .16rem .55rem; border-radius: 4px;
    font-family: 'JetBrains Mono', monospace; font-size: .68rem; font-weight: 700;
    letter-spacing: .06em;
}
.selo-critico { background: rgba(229,72,77,.16); color: var(--alerta); border: 1px solid rgba(229,72,77,.4); }
.selo-alto { background: rgba(229,72,77,.10); color: var(--alerta); border: 1px solid rgba(229,72,77,.28); }
.selo-medio { background: rgba(245,165,36,.13); color: var(--atencao); border: 1px solid rgba(245,165,36,.34); }
.selo-baixo { background: rgba(53,195,154,.12); color: var(--seguro); border: 1px solid rgba(53,195,154,.3); }

.cobertura-linha {
    display: flex; justify-content: space-between; align-items: baseline;
    padding: .4rem 0; border-bottom: 1px solid rgba(42,56,71,.55);
}
.cobertura-rotulo { font-size: .8rem; color: var(--texto-fraco); }
.cobertura-valor {
    font-family: 'JetBrains Mono', monospace; font-size: .95rem;
    font-weight: 700; color: var(--texto);
}
.cobertura-titulo {
    font-family: 'Space Grotesk', sans-serif; font-size: 1rem; font-weight: 700;
    color: var(--texto); margin-bottom: .15rem;
}
.cobertura-sub { font-size: .78rem; color: var(--texto-fraco); margin-bottom: .7rem; }

.motivo {
    border-left: 2px solid var(--borda); padding: .1rem 0 .1rem .7rem;
    margin: .3rem 0; font-size: .86rem; color: var(--texto-fraco);
}
.codigo-regra {
    font-family: 'JetBrains Mono', monospace; font-size: .72rem;
    color: var(--dado); font-weight: 700; margin-right: .4rem;
}
.orientacao {
    background: rgba(76,141,255,.08); border: 1px solid rgba(76,141,255,.24);
    border-radius: 6px; padding: .65rem .8rem; font-size: .86rem; margin-top: .6rem;
}
.rodape-nota {
    font-size: .74rem; color: var(--texto-fraco); border-top: 1px solid var(--borda);
    padding-top: .8rem; margin-top: 1.6rem;
}
</style>
"""

st.markdown(ESTILO, unsafe_allow_html=True)

CLASSE_SELO = {
    "CRITICO": "selo-critico",
    "ALTO": "selo-alto",
    "MEDIO": "selo-medio",
    "BAIXO": "selo-baixo",
}

SUGESTOES = [
    "Tenho caixa para pagar a folha?",
    "Tem algum pagamento suspeito?",
    "Qual a linha de crédito mais barata?",
    "Como identificar um boleto adulterado?",
]

PROVEDORES = ["offline", "ollama", "groq", "gemini"]


def md(texto: str) -> str:
    """Escapa o cifrao para o Streamlit nao interpretar o trecho como formula LaTeX."""
    return texto.replace("$", r"\$")


@st.cache_resource(show_spinner=False)
def obter_agente(provider: str, modelo: str = "") -> AgenteMax:
    return AgenteMax(provider_nome=provider, modelo=modelo or None)


@st.cache_data(show_spinner=False, ttl=300)
def listar_modelos(provider: str) -> list[str]:
    return obter_agente(provider).provider.listar_modelos()


def cartao(rotulo: str, valor: str, nota: str = "", classe: str = "") -> str:
    return (
        f'<div class="painel"><div class="painel-rotulo">{rotulo}</div>'
        f'<div class="painel-valor {classe}">{valor}</div>'
        f'<div class="painel-nota">{nota}</div></div>'
    )


def serie_diaria(contexto) -> pd.DataFrame:
    """Constroi o saldo acumulado por dia para o grafico de trajetoria."""
    projecao = contexto.projecao_sem_suspeitos
    inicio = contexto.base.referencia
    if not projecao.eventos:
        return pd.DataFrame({"Data": [inicio], "Saldo": [projecao.saldo_inicial]})

    fim = projecao.eventos[-1].data
    por_dia: dict = {}
    for evento in projecao.eventos:
        por_dia[evento.data] = evento.saldo_apos

    linhas = []
    saldo = projecao.saldo_inicial
    dia = inicio
    while dia <= fim:
        if dia in por_dia:
            saldo = por_dia[dia]
        linhas.append({"Data": pd.Timestamp(dia), "Saldo": saldo})
        dia += timedelta(days=1)
    return pd.DataFrame(linhas)


def grafico_trajetoria(contexto):
    dados = serie_diaria(contexto)
    dados["Positivo"] = dados["Saldo"].clip(lower=0)
    dados["Negativo"] = dados["Saldo"].clip(upper=0)

    eixo_x = alt.X(
        "Data:T",
        title=None,
        axis=alt.Axis(format="%d/%m", labelColor="#8A9BAE", grid=False, tickColor="#2A3847"),
    )

    area_positiva = (
        alt.Chart(dados)
        .mark_area(opacity=0.30, color="#35C39A", interpolate="step-after")
        .encode(x=eixo_x, y=alt.Y("Positivo:Q", title=None))
    )
    area_negativa = (
        alt.Chart(dados)
        .mark_area(opacity=0.30, color="#E5484D", interpolate="step-after")
        .encode(x=eixo_x, y=alt.Y("Negativo:Q", title=None))
    )
    linha = (
        alt.Chart(dados)
        .mark_line(color="#E6EDF5", strokeWidth=2, interpolate="step-after")
        .encode(
            x=eixo_x,
            y=alt.Y(
                "Saldo:Q",
                title=None,
                axis=alt.Axis(labelColor="#8A9BAE", gridColor="#22303F", format="~s"),
            ),
            tooltip=[
                alt.Tooltip("Data:T", title="Data", format="%d/%m/%Y"),
                alt.Tooltip("Saldo:Q", title="Saldo", format=",.2f"),
            ],
        )
    )
    zero = (
        alt.Chart(pd.DataFrame({"y": [0]}))
        .mark_rule(color="#8A9BAE", strokeDash=[4, 4], strokeWidth=1)
        .encode(y="y:Q")
    )

    return (area_positiva + area_negativa + zero + linha).properties(height=210)


def tabela_agenda(contexto):
    projecao = contexto.projecao_sem_suspeitos
    dados = pd.DataFrame(
        [
            {
                "Data": formatar_data(evento.data),
                "Lançamento": evento.descricao,
                "Centro de custo": evento.categoria,
                "Valor": evento.valor if evento.tipo == "entrada" else -evento.valor,
                "Saldo após": evento.saldo_apos,
            }
            for evento in projecao.eventos
        ]
    )

    def cor(valor: float) -> str:
        return "color: #FF8A8D;" if valor < 0 else "color: #5FD9B6;"

    return (
        dados.style.format({"Valor": formatar_reais, "Saldo após": formatar_reais})
        .map(cor, subset=["Valor", "Saldo após"])
        .set_properties(
            **{"font-family": "JetBrains Mono, monospace"},
            subset=["Valor", "Saldo após"],
        )
    )


def aba_caixa(contexto) -> None:
    projecao = contexto.projecao_sem_suspeitos
    colunas = st.columns(4)

    with colunas[0]:
        st.markdown(
            cartao("Saldo em conta", formatar_reais(projecao.saldo_inicial), "posição de hoje"),
            unsafe_allow_html=True,
        )
    with colunas[1]:
        classe = "negativo" if projecao.pior_saldo < 0 else "positivo"
        nota = (
            f"em {formatar_data(projecao.data_pior_saldo)}"
            if projecao.data_pior_saldo
            else "sem déficit no período"
        )
        st.markdown(
            cartao("Pior saldo projetado", formatar_reais(projecao.pior_saldo), nota, classe),
            unsafe_allow_html=True,
        )
    with colunas[2]:
        st.markdown(
            cartao(
                "Exposição de liquidez",
                formatar_reais(projecao.necessidade_caixa),
                "valor a cobrir",
                "aviso" if projecao.necessidade_caixa else "positivo",
            ),
            unsafe_allow_html=True,
        )
    with colunas[3]:
        st.markdown(
            cartao(
                "Exposição a fraude",
                formatar_reais(contexto.risco["valor_em_risco"]),
                f"{contexto.risco['criticos']} crítico(s), {contexto.risco['altos']} alto(s)",
                "negativo" if contexto.risco["valor_em_risco"] else "positivo",
            ),
            unsafe_allow_html=True,
        )

    st.markdown("### Trajetória do saldo")
    st.altair_chart(grafico_trajetoria(contexto), width="stretch")

    if projecao.primeira_data_negativa:
        dias = (projecao.primeira_data_negativa - contexto.base.referencia).days
        st.warning(
            md(
                f"O saldo fica negativo em {dias} dia(s), a partir de "
                f"{formatar_data(projecao.primeira_data_negativa)}. O cenário já considera a "
                f"retenção dos pagamentos suspeitos. Sem a retenção, o pior saldo seria "
                f"{formatar_reais(contexto.projecao.pior_saldo)}."
            )
        )

    esquerda, direita = st.columns([1.5, 1], gap="large")

    with esquerda:
        st.markdown("### Agenda do período")
        st.dataframe(tabela_agenda(contexto), hide_index=True, width="stretch")

    with direita:
        st.markdown("### Cobertura recomendada")
        recomendacao = contexto.recomendacao
        if not recomendacao:
            st.success("Nenhuma contratação necessária no horizonte analisado.")
        else:
            itens = [
                ("Valor sugerido", formatar_reais(recomendacao["valor_sugerido"])),
                ("Custo em 30 dias", formatar_reais(recomendacao["custo_mensal"])),
                (
                    f"Custo pela {recomendacao['alternativa_cara']}",
                    formatar_reais(recomendacao["custo_alternativa"]),
                ),
            ]
            corpo = "".join(
                f'<div class="cobertura-linha"><span class="cobertura-rotulo">{rotulo}</span>'
                f'<span class="cobertura-valor">{valor}</span></div>'
                for rotulo, valor in itens
            )
            st.markdown(
                f'<div class="painel">'
                f'<div class="cobertura-titulo">{recomendacao["nome"]}</div>'
                f'<div class="cobertura-sub">Taxa {recomendacao["taxa_mensal"] * 100:.2f}% ao mês '
                f'· liberação {recomendacao["prazo_liberacao"]}</div>'
                f"{corpo}</div>",
                unsafe_allow_html=True,
            )
            st.write("")
            diferenca = (
                recomendacao["taxa_alternativa"] - recomendacao["taxa_mensal"]
            ) * 100
            st.metric(
                "Economia ao escolher a linha certa",
                formatar_reais(recomendacao["economia_estimada"]),
                delta=f"{diferenca:.2f} p.p. de taxa evitados",
            )

        st.divider()
        st.markdown("### Catálogo de linhas")
        catalogo = pd.DataFrame(
            [
                {
                    "Linha": linha["nome"],
                    "Taxa a.m.": float(linha["taxa_mensal"]) * 100,
                    "Limite": float(linha["limite_disponivel"]),
                }
                for linha in sorted(
                    contexto.base.linhas_credito, key=lambda item: item["taxa_mensal"]
                )
            ]
        )
        st.dataframe(
            catalogo.style.format({"Taxa a.m.": "{:.2f}%", "Limite": formatar_reais}),
            hide_index=True,
            width="stretch",
        )


def _renderizar_meta(meta: dict) -> None:
    if not meta:
        return
    if meta.get("bloqueado"):
        st.error(
            f"Solicitação interrompida pelo guardrail de entrada. "
            f"Categoria `{meta['categoria']}`, regra `{meta['regra']}`. "
            "O evento consta na trilha de auditoria."
        )
    elif meta.get("substituiu"):
        st.warning(
            md(
                "Resposta produzida pelo motor determinístico, não pelo modelo. "
                + meta.get("motivo", "")
            )
        )
    elif meta.get("provider"):
        detalhes = [f"`{meta['provider']}` · `{meta['modelo']}` · {meta['latencia']} ms"]
        if meta.get("violacoes"):
            detalhes.append("verificações: " + "; ".join(meta["violacoes"]))
        st.caption(" | ".join(detalhes))


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
    colunas = st.columns(len(SUGESTOES))
    escolhida = None
    for coluna, sugestao in zip(colunas, SUGESTOES):
        if coluna.button(sugestao, width="stretch", key=f"sugestao_{sugestao}"):
            escolhida = sugestao

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
    st.markdown("### Pagamentos pendentes sob análise")
    st.caption(
        "Pontuação determinística calculada em código. Cada alerta carrega a regra que o "
        "originou, permitindo auditoria sem depender do modelo de linguagem."
    )

    for analise in contexto.analises:
        selo = (
            f'<span class="selo {CLASSE_SELO[analise.classificacao]}">'
            f"{analise.classificacao} · {analise.pontuacao}/100</span>"
        )
        cabecalho = (
            f"{analise.transacao_id} · {analise.descricao} · "
            f"{formatar_reais(analise.valor)} · {formatar_data(analise.data)}"
        )
        with st.expander(cabecalho, expanded=analise.suspeito):
            st.markdown(selo, unsafe_allow_html=True)
            st.markdown(f"**Beneficiário:** {analise.beneficiario}")
            if not analise.alertas:
                st.markdown(
                    '<div class="motivo">Nenhum sinal de risco identificado.</div>',
                    unsafe_allow_html=True,
                )
            for alerta in analise.alertas:
                st.markdown(
                    f'<div class="motivo"><span class="codigo-regra">{alerta.regra}</span>'
                    f"<strong>{alerta.titulo}</strong> · +{alerta.peso} pontos<br>"
                    f"{alerta.detalhe}</div>",
                    unsafe_allow_html=True,
                )
            if analise.orientacao:
                st.markdown(
                    f'<div class="orientacao">{analise.orientacao}</div>',
                    unsafe_allow_html=True,
                )

    st.markdown("### Base de conhecimento sobre golpes")
    kb = obter_base()
    st.caption(
        f"{len(kb.documentos())} documentos indexados em {len(kb.trechos)} trechos, "
        "recuperados por TF-IDF com similaridade de cosseno."
    )
    st.markdown(
        "\n".join(f"- {nome.replace('-', ' ').capitalize()}" for nome in kb.documentos())
    )


def aba_auditoria() -> None:
    estatisticas = audit.estatisticas()
    colunas = st.columns(5)
    indicadores = [
        ("Interações", str(estatisticas["total"]), ""),
        ("Bloqueios", str(estatisticas["bloqueios"]), "negativo"),
        ("Prompt injection", str(estatisticas["injecoes"]), "negativo"),
        ("Dados mascarados", str(estatisticas["mascaramentos"]), "aviso"),
        ("Latência média", f"{estatisticas['latencia_media_ms']} ms", ""),
    ]
    for coluna, (rotulo, valor, classe) in zip(colunas, indicadores):
        with coluna:
            st.markdown(cartao(rotulo, valor, "", classe), unsafe_allow_html=True)

    st.markdown("### Trilha de auditoria")
    st.caption(
        "Cada interação é registrada em logs/auditoria.jsonl após o mascaramento de dados "
        "identificáveis. Nenhum dado pessoal é gravado em texto puro."
    )

    registros = audit.ler_registros(limite=100)
    if not registros:
        st.info("Sem registros nesta sessão. Faça uma pergunta na aba Consultoria.")
        return

    tabela = pd.DataFrame(
        [
            {
                "Momento": registro["momento"].replace("T", " "),
                "Categoria": registro["categoria"],
                "Regra": registro["regra"] or "—",
                "Bloqueado": "sim" if registro["bloqueado"] else "não",
                "Ancoragem": "ok" if registro["ancoragem_ok"] else "falhou",
                "Latência (ms)": registro["latencia_ms"],
                "Mensagem": registro["mensagem"],
            }
            for registro in registros
        ]
    )
    st.dataframe(tabela, hide_index=True, width="stretch", height=380)

    if st.button("Limpar trilha de auditoria"):
        audit.limpar()
        st.rerun()


def barra_lateral():
    with st.sidebar:
        st.markdown("#### Execução")
        indice = PROVEDORES.index(config.PROVIDER) if config.PROVIDER in PROVEDORES else 0
        provider = st.selectbox(
            "Provedor de modelo",
            options=PROVEDORES,
            index=indice,
            help=(
                "O modo offline usa o motor determinístico e não exige chave de API. "
                "Os demais exigem Ollama local ou chave configurada no arquivo .env."
            ),
        )

        agente = obter_agente(provider)

        modelo_escolhido = ""
        if provider != "offline":
            disponiveis = listar_modelos(provider)
            if disponiveis:
                padrao = agente.provider.modelo
                indice_modelo = (
                    disponiveis.index(padrao) if padrao in disponiveis else 0
                )
                modelo_escolhido = st.selectbox(
                    "Modelo",
                    options=disponiveis,
                    index=indice_modelo,
                    help="Lista obtida do provedor em tempo real.",
                )
                agente = obter_agente(provider, modelo_escolhido)
            else:
                st.caption(
                    "Não foi possível listar os modelos do provedor. "
                    f"Usando `{agente.provider.modelo}`."
                )

        if provider == "offline":
            st.info("Motor determinístico. Nenhuma chamada externa.")
        elif agente.provider.disponivel():
            st.success(f"`{agente.provider.nome}` · `{agente.provider.modelo}`")
            st.caption(f"Tempo limite de {config.TIMEOUT_LLM}s por resposta.")
        else:
            st.warning(
                f"`{agente.provider.nome}` indisponível. As respostas usarão o motor "
                "determinístico e o motivo aparecerá no chat."
            )

        if provider != "offline" and st.button("Testar o provedor", width="stretch"):
            with st.spinner("Enviando uma requisição de teste"):
                teste = agente.provider.gerar(
                    "Responda apenas com a palavra ok.", "", "teste de conexao", []
                )
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
            ("Perfil de risco", perfil["perfil_risco"]),
            ("Faturamento mensal", formatar_reais(perfil["faturamento_medio_mensal"])),
            ("Custo fixo mensal", formatar_reais(perfil["custo_fixo_mensal"])),
            ("Alçada de aprovação", formatar_reais(perfil["alcada_aprovacao_pagamento"])),
            ("Horizonte de análise", f"{config.HORIZONTE_DIAS} dias"),
        ]
        st.markdown(
            "".join(
                f'<div class="lateral-item"><span class="lateral-rotulo">{rotulo}</span>'
                f'<span class="lateral-valor">{valor}</span></div>'
                for rotulo, valor in itens
            ),
            unsafe_allow_html=True,
        )

        st.divider()
        st.caption(
            "Dados fictícios criados para o desafio DIO e Bradesco. Nenhuma informação "
            "real de cliente é utilizada."
        )

    return agente, contexto


def main() -> None:
    agente, contexto = barra_lateral()

    st.markdown(
        '<div class="marca"><span class="marca-sigla">MAX</span>'
        '<span class="marca-nome">Motor de Análise de Exposição</span></div>',
        unsafe_allow_html=True,
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

    st.markdown(
        '<div class="rodape-nota">O MAX é um protótipo consultivo. Não executa '
        "movimentação financeira, não fornece dados identificáveis e não substitui os "
        "controles internos da empresa.</div>",
        unsafe_allow_html=True,
    )


main()
