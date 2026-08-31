# Como executar

## Requisitos

Python 3.11 ou superior. Nada além disso para o modo padrão.

Confira a versão instalada:

```bash
python --version
```

Se o comando não existir, tente `python3 --version`. Em todos os comandos deste documento,
substitua `python` por `python3` se for o seu caso.

---

## Instalação

```bash
git clone https://github.com/vianahugo/max-tesouraria-antifraude.git
cd max-tesouraria-antifraude
```

Crie um ambiente virtual. Não é obrigatório, mas evita conflito com outros projetos.

```bash
python -m venv .venv
```

Ative o ambiente.

No Linux ou macOS:

```bash
source .venv/bin/activate
```

No Windows, com PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Se o PowerShell recusar a execução do script, rode uma vez:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Instale as dependências:

```bash
pip install -r requirements.txt
```

---

## Executar a aplicação

```bash
streamlit run src/app.py
```

O navegador abre em `http://localhost:8501`. Se não abrir sozinho, acesse o endereço
manualmente.

A aplicação inicia no modo offline, que usa o motor determinístico e não exige chave de
API. Todas as funcionalidades estão disponíveis nesse modo: projeção de caixa, análise
antifraude, guardrails, base de conhecimento e trilha de auditoria.

Para encerrar, pressione `Ctrl+C` no terminal.

---

## Executar os testes

```bash
python -m pytest tests/ -q
```

Resultado esperado: 65 testes aprovados.

---

## Executar a avaliação do agente

```bash
python evaluate.py
```

O comando roda os 36 casos de `tests/casos.yaml`, grava os dados brutos em
`reports/avaliacao.json` e regenera `docs/04-metricas.md`.

Para rodar sem sobrescrever o relatório:

```bash
python evaluate.py --sem-relatorio
```

Para avaliar o comportamento de um provedor específico:

```bash
python evaluate.py --provider groq
```

---

## Usar um modelo de linguagem real

O modo offline serve para demonstração e para tornar a avaliação reprodutível. Para usar um
modelo de verdade, copie o arquivo de exemplo e edite:

```bash
cp .env.example .env
```

No Windows:

```powershell
copy .env.example .env
```

O provedor também pode ser trocado direto na barra lateral da aplicação, sem editar
arquivo, desde que a credencial correspondente já esteja configurada.

### Opção A — Groq (recomendada para quem quer testar rápido)

Camada gratuita generosa e resposta rápida.

1. Crie uma conta em `https://console.groq.com`
2. Gere uma chave em Keys
3. No arquivo `.env`:

```
LLM_PROVIDER=groq
GROQ_API_KEY=cole_sua_chave_aqui
```

### Opção B — Google Gemini

1. Gere uma chave em `https://aistudio.google.com/apikey`
2. No arquivo `.env`:

```
LLM_PROVIDER=gemini
GEMINI_API_KEY=cole_sua_chave_aqui
```

### Opção C — Ollama (100% local, sem enviar dados para fora)

Coerente com o caso de uso, já que dados financeiros não saem da máquina.

1. Instale o Ollama em `https://ollama.com`
2. Baixe um modelo:

```bash
ollama pull llama3.1:8b
```

3. No arquivo `.env`:

```
LLM_PROVIDER=ollama
LLM_MODEL=llama3.1:8b
OLLAMA_URL=http://localhost:11434
```

Um modelo de 8 bilhões de parâmetros roda em máquina com 8 GB de memória.

Evite modelos de raciocínio como `gpt-oss:20b` neste projeto. Eles gastam a maior parte do
orçamento de tokens em raciocínio interno antes de produzir a resposta final, o que em CPU
leva vários minutos por pergunta e frequentemente estoura o tempo limite. Quando isso
acontece, a aplicação recorre ao motor determinístico e informa o motivo no chat. Modelos
de instrução como `llama3.1:8b`, `qwen2.5:7b-instruct` ou `mistral:7b-instruct` respondem
em segundos e são a escolha certa para a demonstração.

O botão Testar o provedor, na barra lateral, envia uma requisição curta e mostra o tempo de
resposta. Use antes de gravar o vídeo.

---

## Variáveis de configuração

| Variável | Padrão | Função |
|---|---|---|
| `LLM_PROVIDER` | `offline` | Provedor: `offline`, `ollama`, `groq` ou `gemini` |
| `LLM_MODEL` | vazio | Modelo específico. Vazio usa o padrão do provedor |
| `OLLAMA_URL` | `http://localhost:11434` | Endereço do Ollama local |
| `GROQ_API_KEY` | vazio | Chave da API Groq |
| `GEMINI_API_KEY` | vazio | Chave da API Gemini |
| `HORIZONTE_DIAS` | `21` | Janela da projeção de caixa |
| `TIMEOUT_LLM` | `600` | Tempo limite das chamadas, em segundos |

---

## Publicar na Streamlit Community Cloud

Deixa o projeto acessível por link, sem instalação. Vale muito para quem for avaliar.

1. Envie o repositório para o GitHub com visibilidade pública
2. Acesse `https://share.streamlit.io` e entre com a conta do GitHub
3. Clique em New app e selecione o repositório
4. Em Main file path, informe `src/app.py`
5. Clique em Deploy

O modo offline funciona sem qualquer configuração adicional. Se quiser usar Groq ou Gemini
no ambiente publicado, adicione a chave em Settings, Secrets, no formato:

```toml
LLM_PROVIDER = "groq"
GROQ_API_KEY = "sua_chave"
```

Depois de publicado, cole o link no topo do README.

Não publique o arquivo `.env`. Ele já está no `.gitignore`.

---

## Problemas comuns

**`streamlit: command not found`**
O ambiente virtual não está ativo ou as dependências não foram instaladas. Ative o ambiente
e rode `pip install -r requirements.txt` de novo.

**`ModuleNotFoundError: No module named 'src'`**
O comando está sendo executado de dentro da pasta `src`. Volte para a raiz do repositório e
rode `streamlit run src/app.py` a partir de lá.

**A barra lateral mostra o provedor como indisponível**
Para Ollama, confirme que o serviço está rodando com `ollama list`. Para Groq ou Gemini,
confirme que a chave está no `.env` e que o arquivo está na raiz do projeto. Em qualquer
caso a aplicação continua funcionando, usando o motor determinístico.

**A aba Auditoria está vazia**
É o comportamento esperado em uma sessão nova. Faça uma pergunta na aba Consultoria e os
registros aparecem.

**As datas do cenário parecem estranhas**
As datas são recalculadas a cada execução em relação ao dia corrente, por projeto. O
primeiro lançamento sempre fica doze dias no passado e o furo de caixa a poucos dias no
futuro. Ajuste em `DIAS_ANCORA_PASSADO`, no arquivo `src/config.py`.

**As respostas parecem sempre iguais, mesmo com um modelo configurado**
A aplicação recorre ao motor determinístico em duas situações: quando o provedor falha ou
demora além do tempo limite, e quando a verificação de ancoragem reprova a resposta por
citar um valor que não existe no contexto. Nos dois casos, um aviso amarelo aparece logo
abaixo da resposta explicando o motivo. Se o aviso indicar tempo limite, troque para um
modelo de instrução menor ou aumente `TIMEOUT_LLM`. Se indicar falha de ancoragem, é o
guardrail funcionando: o modelo inventou um número e a resposta foi descartada.
