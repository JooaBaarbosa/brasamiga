# Agenda com calendário + galeria de realizados: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add start/end times and no-conflict scheduling to upcoming events with a JS calendar (public: busy slots only; admin: full detail), and rebuild the past-events gallery as per-event carousels with search/filters, an admin inbox for loose photos, and correct `alt` text everywhere, never exposing an event's real name, place or description publicly.

**Architecture:** Pure scheduling logic in `app/agenda.py`; new nullable columns and an inbox table in `app/db.py` with automatic `ALTER TABLE ADD COLUMN` migration; two JSON endpoints (`/api/agenda`, `/admin/api/agenda`) consumed by one dependency-free calendar component (`agenda.js`); the gallery is server-rendered cards with `data-*` attributes filtered client-side (`galeria.js`) and carousels (`carrossel.js`).

**Tech Stack:** Python 3.14, FastAPI, Jinja2, SQLAlchemy Core, vanilla JS (no libraries), pytest.

**Spec:** `docs/superpowers/specs/2026-10-21-agenda-calendario-design.md` (parts 1 and 2).

## Global Constraints

- `requires-python = ">=3.14,<3.15"`; no new runtime dependencies; no JS libraries/CDNs beyond the existing Google Fonts.
- Public HTML and `/api/agenda` must never contain an event's `titulo`, `local` or `descricao`. Only `titulo_publico`, `categoria`, `convidados`, `pacote`, month/year and times may appear.
- Conflict rule: block = `[início − montagem, fim + folga]`; touching blocks do **not** conflict; defaults `montagem_horas = 1`, `folga_horas = 1` from `[agenda]` in `site.toml`.
- `hora_fim <= hora_inicio` ⇒ ends next day; `hora_fim == hora_inicio` rejected. Futuro without hours (legacy) blocks the whole day and shows "Ocupado (horário a confirmar)".
- Categories default `["Aniversário", "Casamento", "Corporativo", "Outros"]`; guest bands `15–39`, `40–59`, `60+` from `[galeria]` in `site.toml`.
- "Today" always comes from `app.relogio.hoje()` (São Paulo).
- Admin validation errors render HTML (status 400) with the typed values preserved — never the JSON error page.
- All UI copy in pt-BR, matching the spec's wording. Every public `<img>` has an `alt` attribute (spec §9.6 table).
- Run from the worktree root; tests: `uv run pytest -q`. Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. A forged inbox POST naming a file outside the folder (`../../.env`, or a name not in the listing) → rejected with 400, nothing read or stored. *(Task 5)*
2. Owner-typed `titulo_publico` with accents, quotes and `&` (`Festa da Ação & Cia "VIP"`) → page stays valid HTML; `data-busca` is `festa da acao & cia "vip"` escaped; search finds it by `acao`. *(Task 7)*
3. Deleting a past event whose photos came from the inbox → those files reappear in "Fotos sem evento" instead of silently vanishing from the site. *(Task 5)*
4. `/api/agenda?mes=9999-12` or `?mes=0001-01` → 200 with `proximo`/`anterior` = `null` at the edges, no 500. *(Task 3)*
5. Admin `convidados` of `0`, `-5`, `abc` or `99999` → stored as empty (`None`) for blank/garbage, 400 with message for out-of-range numbers; values preserved. *(Task 4)*

