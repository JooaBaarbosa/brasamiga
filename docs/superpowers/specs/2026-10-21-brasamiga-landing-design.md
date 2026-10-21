# Brasamiga: landing page + painel admin (design)

Data: 2026-10-21 · Status: aguardando revisão do dono

## 1. Objetivo

Landing page do Brasamiga (buffet de churrasco para eventos, SP capital e Grande SP) para **atrair clientes novos e levá-los a pedir orçamento**, apresentando a marca, os pacotes com preços, eventos já realizados e a agenda de próximos eventos. Um painel `/admin` permite ao dono cadastrar eventos (realizados e futuros) com fotos e vídeos e acompanhar os pedidos de orçamento.

**Sucesso:**
- O visitante entende em segundos o que é o Brasamiga, vê pacotes e preços e chega ao WhatsApp com a mensagem de orçamento já escrita.
- Nenhum pedido se perde: todo envio do formulário fica salvo no painel, mesmo que o cliente desista no WhatsApp.
- O dono atualiza preços e textos editando um arquivo de texto e publica fotos e vídeos pelo painel, sem mexer em código.
- O site carrega rápido no celular (fotos otimizadas, vídeos em MP4).

## 2. Decisões tomadas com o dono

| Tema | Decisão |
|---|---|
| Preços | Pacotes **com preços abertos** na landing, como no PDF |
| Edição de pacotes/textos | Arquivo `conteudo/site.toml` (sem tela no admin) |
| CTA do formulário | **Salva no painel e abre o WhatsApp** com mensagem pronta |
| Hospedagem | **Docker agora**; **Vercel no futuro** (arquitetura preparada) |
| Abordagem | A: refazer o visual do zero + armazenamento e banco trocáveis por configuração |
| Stack | Python 3.14 (padrão da pasta), FastAPI, Jinja2, SQLAlchemy Core |

## 3. Fonte de conteúdo e identidade

Fonte principal: `conteudo/cardapio/Brasamiga_Proposta_Comercial.pdf` (9 páginas). Logo: `conteudo/logo/` (LOGO-01 fundo branco, LOGO-02 fundo vermelho, LOGO-03 fundo preto, MARCA-BRASAMIGA). Mídias: `conteudo/eventos-realizados/` (21 fotos JPG/JPEG de 0,1 a 2,5 MB, 2 vídeos `.MOV`).

### 3.1 Tokens visuais

| Token | Valor | Uso |
|---|---|---|
| `--madeira` | `#1C1512` | Faixas escuras (hero, eventos, orçamento, rodapé) com textura de madeira + fumaça vermelha em CSS |
| `--papel` | `#F3EBDF` | Fundo das seções claras |
| `--papel-escuro` | `#EADFCE` | Linhas alternadas da tabela, caixas "Incluso no pacote" |
| `--brasa` | `#A93226` | Destaques, filetes, botões, quadradinhos "incluso" |
| `--cobre` | `#B8966A` | Subtítulos e textos auxiliares sobre o escuro |
| `--tinta` | `#1E1A17` | Texto |

Tipografia (Google Fonts): **Anton** para títulos em caixa alta condensada, **Oswald** para rótulos ("ENTRADAS", "INCLUSO NO PACOTE", nomes de pacote), **Lato** para o texto corrido. A caixa alta nos títulos e rótulos é da identidade do PDF e é mantida.

Elementos de marca: logo branco (LOGO-03, recortado/transparente quando possível; senão usado sobre o fundo preto) no topo e no hero; filete vermelho curto sob títulos; caixa escura com borda superior vermelha para preços e números; marca-d'água discreta da cabeça de boi; quadradinho vermelho = incluso na tabela comparativa; selo "MAIS PEDIDO" no Nelore.

### 3.2 Estrutura da página

