"""Testes do motor antifraude e da recuperacao na base de conhecimento."""

from __future__ import annotations

import pytest

from src.data_engine import carregar_base
from src.fraud_engine import analisar_pagamentos_pendentes, resumo_risco
from src.knowledge_base import obter_base


@pytest.fixture(scope="module")
def base():
    return carregar_base()


@pytest.fixture(scope="module")
def analises(base):
    return analisar_pagamentos_pendentes(base)


def _por_id(analises, transacao_id):
    return next(a for a in analises if a.transacao_id == transacao_id)


def test_analisa_todas_as_saidas_pendentes(base, analises):
    pendentes = base.transacoes[
        (base.transacoes["tipo"] == "saida")
        & (base.transacoes["status"].isin(["agendado", "previsto"]))
    ]
    assert len(analises) == len(pendentes)


def test_conta_alterada_recentemente_gera_risco_critico(analises):
    analise = _por_id(analises, "TRX-005")
    assert analise.classificacao == "CRITICO"
    assert "R01" in {alerta.regra for alerta in analise.alertas}


def test_titular_divergente_e_detectado(analises):
    analise = _por_id(analises, "TRX-005")
    assert "R04" in {alerta.regra for alerta in analise.alertas}


def test_beneficiario_novo_sem_historico_e_sinalizado(analises):
    analise = _por_id(analises, "TRX-010")
    assert analise.suspeito
    assert "R03" in {alerta.regra for alerta in analise.alertas}


def test_canal_inseguro_pontua(analises):
    analise = _por_id(analises, "TRX-010")
    assert "R07" in {alerta.regra for alerta in analise.alertas}


def test_valor_atipico_gera_risco_medio(analises):
    analise = _por_id(analises, "TRX-009")
    assert analise.classificacao == "MEDIO"
    assert "R05" in {alerta.regra for alerta in analise.alertas}


def test_pagamento_rotineiro_permanece_com_risco_baixo(analises):
    analise = _por_id(analises, "TRX-004")
    assert analise.classificacao == "BAIXO"
    assert analise.orientacao == ""


def test_folha_de_pagamento_nao_e_falso_positivo(analises):
    analise = _por_id(analises, "TRX-006")
    assert not analise.suspeito


def test_pontuacao_limitada_a_cem(analises):
    assert all(0 <= a.pontuacao <= 100 for a in analises)


def test_alerta_carrega_justificativa(analises):
    for analise in analises:
        for alerta in analise.alertas:
            assert alerta.detalhe.strip()


def test_analises_ordenadas_por_severidade(analises):
    ordem = {"CRITICO": 0, "ALTO": 1, "MEDIO": 2, "BAIXO": 3}
    posicoes = [ordem[a.classificacao] for a in analises]
    assert posicoes == sorted(posicoes)


def test_resumo_consolida_valor_em_risco(analises):
    resumo = resumo_risco(analises)
    esperado = round(sum(a.valor for a in analises if a.suspeito), 2)
    assert resumo["valor_em_risco"] == esperado
    assert set(resumo["ids_suspeitos"]) == {a.transacao_id for a in analises if a.suspeito}


def test_base_de_conhecimento_indexa_todos_os_documentos():
    kb = obter_base()
    assert len(kb.documentos()) == 6
    assert len(kb.trechos) > 20


@pytest.mark.parametrize(
    "consulta,documento_esperado",
    [
        ("como identificar boleto adulterado", "golpe-do-boleto-adulterado"),
        ("fornecedor mudou a conta bancaria", "fraude-do-falso-fornecedor"),
        ("ligacao do gerente pedindo token", "golpe-do-falso-funcionario-do-banco"),
        ("transferencia urgente pedida pelo diretor", "fraude-do-ceo"),
        ("qr code de pix adulterado", "golpes-com-pix"),
    ],
)
def test_recuperacao_encontra_o_documento_correto(consulta, documento_esperado):
    resultados = obter_base().buscar(consulta, k=5)
    assert resultados
    documentos = {trecho.documento for trecho, _ in resultados}
    assert documento_esperado in documentos


def test_consulta_sem_relacao_nao_retorna_trecho():
    assert obter_base().buscar("zzzz qqqq wwww", k=3) == []
