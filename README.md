# Brasamiga · landing page + painel admin

Site do Brasamiga, churrasco para eventos em São Paulo, com a identidade visual da Proposta Comercial 2026:
pacotes com preços, quem somos, galeria de eventos, agenda, condições, FAQ e pedido de orçamento que
fica salvo no painel e abre o WhatsApp com a mensagem pronta.

## Rodando com Docker (recomendado)

```bash
cp .env.example .env          # troque ADMIN_PASSWORD
docker compose up --build
```

- Site: http://localhost:8000
- Painel: http://localhost:8000/admin (usuário e senha do `.env`)

Banco, fotos enviadas pelo painel e versões otimizadas ficam no volume `brasamiga-data`.
A pasta `conteudo/` é lida direto do seu computador: troque fotos ou edite o `site.toml` e recarregue a página.

## Rodando sem Docker

```bash
uv sync
cp .env.example .env
uv run uvicorn app.main:create_app --factory --reload
```

Sem ffmpeg instalado, os vídeos não são convertidos: os da pasta não aparecem e os enviados pelo painel
ficam no formato original.

## Onde editar o quê

| O quê | Onde |
|---|---|
| Pacotes, preços, textos, FAQ, WhatsApp | `conteudo/site.toml` |
| Logo | `conteudo/logo/` (`logo_escuro` no `site.toml` diz qual arquivo usar) |
| PDF da proposta (botão "Baixar") | `conteudo/cardapio/` |
| Fotos e vídeos soltos da galeria | `conteudo/eventos-realizados/` |
| Eventos com nome, data, local e fotos | Painel `/admin` |
| Pedidos de orçamento | Painel `/admin` |

## Testes

```bash
uv run pytest -q
```

## Indo para a Vercel (futuro)

1. Criar um Postgres (Neon) e definir `DATABASE_URL`; adicionar o driver (`uv add "psycopg[binary]"`).
2. Implementar `BlobStorage` em `app/storage.py` e definir `STORAGE_BACKEND=blob` + `BLOB_READ_WRITE_TOKEN`.
3. Rodar `uv run python -m app.preparar` no build para gerar as fotos otimizadas.
4. Uploads acima de 4,5 MB precisam ir direto do navegador para o Blob.