---

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `app/db.py` (modify) | new columns, `caixa_entrada` table, auto-migration, new queries | 1 |
| `app/agenda.py` (create) | pure conflict logic, `[agenda]` params, month helpers, JSON day map | 2, 3 |
| `app/rotas_site.py` (modify) | `GET /api/agenda`; new gallery context | 3, 7 |
| `app/rotas_admin.py` (modify) | `GET /admin/api/agenda`; event form fields + validation; alt editing; inbox | 3, 4, 5 |
| `app/caixa.py` (create) | list untreated folder files (signature), resolve posted names safely | 5 |
| `app/templates/admin/*.html` (modify) | form fields, error box, calendar block, inbox block, alt inputs | 4, 5, 6 |
| `app/static/js/agenda.js` (create) | month calendar component (`publico` / `admin`) | 6 |
| `app/templates/index.html`, `app/static/css/site.css` (modify) | Agenda section, gallery cards, filters | 6, 7 |
| `app/static/js/carrossel.js`, `app/static/js/galeria.js` (create) | carousel; search + chips + URL state | 7 |
| `app/static/js/site.js` (modify) | visor navigates within one event | 7 |
| `app/static/css/admin.css` (modify) | admin calendar + inbox styles | 5, 6 |
| `conteudo/site.toml`, `README.md`, `conteudo/LEIA-ME.md` (modify) | `[agenda]`, `[galeria]`, docs | 2, 7, 8 |
| `tests/test_agenda.py`, `tests/test_caixa.py`, `tests/test_galeria.py` (create); `tests/test_db.py`, `test_admin.py`, `test_site.py` (modify) | tests | all |

---

### Task 1: Schema: new columns, inbox table, automatic migration

**Files:** Modify `app/db.py`; Test `tests/test_db.py`

**Interfaces:**
- Produces (columns): `eventos.hora_inicio TIME NULL`, `eventos.hora_fim TIME NULL`, `eventos.titulo_publico VARCHAR(120) NULL`, `eventos.categoria VARCHAR(30) NULL`, `eventos.convidados INTEGER NULL`, `eventos.pacote VARCHAR(50) NULL`, `midias.alt VARCHAR(200) NULL`; table `caixa_entrada(id, arquivo VARCHAR(300) NOT NULL, assinatura VARCHAR(400) NOT NULL UNIQUE, situacao VARCHAR(10) NOT NULL CHECK IN ('importado','ignorado'), evento_id INTEGER NULL FK eventos.id ON DELETE CASCADE, criado_em)`.
- Produces (methods on `Database`):
  - `criar_evento(titulo, data, local, descricao, tipo, **extras) -> int` and `atualizar_evento(evento_id, titulo, data, local, descricao, tipo, **extras) -> None`, where `extras` ⊆ `{hora_inicio, hora_fim, titulo_publico, categoria, convidados, pacote}` (existing positional callers keep working).
  - `eventos_entre(inicio: date, fim: date, tipo: str | None = None) -> list[dict]` (inclusive, ordered by `data`, `hora_inicio` nulls first, `id`).
  - `horarios_entre(inicio: date, fim: date) -> list[dict]`: selects **only** `data, hora_inicio, hora_fim` of `tipo='futuro'`.
  - `atualizar_alt(midia_id: int, alt: str) -> None`.
  - `registrar_caixa(arquivo: str, assinatura: str, situacao: str, evento_id: int | None = None) -> None` (upsert by `assinatura`).
  - `assinaturas_tratadas() -> set[str]`.
- Migration rule in `_conferir_schema`: missing column that is `nullable` → `ALTER TABLE {t} ADD COLUMN {c} {type compiled for dialect}`; missing non-nullable column → existing "versão antiga" `RuntimeError`. Deleting an event cascades its `caixa_entrada` rows (Review Focus 3).

- [ ] **Step 1: Write failing tests** in `tests/test_db.py`:
  - `test_migra_colunas_novas_sem_perder_dados`: build a SQLite file with the *current* (pre-task) `eventos`/`midias`/`orcamentos` columns via raw `sqlite3`, insert one event `("Antigo", "2026-01-10", "", "", "realizado", now)`; `Database(url)` succeeds; `obter_evento(1)["titulo"] == "Antigo"` and `["hora_inicio"] is None`; `listar_midias(1) == []`.
  - `test_banco_v1_continua_dando_erro` (keep the existing old-schema test passing — `orcamentos` lacking non-null `pacote`/`local` still raises "versão antiga").
  - `test_criar_evento_com_horarios_e_dados_publicos`: `criar_evento(..., "futuro", hora_inicio=time(12), hora_fim=time(17), titulo_publico="Casamento no interior", categoria="Casamento", convidados=120, pacote="Angus")` round-trips all six fields.
  - `test_horarios_entre_so_traz_data_e_horas`: two futuros + one realizado in range; result keys == `{"data", "hora_inicio", "hora_fim"}`; realizado absent.
  - `test_eventos_entre_ordenado_por_data_e_hora`.
  - `test_caixa_registra_e_lista_assinaturas` and `test_excluir_evento_devolve_fotos_para_a_caixa`: `registrar_caixa("a.jpg", "a.jpg:10:1", "importado", ev)`; `excluir_evento(ev)`; `"a.jpg:10:1" not in assinaturas_tratadas()`.
  - `test_atualizar_alt`.
