"""Testes do motor de dados e da projecao de fluxo de caixa."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from src import config
from src.data_engine import (
    carregar_base,
    formatar_reais,
    projetar_caixa,
    recomendar_linha_credito,
    resumo_periodo,
)


@pytest.fixture(scope="module")
def base():
    return carregar_base()


def test_datas_reposicionadas_para_o_presente(base):
    primeira = base.transacoes["data"].min().date()
    esperada = base.referencia - timedelta(days=config.DIAS_ANCORA_PASSADO)
    assert primeira == esperada


def test_projecao_gera_evento_para_cada_lancamento_pendente(base):
    projecao = projetar_caixa(base)
    pendentes = base.transacoes[base.transacoes["status"].isin(["agendado", "previsto"])]
    assert len(projecao.eventos) == len(pendentes)


def test_saldo_acumulado_confere_com_o_ultimo_evento(base):
    projecao = projetar_caixa(base)
    assert projecao.saldo_final == projecao.eventos[-1].saldo_apos


def test_saldo_final_bate_com_entradas_e_saidas(base):
    projecao = projetar_caixa(base)
    esperado = round(
        projecao.saldo_inicial + projecao.total_entradas - projecao.total_saidas, 2
    )
    assert projecao.saldo_final == esperado


def test_cenario_detecta_deficit(base):
    projecao = projetar_caixa(base)
    assert projecao.primeira_data_negativa is not None
    assert projecao.pior_saldo < 0
    assert projecao.necessidade_caixa == round(abs(projecao.pior_saldo), 2)


def test_reter_pagamentos_suspeitos_melhora_o_pior_saldo(base):
    completa = projetar_caixa(base)
    filtrada = projetar_caixa(base, excluir={"TRX-005", "TRX-010"})
    assert filtrada.pior_saldo > completa.pior_saldo


def test_excluir_transacao_remove_o_evento(base):
    projecao = projetar_caixa(base, excluir={"TRX-006"})
    assert all(evento.transacao_id != "TRX-006" for evento in projecao.eventos)


def test_recomendacao_escolhe_a_menor_taxa(base):
    recomendacao = recomendar_linha_credito(base, 20000.0)
    taxas = [float(linha["taxa_mensal"]) for linha in base.linhas_credito]
    assert recomendacao["taxa_mensal"] == min(taxas)


def test_recomendacao_calcula_custo_e_economia(base):
    recomendacao = recomendar_linha_credito(base, 10000.0)
    assert recomendacao["custo_mensal"] == round(10000.0 * recomendacao["taxa_mensal"], 2)
    assert recomendacao["custo_alternativa"] > recomendacao["custo_mensal"]
    assert recomendacao["economia_estimada"] == round(
        recomendacao["custo_alternativa"] - recomendacao["custo_mensal"], 2
    )


def test_sem_necessidade_nao_ha_recomendacao(base):
    assert recomendar_linha_credito(base, 0.0) is None


def test_resumo_traz_dias_ate_o_deficit(base):
    projecao = projetar_caixa(base)
    resumo = resumo_periodo(base, projecao)
    assert resumo["dias_ate_deficit"] >= 0
    assert resumo["empresa"] == base.perfil["razao_social"]


def test_formatacao_de_moeda_brasileira():
    assert formatar_reais(32300.0) == "R$ 32.300,00"
    assert formatar_reais(-1234.5) == "-R$ 1.234,50"
    assert formatar_reais(0.0) == "R$ 0,00"


def test_base_carrega_em_data_arbitraria():
    base = carregar_base(referencia=date(2027, 1, 15))
    assert base.referencia == date(2027, 1, 15)
    assert not base.transacoes.empty
