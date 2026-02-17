# Data Insights

**Transforme perguntas em respostas.** Consulte seus dados usando linguagem natural com um agente de IA que converte suas perguntas em SQL automaticamente.

Desenvolvido por [Sergio Gaiotto](https://www.falagaiotto.com.br) — Especialista, pesquisador e educador em dados e inteligência artificial aplicada.

---

## Sobre

Data Insights é uma aplicação open-source que permite a qualquer pessoa consultar bancos de dados usando português natural, sem precisar escrever SQL. O sistema utiliza um agente LangGraph com OpenAI para interpretar perguntas, gerar consultas SQL, executar no banco SQLite e apresentar os resultados de forma clara com insights automáticos.

Faz parte de uma iniciativa aplicada da [Fala Gaiotto](https://www.falagaiotto.com.br) para democratizar o acesso a dados e inteligência artificial.

---

## Funcionalidades

| Recurso                           | Descrição                                                                       |
|-----------------------------------|---------------------------------------------------------------------------------|
| **Consulta em linguagem natural** | Pergunte em português e receba respostas com SQL gerado automaticamente         |
| **Upload de Excel**               | Importe arquivos `.xlsx` — cada aba vira uma tabela no banco (cria ou atualiza) |
| **Tabelas existentes**            | Trabalhe diretamente com tabelas já cadastradas, sem necessidade de upload      |
| **System Prompts customizados**   | Configure tipos de análise com guardrails de entrada e saída                    |
| **Exportação Excel**              | Exporte os resultados de qualquer consulta para `.xlsx`                         |
| **Envio por email**               | Envie resultados via Outlook com introdução padrão e anexo Excel                |
| **API externa**                   | Integração REST com autenticação por chave SHA256+salt                          |
| **Contexto de conversa**          | Faça perguntas de acompanhamento mantendo o contexto anterior                   |
| **Identidade visual**             | Dark theme Fala Gaiotto, responsivo, Tailwind CSS                               |

---

## Arquitetura

Projeto em arquitetura vertical com separação clara de responsabilidades:

```
data-insights/
├── run.py                         # Ponto de entrada (uvicorn)
├── requirements.txt               # Dependências Python
├── .env                           # Variáveis de ambiente
│
├── app/
│   ├── main.py                    # FastAPI app + startup
│   │
│   ├── api/
│   │   └── routes.py              # 15 endpoints REST
│   │
│   ├── core/
│   │   ├── config.py              # Settings via pydantic-settings
│   │   ├── database.py            # SQLite: schema, CRUD, read-only SQL
│   │   └── security.py            # API keys com SHA256 + salt
│   │
│   ├── models/
│   │   └── schemas.py             # Pydantic: request/response models
│   │
│   ├── services/
│   │   ├── agent_service.py       # LangGraph: agente NL → SQL (3 tools)
│   │   ├── email_service.py       # Envio Outlook/Exchange + anexo Excel
│   │   └── excel_service.py       # Import multi-aba Excel → SQLite
│   │
│   ├── templates/
│   │   └── default.html           # Frontend SPA (4 abas)
│   │
│   └── static/                    # CSS/JS (opcional)
│
├── data/                          # Banco SQLite (auto-criado)
└── uploads/                       # Arquivos Excel enviados
```

---

## Stack Tecnológica

| Camada         | Tecnologia                               |
|----------------|------------------------------------------|
| Backend        | Python 3.11 + FastAPI + Uvicorn          |
| Agente IA      | LangGraph + LangChain + OpenAI (gpt-4.1) |
| Banco de dados | SQLite                                   |
| Frontend       | HTML + Tailwind CSS + JavaScript         |
| Email          | exchangelib (Outlook / Exchange)         |
| Segurança      | SHA256 + salt (API keys)                 |

---

## Setup

### 1. Clone e crie o ambiente virtual

```bash
git clone <repo-url> data-insights
cd data-insights
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux / Mac
```

### 2. Instale as dependências

```bash
pip install -r requirements.txt
```

### 3. Configure o `.env`

Edite o arquivo `.env` na raiz do projeto:

```env
OPENAI_API_KEY=sk-sua-chave-aqui
OPENAI_MODEL=gpt-4.1
```

### 4. Execute

```bash
python run.py
```

Acesse **http://localhost:8000**

---

## Variáveis de Ambiente

| Variável         | Obrig | Descrição                                           |
|------------------|-------|-----------------------------------------------------|
| `OPENAI_API_KEY` | Sim   | Chave da API OpenAI                                 |
| `OPENAI_MODEL`   | Não   | Modelo a utilizar (padrão: `gpt-4.1`)               |
| `API_SALT`       | Não   | Salt para hash SHA256 das API keys                  |
| `API_SECRET_KEY` | Não   | Chave secreta da aplicação                          |
| `EMAIL_ADDRESS`  | Não   | Email Outlook para envio de resultados              |
| `EMAIL_PASSWORD` | Não   | Senha ou app password do email                      |
| `EMAIL_SERVER`   | Não   | Servidor Exchange (padrão: `outlook.office365.com`) |
| `HOST`           | Não   | Host do servidor (padrão: `0.0.0.0`)                |
| `PORT`           | Não   | Porta do servidor (padrão: `8000`)                  |

---

## Como Usar

### Consultar dados

1. Abra a aba **Consultar**
2. Selecione um **Tipo de Análise** no combobox (opcional)
3. Digite sua pergunta em português, por exemplo:
   - *"Quais tabelas existem?"*
   - *"Mostre os 10 primeiros registros da tabela vendas"*
   - *"Qual o total de vendas por categoria?"*
   - *"Quais regiões estão abaixo da meta?"*
4. O agente gera o SQL, executa e apresenta os resultados com insights

### Importar dados via Excel

1. Abra a aba **Tabelas**
2. Arraste um arquivo `.xlsx` para a área de upload ou clique para selecionar
3. Cada aba do Excel vira uma tabela no banco:
   - Se a tabela **não existe** → cria automaticamente
   - Se a tabela **já existe** → acrescenta os dados (append)

### Configurar tipos de análise

1. Abra a aba **Configurar**
2. Crie um novo tipo ou edite um existente
3. Defina:
   - **System Prompt** — instrução base para o agente
   - **Guardrails de Entrada** — regras de validação da pergunta
   - **Guardrails de Saída** — regras de formatação da resposta

### Exportar e compartilhar

- **Excel**: clique em *Exportar Excel* nos resultados para baixar `.xlsx`
- **Email**: clique em *Enviar Email* para enviar via Outlook com anexo

---

## API Externa

Integre com qualquer sistema via REST API autenticada.

### Gerar uma chave

1. Abra a aba **API** na interface
2. Informe um label e clique em **Gerar**
3. Copie a chave (exibida apenas uma vez)

### Fazer consultas

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: SUA_CHAVE_AQUI" \
  -d '{"question": "Qual o total de vendas por região?"}'
```

### Resposta

```json
{
  "question": "Qual o total de vendas por região?",
  "sql_generated": "SELECT regiao, total_vendas FROM regioes ORDER BY total_vendas DESC",
  "explanation": "A região Sudeste lidera com o maior volume...",
  "data": {
    "columns": ["regiao", "total_vendas"],
    "rows": [...],
    "row_count": 5
  }
}
```

### Segurança

As chaves de API são armazenadas com hash **SHA256 + salt**. O valor original nunca é salvo no banco de dados.

---

## Endpoints Disponíveis

| Método   | Rota                         | Descrição                             |
|----------|------------------------------|---------------------------------------|
| `GET`    | `/`                          | Interface web (SPA)                   |
| `GET`    | `/api/tables`                | Listar tabelas do banco               |
| `GET`    | `/api/tables/{name}/preview` | Preview de uma tabela                 |
| `POST`   | `/api/upload`                | Upload de arquivo Excel               |
| `POST`   | `/api/query`                 | Consulta em linguagem natural         |
| `GET`    | `/api/analysis-types`        | Listar tipos de análise               |
| `POST`   | `/api/analysis-types`        | Criar tipo de análise                 |
| `PUT`    | `/api/analysis-types/{id}`   | Atualizar tipo de análise             |
| `DELETE` | `/api/analysis-types/{id}`   | Excluir tipo de análise               |
| `POST`   | `/api/export/excel`          | Exportar dados para Excel             |
| `POST`   | `/api/email`                 | Enviar resultado por email            |
| `POST`   | `/api/keys`                  | Gerar nova API key                    |
| `GET`    | `/api/keys`                  | Listar API keys                       |
| `POST`   | `/api/v1/query`              | Consulta via API externa (autenticada)|
| `GET`    | `/api/history`               | Histórico de consultas                |

---

## Identidade Visual

| Elemento       | Valor                    |
|----------------|--------------------------|
| Background     | `#161b22` / `#0d1117`    |
| Accent         | `#ff6347` (tomato)       |
| Texto          | `#9595ad`                |
| Verde destaque | `#39d353`                |
| Tipografia     | Courier New (monospace)  |
| Framework CSS  | Tailwind CSS (CDN)       |
| Layout         | Responsivo (mobile-first)|

---

## Licença

Apache 2.0

---

<p align="center">
  <strong>DATA</strong><span style="color:#ff6347">INSIGHTS</span><br>
  <a href="https://www.falagaiotto.com.br">falagaiotto.com.br</a>
</p>
