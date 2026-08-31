# Base de Conhecimento

O MAX consulta duas bases distintas. A primeira é estruturada e alimenta os cálculos de
tesouraria e a análise antifraude. A segunda é textual e responde às perguntas de
orientação sobre golpes financeiros.

---

## Base estruturada

| Arquivo | Formato | Uso no agente |
|---|---|---|
| `perfil_empresa.json` | JSON | Saldo em conta, faturamento, custo fixo, alçada de aprovação e política interna de pagamentos |
| `transacoes.csv` | CSV | Agenda financeira que alimenta a projeção diária de saldo |
| `beneficiarios.csv` | CSV | Cadastro cruzado com cada pagamento para produzir os sinais de fraude |
| `linhas_credito.json` | JSON | Catálogo com taxa mensal, limite e prazo de liberação de cada produto |
| `historico_atendimento.csv` | CSV | Contexto de relacionamento que calibra a abordagem do agente |

### Adaptações em relação aos dados do repositório base

O desafio fornece dados de pessoa física voltados a investimentos. Como o caso de uso é
tesouraria de pessoa jurídica, os arquivos foram reconstruídos:

- `perfil_investidor.json` deu lugar a `perfil_empresa.json`, com razão social, setor,
  faturamento, custo fixo e alçada de aprovação em vez de idade e renda pessoal.
- `produtos_financeiros.json` deu lugar a `linhas_credito.json`, com produtos de cobertura
  de caixa em vez de CDB e fundos.
- `beneficiarios.csv` foi criado do zero. É a base que torna a análise antifraude possível,
  porque sem histórico de conta, canal de alteração e titularidade não há como distinguir
  um pagamento rotineiro de uma tentativa de fraude.
- `transacoes.csv` ganhou as colunas `beneficiario_id` e `canal_solicitacao`, e foi montado
  com dois problemas propositais: um furo de caixa entre o quinto e o sétimo dia do
  horizonte e dois pagamentos com indícios de fraude.

### Cenário construído

O cenário é desenhado para que as duas exposições apareçam ao mesmo tempo e o gestor tenha
que priorizar.

**Furo de caixa.** O saldo parte de R$ 14.500,00. Folha de pagamento e aluguel vencem no
mesmo dia, seguidos de manutenção e reforma de maquinário. O recebimento de cartões só
entra seis dias depois do pior saldo. Considerando os pagamentos suspeitos retidos, a
necessidade de cobertura é de R$ 32.300,00.

**Indícios de fraude.** Dois pagamentos somam R$ 41.100,00, valor superior ao próprio furo
de caixa. É esse contraste que sustenta a tese do projeto: em uma PME, prevenir uma fraude
protege mais capital do que otimizar uma taxa de juros.

| Transação | Valor | Classificação | Sinais |
|---|---|---|---|
| TRX-005 | R$ 18.700,00 | CRÍTICO (100/100) | Conta alterada há poucos dias, solicitação por e-mail, titular divergente da razão social, valor acima do histórico |
| TRX-010 | R$ 22.400,00 | CRÍTICO (75/100) | Beneficiário recém-cadastrado sem histórico, valor acima da alçada, solicitação por WhatsApp |
| TRX-009 | R$ 9.600,00 | MÉDIO (20/100) | Valor acima do padrão histórico do fornecedor |

### Datas sempre atuais

Os arquivos guardam datas fixas, mas o motor de dados calcula, no carregamento, a diferença
entre a data mais antiga da agenda e a data corrente menos doze dias, e desloca todas as
datas por esse intervalo. O espaçamento original entre lançamentos é preservado.

O deslocamento é aplicado às transações, às datas de cadastro e de alteração de conta dos
beneficiários e ao histórico de atendimento em conjunto, o que mantém a coerência das
regras antifraude que dependem de janela temporal, como conta alterada nos últimos quinze
dias.

O efeito prático é que o cenário funciona em qualquer data de execução. Quem avaliar o
projeto meses depois vê um furo de caixa a poucos dias de distância, não uma agenda vencida.

---

## Base de conhecimento textual

Seis documentos em `data/kb_golpes/` cobrem os golpes que mais atingem o setor financeiro
de empresas brasileiras:

| Documento | Tema |
|---|---|
| `fraude-do-falso-fornecedor.md` | Troca de dados bancários de credor conhecido |
| `golpe-do-boleto-adulterado.md` | Linha digitável alterada e sequestro de área de transferência |
| `golpe-do-falso-funcionario-do-banco.md` | Engenharia social por telefone, token e acesso remoto |
| `fraude-do-ceo.md` | Comprometimento de e-mail corporativo e ordem falsa de transferência |
| `golpes-com-pix.md` | QR Code adulterado, chave trocada, falso comprovante e o Mecanismo Especial de Devolução |
| `seguranca-de-acessos-e-dados.md` | Credenciais, phishing, acesso remoto e obrigações da LGPD |

Cada documento segue a mesma estrutura: como funciona, sinais de alerta, como se proteger e
o que fazer se o prejuízo já ocorreu. A padronização não é estética, é funcional: permite
que a recuperação selecione a seção certa conforme a intenção da pergunta.

