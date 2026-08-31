# Pitch — MAX: Motor de Análise de Exposição

## 1. O problema

Um dos principais riscos financeiros para pequenas e médias empresas é a ruptura de caixa. Uma empresa pode apresentar faturamento e lucro e, ainda assim, enfrentar dificuldades quando os pagamentos aos fornecedores acontecem antes do recebimento dos clientes.

Muitas vezes, o problema é identificado apenas próximo ao vencimento, quando as alternativas disponíveis são menores e o custo para obter crédito é maior.

Ao mesmo tempo, o contas a pagar das PMEs está exposto a fraudes. Alterações nos dados bancários de fornecedores, por exemplo, podem ser solicitadas por e-mail e passar despercebidas em meio à rotina operacional. O problema só é identificado posteriormente, quando o fornecedor legítimo cobra o pagamento.

Nos dois casos, existe um ponto em comum: a falta de uma visão antecipada sobre as exposições financeiras da empresa.

---

## 2. A solução

O MAX é um Motor de Análise de Exposição desenvolvido para identificar e quantificar riscos de liquidez e de fraude em uma única interface.

Na análise de liquidez, o sistema projeta o saldo da empresa dia a dia, identifica a data do primeiro déficit e apresenta alternativas de crédito, incluindo a diferença de custo entre elas.

Na análise de fraude, cada pagamento pendente recebe uma pontuação baseada em sete regras determinísticas. O sistema verifica alterações na conta bancária, canal da solicitação, correspondência entre titular e razão social e divergências em relação ao histórico de valores, entre outros fatores.

Um princípio central da arquitetura é separar cálculo e geração de linguagem. O modelo de linguagem não realiza cálculos financeiros. Os valores são processados em Python e enviados ao modelo já calculados.

---

## 3. Demonstração

### Aba Caixa

A empresa possui atualmente R$ 14.500,00 em caixa, com uma exposição de liquidez de R$ 32.300,00 e uma exposição a fraude de R$ 41.100,00.

A trajetória do saldo apresenta a evolução projetada do caixa e identifica o período em que o saldo entra em situação negativa.

### Aba Segurança

O pagamento TRX-005, no valor de R$ 18.700,00, recebeu pontuação máxima de risco.

A classificação é baseada em três fatores principais: alteração recente da conta bancária do fornecedor, solicitação realizada por e-mail e divergência entre o titular da conta e a razão social da transportadora.

O sistema também apresenta a ação recomendada: confirmar a alteração por telefone, utilizando um número previamente cadastrado.

### Aba Consultoria

Um teste de prompt injection com a solicitação:

é bloqueado antes de chegar ao modelo de linguagem.
A solicitação é classificada como prompt injection, associada à regra INJ-01 e registrada na auditoria.

### Aba Auditoria

As interações são registradas após o processo de mascaramento dos dados, evitando que informações sensíveis sejam armazenadas diretamente nos logs.

---

## 4. Diferenciais

O projeto possui três características principais que o diferenciam de uma aplicação baseada apenas em prompts.

A primeira é a segurança implementada em código. Um módulo específico bloqueia tentativas de prompt injection, exfiltração de informações e comandos relacionados à execução financeira antes que a solicitação chegue ao modelo. O mapeamento para o OWASP Top 10 para aplicações com LLM também está documentado no repositório.

A segunda é a verificação de ancoragem numérica. Os valores apresentados pelo modelo são comparados com os dados calculados pelo sistema. Caso seja identificado um valor incompatível, a resposta é descartada.

A terceira é a validação automatizada. O projeto possui 36 casos de teste versionados, incluindo testes de segurança, além de 65 testes unitários executados na integração contínua.

O resultado é uma aplicação que combina análise financeira, mecanismos de segurança e geração de respostas em linguagem natural, mantendo os cálculos e as regras críticas sob controle determinístico do sistema.

---

## Link do vídeo

Cole aqui o link após a gravação.
