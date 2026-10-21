# Agenda com calendário + galeria de eventos realizados (design)

Este documento tem duas partes, implementadas num único plano porque mexem na mesma tabela `eventos` e na mesma migração:
- **Parte 1, seções 1 a 8:** agenda com calendário e horários.
- **Parte 2, seção 9:** galeria de eventos realizados com carrosséis, busca e filtros.

Data: 2026-10-21 · Status: aguardando revisão do dono
Base: landing minimalista (direção C) em `main` @ 705ee15

## 1. Objetivo

Dar ao Brasamiga uma **agenda com calendário**:
- O **cliente** vê, antes de pedir orçamento, quais dias e horários já estão ocupados, **sem nunca ver nome, local ou descrição de evento nenhum**.
- O **dono** cadastra próximos eventos com **hora de início e de fim** e pode ter **2 (ou mais) eventos no mesmo dia**, desde que os horários não conflitem, considerando montagem e deslocamento.

**Sucesso:**
- Um cliente abre o site, clica num sábado e vê "12:00–17:00 Ocupado". Com um clique, pede orçamento para aquela data.
- O dono cadastra um segundo evento no mesmo dia: se não houver conflito, ele salva; se houver, a tela explica com quem conflita e nada é salvo.
- Nenhuma resposta pública (HTML ou JSON) contém título, local ou descrição de evento.
- Um banco existente recebe as colunas novas sozinho, sem perder dados.

## 2. Decisões tomadas com o dono

| Tema | Decisão |
|---|---|
| Visão do cliente | Horários ocupados por dia (opção "Horários ocupados") |
| Regra de conflito | Horário + 1h de montagem antes + folga de deslocamento depois (folga configurável, padrão 1h) |
| Confidencialidade | Em **todo** o site público: agenda e galeria de realizados |
| Abordagem técnica | **B**: calendário desenhado em JavaScript a partir de uma API JSON |
| Layout público | **A**: grade do mês + painel do dia com botão "Pedir orçamento para DD/MM" |
| Admin | Calendário com nomes no topo do painel; formulário com Início/Fim; aviso de conflito |

## 3. Dados

### 3.1 Colunas novas em `eventos`

| Coluna | Tipo | Regra |
|---|---|---|
| `hora_inicio` | `TIME NULL` | Obrigatória para `tipo = 'futuro'`; opcional para `realizado` |
| `hora_fim` | `TIME NULL` | Idem. `fim <= inicio` significa que o evento termina no dia seguinte (ex.: 20:00–02:00). `fim == inicio` é recusado. |

Eventos futuros antigos, cadastrados sem hora, continuam válidos. Na agenda eles aparecem como **"Ocupado (horário a confirmar)"** e, para a regra de conflito, bloqueiam o **dia inteiro**.

### 3.2 Migração automática

`Database._conferir_schema` passa a:
1. Para cada coluna do `metadata` ausente no banco que seja **anulável e sem default obrigatório**, executar `ALTER TABLE <tabela> ADD COLUMN <coluna> <tipo>`, que funciona igual em SQLite e Postgres.
2. Continuar lançando o `RuntimeError` "versão antiga" quando faltar uma coluna **não anulável**, o caso do banco da v1.

### 3.3 Consultas novas em `Database`

- `eventos_entre(inicio: date, fim: date, tipo: str | None = None) -> list[dict]`: eventos com `data` no intervalo fechado, ordenados por data e hora.
- `horarios_entre(inicio: date, fim: date) -> list[dict]`: **só** `data`, `hora_inicio`, `hora_fim` de eventos `futuro`. É a única consulta usada pela API pública. Ela não seleciona `titulo`, `local` nem `descricao`, para garantir a confidencialidade na origem.

## 4. Regra de conflito: `app/agenda.py` (funções puras)

