# Segurança do Agente

Este documento descreve o modelo de ameaças do MAX, os controles implementados e o
mapeamento para o OWASP Top 10 para Aplicações com LLM.

---

## Premissa

Instrução em linguagem natural não é controle de segurança.

Um system prompt que diz "não revele dados sensíveis" reduz a probabilidade do
comportamento indesejado, mas não a elimina, porque o modelo processa a instrução e a
tentativa de contorná-la pelo mesmo mecanismo estatístico. Basta que a formulação do
atacante seja mais persuasiva que a do desenvolvedor.

Por isso, no MAX, as restrições que não podem ser violadas rodam em código
(`src/guardrails.py`), fora do alcance do modelo. O prompt continua existindo e continua
sendo a primeira camada, mas a segunda camada não depende dele.

---

## Superfície de ataque

O agente recebe entrada não confiável de uma origem, a mensagem do usuário, e produz saída
que pode conter dados de duas bases locais. Não há navegação web, execução de código,
chamada de ferramenta externa nem escrita em sistemas de terceiros, o que reduz
substancialmente a superfície.

Os pontos de exposição remanescentes são:

1. A mensagem do usuário, que pode conter instruções maliciosas.
2. O contexto enviado ao provedor do modelo, que trafega para fora do ambiente local quando
   o provedor é uma API.
3. A resposta gerada, que pode conter dados sensíveis ou números inventados.
4. A trilha de auditoria, que poderia se tornar um novo repositório de dados sensíveis.

---

## Controles implementados

### Camada 1 — Guardrails de entrada

Executada antes de qualquer chamada ao modelo. Se a mensagem for classificada em uma das
três categorias abaixo, a execução para, uma resposta padrão é devolvida e o evento é
registrado.

| Família | Regras | O que detecta |
|---|---|---|
| `INJ` | INJ-01 a INJ-05 | Descarte de instruções, extração do system prompt, redefinição de persona, solicitação de modo irrestrito, instrução ofuscada |
| `EXF` | EXF-01 a EXF-05 | Pedido de credencial, documento de identificação, dado bancário, dado pessoal de terceiro, exportação integral da base |
| `TRX` | TRX-01 a TRX-04 | Ordem de transferência, de pagamento, de contratação de crédito e de alteração cadastral |

A detecção normaliza a mensagem removendo acentuação e diferenças de caixa antes de aplicar
os padrões, o que impede evasão trivial por variação ortográfica.

Os padrões de exfiltração e transacionais exigem um verbo de solicitação ou forma
imperativa próximo ao termo sensível. Sem essa exigência, o sistema bloquearia perguntas
educativas legítimas, como "como proteger as credenciais do setor financeiro?", o que
degradaria a utilidade sem ganho de segurança.

### Camada 2 — Sanitização do contexto

Antes do envio ao provedor, o bloco de contexto passa pelo mesmo mascaramento aplicado à
saída. O modelo nunca recebe CNPJ, CPF, agência e conta, chave Pix, cartão, e-mail ou
telefone em texto puro.

O ganho é concreto quando o provedor é uma API remota: mesmo que a requisição seja
interceptada ou registrada do lado do provedor, não há dado identificável para vazar.

### Camada 3 — Guardrails de saída

**Mascaramento de dados identificáveis.** Sete padrões cobrem cartão, CNPJ, CPF, agência e
conta, chave Pix em formato UUID, e-mail e telefone. A ordem de aplicação importa: cartão e
CNPJ são avaliados antes de CPF, porque uma sequência de CNPJ contém subsequências que
casariam com o padrão de CPF.

**Verificação de ancoragem numérica.** Todo valor monetário da resposta é extraído por
expressão regular, convertido para número e comparado com o conjunto de valores presentes
no contexto entregue ao modelo. Um valor ausente do conjunto reprova a resposta.

Esse é o controle que transforma anti-alucinação de intenção declarada em verificação
mensurável. O agente não pede ao modelo que não invente números, ele detecta quando o
modelo inventa.

**Substituição segura.** Quando a ancoragem falha, a resposta do modelo é descartada e o
motor determinístico produz a resposta, que passa por nova verificação. O usuário nunca vê
um número não verificado. A violação `resposta_substituida_por_falha_de_ancoragem` fica
registrada na auditoria.

### Camada 4 — Trilha de auditoria

Cada interação gera um registro em `logs/auditoria.jsonl` com momento, sessão, categoria,
regra acionada, indicador de bloqueio, provedor, modelo, latência, violações detectadas,
quantidade de dados mascarados e resultado da ancoragem.

A mensagem do usuário é gravada apenas depois do mascaramento e truncada em 300 caracteres.
O log não se torna, ele próprio, um repositório de dados sensíveis.

O painel de auditoria da aplicação lê esse arquivo e apresenta as estatísticas agregadas,
o que permite demonstrar a eficácia dos controles em vez de afirmá-la.

