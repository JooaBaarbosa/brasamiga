# Brasamiga · landing page + painel admin

Site do Brasamiga, churrasco para eventos em São Paulo, com a identidade visual da Proposta Comercial 2026:
pacotes com preços, quem somos, galeria de eventos, agenda, condições, FAQ e pedido de orçamento que
fica salvo no painel e abre o WhatsApp com a mensagem pronta.

> As fotos e vídeos dos eventos (`conteudo/eventos-realizados/`) e a proposta comercial em PDF
> (`conteudo/cardapio/`) não fazem parte do repositório: as fotos originais trazem a localização (GPS)
> do celular. Coloque seus próprios arquivos nessas pastas; o site gera versões web sem GPS sozinho.

## Rodando com Docker (recomendado)

### 0. Preparar a máquina (uma vez só)

- Docker Desktop instalado e **aberto**. Confira com `docker info`: ele precisa mostrar a versão do
  servidor. Se aparecer `failed to connect to the docker API`, o Docker Desktop está fechado.

### 1. Clonar ou atualizar

```bash
git clone https://github.com/JooaBaarbosa/brasamiga.git && cd brasamiga
```

Se já tem o clone, rode `git status -sb`. Se aparecer `[behind N]`, atualize com `git pull --ff-only`.

### 2. Liberar a porta 8000

O site usa a porta 8000. Rode `docker ps`: se outro projeto estiver nessa porta, pare-o com
`docker compose down` na pasta dele. Sem isso, a subida falha com `port is already allocated`.

### 3. Configurar o `.env`

```bash
cp .env.example .env
```

Troque `ADMIN_PASSWORD` (é a senha do painel).

### 4. Build e subida

```bash
docker compose up -d --build --wait
```

- O comando só termina quando o site está saudável. Confira com `docker compose ps`: `healthy`.
- Erro `Unable to connect to deb.debian.org` (ou outro download) é falha de rede: rode o mesmo comando de novo.
- Se o container parar, veja o motivo com `docker compose logs web --tail 20`.

### 5. Conferir

- Site: http://localhost:8000
- Painel: http://localhost:8000/admin (usuário e senha do `.env`)

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/healthz   # 200
```

### 6. Desligar

```bash
docker compose down        # os dados ficam no volume
docker compose down -v     # apaga também o banco e as fotos enviadas pelo painel
```

Banco, fotos enviadas pelo painel e versões otimizadas ficam no volume `brasamiga-data`.
A pasta `conteudo/` é lida direto do seu computador: troque fotos ou edite o `site.toml` e recarregue a página.
Vídeos novos em `conteudo/eventos-realizados/` aparecem depois de `docker compose restart` (são convertidos para MP4 na inicialização).

Se o site avisar que o banco é "de uma versão antiga", apague a pasta `data/` (ela é da primeira versão do site e não tem pedidos novos).

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
| Foto de capa | `conteudo/eventos-realizados/` (`foto_capa` no `site.toml`) |
| Fotos e vídeos para a galeria | `conteudo/eventos-realizados/` → painel `/admin` → "Fotos sem evento" |
| Eventos (agenda e galeria) | Painel `/admin` |
| Pedidos de orçamento | Painel `/admin` |
| Montagem/folga da agenda, tipos de evento e faixas de convidados | `[agenda]` e `[galeria]` no `site.toml` |

## Agenda e galeria

- **Agenda:** cadastre os próximos eventos no painel com **início e fim**. Cada evento bloqueia a equipe de
  `início − montagem` até `fim + folga` (`montagem_horas` e `folga_horas` em `[agenda]`, padrão 1h cada).
  Dois eventos no mesmo dia são aceitos se esses blocos não se sobrepõem; se conflitarem, o painel diz com qual
  evento e nada é salvo. Fim antes do início = o evento termina no dia seguinte.
- **No site**, o calendário mostra só os horários ocupados. **Nome, local e descrição de um evento nunca
  aparecem no site** — nem na agenda, nem na galeria.
- **Galeria:** cada evento realizado com fotos vira um card com carrossel. O cliente vê só o **título para o
  site**, o tipo, o número de convidados, o mês/ano e o pacote servido, e pode buscar e filtrar por tipo e faixa
  de convidados.
- **Fotos da pasta:** as fotos de `conteudo/eventos-realizados/` aparecem no painel em **"Fotos sem evento"**.
  Marque as fotos e escolha "Adicionar ao evento" (ou "Ignorar"). Só fotos que pertencem a um evento aparecem
  no site. Se um evento for excluído, as fotos dele voltam para "Fotos sem evento".
- **Textos alternativos:** cada foto do evento tem o campo "Descrição da foto"; sem ele, o site usa
  "Foto 2 de 5 do evento: título para o site".

## Testes

```bash
uv run pytest -q
```

## Indo para a Vercel (futuro)

1. Criar um Postgres (Neon) e definir `DATABASE_URL`; adicionar o driver (`uv add "psycopg[binary]"`).
2. Implementar `BlobStorage` em `app/storage.py` e definir `STORAGE_BACKEND=blob` + `BLOB_READ_WRITE_TOKEN`.
3. Rodar `uv run python -m app.preparar` no build para gerar as fotos otimizadas.
4. Uploads acima de 4,5 MB precisam ir direto do navegador para o Blob.
