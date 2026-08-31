"""Abstracao dos provedores de modelo de linguagem.

Quatro backends compartilham a mesma interface. O modo offline responde com um motor
deterministico construido sobre o contexto ja calculado, o que mantem a aplicacao
funcional sem chave de API e torna a avaliacao automatizada reprodutivel.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Protocol

import requests
import re

from . import config


def _detalhar_erro(erro: Exception, resposta: requests.Response | None = None) -> str:
    """Inclui o corpo da resposta na mensagem, nao apenas o codigo HTTP."""
    detalhe = str(erro)
    if resposta is None:
        return detalhe
    try:
        corpo = resposta.json()
        mensagem = corpo.get("error", {}).get("message") or corpo.get("error") or ""
    except ValueError:
        mensagem = resposta.text[:300]

    dica = ""
    if resposta.status_code == 429 and "limit: 0" in str(mensagem):
        dica = (
            " | Esse modelo nao possui cota no plano gratuito. Selecione um modelo "
            "Flash ou Flash-Lite na barra lateral."
        )
    elif resposta.status_code == 429:
        dica = (
            " | Limite de requisicoes atingido. Aguarde alguns segundos ou troque "
            "para um modelo com limite diario maior, como o Flash-Lite."
        )
    elif resposta.status_code == 404:
        dica = (
            " | Modelo indisponivel ou descontinuado. Escolha outro na lista da "
            "barra lateral."
        )

    return f"{detalhe} | {mensagem}{dica}" if mensagem else f"{detalhe}{dica}"


@dataclass
class RespostaLLM:
    texto: str
    provider: str
    modelo: str
    latencia_ms: float
    erro: str = ""


class Provider(Protocol):
    nome: str
    modelo: str

    def disponivel(self) -> bool: ...

    def listar_modelos(self) -> list[str]: ...

    def gerar(
        self, system_prompt: str, contexto: str, mensagem: str, historico: list[dict[str, str]]
    ) -> RespostaLLM: ...


def _montar_mensagens(
    system_prompt: str, contexto: str, mensagem: str, historico: list[dict[str, str]]
) -> list[dict[str, str]]:
    mensagens = [{"role": "system", "content": f"{system_prompt}\n\n{contexto}"}]
    for turno in historico[-6:]:
        mensagens.append({"role": turno["role"], "content": turno["content"]})
    mensagens.append({"role": "user", "content": mensagem})
    return mensagens


class OfflineProvider:
    nome = "offline"

    def __init__(self) -> None:
        self.modelo = config.MODELOS_PADRAO["offline"]
        self._contexto_estruturado: Any = None

    def vincular_contexto(self, contexto: Any) -> None:
        self._contexto_estruturado = contexto

    def disponivel(self) -> bool:
        return True

    def listar_modelos(self) -> list[str]:
        return [self.modelo]

    def gerar(
        self, system_prompt: str, contexto: str, mensagem: str, historico: list[dict[str, str]]
    ) -> RespostaLLM:
        from .offline_responder import responder

        inicio = time.perf_counter()
        texto = responder(mensagem, self._contexto_estruturado)
        latencia = round((time.perf_counter() - inicio) * 1000, 2)
        return RespostaLLM(texto, self.nome, self.modelo, latencia)


class OllamaProvider:
    nome = "ollama"

    def __init__(self) -> None:
        self.modelo = config.MODELO or config.MODELOS_PADRAO["ollama"]

    def disponivel(self) -> bool:
        try:
            resposta = requests.get(f"{config.OLLAMA_URL}/api/tags", timeout=3)
            return resposta.status_code == 200
        except requests.RequestException:
            return False

    def listar_modelos(self) -> list[str]:
        try:
            resposta = requests.get(f"{config.OLLAMA_URL}/api/tags", timeout=5)
            resposta.raise_for_status()
            return sorted(item["name"] for item in resposta.json().get("models", []))
        except (requests.RequestException, KeyError, ValueError):
            return []

    def gerar(
        self, system_prompt: str, contexto: str, mensagem: str, historico: list[dict[str, str]]
    ) -> RespostaLLM:
        inicio = time.perf_counter()
        resposta = None
        try:
            resposta = requests.post(
                f"{config.OLLAMA_URL}/api/chat",
                json={
                    "model": self.modelo,
                    "messages": _montar_mensagens(system_prompt, contexto, mensagem, historico),
                    "stream": False,
                    "options": {"temperature": 0.2, "num_predict": 900},
                },
                timeout=config.TIMEOUT_LLM,
            )
            resposta.raise_for_status()
            mensagem_retorno = resposta.json().get("message", {})
            texto = (mensagem_retorno.get("content") or "").strip()
            latencia = round((time.perf_counter() - inicio) * 1000, 2)
            if not texto and mensagem_retorno.get("thinking"):
                return RespostaLLM(
                    "",
                    self.nome,
                    self.modelo,
                    latencia,
                    "O modelo produziu apenas raciocinio interno, sem resposta final. "
                    "Modelos de raciocinio como gpt-oss costumam exigir mais tempo ou um "
                    "limite de tokens maior. Considere um modelo de instrucao como llama3.1:8b.",
                )
            return RespostaLLM(texto, self.nome, self.modelo, latencia)
        except requests.RequestException as erro:
            latencia = round((time.perf_counter() - inicio) * 1000, 2)
            return RespostaLLM(
                "", self.nome, self.modelo, latencia, _detalhar_erro(erro, resposta)
            )


class GroqProvider:
    nome = "groq"
    endpoint = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self) -> None:
        self.modelo = config.MODELO or config.MODELOS_PADRAO["groq"]

    def disponivel(self) -> bool:
        return bool(config.GROQ_API_KEY)

    def listar_modelos(self) -> list[str]:
        if not config.GROQ_API_KEY:
            return []
        try:
            resposta = requests.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"},
                timeout=10,
            )
            resposta.raise_for_status()
            modelos = [
                item["id"]
                for item in resposta.json().get("data", [])
                if item.get("active", True)
            ]
            return sorted(modelos)
        except (requests.RequestException, KeyError, ValueError):
            return []

    def gerar(
        self, system_prompt: str, contexto: str, mensagem: str, historico: list[dict[str, str]]
    ) -> RespostaLLM:
        inicio = time.perf_counter()
        resposta = None
        try:
            resposta = requests.post(
                self.endpoint,
                headers={
                    "Authorization": f"Bearer {config.GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.modelo,
                    "messages": _montar_mensagens(system_prompt, contexto, mensagem, historico),
                    "temperature": 0.2,
                    "max_tokens": 900,
                },
                timeout=config.TIMEOUT_LLM,
            )
            resposta.raise_for_status()
            dados = resposta.json()
            mensagem_retorno = dados["choices"][0]["message"]
            texto = (mensagem_retorno.get("content") or "").strip()
            latencia = round((time.perf_counter() - inicio) * 1000, 2)
            if not texto and mensagem_retorno.get("reasoning"):
                return RespostaLLM(
                    "",
                    self.nome,
                    self.modelo,
                    latencia,
                    f"O modelo {self.modelo} devolveu apenas raciocinio interno, sem "
                    "resposta final. Selecione outro modelo na barra lateral.",
                )
            return RespostaLLM(texto, self.nome, self.modelo, latencia)
        except (requests.RequestException, KeyError, IndexError) as erro:
            latencia = round((time.perf_counter() - inicio) * 1000, 2)
            return RespostaLLM(
                "", self.nome, self.modelo, latencia, _detalhar_erro(erro, resposta)
            )


class GeminiProvider:
    nome = "gemini"

    def __init__(self) -> None:
        self.modelo = config.MODELO or config.MODELOS_PADRAO["gemini"]

    def disponivel(self) -> bool:
        return bool(config.GEMINI_API_KEY)

    PISO_VERSAO = (3, 1)
    EXCLUIDOS = (
        "embedding", "imagen", "image", "vision", "tts", "live", "veo",
        "aqa", "learnlm", "native-audio", "gemma", "nano-banana", "pro",
    )
    PREFERIDOS = (
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
    )

    @staticmethod
    def _versao(nome: str) -> tuple[int, ...]:
        """Extrai a versao como tupla de inteiros. 3.10 fica acima de 3.5."""
        achado = re.search(r"gemini-(\d+(?:\.\d+)?)", nome.lower())
        if not achado:
            return (0,)
        return tuple(int(parte) for parte in achado.group(1).split("."))

    def listar_modelos(self) -> list[str]:
        if not config.GEMINI_API_KEY:
            return []
        try:
            resposta = requests.get(
                "https://generativelanguage.googleapis.com/v1beta/models"
                f"?key={config.GEMINI_API_KEY}&pageSize=200",
                timeout=10,
            )
            resposta.raise_for_status()
            disponiveis = [
                item["name"].removeprefix("models/")
                for item in resposta.json().get("models", [])
                if "generateContent" in item.get("supportedGenerationMethods", [])
            ]
        except (requests.RequestException, KeyError, ValueError):
            return []

        flash = [
            nome
            for nome in disponiveis
            if "flash" in nome.lower()
            and not any(termo in nome.lower() for termo in self.EXCLUIDOS)
        ]

        def ordem(nome: str) -> tuple:
            preferencia = (
                self.PREFERIDOS.index(nome)
                if nome in self.PREFERIDOS
                else len(self.PREFERIDOS)
            )
            preview = int("preview" in nome.lower() or "exp" in nome.lower())
            # versao decrescente: o mais novo primeiro
            return (preview, preferencia, tuple(-p for p in self._versao(nome)), nome)

        # Filtro ideal: versao no piso ou acima, sem preview.
        recentes = [
            nome
            for nome in flash
            if self._versao(nome) >= self.PISO_VERSAO
            and "preview" not in nome.lower()
            and "exp" not in nome.lower()
        ]
        if recentes:
            return sorted(recentes, key=ordem)

        # Primeiro afrouxamento: aceita preview, mantendo o piso de versao.
        no_piso = [nome for nome in flash if self._versao(nome) >= self.PISO_VERSAO]
        if no_piso:
            return sorted(no_piso, key=ordem)

        # Ultimo recurso: qualquer Flash, com os previews no fim da lista.
        return sorted(flash, key=ordem)
    
    def gerar(
        self, system_prompt: str, contexto: str, mensagem: str, historico: list[dict[str, str]]
    ) -> RespostaLLM:
        inicio = time.perf_counter()
        resposta = None
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.modelo}:generateContent?key={config.GEMINI_API_KEY}"
        )
        conteudos = []
        for turno in historico[-6:]:
            papel = "user" if turno["role"] == "user" else "model"
            conteudos.append({"role": papel, "parts": [{"text": turno["content"]}]})
        conteudos.append({"role": "user", "parts": [{"text": mensagem}]})

        try:
            resposta = requests.post(
                url,
                json={
                    "systemInstruction": {"parts": [{"text": f"{system_prompt}\n\n{contexto}"}]},
                    "contents": conteudos,
                    "generationConfig": {"temperature": 0.2, "maxOutputTokens": 900},
                },
                timeout=config.TIMEOUT_LLM,
            )
            resposta.raise_for_status()
            dados = resposta.json()
            texto = dados["candidates"][0]["content"]["parts"][0]["text"].strip()
            latencia = round((time.perf_counter() - inicio) * 1000, 2)
            return RespostaLLM(texto, self.nome, self.modelo, latencia)
        except (requests.RequestException, KeyError, IndexError) as erro:
            latencia = round((time.perf_counter() - inicio) * 1000, 2)
            return RespostaLLM(
                "", self.nome, self.modelo, latencia, _detalhar_erro(erro, resposta)
            )


PROVIDERS = {
    "offline": OfflineProvider,
    "ollama": OllamaProvider,
    "groq": GroqProvider,
    "gemini": GeminiProvider,
}


def obter_provider(nome: str | None = None, modelo: str | None = None) -> Provider:
    escolhido = (nome or config.PROVIDER).lower()
    classe = PROVIDERS.get(escolhido, OfflineProvider)
    provider = classe()
    if modelo:
        provider.modelo = modelo
    return provider