- [ ] **Step 2:** `uv run pytest tests/test_db.py -q` → new tests FAIL (unknown keyword / missing method / missing column).
- [ ] **Step 3: Implement** in `app/db.py` per Interfaces. Compile the column type with `coluna.type.compile(dialect=self.engine.dialect)`; run each `ALTER` inside `engine.begin()`. `ON DELETE CASCADE` for `caixa_entrada.evento_id` relies on the existing SQLite `PRAGMA foreign_keys`; also delete the rows explicitly in `excluir_evento` (Postgres-safe and SQLite-safe).
- [ ] **Step 4:** `uv run pytest -q` → all pass.
- [ ] **Step 5: Commit** `git commit -m "Adiciona horários, dados públicos e caixa de entrada ao banco com migração automática"`.

---

### Task 2: Conflict logic (`app/agenda.py`)

**Files:** Create `app/agenda.py`; Modify `conteudo/site.toml`; Test `tests/test_agenda.py`

**Interfaces:**
- `@dataclass(frozen=True) class Janela: inicio: datetime; fim: datetime`
- `janela_evento(data: date, hora_inicio: time | None, hora_fim: time | None) -> Janela`: no hours → `[data 00:00, data+1 00:00)`; `fim <= inicio` → fim on `data+1`.
- `bloqueio(janela: Janela, montagem: timedelta, folga: timedelta, dia_inteiro: bool = False) -> Janela`: whole-day windows are not extended.
- `conflitam(a: Janela, b: Janela) -> bool`: `a.inicio < b.fim and b.inicio < a.fim`.
- `conflitos(novo: dict, existentes: list[dict], montagem: timedelta, folga: timedelta) -> list[dict]`: dicts have `id` (novo may have `None`), `data`, `hora_inicio`, `hora_fim`; skips existing with same `id`; returns the conflicting existing dicts.
- `parametros(site: dict) -> tuple[timedelta, timedelta]`: reads `site["agenda"]["montagem_horas" | "folga_horas"]`; missing, non-numeric or negative → `1`.
- `site.toml`: add `[agenda]` with `titulo = "Agenda"`, `texto = "Veja os horários já reservados antes de pedir o seu."`, `montagem_horas = 1`, `folga_horas = 1`.

- [ ] **Step 1: Write failing tests** `tests/test_agenda.py` (all with `montagem=folga=timedelta(hours=1)`):
  - `test_janela_simples`: 31/10 12:00–17:00 → `Janela(31/10 12:00, 31/10 17:00)`.
  - `test_janela_passa_da_meia_noite`: 20:00–02:00 → fim `01/11 02:00`.
  - `test_janela_sem_horas_e_o_dia_inteiro`.
  - `test_blocos_que_encostam_nao_conflitam`: existing 12–17, novo 19–23 → `[]`.
  - `test_um_minuto_de_sobreposicao_conflita`: existing 12–17, novo 18:59–23 → `[existing]`.
  - `test_evento_noturno_conflita_com_manha_seguinte`: existing 31/10 20:00–02:00; novo 01/11 03:30–08:00 → conflict (block ends 03:00 + ... montagem 02:30 overlaps 03:00).
  - `test_edicao_ignora_o_proprio_evento`.
  - `test_evento_sem_horas_bloqueia_o_dia`: existing no hours on 31/10, novo 31/10 08:00–10:00 → conflict; novo 01/11 08:00–10:00 → none (montagem 07:00 > 00:00).
  - `test_parametros_do_site_toml`: `{}` → (1h, 1h); `{"agenda": {"montagem_horas": 2, "folga_horas": 0.5}}` → (2h, 30min); `{"agenda": {"montagem_horas": "x", "folga_horas": -1}}` → (1h, 1h).
