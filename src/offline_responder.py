"""Motor deterministico de respostas usado no modo offline.

Roteia a pergunta por intencao e compoe a resposta a partir do contexto ja calculado.
Nenhum valor e gerado por inferencia, o que garante execucao sem chave de API e
resultados reprodutiveis na avaliacao automatizada.
"""

from __future__ import annotations

import re
import unicodedata

from .context_builder import ContextoAgente
from .data_engine import formatar_data, formatar_reais
from .knowledge_base import obter_base

INTENCOES = {
    "fraude": [
        "suspeit", "fraude", "risco", "alerta", "indicio", "irregular", "estranho",
        "beneficiario", "fornecedor", "reter", "bloquear pagamento", "conferir pagamento",
    ],
    "caixa": [
        "caixa", "saldo", "deficit", "negativo", "folha", "pagar", "projec",
        "vencimento", "agenda", "furo", "liquidez", "dinheiro", "conta a pagar",
    ],
    "credito": [
        "credito", "antecipa", "emprestimo", "taxa", "juros", "cheque especial",
        "giro", "linha", "financiamento", "cet", "custo de capital",
    ],
}

MARCADORES_ORIENTACAO = [
    "como", "o que fazer", "o que e", "quais sinais", "sinais de", "dica",
    "prevenir", "evitar", "identificar", "proteger", "protecao", "reconhecer",
    "me explique", "explica", "funciona", "devo fazer", "boas praticas",
]

TEMAS_SEGURANCA = [
    "golpe", "fraude", "boleto", "pix", "phishing", "senha", "token", "credenci",
    "engenharia social", "falso funcionario", "falso fornecedor", "ceo", "estelionato",
    "seguranca", "hacker", "invas", "vazamento", "qr code", "acesso remoto", "lgpd",
]

SAUDACOES = [
    "oi", "ola", "bom dia", "boa tarde", "boa noite", "tudo bem", "e ai", "salve",
]

ESCOPO = (
    [termo for termos in INTENCOES.values() for termo in termos]
    + TEMAS_SEGURANCA
    + [
        "empresa", "banco", "financeiro", "tesouraria", "fatura", "nota fiscal",
        "recebivel", "cliente", "max", "situacao", "panorama", "resumo", "relatorio",
        "transacao", "lancamento", "pagamento", "extrato", "faturamento", "capital",
        "alcada", "aprovacao", "politica", "auditoria", "analise", "recomenda",
    ]
)


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto.lower()


PERGUNTAS_DIRETAS = {
    "saldo": [
        "qual o meu saldo", "qual meu saldo", "qual o saldo", "saldo atual",
        "quanto tenho em conta", "quanto tem na conta", "quanto tenho de saldo",
        "quanto tenho disponivel", "quanto ha em conta",
    ],
    "agenda": [
        "o que vence", "quais os vencimentos", "quais vencimentos", "proximos vencimentos",
        "o que tenho a pagar", "o que vou pagar", "quais pagamentos", "agenda do periodo",
        "o que tenho a receber", "proximos lancamentos",
    ],
    "quando": [
        "quando fica negativo", "quando o caixa fica negativo", "que dia fica negativo",
        "quando comeca o deficit", "quantos dias ate o deficit", "quando falta dinheiro",
    ],
}


def _classificar_intencao(mensagem: str) -> str:
    texto = _normalizar(mensagem)

    if any(texto.strip().startswith(s) for s in SAUDACOES) and len(texto.split()) <= 4:
        return "panorama"

    for intencao, gatilhos in PERGUNTAS_DIRETAS.items():
        if any(gatilho in texto for gatilho in gatilhos):
            return intencao

    tema_seguranca = any(tema in texto for tema in TEMAS_SEGURANCA)
    pede_orientacao = any(marcador in texto for marcador in MARCADORES_ORIENTACAO)
    if tema_seguranca and pede_orientacao:
        return "educacao"

    pontos = {
        intencao: sum(1 for termo in termos if termo in texto)
        for intencao, termos in INTENCOES.items()
    }
    if tema_seguranca:
        pontos["fraude"] += 1

    melhor = max(pontos, key=lambda chave: pontos[chave])
    if pontos[melhor] > 0:
        return melhor

    if any(termo in texto for termo in ESCOPO):
        return "panorama"
    return "fora_de_escopo"


