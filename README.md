# Brasamiga: landing page + painel admin

Site do Brasamiga, buffet de churrasco: landing page com chamada para orçamento, serviços, cardápio, galeria de eventos realizados e agenda de próximos eventos, mais um painel em `/admin` para cadastrar eventos com fotos e vídeos e ver os pedidos de orçamento.

Stack: Python 3.14, FastAPI, Jinja2, SQLite.

## Rodando

```bash
uv sync
cp .env.example .env        # depois troque ADMIN_PASSWORD
uv run uvicorn app.main:create_app --factory --reload
```

- Site: http://127.0.0.1:8000
- Painel: http://127.0.0.1:8000/admin (usuário e senha do `.env`)

Sem `ADMIN_PASSWORD` no `.env`, o painel fica desligado.

## Onde colocar logo, cardápio e fotos

Na pasta [`conteudo/`](conteudo/LEIA-ME.md):

```
conteudo/
├── site.toml              textos, WhatsApp, Instagram, serviços e cardápio em texto
├── logo/                  logo da marca
├── cardapio/              cardápio em PDF e/ou fotos
└── eventos-realizados/    fotos e vídeos soltos de festas já feitas
```

Para fotos organizadas por evento (com nome, data e local), use o painel `/admin`. Os arquivos enviados por lá ficam em `data/uploads/`, e o banco fica em `data/brasamiga.db`.

## Painel admin

- **Cadastrar evento:** nome, data, local, descrição e situação (já realizado → galeria; vai acontecer → agenda). Aceita várias fotos e vídeos de uma vez.
- **Editar evento:** muda os dados, envia mais arquivos e exclui fotos ou vídeos.
- **Pedidos de orçamento:** tudo o que chega pelo formulário do site, com a opção de marcar como respondido.

## Testes

```bash
uv run pytest
```

## Publicando

Antes de colocar no ar, use HTTPS (a senha do painel é enviada a cada requisição) e faça backup da pasta `data/`. O WhatsApp e os contatos do `site.toml` vêm com valores de exemplo marcados com `TROCAR`.
