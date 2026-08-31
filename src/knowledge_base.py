"""Indexacao e recuperacao dos documentos de seguranca financeira.

A busca usa TF-IDF com similaridade de cosseno implementados em Python puro, o que
mantem a aplicacao sem dependencias pesadas e permite auditar o criterio de
recuperacao. Os documentos sao fatiados por secao para que o trecho devolvido ao
modelo seja curto e especifico.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache

from . import config

STOPWORDS = {
    "a", "as", "ao", "aos", "com", "como", "da", "das", "de", "do", "dos", "e", "em",
    "ele", "ela", "essa", "esse", "esta", "este", "eu", "for", "foi", "ha", "isso",
    "ja", "la", "lhe", "mais", "mas", "me", "mesmo", "meu", "minha", "muito", "na",
    "nao", "nas", "no", "nos", "num", "o", "os", "ou", "para", "pela", "pelo", "por",
    "que", "quem", "se", "sem", "ser", "seu", "sua", "sao", "so", "tem", "um", "uma",
    "voce", "ate", "quando", "onde", "qual", "quais", "pode", "posso", "fazer",
}


@dataclass
class Trecho:
    documento: str
    titulo: str
    secao: str
    conteudo: str
    tags: str

    @property
    def referencia(self) -> str:
        return f"{self.titulo} / {self.secao}"


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto.lower()


def _radical(token: str) -> str:
    if len(token) > 4 and token.endswith("oes"):
        return token[:-3] + "ao"
    if len(token) > 4 and token.endswith("s"):
        return token[:-1]
    return token


def tokenizar(texto: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", normalizar(texto))
    return [_radical(t) for t in tokens if len(t) > 2 and t not in STOPWORDS]


def _ler_frontmatter(bruto: str) -> tuple[dict[str, str], str]:
    if not bruto.startswith("---"):
        return {}, bruto
    partes = bruto.split("---", 2)
    if len(partes) < 3:
        return {}, bruto
    meta: dict[str, str] = {}
    for linha in partes[1].strip().splitlines():
        if ":" in linha:
            chave, valor = linha.split(":", 1)
            meta[chave.strip()] = valor.strip()
    return meta, partes[2]


def _fatiar(corpo: str) -> list[tuple[str, str]]:
    secoes: list[tuple[str, str]] = []
    titulo_atual = "Introducao"
    buffer: list[str] = []
    for linha in corpo.splitlines():
        if linha.startswith("## "):
            if buffer and "".join(buffer).strip():
                secoes.append((titulo_atual, "\n".join(buffer).strip()))
            titulo_atual = linha[3:].strip()
            buffer = []
        elif linha.startswith("# "):
            continue
        else:
            buffer.append(linha)
    if buffer and "".join(buffer).strip():
        secoes.append((titulo_atual, "\n".join(buffer).strip()))
    return secoes


class BaseConhecimento:
    def __init__(self, trechos: list[Trecho]):
        self.trechos = trechos
        self._documentos_tokens = [
            tokenizar(f"{t.titulo} {t.tags} {t.secao} {t.conteudo}") for t in trechos
        ]
        self._idf = self._calcular_idf()
        self._vetores = [self._vetorizar(tokens) for tokens in self._documentos_tokens]

    def _calcular_idf(self) -> dict[str, float]:
        total = len(self._documentos_tokens) or 1
        frequencia: Counter[str] = Counter()
        for tokens in self._documentos_tokens:
            frequencia.update(set(tokens))
        return {
            termo: math.log((total + 1) / (contagem + 1)) + 1.0
            for termo, contagem in frequencia.items()
        }

    def _vetorizar(self, tokens: list[str]) -> dict[str, float]:
        if not tokens:
            return {}
        contagem = Counter(tokens)
        maximo = max(contagem.values())
        vetor = {
            termo: (0.5 + 0.5 * quantidade / maximo) * self._idf.get(termo, 1.0)
            for termo, quantidade in contagem.items()
        }
        norma = math.sqrt(sum(v * v for v in vetor.values())) or 1.0
        return {termo: valor / norma for termo, valor in vetor.items()}

    def buscar(self, consulta: str, k: int = 2, minimo: float = 0.05) -> list[tuple[Trecho, float]]:
        vetor_consulta = self._vetorizar(tokenizar(consulta))
        if not vetor_consulta:
            return []
        pontuacoes: list[tuple[Trecho, float]] = []
        for trecho, vetor in zip(self.trechos, self._vetores):
            score = sum(peso * vetor.get(termo, 0.0) for termo, peso in vetor_consulta.items())
            if score >= minimo:
                pontuacoes.append((trecho, round(score, 4)))
        pontuacoes.sort(key=lambda item: item[1], reverse=True)
        return pontuacoes[:k]

    def por_tema(self, tema: str, k: int = 1) -> list[Trecho]:
        alvo = normalizar(tema)
        candidatos = [t for t in self.trechos if normalizar(t.documento).startswith(alvo)]
        preferidas = [t for t in candidatos if "prote" in normalizar(t.secao)]
        selecionados = preferidas or candidatos
        return selecionados[:k]

    def documentos(self) -> list[str]:
        return sorted({t.documento for t in self.trechos})


def _carregar_trechos() -> list[Trecho]:
    trechos: list[Trecho] = []
    if not config.KB_DIR.exists():
        return trechos
    for caminho in sorted(config.KB_DIR.glob("*.md")):
        bruto = caminho.read_text(encoding="utf-8")
        meta, corpo = _ler_frontmatter(bruto)
        titulo = meta.get("titulo", caminho.stem.replace("-", " ").capitalize())
        tags = meta.get("tags", "")
        for secao, conteudo in _fatiar(corpo):
            trechos.append(
                Trecho(
                    documento=caminho.stem,
                    titulo=titulo,
                    secao=secao,
                    conteudo=conteudo,
                    tags=tags,
                )
            )
    return trechos


@lru_cache(maxsize=1)
def obter_base() -> BaseConhecimento:
    return BaseConhecimento(_carregar_trechos())
