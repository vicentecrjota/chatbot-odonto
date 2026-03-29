# chatbot-odonto

Chatbot orientado ao contexto odontológico: API em Python para conversas assistidas por modelo de linguagem, com separação clara entre rotas, domínio, integrações e prompts.

## Estrutura do repositório

| Caminho | Função |
|--------|--------|
| `app/main.py` | Ponto de entrada da aplicação (FastAPI / Uvicorn). |
| `app/api/` | Rotas HTTP, dependências de request/response. |
| `app/core/` | Configuração, utilidades centrais e constantes. |
| `app/models/` | Esquemas e modelos de dados (ex.: Pydantic). |
| `app/services/` | Regras de negócio, orquestração e chamadas a APIs externas. |
| `app/prompts/` | Textos de system prompt e templates para o LLM. |
| `dashboard/` | Espaço reservado para interface web ou painel administrativo. |
| `scripts/` | Scripts auxiliares (migrações, seeds, tarefas locais). |
| `tests/` | Testes automatizados. |

Na raiz ficam `Dockerfile`, `docker-compose.yml`, `requirements.txt` e `.env.example` para ambiente reproduzível e variáveis de configuração.

## Pré-requisitos

- Python 3.12+ (recomendado)
- Opcional: Docker e Docker Compose

## Configuração local

1. Crie um ambiente virtual e instale dependências:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Copie as variáveis de ambiente:

   ```bash
   copy .env.example .env
   ```

   Edite `.env` com chaves e URLs reais (nunca commite `.env`; ele está no `.gitignore`).

## Executar a API

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Documentação interativa: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## Docker

Com `.env` presente na raiz:

```bash
docker compose up --build
```

A API fica em [http://localhost:8000](http://localhost:8000).

## Próximos passos sugeridos

- Registrar routers em `app/api/` e incluí-los em `app/main.py`.
- Centralizar leitura de config em `app/core/` (ex.: `pydantic-settings`).
- Implementar o fluxo do chatbot em `app/services/` e prompts em `app/prompts/`.

## Licença

Defina a licença do projeto conforme a política da sua organização.