```python
@dataclass(frozen=True)
class Janela:
    inicio: datetime
    fim: datetime

def janela_evento(data: date, hora_inicio: time | None, hora_fim: time | None) -> Janela
    # sem horas → 00:00 do dia até 00:00 do dia seguinte (dia inteiro)
    # hora_fim <= hora_inicio → fim no dia seguinte
def bloqueio(janela: Janela, montagem: timedelta, folga: timedelta) -> Janela
    # Janela(inicio - montagem, fim + folga); dia inteiro não é estendido
def conflitam(a: Janela, b: Janela) -> bool
    # a.inicio < b.fim and b.inicio < a.fim  (encostar no limite NÃO conflita)
def conflitos(novo: dict, existentes: list[dict], montagem: timedelta, folga: timedelta) -> list[dict]
    # compara bloqueio(novo) × bloqueio(cada existente); ignora existente com mesmo id do novo
```

Exemplo com montagem 1h e folga 1h:
- Um evento de 12:00 a 17:00 bloqueia de 11:00 a 18:00.
- Um evento de 19:00 a 23:00 bloqueia de 18:00 a 24:00. Os blocos encostam às 18:00, então **não conflitam**.
- Um evento de 18:00 a 22:00 bloqueia de 17:00 a 23:00, então **conflita**.

Configuração no `site.toml`:

```toml
[agenda]
titulo = "Agenda"
texto = "Veja os horários já reservados antes de pedir o seu."
montagem_horas = 1
folga_horas = 1
```

Sem a seção, os valores padrão são 1 e 1. Valores não numéricos ou negativos voltam ao padrão.

## 5. API

### 5.1 Pública: `GET /api/agenda?mes=AAAA-MM`

```json
{"mes": "2026-10", "anterior": "2026-09", "proximo": "2026-11", "hoje": "2026-10-21",
 "dias": {"2026-10-31": [{"inicio": "12:00", "fim": "17:00"}, {"inicio": "19:00", "fim": "23:00"}],
          "2026-11-07": [{"inicio": null, "fim": null}]}}
```

- Um `mes` ausente ou inválido vira o mês atual, no fuso de São Paulo (`app/relogio.py`).
- Só entram eventos `futuro` com `data >= hoje`. Meses inteiramente passados vêm com `dias: {}`.
- Um evento que passa da meia-noite aparece no dia em que **começa**, com o `fim` real (ex.: `"02:00"`).

### 5.2 Admin: `GET /admin/api/agenda?mes=AAAA-MM`

Protegida pela mesma autenticação do painel. Usa a mesma estrutura, e cada item traz também `id`, `titulo`, `local` e `tipo`, com eventos futuros e realizados.

## 6. Interface

### 6.1 Site público

- Nova seção **Agenda** logo depois de "Escolha o seu pacote". Ela substitui a antiga lista "Próximos eventos".
- O componente `app/static/js/agenda.js` lê `data-api` e `data-modo="publico"` e desenha:
  - o cabeçalho com "‹ Outubro 2026 ›", que navega pela API;
  - a grade D–S, com dias passados esmaecidos, contorno no dia de hoje, uma bolinha dourada para 1 horário ocupado e duas vermelhas para 2 ou mais;
  - ao clicar num dia, um painel escuro com "12:00 – 17:00 · Ocupado" (ou "Horário a confirmar") e o botão **"Pedir orçamento para DD/MM"**. O botão preenche `data_evento` no formulário e rola até ele.
  - Num dia sem evento, o painel diz "Dia livre" e mostra o mesmo botão.
- Sem JavaScript, um `<noscript>` diz para ativar o JavaScript ou chamar no WhatsApp.
- Acessibilidade: os dias são `<button>` com `aria-label` (ex.: "31 de outubro, 2 horários ocupados") e o painel tem `aria-live="polite"`.
- **Galeria de realizados:** é redesenhada conforme a seção 9. Ela nunca exibe `titulo`, `local` ou `descricao`; mostra só o **título público**.

### 6.2 Admin

- **Calendário no topo do `/admin`**, com o mesmo componente em `data-modo="admin"` e a API do admin:
  - cada célula do dia lista "12h Casamento", em vermelho para futuros e verde para realizados;
  - ao clicar, aparece a lista do dia (horário, nome e local, com link para editar) e o botão "+ Cadastrar evento neste dia", que preenche a data no formulário de cadastro.