---

## Mapeamento OWASP Top 10 para Aplicações com LLM

| Risco | Aplicabilidade ao MAX | Controle implementado |
|---|---|---|
| **LLM01 — Prompt Injection** | Alta. Entrada livre do usuário. | Guardrails `INJ-01` a `INJ-05` em código, antes da chamada ao modelo. Regra 8 do system prompt como camada complementar. Seis casos de teste na bateria. |
| **LLM02 — Insecure Output Handling** | Média. A saída é renderizada como markdown. | Mascaramento de PII e verificação de ancoragem antes da renderização. A aplicação não interpreta a saída como comando nem a repassa a outro sistema. |
| **LLM03 — Training Data Poisoning** | Baixa. Não há treinamento nem ajuste fino. | Fora de escopo. A base de conhecimento é versionada no repositório e revisada por pull request. |
| **LLM04 — Model Denial of Service** | Média. Chamadas a provedor externo. | Tempo limite configurável em `TIMEOUT_LLM`, histórico limitado às seis últimas mensagens e teto de tokens na requisição. |
| **LLM05 — Supply Chain Vulnerabilities** | Média. Dependências de terceiros. | Cinco dependências diretas com versão mínima fixada, sem scikit-learn nem framework de orquestração. Integração contínua executa testes a cada alteração. |
| **LLM06 — Sensitive Information Disclosure** | Alta. O agente opera sobre dados financeiros. | Três camadas: bloqueio do pedido na entrada (`EXF`), sanitização do contexto antes do envio e mascaramento da saída. Cinco casos de teste na bateria. |
| **LLM07 — Insecure Plugin Design** | Não aplicável. | O agente não expõe nem consome ferramentas externas. |
| **LLM08 — Excessive Agency** | Alta. Um agente financeiro com permissão de execução seria alvo de alto valor. | O agente é estritamente consultivo por projeto. Não existe função de escrita, transferência ou alteração cadastral no código. As regras `TRX` bloqueiam a solicitação antes mesmo de chegar ao modelo. |
| **LLM09 — Overreliance** | Alta. Decisões financeiras baseadas em saída de modelo. | Cálculo determinístico em Python, verificação de ancoragem, exibição da regra que originou cada alerta e limitações declaradas na interface e na documentação. Cada alerta de fraude vem acompanhado da instrução de verificação humana. |
| **LLM10 — Model Theft** | Não aplicável. | Não há modelo proprietário. Os provedores são intercambiáveis. |

---

## Segurança como conteúdo

O desafio prevê duas frentes de cibersegurança. A seção anterior trata da segurança interna
do agente. Esta trata do que o agente ensina.

O MAX orienta a equipe financeira sobre os golpes que efetivamente atingem PMEs
brasileiras, a partir de seis documentos versionados em `data/kb_golpes/`. A escolha dos
temas segue o perfil de risco real do setor de contas a pagar, não uma lista genérica de
boas práticas:

- Fraude do falso fornecedor, que explora a rotina de alteração cadastral
- Golpe do boleto adulterado, incluindo sequestro de área de transferência por malware
- Golpe do falso funcionário do banco, com engenharia social por telefone
- Fraude do CEO e comprometimento de e-mail corporativo
- Golpes com Pix e o Mecanismo Especial de Devolução
- Proteção de credenciais, phishing e obrigações da LGPD

A orientação não fica restrita ao canal de perguntas. Quando o motor antifraude classifica
um pagamento como de risco alto ou crítico, a orientação prática de verificação acompanha o
alerta, no momento em que ela é útil. A instrução de confirmar por telefone em número já
cadastrado antes da solicitação suspeita é o controle que efetivamente derruba a fraude do
falso fornecedor, e por isso aparece em toda orientação de risco elevado.

---

## O que não está implementado

Registrado aqui porque um modelo de ameaças honesto declara as lacunas.

- **Autenticação e autorização.** O protótipo não tem controle de acesso. Em produção, o
  agente precisaria herdar a identidade e as permissões do usuário no sistema corporativo,
  e a alçada de aprovação teria que ser verificada contra o perfil real, não contra um
  campo de arquivo.
- **Limitação de taxa.** Não há limite de requisições por sessão. Em produção seria
  necessário para conter tanto abuso quanto custo.
- **Criptografia da trilha de auditoria.** O log é gravado em texto puro, protegido apenas
  pelo mascaramento. Em produção deveria ser cifrado em repouso e ter retenção definida.
- **Detecção semântica de injeção.** A detecção atual é baseada em padrões. Um atacante
  determinado pode formular a tentativa fora dos padrões cobertos. Uma camada
  classificadora complementar reduziria essa lacuna.
- **Segregação de ambiente.** Provedor, chaves e dados convivem no mesmo processo. Em
  produção, o acesso ao provedor deveria passar por um serviço intermediário com as chaves
  isoladas.