def _bloco_fraude(contexto: ContextoAgente) -> str:
    suspeitos = [a for a in contexto.analises if a.suspeito]
    if not suspeitos:
        return (
            "Nenhum pagamento pendente atingiu classificacao alta ou critica na analise "
            "antifraude desta rodada. Os lancamentos seguem dentro do padrao historico de "
            "beneficiario, valor e canal de solicitacao."
        )

    partes = [
        f"Identifiquei {len(suspeitos)} pagamento(s) com indicios de fraude, somando "
        f"{formatar_reais(contexto.risco['valor_em_risco'])}. Recomendo reter esses "
        "lancamentos antes de qualquer decisao de credito."
    ]
    for analise in suspeitos:
        motivos = "; ".join(f"{a.titulo.lower()}" for a in analise.alertas[:3])
        partes.append(
            f"{analise.transacao_id}, {analise.descricao}, {formatar_reais(analise.valor)}, "
            f"vencimento em {formatar_data(analise.data)}. Classificacao {analise.classificacao} "
            f"({analise.pontuacao}/100). Motivos: {motivos}."
        )
    partes.append(suspeitos[0].orientacao)
    return "\n\n".join(partes)


def _bloco_saldo(contexto: ContextoAgente) -> str:
    projecao = contexto.projecao_sem_suspeitos
    partes = [
        f"O saldo atual em conta e {formatar_reais(projecao.saldo_inicial)}, posicao de "
        f"{formatar_data(contexto.base.referencia)}."
    ]
    if projecao.primeira_data_negativa:
        dias = (projecao.primeira_data_negativa - contexto.base.referencia).days
        partes.append(
            f"Esse saldo cobre os compromissos por {dias} dia(s). A partir de "
            f"{formatar_data(projecao.primeira_data_negativa)} a projecao fica negativa."
        )
    else:
        partes.append(
            f"O saldo se mantem positivo em todo o horizonte de {projecao.horizonte_dias} dias."
        )
    partes.append("Quer ver a agenda de vencimentos que sustenta essa projecao?")
    return " ".join(partes)


def _bloco_agenda(contexto: ContextoAgente) -> str:
    projecao = contexto.projecao_sem_suspeitos
    if not projecao.eventos:
        return "Nao ha lancamentos pendentes no horizonte analisado."

    partes = [
        f"Agenda dos proximos {projecao.horizonte_dias} dias, com o saldo acumulado apos "
        "cada lancamento:"
    ]
    for evento in projecao.eventos:
        sinal = "entrada" if evento.tipo == "entrada" else "saida"
        partes.append(
            f"- {formatar_data(evento.data)} | {evento.descricao} | {sinal} de "
            f"{formatar_reais(evento.valor)} | saldo apos: {formatar_reais(evento.saldo_apos)}"
        )
    return "\n".join(partes)


def _bloco_quando(contexto: ContextoAgente) -> str:
    projecao = contexto.projecao_sem_suspeitos
    if projecao.primeira_data_negativa is None:
        return (
            f"O caixa nao fica negativo dentro do horizonte de {projecao.horizonte_dias} dias. "
            f"O menor patamar do periodo e {formatar_reais(projecao.pior_saldo)}."
        )
    dias = (projecao.primeira_data_negativa - contexto.base.referencia).days
    return (
        f"O caixa fica negativo em {dias} dia(s), a partir de "
        f"{formatar_data(projecao.primeira_data_negativa)}. O pior patamar e "
        f"{formatar_reais(projecao.pior_saldo)} em {formatar_data(projecao.data_pior_saldo)}, "
        f"o que define uma necessidade de cobertura de "
        f"{formatar_reais(projecao.necessidade_caixa)}."
    )