- O **formulário de evento** (`_campos_evento.html`) ganha os campos **Início** e **Fim**, com `<input type="time">`.
- **Validação** (criar e editar), feita no servidor:
  - Para um evento futuro: data, início e fim são obrigatórios, e `fim == inicio` é recusado.
  - Para um evento futuro: aplica `agenda.conflitos`, comparando com os eventos futuros de `data − 1` até `data + 1`, sem contar o próprio evento quando é uma edição.
  - Em caso de erro, nada é salvo. A página é renderizada de novo com os valores digitados (o painel inteiro no cadastro, a página do evento na edição), status 400, e a mensagem: *"Esse horário conflita com 'Casamento da Ana' (31/10, 12:00–17:00). Entre um evento e outro é preciso deixar 1h de montagem e 1h de folga."* Ela lista todos os conflitos e usa os valores do `site.toml`.
  - Os erros de validação do formulário de evento, como título vazio, passam a aparecer nessa mesma mensagem em HTML, em vez da página JSON.

## 7. Testes

- **`agenda`:**
  - a janela simples;
  - um evento que passa da meia-noite;
  - um evento sem horas (dia inteiro);
  - dois blocos que só encostam não conflitam;
  - uma sobreposição de 1 minuto conflita;
  - um evento noturno conflita com um da manhã seguinte;
  - o próprio evento é ignorado na edição;
  - valores de montagem e folga vindos do `site.toml`, incluindo padrão e valor inválido.
- **`db`:**
  - um banco sem as colunas novas é migrado e mantém as linhas;
  - um banco v1 continua dando o erro "versão antiga";
  - `horarios_entre` devolve só data e horas.
- **API pública:**
  - estrutura e meses vizinhos;
  - mês inválido vira o mês atual;
  - mês passado vem vazio;
  - evento noturno aparece no dia de início;
  - **o JSON não contém título nem local**, verificado com strings marcadoras;
  - eventos realizados não aparecem.
- **API admin:** exige senha; traz título e local.
- **Admin:**
  - 2 eventos no mesmo dia em horários compatíveis são salvos;
  - um conflito não salva e mostra a mensagem com os valores mantidos;
  - um evento futuro sem hora dá erro em HTML;
  - editar sem mudar o horário não acusa conflito consigo mesmo.
- **Site:**
  - a seção Agenda tem `data-api="/api/agenda"`;
  - a página HTML não contém título nem local de evento futuro ou realizado (testes da galeria na seção 9.7).
- **Visual:** screenshots do calendário no computador e no celular, com dados de exemplo (2 eventos no mesmo sábado).

## 8. Fora do escopo

- O cliente escolher horário no formulário de orçamento (só a data é preenchida).
- Sugestão automática de horário livre.
- Eventos recorrentes, bloqueio manual de dias (férias) e sincronização com Google Calendar.
- Limite de eventos por dia além da regra de conflito.
- Busca no servidor e paginação da galeria (a filtragem é no navegador; ver 9.4).

---

# Parte 2: galeria de eventos realizados

## 9.1 Objetivo e decisões

O cliente navega pelos eventos já realizados como **cards com carrossel**: 1 evento tem N fotos e vídeos. Uma **barra de busca** e **filtros** ajudam a achar eventos parecidos com o dele. **Nenhuma foto fica solta no site**: toda foto pública pertence a um evento.

| Tema | Decisão do dono |
|---|---|
| Layout | **A**: grade de cards com carrossel; 3 por linha no computador, 2 no tablet e 1 no celular |
| Busca | Procura num **título público** que o dono escreve por evento (o nome real e o local continuam só no admin) |
| Fotos soltas da pasta | Viram uma **caixa de entrada** no admin, onde são atribuídas a um evento ou ignoradas |
| Filtros | Tipo: **Aniversário, Casamento, Corporativo, Outros**. Convidados: **15–39, 40–59, 60+** (faixas do PDF) |
| Card | Tipo · convidados, título público, mês/ano · **pacote servido** |

## 9.2 Dados