- [ ] **Step 2:** `uv run pytest tests/test_agenda.py -q` → FAIL (module missing).
- [ ] **Step 3: Implement** `app/agenda.py` per Interfaces; add `[agenda]` to `site.toml` after `[contato]`.
- [ ] **Step 4:** `uv run pytest -q` → all pass.
- [ ] **Step 5: Commit** `"Adiciona regra de conflito de horários da agenda"`.

---

### Task 3: Agenda JSON APIs

**Files:** Modify `app/agenda.py`, `app/rotas_site.py`, `app/rotas_admin.py`; Test `tests/test_agenda.py`, `tests/test_site.py`, `tests/test_admin.py`

**Interfaces:**
- `agenda.mes_ou_atual(texto: str | None, hoje: date) -> date` (first day of month; invalid/out-of-range → `hoje.replace(day=1)`).
- `agenda.vizinhos(mes: date) -> tuple[str | None, str | None]` → `("AAAA-MM", "AAAA-MM")`, `None` beyond year 1/9999 (Review Focus 4).
- `agenda.mapa_dias(linhas: list[dict], campos_extras: tuple[str, ...] = ()) -> dict[str, list[dict]]`: key = ISO `data`; item = `{"inicio": "HH:MM"|None, "fim": "HH:MM"|None, **{c: linha[c] for c in campos_extras}}`, ordered by `inicio` (None first).
- `GET /api/agenda?mes=` → `{"mes", "anterior", "proximo", "hoje", "dias"}`; uses `db.horarios_entre(max(primeiro_dia, hoje), ultimo_dia)` (so past days/months are empty).
- `GET /admin/api/agenda?mes=` (behind `exigir_admin`) → same shape; uses `db.eventos_entre(primeiro, ultimo)` (both tipos) with `campos_extras=("id", "titulo", "local", "tipo")`.

- [ ] **Step 1: Write failing tests:**
  - `test_mes_ou_atual` (`"2026-11"` → 1/11/2026; `"abc"`, `"2026-13"`, `None` → 1/10/2026 for hoje 21/10/2026) and `test_vizinhos_nas_bordas` (`date(9999,12,1)` → `("9999-11", None)`; `date(1,1,1)` → `(None, "0001-02")`).
  - `test_api_agenda_publica_estrutura`: monkeypatch `app.relogio.hoje` → 21/10/2026; futuros 31/10 12–17 and 19–23 (titulo `"NOME-SECRETO"`, local `"LOCAL-SECRETO"`, descricao `"DESC-SECRETA"`), a realizado on 31/10; `GET /api/agenda?mes=2026-10` → `dias == {"2026-10-31": [{"inicio": "12:00", "fim": "17:00"}, {"inicio": "19:00", "fim": "23:00"}]}`, `anterior == "2026-09"`, `proximo == "2026-11"`, and `"SECRET" not in resp.text`.
  - `test_api_agenda_mes_passado_vazio`, `test_api_agenda_mes_invalido_usa_atual`, `test_api_agenda_bordas_do_calendario` (`?mes=9999-12` → 200, `proximo is None`).
  - `test_api_agenda_evento_noturno_no_dia_de_inicio` (20:00–02:00 on 31/10 → key `2026-10-31`, `fim == "02:00"`).
  - `test_api_agenda_admin_exige_senha_e_traz_nome` (401 without auth; with `AUTH` items contain `titulo`, `local`, `tipo`, `id`).
- [ ] **Step 2:** run → FAIL (404 / missing functions).
- [ ] **Step 3: Implement** helpers in `agenda.py` and both routes.
- [ ] **Step 4:** `uv run pytest -q` → all pass.
- [ ] **Step 5: Commit** `"Adiciona APIs da agenda pública e do admin"`.

---

### Task 4: Admin event form: times, public data, validation, conflict, alt

