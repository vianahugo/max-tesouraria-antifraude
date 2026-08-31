"""Camada de controle de seguranca aplicada antes e depois do modelo de linguagem.

A protecao nao depende de instrucoes no prompt. Cada verificacao roda em codigo,
retorna um veredito explicito e alimenta a trilha de auditoria. O mapeamento das
regras para o OWASP Top 10 para Aplicacoes com LLM esta em docs/06-seguranca.md.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable

TOLERANCIA_ANCORAGEM = 0.05
VALORES_LIVRES = {0.0, 1.0, 2.0, 3.0, 100.0}


@dataclass
class Veredito:
    permitido: bool
    categoria: str = "ok"
    regra: str = ""
    motivo: str = ""
    resposta_padrao: str = ""
    trecho: str = ""


@dataclass
class ResultadoSaida:
    texto: str
    violacoes: list[str] = field(default_factory=list)
    dados_mascarados: int = 0
    ancoragem_ok: bool = True
    valores_nao_ancorados: list[str] = field(default_factory=list)


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto.lower()


RESPOSTA_INJECAO = (
    "Nao vou seguir essa instrucao. Minhas regras de operacao e o conteudo interno da "
    "sessao nao sao acessiveis por solicitacao, e essa tentativa foi registrada na trilha "
    "de auditoria. Posso continuar ajudando com a projecao de caixa, com a analise dos "
    "pagamentos pendentes ou com orientacao sobre golpes financeiros."
)

RESPOSTA_EXFILTRACAO = (
    "Nao forneco documentos completos, dados bancarios, credenciais ou informacoes que "
    "identifiquem pessoas. Trabalho com valores consolidados por categoria. Se precisar "
    "desses dados para uma conferencia, consulte o cadastro no sistema corporativo com o "
    "acesso nominal apropriado."
)

RESPOSTA_TRANSACIONAL = (
    "Nao executo movimentacao financeira. Nao realizo Pix, transferencias, pagamentos de "
    "boleto nem alteracao de cadastro. Minha funcao e analitica e consultiva: posso "
    "projetar o impacto da operacao no caixa e indicar a linha de credito de menor custo, "
    "mas a execucao permanece com voce, no canal oficial do banco."
)

RESPOSTA_FORA_ESCOPO = (
    "Esse tema esta fora do meu escopo. Atuo em tesouraria, fluxo de caixa, custo de "
    "credito e seguranca contra fraudes financeiras da empresa."
)

PADROES_INJECAO: list[tuple[str, str, str]] = [
    ("INJ-01", r"ignore?\s+(todas?\s+)?(as\s+)?(instru[cç][oõ]es|regras|orienta[cç][oõ]es)", "Pedido de descarte das instrucoes"),
    ("INJ-01", r"ignore\s+(all\s+)?(previous|prior)\s+instructions", "Pedido de descarte das instrucoes"),
    ("INJ-01", r"esque[cç]a\s+(tudo|as\s+regras|as\s+instru[cç][oõ]es|o\s+que)", "Pedido de descarte das instrucoes"),
    ("INJ-01", r"desconsidere\s+(as\s+)?(regras|instru[cç][oõ]es|restri[cç][oõ]es)", "Pedido de descarte das instrucoes"),
    ("INJ-02", r"(system|prompt)\s*(prompt|de\s+sistema)", "Tentativa de extrair o prompt de sistema"),
    ("INJ-02", r"(mostre|exiba|imprima|revele|repita|liste)\s+(me\s+)?(suas?|as|o)\s+(instru[cç][oõ]es|regras|prompt|configura[cç][oõ]es)", "Tentativa de extrair o prompt de sistema"),
    ("INJ-02", r"(reveal|show|repeat|print)\s+(your|the)\s+(system\s+)?(prompt|instructions|rules)", "Tentativa de extrair o prompt de sistema"),
    ("INJ-02", r"quais\s+s[aã]o\s+(as\s+)?suas\s+(instru[cç][oõ]es|regras\s+internas)", "Tentativa de extrair o prompt de sistema"),
    ("INJ-03", r"(a\s+partir\s+de\s+agora|de\s+agora\s+em\s+diante)\s+voc[eê]\s+", "Tentativa de redefinicao de persona"),
    ("INJ-03", r"voc[eê]\s+(agora\s+)?[eé]\s+(um|uma)\s+(?!agente\s+de\s+tesouraria)", "Tentativa de redefinicao de persona"),
    ("INJ-03", r"finja\s+que\s+(voc[eê]\s+)?(n[aã]o\s+tem|[eé]|pode)", "Tentativa de redefinicao de persona"),
    ("INJ-03", r"\b(atue|aja)\s+como\s+(se\s+)?(voc[eê]\s+)?(n[aã]o|um\s+modelo\s+sem)", "Tentativa de redefinicao de persona"),
    ("INJ-04", r"\b(modo|mode)\s+(desenvolvedor|developer|debug|deus|god)\b", "Solicitacao de modo irrestrito"),
    ("INJ-04", r"\bdan\s+mode\b|\bjailbreak\b|\bsem\s+(nenhuma\s+)?restri[cç][oõ]es?\b", "Solicitacao de modo irrestrito"),
    ("INJ-04", r"sem\s+(seus\s+)?(filtros|guardrails|limites)", "Solicitacao de modo irrestrito"),
    ("INJ-05", r"\b(decodifique|decode)\b.{0,40}\b(base64|hex|rot13)\b", "Instrucao ofuscada"),
    ("INJ-05", r"\bbase64\b.{0,40}\b(execute|siga|obede[cç]a)\b", "Instrucao ofuscada"),
]

REQUISICAO = (
    r"(qual|quais|informe|informa|mostre|mostra|diga|diz|revele|liste|lista|"
    r"me\s+d[ea]|me\s+passe|me\s+envie|envie|forneca|preciso\s+d[oa]|"
    r"quero\s+(saber\s+)?[oa])"
)

PADROES_EXFILTRACAO: list[tuple[str, str, str]] = [
    ("EXF-01", rf"\b{REQUISICAO}\b[^.?!]{{0,35}}\b(senha|password|credencial|credenciais|token\s+de\s+acesso|chave\s+de\s+acesso|api[\s_-]?key)\b", "Pedido de credencial"),
    ("EXF-02", r"\b(cpf|cnpj|documento)\s+completo\b", "Pedido de documento de identificacao"),
    ("EXF-02", rf"\b{REQUISICAO}\b[^.?!]{{0,30}}\b(cpf|cnpj)\b", "Pedido de documento de identificacao"),
    ("EXF-03", rf"\b{REQUISICAO}\b[^.?!]{{0,35}}\b(numero\s+d[ao]\s+conta|conta\s+bancaria|agencia\s+e\s+conta|chave\s+pix|dados\s+bancarios)\b", "Pedido de dado bancario"),
    ("EXF-04", r"\bsalario\s+(individual|de\s+cada|do\s+funcionario|dos\s+funcionarios)\b", "Pedido de dado pessoal de terceiro"),
    ("EXF-04", r"\b(quanto\s+ganha|remuneracao\s+individual)\b", "Pedido de dado pessoal de terceiro"),
    ("EXF-05", r"\b(despeje|dump|exporte|extraia|baixe)\b[^.?!]{0,30}\b(base|dados|arquivo|csv|json|tabela)\b", "Pedido de exportacao integral da base"),
]

PEDIDO = r"(pode|poderia|consegue|quero\s+que\s+voce|preciso\s+que\s+voce|vai|va)"

PADROES_TRANSACIONAIS: list[tuple[str, str, str]] = [
    ("TRX-01", r"\b(faca|faz|manda|mande|envie|realize|efetue|execute|processe)\b[^.?!]{0,30}\b(pix|transferencia|ted|doc)\b", "Ordem de transferencia"),
    ("TRX-01", r"\b(transfira|transfere)\b", "Ordem de transferencia"),
    ("TRX-01", rf"\b{PEDIDO}\b[^.?!]{{0,25}}\b(fazer|mandar|enviar|realizar)\b[^.?!]{{0,20}}\b(pix|transferencia|ted)\b", "Ordem de transferencia"),
    ("TRX-02", r"\b(pague|quite|liquide)\b", "Ordem de pagamento"),
    ("TRX-02", r"\b(faca|faz|efetue|realize|execute|processe|autorize|confirme)\b[^.?!]{0,25}\b(pagamento|boleto|fatura|folha)\b", "Ordem de pagamento"),
    ("TRX-02", rf"\b{PEDIDO}\b[^.?!]{{0,25}}\b(pagar|quitar|liquidar)\b", "Ordem de pagamento"),
    ("TRX-03", r"\b(contrate|aprove|libere|solicite|assine)\b[^.?!]{0,30}\b(emprestimo|credito|antecipacao|limite|linha)\b", "Ordem de contratacao de credito"),
    ("TRX-03", rf"\b{PEDIDO}\b[^.?!]{{0,25}}\b(contratar|aprovar|liberar|solicitar)\b[^.?!]{{0,20}}\b(emprestimo|credito|antecipacao|limite)\b", "Ordem de contratacao de credito"),
    ("TRX-04", r"\b(altere|cadastre|atualize|troque|substitua)\b[^.?!]{0,30}\b(conta|dados\s+bancarios|beneficiario|chave\s+pix|cadastro)\b", "Ordem de alteracao cadastral"),
]

PADROES_PII: list[tuple[str, str, str]] = [
    ("CARTAO", r"\b(?:\d{4}[\s.-]?){3}\d{4}\b", "[cartao protegido]"),
    ("CNPJ", r"\b\d{2}\.?\d{3}\.?\d{3}/\d{4}-?\d{2}\b", "[CNPJ protegido]"),
    ("CPF", r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b", "[CPF protegido]"),
    ("CONTA", r"(?i)\b(ag[eê]ncia|conta)\s*:?\s*n?[oº]?\s*\d{3,6}-?\d?\b", "[dado bancario protegido]"),
    ("PIX_UUID", r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b", "[chave Pix protegida]"),
    ("EMAIL", r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b", "[e-mail protegido]"),
    ("TELEFONE", r"\b\(?\d{2}\)?\s?9?\d{4}[-\s]?\d{4}\b", "[telefone protegido]"),
]


def verificar_entrada(mensagem: str) -> Veredito:
    """Classifica a mensagem do usuario antes de qualquer chamada ao modelo."""
    texto = _normalizar(mensagem)

    for regra, padrao, motivo in PADROES_INJECAO:
        achado = re.search(padrao, texto)
        if achado:
            return Veredito(False, "prompt_injection", regra, motivo, RESPOSTA_INJECAO, achado.group(0))

    for regra, padrao, motivo in PADROES_TRANSACIONAIS:
        achado = re.search(padrao, texto)
        if achado:
            return Veredito(False, "transacional", regra, motivo, RESPOSTA_TRANSACIONAL, achado.group(0))

    for regra, padrao, motivo in PADROES_EXFILTRACAO:
        achado = re.search(padrao, texto)
        if achado:
            return Veredito(False, "exfiltracao", regra, motivo, RESPOSTA_EXFILTRACAO, achado.group(0))

    return Veredito(True)


def mascarar_pii(texto: str) -> tuple[str, int, list[str]]:
    """Substitui identificadores diretos por marcadores neutros."""
    ocorrencias = 0
    tipos: list[str] = []
    for nome, padrao, substituto in PADROES_PII:
        texto, quantidade = re.subn(padrao, substituto, texto)
        if quantidade:
            ocorrencias += quantidade
            tipos.append(nome)
    return texto, ocorrencias, tipos


def extrair_valores_monetarios(texto: str) -> list[tuple[str, float]]:
    valores: list[tuple[str, float]] = []
    for achado in re.finditer(r"R\$\s*(-?[\d.]+,\d{2}|-?[\d.]+)", texto):
        bruto = achado.group(1)
        limpo = bruto.replace(".", "").replace(",", ".")
        try:
            valores.append((achado.group(0), abs(float(limpo))))
        except ValueError:
            continue
    return valores


def verificar_ancoragem(texto: str, valores_permitidos: Iterable[float]) -> tuple[bool, list[str]]:
    """Confere se todo valor monetario citado existe no contexto entregue ao modelo."""
    permitidos = {round(abs(float(v)), 2) for v in valores_permitidos}
    permitidos |= {round(v, 0) for v in permitidos}
    permitidos |= VALORES_LIVRES

    nao_ancorados: list[str] = []
    for original, valor in extrair_valores_monetarios(texto):
        if any(abs(valor - referencia) <= TOLERANCIA_ANCORAGEM for referencia in permitidos):
            continue
        nao_ancorados.append(original)
    return (not nao_ancorados), nao_ancorados


def verificar_saida(
    texto: str, valores_permitidos: Iterable[float] | None = None
) -> ResultadoSaida:
    """Aplica mascaramento de dados e verificacao de ancoragem sobre a resposta gerada."""
    violacoes: list[str] = []
    texto_seguro, mascarados, tipos = mascarar_pii(texto)
    if mascarados:
        violacoes.append(f"pii_mascarada:{','.join(sorted(set(tipos)))}")

    ancoragem_ok = True
    nao_ancorados: list[str] = []
    if valores_permitidos is not None:
        ancoragem_ok, nao_ancorados = verificar_ancoragem(texto_seguro, valores_permitidos)
        if not ancoragem_ok:
            violacoes.append(f"valor_sem_ancoragem:{'|'.join(nao_ancorados)}")

    return ResultadoSaida(
        texto=texto_seguro,
        violacoes=violacoes,
        dados_mascarados=mascarados,
        ancoragem_ok=ancoragem_ok,
        valores_nao_ancorados=nao_ancorados,
    )


def sanitizar_contexto(texto: str) -> str:
    """Remove identificadores diretos antes do envio ao provedor do modelo."""
    limpo, _, _ = mascarar_pii(texto)
    return limpo
