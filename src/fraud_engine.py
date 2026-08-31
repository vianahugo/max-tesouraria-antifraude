"""Motor de analise antifraude aplicado aos pagamentos pendentes.

As regras reproduzem sinais reconhecidos de fraude no contas a pagar de pequenas e
medias empresas. A pontuacao e deterministica e cada alerta carrega a justificativa
que o gera, de modo que o resultado possa ser auditado sem depender do modelo de
linguagem.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pandas as pd

from . import config
from .data_engine import BaseEstruturada, formatar_data, formatar_reais

CANAIS_INSEGUROS = {"email", "whatsapp", "sms", "telefone"}
JANELA_ALTERACAO_RECENTE = 15
JANELA_CADASTRO_RECENTE = 10
FATOR_VALOR_ATIPICO = 2.5


@dataclass
class Alerta:
    regra: str
    titulo: str
    peso: int
    detalhe: str


@dataclass
class AnalisePagamento:
    transacao_id: str
    descricao: str
    data: date
    valor: float
    beneficiario: str
    beneficiario_id: str
    pontuacao: int
    classificacao: str
    alertas: list[Alerta] = field(default_factory=list)
    orientacao: str = ""
    tema_kb: str = ""

    @property
    def suspeito(self) -> bool:
        return self.classificacao in {"ALTO", "CRITICO"}


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto.lower().strip()


def _classificar(pontuacao: int) -> str:
    if pontuacao >= config.LIMIAR_RISCO["CRITICO"]:
        return "CRITICO"
    if pontuacao >= config.LIMIAR_RISCO["ALTO"]:
        return "ALTO"
    if pontuacao >= config.LIMIAR_RISCO["MEDIO"]:
        return "MEDIO"
    return "BAIXO"


def _titular_diverge(nome: str, titular: str) -> bool:
    nome_norm = _normalizar(nome)
    titular_norm = _normalizar(titular)
    if not titular_norm or nome_norm == titular_norm:
        return False
    tokens_nome = {t for t in nome_norm.split() if len(t) > 3}
    tokens_titular = {t for t in titular_norm.split() if len(t) > 3}
    return not (tokens_nome & tokens_titular)


def analisar_pagamento(
    transacao: pd.Series, beneficiario: pd.Series | None, perfil: dict[str, Any], referencia: date
) -> AnalisePagamento:
    alertas: list[Alerta] = []
    valor = float(transacao["valor"])
    canal = _normalizar(transacao.get("canal_solicitacao", ""))
    tema = ""

    if beneficiario is not None:
        nome = str(beneficiario["nome"])
        alteracao = pd.to_datetime(beneficiario["ultima_alteracao_conta"]).date()
        cadastro = pd.to_datetime(beneficiario["data_cadastro"]).date()
        pagamentos = int(beneficiario["qtd_pagamentos_anteriores"])
        media = float(beneficiario["valor_medio_historico"])
        canal_alteracao = _normalizar(beneficiario["canal_ultima_alteracao"])
        dias_alteracao = (referencia - alteracao).days
        dias_cadastro = (referencia - cadastro).days

        if pagamentos >= 3 and 0 <= dias_alteracao <= JANELA_ALTERACAO_RECENTE:
            alertas.append(
                Alerta(
                    regra="R01",
                    titulo="Conta bancaria alterada recentemente",
                    peso=45,
                    detalhe=(
                        f"O beneficiario possui {pagamentos} pagamentos anteriores e teve os "
                        f"dados bancarios alterados em {formatar_data(alteracao)}, "
                        f"ha {dias_alteracao} dia(s)."
                    ),
                )
            )
            tema = tema or "fraude-do-falso-fornecedor"

        if canal_alteracao in CANAIS_INSEGUROS and 0 <= dias_alteracao <= 90:
            alertas.append(
                Alerta(
                    regra="R02",
                    titulo="Alteracao solicitada por canal inseguro",
                    peso=20,
                    detalhe=(
                        f"A alteracao de conta foi solicitada por {canal_alteracao}, "
                        "canal que nao permite validacao de identidade."
                    ),
                )
            )
            tema = tema or "fraude-do-falso-fornecedor"

        if pagamentos == 0 and 0 <= dias_cadastro <= JANELA_CADASTRO_RECENTE:
            alertas.append(
                Alerta(
                    regra="R03",
                    titulo="Beneficiario novo sem historico",
                    peso=30,
                    detalhe=(
                        f"Cadastrado em {formatar_data(cadastro)} e sem pagamentos anteriores "
                        "registrados."
                    ),
                )
            )
            tema = tema or "fraude-do-ceo"

        if _titular_diverge(nome, str(beneficiario["titular_conta"])):
            alertas.append(
                Alerta(
                    regra="R04",
                    titulo="Titular da conta diverge do fornecedor",
                    peso=25,
                    detalhe=(
                        f"A conta informada esta em nome de {beneficiario['titular_conta']}, "
                        f"diferente da razao social {nome}."
                    ),
                )
            )
            tema = tema or "fraude-do-falso-fornecedor"

        if media > 0 and valor > media * FATOR_VALOR_ATIPICO:
            alertas.append(
                Alerta(
                    regra="R05",
                    titulo="Valor fora do padrao historico",
                    peso=20,
                    detalhe=(
                        f"O valor de {formatar_reais(valor)} supera em mais de "
                        f"{FATOR_VALOR_ATIPICO:.1f}x a media historica de "
                        f"{formatar_reais(media)} paga a este beneficiario."
                    ),
                )
            )
        elif media == 0 and valor > float(perfil["alcada_aprovacao_pagamento"]):
            alertas.append(
                Alerta(
                    regra="R05",
                    titulo="Valor alto sem historico de comparacao",
                    peso=20,
                    detalhe=(
                        f"Primeiro pagamento ao beneficiario, no valor de {formatar_reais(valor)}, "
                        "sem base historica para comparacao."
                    ),
                )
            )
        nome_exibicao = nome
        beneficiario_id = str(beneficiario["beneficiario_id"])
    else:
        nome_exibicao = "Nao identificado"
        beneficiario_id = ""

    if valor > float(perfil["alcada_aprovacao_pagamento"]):
        alertas.append(
            Alerta(
                regra="R06",
                titulo="Pagamento acima da alcada",
                peso=10,
                detalhe=(
                    f"O valor supera a alcada de "
                    f"{formatar_reais(float(perfil['alcada_aprovacao_pagamento']))} e exige "
                    "dupla aprovacao pela politica interna."
                ),
            )
        )

    if canal in CANAIS_INSEGUROS:
        alertas.append(
            Alerta(
                regra="R07",
                titulo="Pagamento solicitado por canal inseguro",
                peso=15,
                detalhe=(
                    f"A solicitacao chegou por {canal}, fora do fluxo padrao de contas a pagar."
                ),
            )
        )
        tema = tema or "fraude-do-ceo"

    pontuacao = min(sum(alerta.peso for alerta in alertas), 100)
    classificacao = _classificar(pontuacao)

    orientacao = ""
    if classificacao in {"ALTO", "CRITICO"}:
        orientacao = (
            "Retenha o pagamento e confirme os dados bancarios por telefone, usando um numero "
            "que ja estava no cadastro antes desta solicitacao. Nao utilize contatos informados "
            "na mensagem que pediu a alteracao."
        )
    elif classificacao == "MEDIO":
        orientacao = (
            "Confira a documentacao de suporte e submeta o pagamento a segunda aprovacao antes "
            "de liberar."
        )

    return AnalisePagamento(
        transacao_id=str(transacao["transacao_id"]),
        descricao=str(transacao["descricao"]),
        data=transacao["data"].date()
        if hasattr(transacao["data"], "date")
        else transacao["data"],
        valor=valor,
        beneficiario=nome_exibicao,
        beneficiario_id=beneficiario_id,
        pontuacao=pontuacao,
        classificacao=classificacao,
        alertas=alertas,
        orientacao=orientacao,
        tema_kb=tema,
    )


def analisar_pagamentos_pendentes(base: BaseEstruturada) -> list[AnalisePagamento]:
    """Aplica as regras a todas as saidas ainda nao liquidadas."""
    pendentes = base.transacoes[
        (base.transacoes["tipo"] == "saida")
        & (base.transacoes["status"].isin(["agendado", "previsto"]))
    ]
    indexado = base.beneficiarios.set_index("beneficiario_id")

    analises: list[AnalisePagamento] = []
    for _, transacao in pendentes.iterrows():
        chave = str(transacao["beneficiario_id"]).strip()
        beneficiario = indexado.loc[chave].copy() if chave in indexado.index else None
        if beneficiario is not None:
            beneficiario["beneficiario_id"] = chave
        analises.append(
            analisar_pagamento(transacao, beneficiario, base.perfil, base.referencia)
        )

    ordem = {"CRITICO": 0, "ALTO": 1, "MEDIO": 2, "BAIXO": 3}
    return sorted(analises, key=lambda a: (ordem[a.classificacao], -a.pontuacao))


def resumo_risco(analises: list[AnalisePagamento]) -> dict[str, Any]:
    suspeitos = [a for a in analises if a.suspeito]
    return {
        "total_analisado": len(analises),
        "criticos": sum(1 for a in analises if a.classificacao == "CRITICO"),
        "altos": sum(1 for a in analises if a.classificacao == "ALTO"),
        "medios": sum(1 for a in analises if a.classificacao == "MEDIO"),
        "valor_em_risco": round(sum(a.valor for a in suspeitos), 2),
        "ids_suspeitos": [a.transacao_id for a in suspeitos],
    }
