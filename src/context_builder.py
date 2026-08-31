"""Montagem do contexto que acompanha cada chamada ao modelo.

O bloco de contexto reune numeros ja calculados, alertas de fraude ja pontuados e
trechos recuperados da base de conhecimento. O conjunto de valores numericos exposto
neste bloco define o universo aceito pela verificacao de ancoragem da resposta.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import guardrails
from .data_engine import (
    BaseEstruturada,
    ProjecaoCaixa,
    carregar_base,
    formatar_data,
    formatar_reais,
    projetar_caixa,
    recomendar_linha_credito,
    resumo_periodo,
)
from .fraud_engine import AnalisePagamento, analisar_pagamentos_pendentes, resumo_risco
from .knowledge_base import Trecho, obter_base


@dataclass
class ContextoAgente:
    base: BaseEstruturada
    projecao: ProjecaoCaixa
    projecao_sem_suspeitos: ProjecaoCaixa
    resumo: dict[str, Any]
    recomendacao: dict[str, Any] | None
    analises: list[AnalisePagamento]
    risco: dict[str, Any]
    trechos: list[Trecho] = field(default_factory=list)
    valores_permitidos: set[float] = field(default_factory=set)


def _coletar_valores(contexto: ContextoAgente) -> set[float]:
    valores: set[float] = set()
    perfil = contexto.base.perfil
    for chave in (
        "saldo_atual_conta",
        "faturamento_medio_mensal",
        "custo_fixo_mensal",
        "alcada_aprovacao_pagamento",
    ):
        valores.add(round(float(perfil[chave]), 2))

    for projecao in (contexto.projecao, contexto.projecao_sem_suspeitos):
        valores.update(
            {
                round(projecao.saldo_inicial, 2),
                round(projecao.saldo_final, 2),
                round(projecao.pior_saldo, 2),
                round(projecao.necessidade_caixa, 2),
                round(projecao.total_entradas, 2),
                round(projecao.total_saidas, 2),
            }
        )
        for evento in projecao.eventos:
            valores.add(round(evento.valor, 2))
            valores.add(round(evento.saldo_apos, 2))

    for linha in contexto.base.linhas_credito:
        valores.add(round(float(linha["limite_disponivel"]), 2))

    if contexto.recomendacao:
        valores.update(
            {
                round(contexto.recomendacao["valor_sugerido"], 2),
                round(contexto.recomendacao["custo_mensal"], 2),
                round(contexto.recomendacao["custo_periodo"], 2),
                round(contexto.recomendacao["custo_alternativa"], 2),
                round(contexto.recomendacao["economia_estimada"], 2),
            }
        )

    valores.add(round(float(contexto.risco["valor_em_risco"]), 2))
    for analise in contexto.analises:
        valores.add(round(analise.valor, 2))

    for beneficiario in contexto.base.beneficiarios.itertuples():
        valores.add(round(float(beneficiario.valor_medio_historico), 2))

    return {round(abs(v), 2) for v in valores}


def construir_contexto(consulta: str = "", base: BaseEstruturada | None = None) -> ContextoAgente:
    base = base or carregar_base()
    analises = analisar_pagamentos_pendentes(base)
    risco = resumo_risco(analises)

    projecao = projetar_caixa(base)
    projecao_limpa = projetar_caixa(base, excluir=set(risco["ids_suspeitos"]))
    resumo = resumo_periodo(base, projecao_limpa)

    dias_exposicao = 30
    if projecao_limpa.primeira_data_negativa and projecao_limpa.saldo_final > 0:
        dias_exposicao = max(
            1,
            (
                projecao_limpa.eventos[-1].data - projecao_limpa.primeira_data_negativa
            ).days,
        )

    recomendacao = recomendar_linha_credito(
        base, projecao_limpa.necessidade_caixa, dias_exposicao
    )

    trechos: list[Trecho] = []
    kb = obter_base()
    if consulta:
        trechos = [t for t, _ in kb.buscar(consulta, k=2)]
    if not trechos:
        temas = [a.tema_kb for a in analises if a.suspeito and a.tema_kb]
        if temas:
            trechos = kb.por_tema(temas[0], k=1)

    contexto = ContextoAgente(
        base=base,
        projecao=projecao,
        projecao_sem_suspeitos=projecao_limpa,
        resumo=resumo,
        recomendacao=recomendacao,
        analises=analises,
        risco=risco,
        trechos=trechos,
    )
    contexto.valores_permitidos = _coletar_valores(contexto)
    return contexto


def montar_bloco_contexto(contexto: ContextoAgente) -> str:
    """Serializa o contexto em texto ja sanitizado para envio ao provedor."""
    perfil = contexto.base.perfil
    projecao = contexto.projecao_sem_suspeitos
    linhas: list[str] = ["[CONTEXTO CALCULADO PELO BACKEND]"]

    linhas.append(
        f"Empresa: {perfil['razao_social']} | Setor: {perfil['setor']} | "
        f"Porte: {perfil['porte']} | Funcionarios: {perfil['funcionarios']} | "
        f"Perfil de risco: {perfil['perfil_risco']}"
    )
    linhas.append(
        f"Data de referencia: {formatar_data(contexto.base.referencia)} | "
        f"Horizonte analisado: {projecao.horizonte_dias} dias"
    )
    linhas.append(f"Saldo atual em conta: {formatar_reais(projecao.saldo_inicial)}")
    linhas.append(
        f"Faturamento medio mensal: "
        f"{formatar_reais(float(perfil['faturamento_medio_mensal']))}"
    )
    linhas.append(
        f"Custo fixo mensal: {formatar_reais(float(perfil['custo_fixo_mensal']))}"
    )
    linhas.append(
        f"Alcada de aprovacao: {formatar_reais(float(perfil['alcada_aprovacao_pagamento']))}"
    )
    linhas.append(f"Meta financeira declarada: {perfil['meta_financeira']}")
    linhas.append(f"Politica interna: {perfil['politica_interna']}")

    linhas.append("")
    linhas.append("PROJECAO DE CAIXA (pagamentos suspeitos retidos):")
    linhas.append(f"- Entradas previstas: {formatar_reais(projecao.total_entradas)}")
    linhas.append(f"- Saidas previstas: {formatar_reais(projecao.total_saidas)}")
    linhas.append(f"- Saldo ao fim do horizonte: {formatar_reais(projecao.saldo_final)}")
    if projecao.primeira_data_negativa:
        linhas.append(
            f"- Primeiro dia com saldo negativo: {formatar_data(projecao.primeira_data_negativa)}"
        )
        linhas.append(
            f"- Pior saldo do periodo: {formatar_reais(projecao.pior_saldo)} em "
            f"{formatar_data(projecao.data_pior_saldo)}"
        )
        linhas.append(
            f"- Necessidade de caixa a cobrir: {formatar_reais(projecao.necessidade_caixa)}"
        )
    else:
        linhas.append("- Nenhum dia com saldo negativo no horizonte analisado.")

    linhas.append("")
    linhas.append("CENARIO SEM RETENCAO DOS PAGAMENTOS SUSPEITOS:")
    linhas.append(f"- Pior saldo: {formatar_reais(contexto.projecao.pior_saldo)}")
    linhas.append(f"- Saldo final: {formatar_reais(contexto.projecao.saldo_final)}")

    linhas.append("")
    linhas.append("AGENDA DO PERIODO:")
    for evento in projecao.eventos:
        sinal = "+" if evento.tipo == "entrada" else "-"
        linhas.append(
            f"- {formatar_data(evento.data)} | {evento.descricao} | {sinal}"
            f"{formatar_reais(evento.valor)} | saldo apos: {formatar_reais(evento.saldo_apos)}"
        )

    if contexto.recomendacao:
        rec = contexto.recomendacao
        linhas.append("")
        linhas.append("RECOMENDACAO DE COBERTURA (calculada pelo backend):")
        linhas.append(
            f"- Linha indicada: {rec['nome']} | taxa {rec['taxa_mensal'] * 100:.2f}% ao mes | "
            f"liberacao {rec['prazo_liberacao']}"
        )
        linhas.append(f"- Valor sugerido: {formatar_reais(rec['valor_sugerido'])}")
        linhas.append(f"- Custo estimado em 30 dias: {formatar_reais(rec['custo_mensal'])}")
        linhas.append(
            f"- Custo proporcional a {rec['dias_exposicao']} dias de exposicao: "
            f"{formatar_reais(rec['custo_periodo'])}"
        )
        linhas.append(
            f"- Custo pela alternativa mais cara ({rec['alternativa_cara']}, "
            f"{rec['taxa_alternativa'] * 100:.2f}% ao mes): "
            f"{formatar_reais(rec['custo_alternativa'])}"
        )
        linhas.append(f"- Economia estimada: {formatar_reais(rec['economia_estimada'])}")

    linhas.append("")
    linhas.append("CATALOGO DE LINHAS DE CREDITO:")
    for linha in contexto.base.linhas_credito:
        linhas.append(
            f"- {linha['nome']} | {float(linha['taxa_mensal']) * 100:.2f}% ao mes | "
            f"limite {formatar_reais(float(linha['limite_disponivel']))} | "
            f"liberacao {linha['prazo_liberacao']}"
        )

    linhas.append("")
    linhas.append("ANALISE ANTIFRAUDE DOS PAGAMENTOS PENDENTES:")
    linhas.append(
        f"- Pagamentos analisados: {contexto.risco['total_analisado']} | "
        f"criticos: {contexto.risco['criticos']} | altos: {contexto.risco['altos']} | "
        f"medios: {contexto.risco['medios']}"
    )
    linhas.append(f"- Valor sob suspeita: {formatar_reais(contexto.risco['valor_em_risco'])}")
    for analise in contexto.analises:
        if analise.classificacao == "BAIXO":
            continue
        linhas.append(
            f"- [{analise.classificacao}] {analise.transacao_id} | {analise.descricao} | "
            f"{formatar_reais(analise.valor)} | beneficiario: {analise.beneficiario} | "
            f"pontuacao {analise.pontuacao}/100"
        )
        for alerta in analise.alertas:
            linhas.append(f"    * {alerta.regra} {alerta.titulo}: {alerta.detalhe}")
        if analise.orientacao:
            linhas.append(f"    * Orientacao: {analise.orientacao}")

    if contexto.trechos:
        linhas.append("")
        linhas.append("BASE DE CONHECIMENTO SOBRE GOLPES FINANCEIROS:")
        for trecho in contexto.trechos:
            linhas.append(f"- Fonte: {trecho.referencia}")
            linhas.append(trecho.conteudo)

    historico = contexto.base.historico
    if not historico.empty:
        linhas.append("")
        linhas.append("HISTORICO DE RELACIONAMENTO:")
        for registro in historico.tail(3).itertuples():
            linhas.append(
                f"- {formatar_data(registro.data_atendimento)} | {registro.assunto} | "
                f"{registro.resumo}"
            )

    return guardrails.sanitizar_contexto("\n".join(linhas))
