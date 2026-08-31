"""Carregamento da base de conhecimento estruturada e projecao de fluxo de caixa.

Todo calculo numerico exibido ao usuario nasce aqui. O modelo de linguagem nunca
executa aritmetica: ele recebe resultados prontos e apenas os interpreta.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd

from . import config


@dataclass
class EventoCaixa:
    data: date
    descricao: str
    categoria: str
    valor: float
    tipo: str
    status: str
    saldo_apos: float
    transacao_id: str


@dataclass
class ProjecaoCaixa:
    saldo_inicial: float
    horizonte_dias: int
    eventos: list[EventoCaixa]
    saldo_final: float
    pior_saldo: float
    data_pior_saldo: date | None
    primeira_data_negativa: date | None
    necessidade_caixa: float
    total_entradas: float
    total_saidas: float


@dataclass
class BaseEstruturada:
    perfil: dict[str, Any]
    transacoes: pd.DataFrame
    beneficiarios: pd.DataFrame
    linhas_credito: list[dict[str, Any]]
    historico: pd.DataFrame
    referencia: date
    deslocamento_dias: int = 0
    metadados: dict[str, Any] = field(default_factory=dict)


def _ler_json(nome: str) -> Any:
    caminho = config.DATA_DIR / nome
    with caminho.open(encoding="utf-8") as arquivo:
        return json.load(arquivo)


def _deslocar_datas(df: pd.DataFrame, colunas: list[str], delta: timedelta) -> pd.DataFrame:
    for coluna in colunas:
        if coluna in df.columns:
            df[coluna] = pd.to_datetime(df[coluna], errors="coerce") + delta
    return df


def carregar_base(referencia: date | None = None) -> BaseEstruturada:
    """Le os arquivos de dados e reposiciona as datas em relacao ao dia corrente.

    O deslocamento mantem os intervalos originais entre lancamentos e garante que o
    cenario de teste permaneca valido em qualquer data de execucao.
    """
    referencia = referencia or date.today()

    perfil = _ler_json("perfil_empresa.json")
    linhas_credito = _ler_json("linhas_credito.json")

    transacoes = pd.read_csv(config.DATA_DIR / "transacoes.csv")
    beneficiarios = pd.read_csv(config.DATA_DIR / "beneficiarios.csv")
    historico = pd.read_csv(config.DATA_DIR / "historico_atendimento.csv")

    transacoes["data"] = pd.to_datetime(transacoes["data"])
    ancora = transacoes["data"].min()
    alvo = pd.Timestamp(referencia) - pd.Timedelta(days=config.DIAS_ANCORA_PASSADO)
    delta = alvo - ancora

    transacoes["data"] = transacoes["data"] + delta
    beneficiarios = _deslocar_datas(
        beneficiarios, ["data_cadastro", "ultima_alteracao_conta"], delta
    )
    historico = _deslocar_datas(historico, ["data_atendimento"], delta)

    transacoes = transacoes.sort_values(["data", "transacao_id"]).reset_index(drop=True)
    transacoes["beneficiario_id"] = transacoes["beneficiario_id"].fillna("")

    return BaseEstruturada(
        perfil=perfil,
        transacoes=transacoes,
        beneficiarios=beneficiarios,
        linhas_credito=linhas_credito,
        historico=historico,
        referencia=referencia,
        deslocamento_dias=int(delta.days),
        metadados={"registros": len(transacoes), "beneficiarios": len(beneficiarios)},
    )


def projetar_caixa(
    base: BaseEstruturada,
    horizonte_dias: int | None = None,
    excluir: set[str] | None = None,
) -> ProjecaoCaixa:
    """Calcula o saldo acumulado dia a dia dentro do horizonte informado.

    O parametro ``excluir`` permite simular a retencao de pagamentos suspeitos.
    """
    horizonte_dias = horizonte_dias or config.HORIZONTE_DIAS
    excluir = excluir or set()

    limite = pd.Timestamp(base.referencia) + pd.Timedelta(days=horizonte_dias)
    pendentes = base.transacoes[
        (base.transacoes["status"].isin(["agendado", "previsto"]))
        & (base.transacoes["data"] <= limite)
        & (~base.transacoes["transacao_id"].isin(excluir))
    ].copy()

    saldo = float(base.perfil["saldo_atual_conta"])
    eventos: list[EventoCaixa] = []
    pior_saldo = saldo
    data_pior: date | None = None
    primeira_negativa: date | None = None
    total_entradas = 0.0
    total_saidas = 0.0

    for _, linha in pendentes.iterrows():
        valor = float(linha["valor"])
        if linha["tipo"] == "entrada":
            saldo += valor
            total_entradas += valor
        else:
            saldo -= valor
            total_saidas += valor

        data_evento = linha["data"].date()
        eventos.append(
            EventoCaixa(
                data=data_evento,
                descricao=str(linha["descricao"]),
                categoria=str(linha["categoria"]),
                valor=valor,
                tipo=str(linha["tipo"]),
                status=str(linha["status"]),
                saldo_apos=round(saldo, 2),
                transacao_id=str(linha["transacao_id"]),
            )
        )

        if saldo < pior_saldo:
            pior_saldo = saldo
            data_pior = data_evento
        if saldo < 0 and primeira_negativa is None:
            primeira_negativa = data_evento

    return ProjecaoCaixa(
        saldo_inicial=round(float(base.perfil["saldo_atual_conta"]), 2),
        horizonte_dias=horizonte_dias,
        eventos=eventos,
        saldo_final=round(saldo, 2),
        pior_saldo=round(pior_saldo, 2),
        data_pior_saldo=data_pior,
        primeira_data_negativa=primeira_negativa,
        necessidade_caixa=round(abs(min(pior_saldo, 0.0)), 2),
        total_entradas=round(total_entradas, 2),
        total_saidas=round(total_saidas, 2),
    )


def recomendar_linha_credito(
    base: BaseEstruturada, necessidade: float, dias_exposicao: int = 30
) -> dict[str, Any] | None:
    """Seleciona a linha de menor custo capaz de cobrir a necessidade informada."""
    if necessidade <= 0:
        return None

    elegiveis = [
        linha
        for linha in base.linhas_credito
        if float(linha["limite_disponivel"]) >= necessidade
    ]
    if not elegiveis:
        elegiveis = sorted(
            base.linhas_credito, key=lambda linha: -float(linha["limite_disponivel"])
        )[:1]

    escolhida = min(elegiveis, key=lambda linha: float(linha["taxa_mensal"]))
    taxa = float(escolhida["taxa_mensal"])
    custo_mensal = necessidade * taxa
    custo_periodo = custo_mensal * (dias_exposicao / 30)

    mais_cara = max(base.linhas_credito, key=lambda linha: float(linha["taxa_mensal"]))
    custo_alternativa = necessidade * float(mais_cara["taxa_mensal"])
    economia = custo_alternativa - custo_mensal

    return {
        "codigo": escolhida["codigo"],
        "nome": escolhida["nome"],
        "taxa_mensal": taxa,
        "prazo_liberacao": escolhida["prazo_liberacao"],
        "valor_sugerido": round(necessidade, 2),
        "custo_mensal": round(custo_mensal, 2),
        "custo_periodo": round(custo_periodo, 2),
        "dias_exposicao": dias_exposicao,
        "alternativa_cara": mais_cara["nome"],
        "taxa_alternativa": float(mais_cara["taxa_mensal"]),
        "custo_alternativa": round(custo_alternativa, 2),
        "economia_estimada": round(economia, 2),
    }


def resumo_periodo(base: BaseEstruturada, projecao: ProjecaoCaixa) -> dict[str, Any]:
    dias_ate_deficit = None
    if projecao.primeira_data_negativa:
        dias_ate_deficit = (projecao.primeira_data_negativa - base.referencia).days

    return {
        "empresa": base.perfil["razao_social"],
        "referencia": base.referencia.isoformat(),
        "saldo_atual": projecao.saldo_inicial,
        "horizonte_dias": projecao.horizonte_dias,
        "total_entradas": projecao.total_entradas,
        "total_saidas": projecao.total_saidas,
        "saldo_final": projecao.saldo_final,
        "pior_saldo": projecao.pior_saldo,
        "data_pior_saldo": projecao.data_pior_saldo.isoformat()
        if projecao.data_pior_saldo
        else None,
        "primeira_data_negativa": projecao.primeira_data_negativa.isoformat()
        if projecao.primeira_data_negativa
        else None,
        "dias_ate_deficit": dias_ate_deficit,
        "necessidade_caixa": projecao.necessidade_caixa,
    }


def formatar_reais(valor: float) -> str:
    inteiro = f"{abs(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    sinal = "-" if valor < 0 else ""
    return f"{sinal}R$ {inteiro}"


def formatar_data(valor: date | datetime | None) -> str:
    if valor is None:
        return "sem data"
    if isinstance(valor, datetime):
        valor = valor.date()
    return valor.strftime("%d/%m/%Y")
