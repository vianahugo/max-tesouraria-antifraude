"""Trilha de auditoria das interacoes com o agente.

Cada registro guarda a classificacao da entrada, as violacoes detectadas na saida e
metricas de execucao. A mensagem do usuario e gravada apenas depois do mascaramento
de dados identificaveis.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from . import config
from .guardrails import mascarar_pii


@dataclass
class RegistroAuditoria:
    momento: str
    sessao: str
    categoria: str
    regra: str
    bloqueado: bool
    provider: str
    modelo: str
    latencia_ms: float
    mensagem: str
    violacoes: list[str] = field(default_factory=list)
    dados_mascarados: int = 0
    ancoragem_ok: bool = True
    caracteres_resposta: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def registrar(
    sessao: str,
    mensagem: str,
    categoria: str,
    regra: str = "",
    bloqueado: bool = False,
    provider: str = "",
    modelo: str = "",
    latencia_ms: float = 0.0,
    violacoes: list[str] | None = None,
    dados_mascarados: int = 0,
    ancoragem_ok: bool = True,
    caracteres_resposta: int = 0,
) -> RegistroAuditoria:
    mensagem_segura, _, _ = mascarar_pii(mensagem)
    registro = RegistroAuditoria(
        momento=datetime.now().isoformat(timespec="seconds"),
        sessao=sessao,
        categoria=categoria,
        regra=regra,
        bloqueado=bloqueado,
        provider=provider,
        modelo=modelo,
        latencia_ms=latencia_ms,
        mensagem=mensagem_segura[:300],
        violacoes=violacoes or [],
        dados_mascarados=dados_mascarados,
        ancoragem_ok=ancoragem_ok,
        caracteres_resposta=caracteres_resposta,
    )

    config.garantir_diretorios()
    with config.ARQUIVO_AUDITORIA.open("a", encoding="utf-8") as arquivo:
        arquivo.write(json.dumps(registro.to_dict(), ensure_ascii=False) + "\n")
    return registro


def ler_registros(limite: int = 200) -> list[dict[str, Any]]:
    if not config.ARQUIVO_AUDITORIA.exists():
        return []
    linhas = config.ARQUIVO_AUDITORIA.read_text(encoding="utf-8").strip().splitlines()
    registros: list[dict[str, Any]] = []
    for linha in linhas[-limite:]:
        try:
            registros.append(json.loads(linha))
        except json.JSONDecodeError:
            continue
    return list(reversed(registros))


def estatisticas() -> dict[str, Any]:
    registros = ler_registros(limite=1000)
    if not registros:
        return {
            "total": 0,
            "bloqueios": 0,
            "injecoes": 0,
            "exfiltracao": 0,
            "transacional": 0,
            "mascaramentos": 0,
            "latencia_media_ms": 0.0,
        }
    bloqueados = [r for r in registros if r.get("bloqueado")]
    latencias = [r.get("latencia_ms", 0) for r in registros if not r.get("bloqueado")]
    return {
        "total": len(registros),
        "bloqueios": len(bloqueados),
        "injecoes": sum(1 for r in bloqueados if r.get("categoria") == "prompt_injection"),
        "exfiltracao": sum(1 for r in bloqueados if r.get("categoria") == "exfiltracao"),
        "transacional": sum(1 for r in bloqueados if r.get("categoria") == "transacional"),
        "mascaramentos": sum(r.get("dados_mascarados", 0) for r in registros),
        "latencia_media_ms": round(sum(latencias) / len(latencias), 2) if latencias else 0.0,
    }


def limpar() -> None:
    if config.ARQUIVO_AUDITORIA.exists():
        config.ARQUIVO_AUDITORIA.unlink()