def _bloco_caixa(contexto: ContextoAgente) -> str:
    projecao = contexto.projecao_sem_suspeitos
    resumo = contexto.resumo

    if projecao.primeira_data_negativa is None:
        return (
            f"O caixa se mantem positivo em todo o horizonte de {projecao.horizonte_dias} dias. "
            f"O saldo parte de {formatar_reais(projecao.saldo_inicial)} e termina em "
            f"{formatar_reais(projecao.saldo_final)}, com o menor patamar do periodo em "
            f"{formatar_reais(projecao.pior_saldo)}."
        )

    dias = resumo["dias_ate_deficit"]
    partes = [
        f"O caixa fica negativo em {dias} dia(s), a partir de "
        f"{formatar_data(projecao.primeira_data_negativa)}. O pior patamar do periodo e "
        f"{formatar_reais(projecao.pior_saldo)} em "
        f"{formatar_data(projecao.data_pior_saldo)}, o que define uma necessidade de "
        f"{formatar_reais(projecao.necessidade_caixa)} para atravessar o mes sem atraso. "
        f"Esse cenario ja considera a retencao dos pagamentos suspeitos; sem essa retencao "
        f"o pior saldo seria {formatar_reais(contexto.projecao.pior_saldo)}."
    ]

    if contexto.recomendacao:
        rec = contexto.recomendacao
        partes.append(
            f"A cobertura mais barata disponivel e {rec['nome']}, a "
            f"{rec['taxa_mensal'] * 100:.2f}% ao mes com liberacao {rec['prazo_liberacao']}. "
            f"Contratar {formatar_reais(rec['valor_sugerido'])} custa "
            f"{formatar_reais(rec['custo_mensal'])} em trinta dias, contra "
            f"{formatar_reais(rec['custo_alternativa'])} pela "
            f"{rec['alternativa_cara']}."
        )

    partes.append(
        "Proxima acao sugerida: confirmar a agenda de recebiveis e decidir o valor a "
        "antecipar antes do primeiro vencimento negativo."
    )
    return "\n\n".join(partes)


def _bloco_credito(contexto: ContextoAgente) -> str:
    linhas = sorted(contexto.base.linhas_credito, key=lambda item: float(item["taxa_mensal"]))
    partes = ["Comparativo das linhas disponiveis, da mais barata para a mais cara:"]
    for linha in linhas:
        partes.append(
            f"- {linha['nome']}: {float(linha['taxa_mensal']) * 100:.2f}% ao mes, limite de "
            f"{formatar_reais(float(linha['limite_disponivel']))}, liberacao "
            f"{linha['prazo_liberacao']}."
        )

    if contexto.recomendacao:
        rec = contexto.recomendacao
        partes.append(
            f"Para a necessidade atual de {formatar_reais(rec['valor_sugerido'])}, a "
            f"indicacao e {rec['nome']}. O custo estimado e "
            f"{formatar_reais(rec['custo_mensal'])} em trinta dias e a economia frente a "
            f"{rec['alternativa_cara']} chega a {formatar_reais(rec['economia_estimada'])}."
        )
    else:
        partes.append(
            "Nao ha necessidade de cobertura no horizonte atual, entao nenhuma contratacao "
            "e recomendada neste momento."
        )
    return "\n".join(partes)


PREFERENCIA_SECAO = [
    (["o que fazer", "cai no", "caiu", "ja paguei", "ja saiu", "fui vitima"], "o que fazer"),
    (["identific", "sinais", "reconhec", "perceber", "detectar", "desconfiar"], "sinais"),
    (["proteger", "protecao", "evitar", "prevenir", "boas praticas", "reduzir"], "proteger"),
    (["como funciona", "o que e", "explica", "entender"], "como funciona"),
]


def _selecionar_secao(mensagem: str, candidatos: list) -> list:
    texto = _normalizar(mensagem)

    por_titulo = [
        t
        for t in candidatos
        if any(
            palavra in texto
            for palavra in _normalizar(t.secao).split()
            if len(palavra) > 4
        )
    ]
    if por_titulo:
        return por_titulo

    for gatilhos, alvo in PREFERENCIA_SECAO:
        if not any(gatilho in texto for gatilho in gatilhos):
            continue
        preferidos = [t for t in candidatos if alvo in _normalizar(t.secao)]
        if preferidos:
            return preferidos
    return candidatos