1. **Topo:** logo + links (Pacotes, Eventos, FAQ) + botão WhatsApp.
2. **Hero (madeira):** logo grande, "CHURRASCO PARA EVENTOS", filete, "De reuniões em família a grandes eventos corporativos", botões "Pedir orçamento" e "Chamar no WhatsApp".
3. **Quem somos (papel):** texto do PDF (p. 2) + caixa escura com 2022 / SP / 15–200.
4. **Por que escolher:** Tudo incluso, Menu flexível, Serviço completo, Transparência.
5. **Nossos pacotes:** tabela comparativa (p. 3), que vira cards empilhados no celular; detalhe de cada pacote (p. 4–7) com cardápio completo em blocos que abrem e fecham; notas sobre faixas de desconto, crianças até 7 anos 50%, vegetarianos, porção ~450 g, bebidas à parte.
6. **Eventos realizados (madeira):** galeria das fotos e vídeos da pasta + eventos cadastrados no admin (título, data, local, mídias). Clique abre o visor.
7. **Próximos eventos:** agenda vinda do admin; some sozinha quando não há eventos futuros.
8. **Condições + FAQ:** serviço e horário, pagamento e reserva, perguntas frequentes (p. 8), em blocos que abrem e fecham.
9. **Orçamento (madeira, como a p. 9):** "VAMOS PLANEJAR O SEU EVENTO?" + formulário.
10. **Rodapé:** Instagram @brasamiga · BRASAMIGA · WhatsApp (11) 99343-3998. Botão flutuante de WhatsApp no celular.

O texto vem do PDF, sem inventar números, depoimentos ou promessas. O único movimento automático é uma entrada discreta do hero, desligada com `prefers-reduced-motion`.

## 4. Arquitetura

```
app/
  config.py        Settings a partir do .env
  db.py            SQLAlchemy Core: eventos, midias, orcamentos
  storage.py       Armazenamento (interface) · LocalStorage · BlobStorage (esqueleto)
  midia.py         validação, otimização de imagem (Pillow), conversão de vídeo (ffmpeg)
  conteudo.py      site.toml + pastas de conteudo/, cache das versões web
  whatsapp.py      montagem do link wa.me com a mensagem de orçamento
  rotas_site.py    GET /, POST /orcamento
  rotas_admin.py   /admin/*
  preparar.py      pré-otimiza conteudo/ (usado no build da Vercel)
  main.py          create_app()
  templates/, static/
conteudo/          editado pelo dono (site.toml, logo/, cardapio/, eventos-realizados/)
data/              volume: brasamiga.db, uploads/, cache/
Dockerfile, docker-compose.yml, .env.example
```

### 4.1 Configuração (`.env`)

| Variável | Padrão | Função |
|---|---|---|
| `ADMIN_USER` / `ADMIN_PASSWORD` | `admin` / vazio | Sem senha → painel desligado (503) |
| `DATABASE_URL` | `sqlite:///data/brasamiga.db` | Postgres depois, mesma API |
| `STORAGE_BACKEND` | `local` | `local` ou `blob` |
| `BLOB_READ_WRITE_TOKEN` | — | Só para `blob` |
| `DATA_DIR` / `CONTENT_DIR` | `./data` / `./conteudo` | Caminhos |
| `MAX_UPLOAD_MB` | `300` | Limite por arquivo |

### 4.2 Banco (SQLAlchemy Core)

- `eventos(id, titulo, data DATE NULL, local, descricao, tipo 'realizado'|'futuro', criado_em)`
- `midias(id, evento_id FK ON DELETE CASCADE, chave, chave_miniatura NULL, tipo 'imagem'|'video', criado_em)`. `chave` é o identificador no armazenamento, não um caminho de disco.
- `orcamentos(id, nome, telefone, email, data_evento, local, convidados, pacote, mensagem, lido, criado_em)`

As tabelas são criadas com `metadata.create_all` na inicialização. Migrations (Alembic) ficam fora do escopo até a primeira mudança de schema em produção.

### 4.3 Armazenamento

```python
class Armazenamento(Protocol):
    def salvar(self, chave: str, dados: BinaryIO, content_type: str) -> None: ...
    def apagar(self, chave: str) -> None: ...
    def url(self, chave: str) -> str: ...
```

- `LocalStorage`: grava em `data/uploads/`, servido em `/uploads/`.
- `BlobStorage`: esqueleto que levanta `NotImplementedError`, com a interface documentada e um ponteiro para a API do Vercel Blob. A implementação fica para a migração.

### 4.4 Mídia

