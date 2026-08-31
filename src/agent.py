"""Orquestracao do agente.

Fluxo de uma interacao:
entrada -> guardrails de entrada -> contexto deterministico -> modelo ->
guardrails de saida -> auditoria -> resposta.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from . import audit, config, guardrails
from .context_builder import ContextoAgente, construir_contexto, montar_bloco_contexto
from .llm_provider import OfflineProvider, RespostaLLM, obter_provider
from .offline_responder import responder as responder_offline
from .prompts import EXEMPLOS_FEW_SHOT, SYSTEM_PROMPT


@dataclass
class RespostaAgente:
    texto: str
    bloqueado: bool = False
    categoria: str = "ok"
    regra: str = ""
    provider: str = ""
    modelo: str = ""
    latencia_ms: float = 0.0
    violacoes: list[str] = field(default_factory=list)
    dados_mascarados: int = 0
    ancoragem_ok: bool = True
    substituiu_por_deterministico: bool = False
    motivo_substituicao: str = ""
    erro_provider: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "texto": self.texto,
            "bloqueado": self.bloqueado,
            "categoria": self.categoria,
            "regra": self.regra,
            "provider": self.provider,
            "modelo": self.modelo,
            "latencia_ms": self.latencia_ms,
            "violacoes": self.violacoes,
            "ancoragem_ok": self.ancoragem_ok,
        }


class AgenteMax:
    def __init__(
        self,
        provider_nome: str | None = None,
        sessao: str | None = None,
        modelo: str | None = None,
    ):
        self.provider = obter_provider(provider_nome, modelo)
        self.sessao = sessao or uuid.uuid4().hex[:12]
        self.contexto: ContextoAgente | None = None

    def preparar_contexto(self, consulta: str = "") -> ContextoAgente:
        self.contexto = construir_contexto(consulta)
        return self.contexto

    def _gerar(
        self, mensagem: str, contexto: ContextoAgente, historico: list[dict[str, str]]
    ) -> RespostaLLM:
        bloco = montar_bloco_contexto(contexto)
        system = f"{SYSTEM_PROMPT}\n\nEXEMPLOS DE RESPOSTA ESPERADA:{EXEMPLOS_FEW_SHOT}"

        if isinstance(self.provider, OfflineProvider):
            self.provider.vincular_contexto(contexto)

        return self.provider.gerar(system, bloco, mensagem, historico)

    def responder(
        self, mensagem: str, historico: list[dict[str, str]] | None = None
    ) -> RespostaAgente:
        historico = historico or []

        veredito = guardrails.verificar_entrada(mensagem)
        if not veredito.permitido:
            audit.registrar(
                sessao=self.sessao,
                mensagem=mensagem,
                categoria=veredito.categoria,
                regra=veredito.regra,
                bloqueado=True,
                provider=self.provider.nome,
                modelo=self.provider.modelo,
                caracteres_resposta=len(veredito.resposta_padrao),
            )
            return RespostaAgente(
                texto=veredito.resposta_padrao,
                bloqueado=True,
                categoria=veredito.categoria,
                regra=veredito.regra,
                provider=self.provider.nome,
                modelo=self.provider.modelo,
            )

        contexto = self.preparar_contexto(mensagem)
        resultado_llm = self._gerar(mensagem, contexto, historico)

        substituiu = False
        motivo = ""
        texto = resultado_llm.texto
        if not texto.strip():
            texto = responder_offline(mensagem, contexto)
            substituiu = True
            motivo = (
                f"O provedor {resultado_llm.provider} nao retornou conteudo. {resultado_llm.erro}"
                if resultado_llm.erro
                else f"O provedor {resultado_llm.provider} retornou uma resposta vazia."
            )

        verificacao = guardrails.verificar_saida(texto, contexto.valores_permitidos)
        if not verificacao.ancoragem_ok:
            valores = ", ".join(verificacao.valores_nao_ancorados)
            texto_seguro = responder_offline(mensagem, contexto)
            verificacao = guardrails.verificar_saida(
                texto_seguro, contexto.valores_permitidos
            )
            verificacao.violacoes.append("resposta_substituida_por_falha_de_ancoragem")
            substituiu = True
            motivo = (
                "A resposta do modelo citou valores que nao existem no contexto calculado "
                f"({valores}) e foi descartada pela verificacao de ancoragem."
            )

        audit.registrar(
            sessao=self.sessao,
            mensagem=mensagem,
            categoria="atendida",
            bloqueado=False,
            provider=resultado_llm.provider,
            modelo=resultado_llm.modelo,
            latencia_ms=resultado_llm.latencia_ms,
            violacoes=verificacao.violacoes,
            dados_mascarados=verificacao.dados_mascarados,
            ancoragem_ok=verificacao.ancoragem_ok,
            caracteres_resposta=len(verificacao.texto),
        )

        return RespostaAgente(
            texto=verificacao.texto,
            categoria="atendida",
            provider=resultado_llm.provider,
            modelo=resultado_llm.modelo,
            latencia_ms=resultado_llm.latencia_ms,
            violacoes=verificacao.violacoes,
            dados_mascarados=verificacao.dados_mascarados,
            ancoragem_ok=verificacao.ancoragem_ok,
            substituiu_por_deterministico=substituiu,
            motivo_substituicao=motivo,
            erro_provider=resultado_llm.erro,
        )


def mensagem_de_abertura(contexto: ContextoAgente) -> str:
    from .data_engine import formatar_data, formatar_reais

    projecao = contexto.projecao_sem_suspeitos
    partes = ["Bom dia. Revisei a agenda financeira da empresa."]

    if contexto.risco["valor_em_risco"] > 0:
        partes.append(
            f"Encontrei {contexto.risco['criticos'] + contexto.risco['altos']} pagamento(s) "
            f"com indicios de fraude, somando "
            f"{formatar_reais(contexto.risco['valor_em_risco'])}. Recomendo tratar esses "
            "lancamentos antes de qualquer decisao de credito."
        )

    if projecao.primeira_data_negativa:
        partes.append(
            f"Mesmo retendo esses pagamentos, o caixa fica negativo em "
            f"{formatar_data(projecao.primeira_data_negativa)} e chega a "
            f"{formatar_reais(projecao.pior_saldo)} no pior dia."
        )

    partes.append("Por onde prefere comecar?")
    return " ".join(partes)


def informacoes_execucao() -> dict[str, str]:
    return {
        "provider": config.PROVIDER,
        "modelo": config.modelo_efetivo(),
        "horizonte_dias": str(config.HORIZONTE_DIAS),
    }