**Files:** Modify `app/rotas_admin.py`, `app/templates/admin/_campos_evento.html`, `admin/index.html`, `admin/evento.html`; Test `tests/test_admin.py`

**Interfaces:**
- Consumes: `agenda.conflitos`, `agenda.parametros`, `db.eventos_entre`, `db.atualizar_alt`, Task 1 `extras`.
- `class ErroFormulario(Exception): mensagens: list[str]`.
- `_campos_evento(form: dict[str, str], site: dict) -> dict` (replaces the current signature; raises `ErroFormulario`). Rules: titulo required; tipo ∈ TIPOS; data ISO or None; futuro requires data + `hora_inicio` + `hora_fim` (`HH:MM`), `fim != inicio`; realizado requires `titulo_publico` (≤120); `categoria` ∈ `[galeria].categorias` (default list in Global Constraints) else "Outros"; `convidados`: blank/non-numeric → `None`, numeric outside 1–5000 → error "Informe entre 1 e 5000 convidados." (Review Focus 5); `pacote` ∈ names of `[[pacotes]]` else `None`.
- `_checar_conflito(db, campos: dict, evento_id: int | None, site: dict) -> None` raises `ErroFormulario` with: `Esse horário conflita com "{titulo}" ({dd/mm}, {HH:MM}–{HH:MM}). Entre um evento e outro é preciso deixar {m}h de montagem e {f}h de folga.` — one line per conflict; hours formatted without trailing `.0` (`1h`, `0,5h`). Compares against `db.eventos_entre(data−1, data+1, "futuro")`; only for tipo futuro.
- On `ErroFormulario`: create → render `admin/index.html` (status 400) with `erros` and `form` (typed values); update → render `admin/evento.html` (400) with `erros` and the typed values. Form fields: `titulo, tipo, data, hora_inicio, hora_fim, local, descricao, titulo_publico, categoria, convidados, pacote`.
- `POST /admin/midias/{id}/alt` (form `alt`, trimmed ≤200) → `db.atualizar_alt`, redirect to the event page.

- [ ] **Step 1: Write failing tests** in `tests/test_admin.py` (helper `_criar_futuro(client, data, inicio, fim, titulo)`):
  - `test_dois_eventos_no_mesmo_dia_sem_conflito` (12:00–17:00 then 19:00–23:00 → both 303; two rows in DB).
  - `test_conflito_nao_salva_e_mostra_mensagem` (12–17 then 18:00–22:00 → 400; text contains `Esse horário conflita com "Casamento da Ana"` and `1h de montagem e 1h de folga`; `value="18:00"` kept; one row in DB).
  - `test_futuro_sem_horario_da_erro_em_html` (400, `text/html`, message mentions início e fim).
  - `test_editar_sem_mudar_horario_nao_conflita_consigo`.
  - `test_realizado_exige_titulo_publico`.
  - `test_convidados_invalidos` (`"abc"` → saved `None`; `"0"` and `"99999"` → 400 "Informe entre 1 e 5000 convidados.").
  - `test_alt_manual_da_midia` (POST alt → `listar_midias()[0]["alt"] == "Mesa de frios"`).
  - Update the existing `test_titulo_obrigatorio` to expect HTML 400 with "Dê um nome ao evento." and adjust `_criar` to send `titulo_publico` for realizados.
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3: Implement.** Template fields: Início/Fim `<input type="time">` in the date row; "Título para o site (o que o cliente vê)" with hint "Nome e local reais nunca aparecem no site."; Tipo `<select>` from categorias; Convidados `type=number min=1 max=5000`; Pacote `<select>` (empty "—" + `[[pacotes]]` names). Error box `.aviso.erro` listing `erros`. In `evento.html`, under each media: input "Descrição da foto (para leitores de tela)" + "Salvar descrição"; the admin `<img>`/`<video>` use `alt`/`aria-label` = `midia.alt` or "Foto {n} do evento {título}" (spec §9.6).
- [ ] **Step 4:** `uv run pytest -q` → all pass.
- [ ] **Step 5: Commit** `"Formulário de eventos com horários, dados públicos e checagem de conflito"`.

