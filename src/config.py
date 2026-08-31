"""Configuracao central da aplicacao."""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
KB_DIR = DATA_DIR / "kb_golpes"
DOCS_DIR = BASE_DIR / "docs"
LOG_DIR = BASE_DIR / "logs"
REPORT_DIR = BASE_DIR / "reports"

ARQUIVO_AUDITORIA = LOG_DIR / "auditoria.jsonl"


def _carregar_env() -> None:
    caminho = BASE_DIR / ".env"
    if not caminho.exists():
        return
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))


_carregar_env()

PROVIDER = os.getenv("LLM_PROVIDER", "offline").strip().lower()
MODELO = os.getenv("LLM_MODEL", "").strip()
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
TIMEOUT_LLM = int(os.getenv("TIMEOUT_LLM", "300"))

HORIZONTE_DIAS = int(os.getenv("HORIZONTE_DIAS", "21"))
DIAS_ANCORA_PASSADO = int(os.getenv("DIAS_ANCORA_PASSADO", "12"))

LIMIAR_RISCO = {"BAIXO": 0, "MEDIO": 20, "ALTO": 45, "CRITICO": 70}

MODELOS_PADRAO = {
    "ollama": "llama3.1:8b",
    "groq": "openai/gpt-oss-120b",
    "gemini": "gemini-3.1-flash-lite",
    "offline": "motor-deterministico",
}


def modelo_efetivo() -> str:
    return MODELO or MODELOS_PADRAO.get(PROVIDER, "desconhecido")


def garantir_diretorios() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