**Colunas novas em `eventos`** (todas anuláveis; a migração automática da seção 3.2 as acrescenta):

| Coluna | Tipo | Regra |
|---|---|---|
| `titulo_publico` | `VARCHAR(120)` | **Obrigatório** para `realizado`. É o único texto do evento exibido e pesquisável no site. |
| `categoria` | `VARCHAR(30)` | Um dos `[galeria] categorias` do `site.toml`. Padrão: "Outros". |
| `convidados` | `INTEGER` | Opcional, entre 1 e 5000. Sem valor, o evento só aparece em "Qualquer tamanho". |
| `pacote` | `VARCHAR(50)` | Opcional; um dos nomes de `[[pacotes]]`. Se preenchido, aparece no card ("Pacote Angus"). |

**Coluna nova em `midias`:** `alt VARCHAR(200)`, opcional. É a descrição da foto escrita pelo dono e tem prioridade sobre o alt automático (seção 9.6).

**Tabela nova `caixa_entrada`:**
- Colunas: `id`, `arquivo` (nome em `conteudo/eventos-realizados/`), `assinatura` (nome:tamanho:mtime), `situacao` (`'importado'` ou `'ignorado'`), `evento_id` (anulável) e `criado_em`.
- Ela registra o que já foi tratado. Assim, a pasta, que no Docker é montada só para leitura, nunca precisa ser alterada.

**`site.toml`:**

```toml
[galeria]
titulo = "Eventos realizados"
categorias = ["Aniversário", "Casamento", "Corporativo", "Outros"]
faixas = [                       # convidados
  { rotulo = "15–39", min = 15, max = 39 },
  { rotulo = "40–59", min = 40, max = 59 },
  { rotulo = "60+",   min = 60 },
]
```

## 9.3 Caixa de entrada no admin

- **Bloco "Fotos sem evento (N)"** no `/admin`, mostrado só se houver alguma. Ele lista, como miniaturas (as versões web em cache, sem GPS), os arquivos da pasta que não estão em `caixa_entrada`. Um arquivo que mudar de tamanho ou de data volta a aparecer.
- **Seleção:** cada foto tem um checkbox, e há os atalhos "selecionar todas" e "selecionar nenhuma".
- **Ações:**
  - **"Adicionar ao evento"**, com um seletor dos eventos realizados mais a opção "+ Novo evento realizado…", que leva ao formulário. Cada arquivo passa por `midia.processar` (WEBP sem GPS, MP4) e é gravado no armazenamento como um upload. Depois, o arquivo é marcado como `importado`.
  - **"Ignorar"** marca o arquivo como `ignorado` (por exemplo, uma foto repetida).
- **Erros:** os arquivos que falharem (imagem inválida, vídeo sem ffmpeg) ficam na caixa, com uma mensagem por arquivo. Os outros seguem.
- **Foto de capa:** a `foto_capa` continua vindo da pasta (é a abertura do site, não uma foto da galeria) e não entra na caixa de entrada.
- **Galeria pública:** `Conteudo.galeria()` deixa de ser usada nela. Ela passa a se basear só em eventos realizados com pelo menos 1 mídia.

## 9.4 Galeria pública

- **Estrutura:** a seção "Eventos realizados" tem a barra de busca, depois as linhas de chips de filtro (tipo | tamanho), o contador "N eventos" e a grade de cards.
- **Renderização:** os cards são gerados no servidor com `data-categoria`, `data-convidados` e `data-busca`. O `data-busca` é o texto normalizado (minúsculas, sem acento) do título público, da categoria e do pacote.
- **Filtragem:** o script `app/static/js/galeria.js` filtra na hora, enquanto o cliente digita (com debounce de 150 ms) ou clica nos chips. A filtragem é no navegador porque a galeria de um buffet tem dezenas de eventos, não milhares.
- **Link compartilhável:** a URL guarda o filtro (`?tipo=casamento&pessoas=60&q=interior`), sem recarregar a página (`history.replaceState`). Abrir esse link já aplica os filtros.
- **Sem resultado:** aparece "Nenhum evento com esses filtros." com o botão **Limpar filtros**.
- **Sem JavaScript:** todos os cards aparecem e os chips ficam escondidos.
- **Ordem:** os eventos mais recentes aparecem primeiro.