def _bloco_educacao(mensagem: str, contexto: ContextoAgente) -> str:
    kb = obter_base()
    resultados = kb.buscar(mensagem, k=10)
    candidatos = []
    if resultados:
        pontos_por_documento: dict[str, float] = {}
        for trecho, score in resultados:
            pontos_por_documento[trecho.documento] = (
                pontos_por_documento.get(trecho.documento, 0.0) + score
            )
        documento_alvo = max(pontos_por_documento, key=lambda d: pontos_por_documento[d])
        mesmo_documento = [t for t, _ in resultados if t.documento == documento_alvo]
        candidatos = _selecionar_secao(mensagem, mesmo_documento) or mesmo_documento
    trechos = candidatos or contexto.trechos
    if not trechos:
        return (
            "Nao encontrei esse tema na base de conhecimento de seguranca. Posso orientar "
            "sobre fraude do falso fornecedor, boleto adulterado, falso funcionario do banco, "
            "fraude do CEO, golpes com Pix e protecao de acessos."
        )
    trecho = trechos[0]
    conteudo = re.sub(r"\n{2,}", "\n", trecho.conteudo).strip()
    linhas = [linha.strip() for linha in conteudo.splitlines() if linha.strip()][:6]
    return f"{trecho.titulo} — {trecho.secao}\n\n" + "\n".join(linhas)


def _bloco_panorama(contexto: ContextoAgente) -> str:
    projecao = contexto.projecao_sem_suspeitos
    partes = [
        f"Panorama de {contexto.base.perfil['razao_social']} em "
        f"{formatar_data(contexto.base.referencia)}. Saldo atual de "
        f"{formatar_reais(projecao.saldo_inicial)}, com "
        f"{formatar_reais(projecao.total_saidas)} a pagar e "
        f"{formatar_reais(projecao.total_entradas)} a receber nos proximos "
        f"{projecao.horizonte_dias} dias."
    ]

    if projecao.primeira_data_negativa:
        partes.append(
            f"O saldo fica negativo em {formatar_data(projecao.primeira_data_negativa)} e "
            f"atinge {formatar_reais(projecao.pior_saldo)} no pior dia, o que exige cobertura "
            f"de {formatar_reais(projecao.necessidade_caixa)}."
        )

    if contexto.risco["valor_em_risco"] > 0:
        partes.append(
            f"Na revisao antifraude, {contexto.risco['criticos']} pagamento(s) critico(s) e "
            f"{contexto.risco['altos']} de risco alto somam "
            f"{formatar_reais(contexto.risco['valor_em_risco'])} e devem ser confirmados antes "
            "da liberacao."
        )

    partes.append(
        "Posso detalhar a agenda de vencimentos, comparar as linhas de credito ou explicar "
        "os indicios de fraude encontrados."
    )
    return "\n\n".join(partes)


def responder(mensagem: str, contexto: ContextoAgente | None) -> str:
    if contexto is None:
        return (
            "O contexto financeiro nao foi carregado nesta sessao. Recarregue a aplicacao "
            "para que a projecao de caixa e a analise antifraude sejam recalculadas."
        )

    intencao = _classificar_intencao(mensagem)
    if intencao == "fora_de_escopo":
        return (
            "Esse tema esta fora do meu escopo. Atuo em tesouraria, fluxo de caixa, custo "
            "de credito e seguranca contra fraudes financeiras da empresa. Posso mostrar a "
            "projecao de caixa do periodo, revisar os pagamentos pendentes ou orientar sobre "
            "golpes que atingem o setor financeiro."
        )
    if intencao == "saldo":
        return _bloco_saldo(contexto)
    if intencao == "agenda":
        return _bloco_agenda(contexto)
    if intencao == "quando":
        return _bloco_quando(contexto)
    if intencao == "fraude":
        return _bloco_fraude(contexto)
    if intencao == "caixa":
        return _bloco_caixa(contexto)
    if intencao == "credito":
        return _bloco_credito(contexto)
    if intencao == "educacao":
        return _bloco_educacao(mensagem, contexto)
    return _bloco_panorama(contexto)