---

### Task 5: Admin inbox for loose folder photos

**Files:** Create `app/caixa.py`; Modify `app/rotas_admin.py`, `admin/index.html`, `admin.css`; Test `tests/test_caixa.py`

**Interfaces:**
- `caixa.assinatura(arquivo: Path) -> str` = `f"{nome}:{tamanho}:{mtime_ns}"`.
- `caixa.pendentes(conteudo: Conteudo, tratadas: set[str], foto_capa: str | None) -> list[dict]` → `[{"nome", "assinatura", "tipo", "miniatura_url" | None}]` for files in `eventos-realizados/` of a known media type, not in `tratadas`, not `foto_capa`; thumbnails via `conteudo` cache (images); videos get `None`.
- `caixa.resolver(conteudo: Conteudo, nomes: list[str]) -> list[Path]`: returns only paths whose name is **exactly** a current pending file name (no path separators, no `..`); any other name → raises `ValueError` (route answers 400, Review Focus 1).
- Routes (admin): `POST /admin/caixa/adicionar` (form: `arquivos: list[str]`, `evento_id: int`) → for each path: copy into tmp, `midia.processar`, `storage.salvar`, `db.adicionar_midia`, `db.registrar_caixa(nome, assinatura, "importado", evento_id)`; failures stay pending and are listed; redirect `/admin#caixa` (or 400 page with errors). `POST /admin/caixa/ignorar` (form `arquivos`) → `registrar_caixa(..., "ignorado")`.
- Admin index context gains `caixa: list[dict]` and `realizados_opcoes` (id + titulo).

- [ ] **Step 1: Write failing tests** `tests/test_caixa.py`:
  - `test_lista_pendentes_sem_foto_capa`; `test_adicionar_ao_evento_importa_sem_gps` (uploads dir gains `.webp` + `-mini.webp`; output EXIF empty; file leaves the list; event has 1 media).
  - `test_ignorar_tira_da_caixa`; `test_arquivo_alterado_volta_para_a_caixa` (rewrite file with different size).
  - `test_arquivo_invalido_fica_na_caixa_com_erro` (one valid + one `quebrada.jpg` → valid imported, broken still pending, message shows its name).
  - `test_nome_forjado_e_recusado` (`arquivos=["../../.env"]` and `["nao-existe.jpg"]` → 400; uploads dir unchanged).
  - `test_excluir_evento_devolve_fotos` (import, delete event → file pending again).
  - `test_caixa_exige_senha`.
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3: Implement.** Admin block "Fotos sem evento (N)" (only when N>0): grid of checkbox tiles (`alt="Foto sem evento: {nome}"`), "Selecionar todas / nenhuma" (inline JS), `<select name="evento_id">` of realizados + link "+ Novo evento realizado" to the form anchor, buttons "Adicionar ao evento" and "Ignorar selecionadas" (`formaction`).
- [ ] **Step 4:** `uv run pytest -q` → all pass.
- [ ] **Step 5: Commit** `"Caixa de entrada no admin para atribuir fotos da pasta a eventos"`.

---

### Task 6: Calendar component on the site and in the admin

**Files:** Create `app/static/js/agenda.js`; Modify `index.html`, `admin/index.html`, `site.css`, `admin.css`, `rotas_site.py` (context `agenda` texts); Test `tests/test_site.py`, `tests/test_admin.py`