## 9.5 Carrossel

- **Componente:** `app/static/js/carrossel.js`, sem dependências.
  - A trilha usa `scroll-snap`, então o arraste no celular é nativo.
  - Tem botões ‹ ›, contador "1/5" e bolinhas clicáveis. As bolinhas são trocadas por apenas "1/5" quando houver mais de 8 fotos.
  - Aceita setas do teclado quando o carrossel está em foco.
  - Fotos usam `loading="lazy"`, a partir da segunda.
- **Tela cheia:** clicar numa foto abre o visor `<dialog>`, que navega (‹ › e setas do teclado) **só pelas fotos daquele evento**, com legenda "3 de 5 · Título público".
- **Vídeos:** entram no carrossel com o ícone de play e tocam no visor.
- **Movimento:** com `prefers-reduced-motion`, a rolagem entre fotos é instantânea.

## 9.6 Textos alternativos (alt): revisão de todas as imagens do site

| Imagem | alt |
|---|---|
| Logo no topo e na capa | "Brasamiga" (texto do logo) |
| Foto de capa (decorativa, com texto por cima) | `alt=""` com `role="presentation"` |
| Foto de evento no carrossel | `midia.alt` se preenchido; senão "Foto 2 de 5 do evento: {título público}" |
| Vídeo de evento | `aria-label` "Vídeo 1 de 5 do evento: {título público}" |
| Foto no visor | O mesmo alt da foto de origem |
| Miniaturas da caixa de entrada (admin) | "Foto sem evento: {nome do arquivo}" |
| Fotos e vídeos na página do evento (admin) | `midia.alt` ou "Foto N do evento {título}" |
| Ícone de favicon e marca-d'água | Sem alt (não são `<img>` de conteúdo) |

Na página do evento, cada mídia ganha o campo **"Descrição da foto (para leitores de tela)"**, que vai em `midia.alt`, com até 200 caracteres. Os botões de seta do carrossel e do visor têm `aria-label` ("Foto anterior", "Próxima foto").

## 9.7 Testes

- **Banco:**
  - a migração acrescenta `titulo_publico`, `categoria`, `convidados`, `pacote` e `midias.alt` sem perder dados;
  - a `caixa_entrada` marca arquivos como importados ou ignorados;
  - um arquivo alterado volta para a caixa.
- **Caixa de entrada:**
  - lista só os arquivos não tratados, sem incluir a `foto_capa`;
  - "Adicionar ao evento" cria as mídias, gera WEBP sem GPS e tira o arquivo da caixa;
  - "Ignorar" tira o arquivo da caixa;
  - um arquivo inválido fica na caixa com erro, e os outros são importados;
  - exige senha.
- **Galeria:**
  - um evento realizado sem mídia não aparece;
  - uma foto solta da pasta não aparece em nenhum lugar do HTML público;
  - o card mostra categoria, convidados, título público, mês/ano e pacote;
  - **`titulo`, `local` e `descricao` reais não aparecem** (strings marcadoras);
  - os `data-*` estão normalizados (sem acento);
  - um evento realizado sem título público é recusado no admin.
- **Alt:**
  - todo `<img>` da página pública tem o atributo `alt`;
  - fotos de evento usam o alt manual ou o automático;
  - o alt manual editado no admin aparece no site.
- **JavaScript:** checado no navegador com screenshots (computador e celular):
  - busca, chips e a mensagem de "nenhum resultado";
  - o link com filtros;
  - o carrossel (setas e contador);
  - o visor navegando dentro do evento.

## 9.8 Fora do escopo (parte 2)

- Reordenar as fotos dentro do evento (a ordem é a de envio).
- Mover uma foto de um evento para outro (dá para excluir e reenviar).
- Paginação ou "carregar mais" (só entra se a galeria passar de ~60 eventos).
- Busca por data ou intervalo de datas.