### Como a recuperação funciona

A indexação acontece em três etapas, todas em `src/knowledge_base.py`:

1. **Fatiamento.** Cada documento é dividido por cabeçalho de segunda ordem, gerando
   trechos curtos e temáticos em vez de documentos inteiros. Os metadados do cabeçalho
   YAML, título e tags, entram na indexação de cada trecho.
2. **Vetorização.** TF-IDF com normalização de plurais, implementado em Python puro. Não há
   dependência de scikit-learn, o que mantém a instalação leve e o critério de recuperação
   auditável.
3. **Busca.** Similaridade de cosseno entre a pergunta e cada trecho, com limiar mínimo
   para evitar retorno de conteúdo irrelevante.

Sobre o resultado bruto, o agente aplica duas seleções. Primeiro escolhe o documento com
maior soma de relevância entre os trechos recuperados, o que evita responder sobre boleto
quando a pergunta é sobre Pix. Depois escolhe a seção dentro daquele documento conforme a
intenção detectada: quem pergunta "como identificar" recebe os sinais de alerta, quem
pergunta "o que fazer" recebe o procedimento de resposta ao incidente.

---

## Como os dados entram no prompt

Os arquivos nunca são despejados crus no contexto. O construtor de contexto
(`src/context_builder.py`) monta um bloco de texto com os resultados já calculados:

1. O motor de dados projeta o caixa em dois cenários, com e sem os pagamentos suspeitos.
2. O motor antifraude pontua cada pagamento pendente e produz os alertas com justificativa.
3. A base de conhecimento devolve até dois trechos relacionados à pergunta.
4. O bloco resultante passa pelo mascaramento de dados identificáveis antes de ser enviado
   ao provedor do modelo.

Em paralelo, é montado o conjunto de todos os valores monetários presentes no contexto.
Esse conjunto é o universo aceito pela verificação de ancoragem na saída. Um valor citado
na resposta que não esteja nele reprova a resposta.

### Exemplo de contexto montado

```
[CONTEXTO CALCULADO PELO BACKEND]
Empresa: TechIndustrial Peças LTDA | Setor: Indústria metalúrgica | Perfil de risco: Conservador
Data de referencia: 30/08/2026 | Horizonte analisado: 21 dias
Saldo atual em conta: R$ 14.500,00
Alcada de aprovacao: R$ 20.000,00

PROJECAO DE CAIXA (pagamentos suspeitos retidos):
- Entradas previstas: R$ 60.000,00
- Saidas previstas: R$ 46.800,00
- Saldo ao fim do horizonte: R$ 27.700,00
- Primeiro dia com saldo negativo: 04/09/2026
- Pior saldo do periodo: -R$ 32.300,00 em 06/09/2026
- Necessidade de caixa a cobrir: R$ 32.300,00

CENARIO SEM RETENCAO DOS PAGAMENTOS SUSPEITOS:
- Pior saldo: -R$ 73.400,00
- Saldo final: -R$ 13.400,00

AGENDA DO PERIODO:
- 30/08/2026 | Energia eletrica - unidade fabril | -R$ 4.200,00 | saldo apos: R$ 10.300,00
- 04/09/2026 | Folha de pagamento | -R$ 25.000,00 | saldo apos: -R$ 14.700,00
...

RECOMENDACAO DE COBERTURA (calculada pelo backend):
- Linha indicada: Antecipação de Recebíveis de Cartão | taxa 1.85% ao mes | liberacao D+0
- Valor sugerido: R$ 32.300,00
- Custo estimado em 30 dias: R$ 597,55
- Custo pela alternativa mais cara (Cheque Especial PJ, 8.90% ao mes): R$ 2.874,70
- Economia estimada: R$ 2.277,15

ANALISE ANTIFRAUDE DOS PAGAMENTOS PENDENTES:
- Pagamentos analisados: 7 | criticos: 2 | altos: 0 | medios: 1
- Valor sob suspeita: R$ 41.100,00
- [CRITICO] TRX-005 | Pagamento Transportadora Rota Norte - NF 2214 | R$ 18.700,00 | pontuacao 100/100
    * R01 Conta bancaria alterada recentemente: O beneficiario possui 9 pagamentos anteriores
      e teve os dados bancarios alterados ha 4 dia(s).
    * R02 Alteracao solicitada por canal inseguro: solicitada por email.
    * R04 Titular da conta diverge do fornecedor.
    * Orientacao: Retenha o pagamento e confirme por telefone em numero ja cadastrado.
...
```

Note que o CNPJ da empresa, presente no arquivo de origem, não aparece no contexto. Ele é
removido pelo mascaramento antes do envio ao provedor.

---

## Privacidade dos dados

Todos os dados são fictícios e foram criados para este desafio. Nenhuma informação real de
cliente, funcionário ou fornecedor é utilizada.

Os documentos presentes nos arquivos são inventados e, mesmo assim, passam pelo
mascaramento antes de qualquer exibição ou envio ao provedor do modelo. A trilha de
auditoria também grava a mensagem do usuário apenas depois do mascaramento, de modo que o
arquivo de log não se torne um novo repositório de dados sensíveis.