**Interfaces:**
- Markup contract: `<div class="calendario" data-api="/api/agenda" data-modo="publico" data-alvo-data="#orcamento input[name=data_evento]">` (admin: `data-api="/admin/api/agenda" data-modo="admin" data-alvo-data="#form-evento input[name=data]"`), followed by `<noscript>`.
- `agenda.js` renders: header (`‹` button `aria-label="Mês anterior"`, month title, `›` `aria-label="Próximo mês"`, disabled when `anterior/proximo` is `null`); weekday row D S T Q Q S S; day `<button>`s with classes `passado`, `hoje`, `um` (1 item), `varios` (≥2), `sel`; `aria-label` like "31 de outubro, 2 horários ocupados"; day panel (`aria-live="polite"`):
  - **publico:** each item "12:00 – 17:00 · Ocupado" (null times → "Horário a confirmar · Ocupado"); empty day → "Dia livre"; button "Pedir orçamento para DD/MM" that sets the target input to `AAAA-MM-DD`, selects nothing else, and scrolls to `#orcamento`.
  - **admin:** each item "12:00–17:00 Título · Local" linking to `/admin/eventos/{id}` (red for futuro, green for realizado); cell shows up to 2 short labels "12h Título"; button "+ Cadastrar evento neste dia" sets the form date, selects "Vai acontecer" and scrolls to `#form-evento`.
- Public section placed right after `#pacotes`, `<section id="agenda">` with `[agenda].titulo/texto`; the old "Próximos eventos" list is removed. `<noscript>`: "Ative o JavaScript para ver a agenda ou chame a gente no WhatsApp."

- [ ] **Step 1: Write failing tests:** `test_secao_agenda_usa_api` (`data-api="/api/agenda"` present; "Próximos eventos" absent; futuro marker `"NOME-SECRETO"` absent from HTML); `test_admin_tem_calendario` (`data-api="/admin/api/agenda"` in `/admin`).
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3: Implement** `agenda.js` (fetch JSON; ISO date math in local time; week starts Sunday) and the CSS in the identity (papel card, Anton month title, gold dot `#B8966A` for 1, double red `#A93226` for ≥2, dark day panel with red top border; on ≤52rem the panel goes below).
- [ ] **Step 4:** `uv run pytest -q` → pass. Then visual check: run the app with `DATA_DIR=C:/Users/JV/.claude/jobs/bfe8b7c0/tmp/data-agenda`, create two futuros on the same upcoming Saturday through the admin, screenshot `/` and `/admin` (desktop 1366 + phone 390 via iframe as before), click-through verified by screenshot after `?mes=` navigation. Expected: calendar matches mockup A; no event names on `/`.
- [ ] **Step 5: Commit** `"Calendário da agenda no site e no painel"`.

---

### Task 7: Past-events gallery: cards, carousels, search, filters, alt

**Files:** Create `app/static/js/carrossel.js`, `app/static/js/galeria.js`, `tests/test_galeria.py`; Modify `rotas_site.py`, `index.html`, `site.css`, `site.js`, `conteudo/site.toml`, `app/web.py`

**Interfaces:**
- `web.normalizar(texto: str) -> str` (Jinja filter `normalizar`): lowercase, strip accents (`unicodedata` NFKD, drop combining), collapse spaces.
- Context: `eventos_galeria: list[dict]` = realizados with ≥1 media, newest first, each with `titulo_publico, categoria, convidados, pacote, data, midias` (media dicts with `url`, `url_miniatura`, `tipo`, `alt`); `galeria_cfg = {"titulo", "categorias", "faixas"}` from `[galeria]` with defaults. `Conteudo.galeria()` is no longer used by the public page (capa keeps using `Conteudo.capa`).
- Card markup: `<article class="evento-card" data-categoria="{{ categoria | normalizar }}" data-convidados="{{ convidados or '' }}" data-busca="{{ (titulo_publico ~ ' ' ~ categoria ~ ' ' ~ (pacote or '')) | normalizar }}">` → `.carrossel` (track of slides, `‹`/`›` buttons `aria-label="Foto anterior"/"Próxima foto"`, counter `1/N`, dots when N ≤ 8) → body: `.evento-tag` "{categoria} · {convidados} convidados" (omit part if empty), `<h3>` título público, `.evento-meta` "{Mês AAAA}{ · Pacote X}".
- Alt per spec §9.6: photo `alt = midia.alt or "Foto {i} de {n} do evento: {titulo_publico}"`; video `aria-label` "Vídeo {i} de {n} do evento: {titulo_publico}"; capa `<img alt="" role="presentation">`.
- Filters UI: `<input type="search" aria-label="Buscar eventos">`, chip groups `data-filtro="tipo"` (Todos + categorias) and `data-filtro="pessoas"` (Qualquer tamanho + faixas, `data-min`/`data-max`); `<p class="contador" aria-live="polite">N eventos</p>`; empty state "Nenhum evento com esses filtros." + "Limpar filtros". URL params `tipo` (normalized category), `pessoas` (band min), `q`.
- `carrossel.js`: the carousel is focusable (`tabindex="0"`, `aria-roledescription="carrossel"`, `aria-label="Fotos do evento: {título público}"`) and ArrowLeft/ArrowRight move one slide while it has focus; slides after the first use `loading="lazy"`.
- `site.js` visor: opening a slide navigates (`‹ ›`, ArrowLeft/Right) only within that card's media, caption "{i} de {n} · {título público}".
- `site.toml`: add `[galeria]` (titulo, categorias, faixas exactly as spec §9.2).

