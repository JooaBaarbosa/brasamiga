# Agenda com calendário e horários (design)

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
- **Galeria de realizados:** os eventos do admin deixam de exibir título, local e descrição. Cada um mostra só "Maio 2026", o mês e o ano da data, e as fotos.

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
  - a página HTML não contém título nem local de evento futuro ou realizado;
  - a galeria mostra o mês e o ano.
- **Visual:** screenshots do calendário no computador e no celular, com dados de exemplo (2 eventos no mesmo sábado).

## 8. Fora do escopo

- O cliente escolher horário no formulário de orçamento (só a data é preenchida).
- Sugestão automática de horário livre.
- Eventos recorrentes, bloqueio manual de dias (férias) e sincronização com Google Calendar.
- Limite de eventos por dia além da regra de conflito.