- **Aceitos:** JPG, JPEG, PNG, WEBP, HEIC (via `pillow-heif`), MP4, MOV, WEBM. O tipo é checado pela extensão e pelo conteúdo (Pillow abre a imagem; ffprobe lê o vídeo).
- **Imagem:** corrige a rotação EXIF, remove metadados (inclusive GPS), gera WEBP de 1600 px de lado maior (q≈80) e miniatura de 600 px.
- **Vídeo:** `ffmpeg -c:v libx264 -crf 26 -preset veryfast -c:a aac -movflags +faststart`, limitado a 1080p. Se falhar, guarda o original e avisa no admin.
- **Pasta `conteudo/eventos-realizados/`:** versões web geradas sob demanda em `data/cache/`, com chave pelo nome, tamanho e data de modificação do original.

### 4.5 Fluxos

1. **GET /:** lê `site.toml` e pastas, busca eventos realizados (data desc) e futuros com data ≥ hoje ou sem data (data asc), e renderiza a página.
2. **POST /orcamento:** valida nome e telefone (obrigatórios); data, local, convidados, pacote e mensagem são opcionais; o campo-isca preenchido descarta o envio. Salva e responde `303` para `https://wa.me/5511993433998?text=<mensagem>`. Em erro, re-renderiza o formulário com os valores e a mensagem do que falta (status 400).
3. **Admin:** HTTP Basic com `compare_digest`; POST com `Origin` de outro host → 403. Cadastrar, editar e excluir evento; enviar e excluir mídias; marcar orçamento como respondido.

Modelo da mensagem do WhatsApp (só os campos preenchidos):
> Olá! Sou {nome} e quero um orçamento do Brasamiga. Pacote: {pacote}. Data: {dd/mm/aaaa}. Local: {local}. Convidados: {n}. {mensagem}

### 4.6 `site.toml`

Seções `[marca]`, `[contato]`, `[[numeros]]`, `[[diferenciais]]`, `[[pacotes]]` (nome, ordem, preço, unidade, resumo, destaque, itens por categoria, incluso), `[[comparativo]]` (linhas da tabela), `[notas]`, `[[condicoes]]` e `[[faq]]`, preenchidas com o conteúdo do PDF. Um erro de sintaxe vira uma página 500 legível com o arquivo e a linha.

## 5. Erros

| Situação | Comportamento |
|---|---|
| Arquivo com formato inválido ou acima do limite | Recusado com nome e motivo; os outros arquivos do envio seguem |
| ffmpeg falha | Original mantido + aviso no admin |
| `site.toml` inválido | Página de erro com arquivo e linha |
| Orçamento sem nome ou telefone | Formulário volta preenchido + mensagem |
| Admin sem `ADMIN_PASSWORD` | 503 explicando como ligar |

## 6. Docker

- `Dockerfile`: `python:3.14-slim` + `ffmpeg` + `uv`; `uv sync --frozen --no-dev`; usuário sem root; `uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000`.
- `docker-compose.yml`: serviço `web`, porta 8000, `env_file: .env`, volume nomeado `brasamiga-data:/app/data`, bind de `./conteudo:/app/conteudo:ro`, healthcheck em `/`.

## 7. Testes

pytest, sem rede:
- WhatsApp: mensagem com e sem campos opcionais, URL codificada.
- `conteudo`: leitura dos pacotes do `site.toml` real, erro com a linha, cache de imagens.
- `midia`: imagem gerada no teste (rotação EXIF, saída WEBP, GPS removido); vídeo convertido (pulado sem ffmpeg).
- `LocalStorage`: salvar, url, apagar.
- Admin: 401/503/403, CRUD de evento, upload inválido e acima do limite, exclusão apaga arquivos.
- Landing: 4 pacotes com preços, selo "Mais pedido", FAQ, galeria, agenda some sem eventos futuros.
- Orçamento: salva e redireciona ao `wa.me`; erro mantém os valores; o campo-isca descarta.
- Smoke test manual do Docker: `docker compose up --build` → `/` 200, `/admin` 401.

## 8. Fora do escopo

- Implementar o `BlobStorage` e fazer o deploy na Vercel (incluindo upload direto ao Blob por causa do limite de 4,5 MB por requisição).
- Tela de edição de pacotes no admin.
- Alembic, múltiplos usuários no admin, envio de e-mail ou notificação de novos pedidos.
- Analytics e pixel de anúncios.