- [ ] **Step 1: Write failing tests** `tests/test_galeria.py`:
  - `test_evento_sem_midia_nao_aparece`; `test_foto_solta_da_pasta_nao_aparece` (file in folder, not foto_capa → its cache key absent from `/`).
  - `test_card_mostra_dados_publicos_e_esconde_os_reais` (titulo `"NOME-SECRETO"`, local `"LOCAL-SECRETO"`, descricao `"DESC-SECRETA"` absent; "Casamento · 120 convidados", "Casamento no interior", "Maio 2026 · Pacote Angus" present).
  - `test_busca_normalizada_e_escapada` (Review Focus 2: titulo_publico `Festa da Ação & Cia "VIP"` → HTML contains `data-busca="festa da acao &amp; cia &#34;vip&#34; outros"` or the equivalent escaping Jinja produces; assert via `html.unescape` on the attribute value == `festa da acao & cia "vip" outros`).
  - `test_todas_as_imagens_publicas_tem_alt` (parse with `html.parser`; every `<img>` has `alt` attr).
  - `test_alt_automatico_e_manual` ("Foto 1 de 2 do evento: Casamento no interior"; after `atualizar_alt`, the manual text).
  - `test_filtros_vem_do_site_toml` (chips "Aniversário", "Casamento", "Corporativo", "Outros", "15–39", "40–59", "60+").
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3: Implement** templates, CSS (cards grid 3/2/1 columns at >64rem/>40rem/else; carousel `scroll-snap-type: x mandatory`; chips like the mockup; `[hidden]` already forced) and the two JS files (`carrossel.js`: buttons scroll by one slide, update counter/dots on `scroll` via `IntersectionObserver` or `scrollLeft`; `prefers-reduced-motion` → `behavior: "auto"`; `galeria.js`: debounce 150 ms, read/write URL with `history.replaceState`, hide chips when JS absent is implicit since they're rendered `hidden` and un-hidden by JS).
- [ ] **Step 4:** `uv run pytest -q` → pass. Visual check as in Task 6 with 3 realizados (import folder photos through the inbox into them): screenshots desktop + phone; type a search and click a chip, screenshot the filtered state and the empty state; open the visor and screenshot navigation within one event.
- [ ] **Step 5: Commit** `"Galeria de realizados com carrosséis, busca, filtros e textos alternativos"`.

---

### Task 8: Docs and full verification

**Files:** Modify `README.md`, `conteudo/LEIA-ME.md`

- [ ] **Step 1:** README: section "Agenda e galeria" (how hours/conflict work with the `[agenda]` values; inbox flow; that names/locals are never public; `[galeria]` categories/bands editable). LEIA-ME: `eventos-realizados/` row now says photos go to the site **only after** being added to an event in `/admin` → "Fotos sem evento"; `foto_capa` stays automatic.
- [ ] **Step 2:** `uv run pytest -q` → all pass; Docker smoke: `docker compose up --build -d`, `curl /` 200, `curl /api/agenda` 200 JSON without `titulo`, `curl -u admin:<demo> /admin` 200, `docker compose down`.
- [ ] **Step 3: Commit** `"Documenta agenda, caixa de entrada e galeria"`.
