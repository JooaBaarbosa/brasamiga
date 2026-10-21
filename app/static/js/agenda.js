// Calendário da agenda. Lê o mês de data-api e desenha a grade + o painel do dia.
// data-modo="publico": só horários ocupados. data-modo="admin": horário, nome e local.
(() => {
  const MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
    "agosto", "setembro", "outubro", "novembro", "dezembro"];
  const SEMANA = ["Domingo", "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"];
  const pad = (n) => String(n).padStart(2, "0");
  const ddmm = (iso) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;
  const horario = (item) => (item.inicio ? `${item.inicio} – ${item.fim}` : "Horário a confirmar");

  function el(tag, classe, texto) {
    const no = document.createElement(tag);
    if (classe) no.className = classe;
    if (texto !== undefined) no.textContent = texto;
    return no;
  }

  function iniciar(raiz) {
    const modo = raiz.dataset.modo;
    const caixa = el("div", "cal-caixa");
    const cabeca = el("div", "cal-cabeca");
    const anterior = el("button", "cal-nav", "‹");
    const proximo = el("button", "cal-nav", "›");
    const titulo = el("h3", "cal-titulo");
    anterior.type = proximo.type = "button";
    anterior.setAttribute("aria-label", "Mês anterior");
    proximo.setAttribute("aria-label", "Próximo mês");
    cabeca.append(anterior, titulo, proximo);
    const semana = el("div", "cal-semana");
    "DSTQQSS".split("").forEach((letra, i) => {
      const dia = el("span", null, letra);
      dia.title = SEMANA[i];
      semana.append(dia);
    });
    const grade = el("div", "cal-dias");
    caixa.append(cabeca, semana, grade);
    if (modo === "publico") {
      const legenda = el("p", "cal-legenda");
      legenda.innerHTML = '<span><i class="cal-ponto"></i>1 horário ocupado</span><span><i class="cal-ponto cal-ponto-varios"></i>2 ou mais</span>';
      caixa.append(legenda);
    }
    const painel = el("div", "cal-painel");
    painel.setAttribute("aria-live", "polite");
    raiz.replaceChildren(caixa, painel);

    let dados = null;
    let selecionado = null;

    async function carregar(mes) {
      try {
        // location.origin nunca traz usuário:senha, que o fetch recusa em URLs relativas.
        const url = new URL(raiz.dataset.api, location.origin);
        if (mes) url.searchParams.set("mes", mes);
        const resposta = await fetch(url, { credentials: "same-origin" });
        if (!resposta.ok) throw new Error(resposta.status);
        dados = await resposta.json();
      } catch {
        painel.replaceChildren(el("p", "cal-vazio", "Não foi possível carregar a agenda. Recarregue a página."));
        return;
      }
      if (!selecionado || !selecionado.startsWith(dados.mes)) selecionado = primeiroOcupado();
      desenhar();
    }

    function primeiroOcupado() {
      return Object.keys(dados.dias).sort().find((iso) => iso >= dados.hoje) || null;
    }

    anterior.addEventListener("click", () => dados?.anterior && carregar(dados.anterior));
    proximo.addEventListener("click", () => dados?.proximo && carregar(dados.proximo));

    function desenhar() {
      const [ano, mes] = dados.mes.split("-").map(Number);
      titulo.textContent = `${MESES[mes - 1]} ${ano}`;
      anterior.disabled = !dados.anterior;
      proximo.disabled = !dados.proximo;
      grade.replaceChildren();
      const inicioSemana = new Date(ano, mes - 1, 1).getDay();
      const totalDias = new Date(ano, mes, 0).getDate();
      for (let i = 0; i < inicioSemana; i++) grade.append(el("span", "cal-vazio-dia"));
      for (let d = 1; d <= totalDias; d++) {
        const iso = `${ano}-${pad(mes)}-${pad(d)}`;
        const itens = dados.dias[iso] || [];
        const botao = el("button", "cal-dia");
        botao.type = "button";
        botao.append(el("b", null, String(d)));
        if (iso < dados.hoje) botao.classList.add("passado");
        if (iso === dados.hoje) botao.classList.add("hoje");
        if (itens.length === 1) botao.classList.add("um");
        if (itens.length > 1) botao.classList.add("varios");
        if (iso === selecionado) botao.classList.add("sel");
        const ocupados = itens.length === 0 ? "livre" : itens.length === 1 ? "1 horário ocupado" : `${itens.length} horários ocupados`;
        botao.setAttribute("aria-label", `${d} de ${MESES[mes - 1]}, ${ocupados}`);
        botao.setAttribute("aria-pressed", String(iso === selecionado));
        if (modo === "admin") {
          itens.slice(0, 2).forEach((item) => {
            const rotulo = `${item.inicio ? item.inicio.slice(0, 2) + "h " : ""}${item.titulo}`;
            botao.append(el("span", `cal-rotulo cal-${item.tipo}`, rotulo));
          });
          if (itens.length > 2) botao.append(el("span", "cal-rotulo", `+${itens.length - 2}`));
        }
        botao.addEventListener("click", () => {
          selecionado = iso;
          desenhar();
        });
        grade.append(botao);
      }
      desenharPainel();
    }

    function desenharPainel() {
      if (!selecionado) {
        painel.replaceChildren(el("p", "cal-vazio", "Clique num dia para ver os horários."));
        return;
      }
      const [ano, mes, dia] = selecionado.split("-").map(Number);
      const nomeDia = SEMANA[new Date(ano, mes - 1, dia).getDay()];
      const itens = dados.dias[selecionado] || [];
      const conteudo = [el("h4", "cal-painel-titulo", `${nomeDia}, ${ddmm(selecionado)}`)];
      const lista = el("ul", "cal-itens");
      if (!itens.length) lista.append(el("li", "cal-livre", "Dia livre"));
      itens.forEach((item) => {
        const linha = el("li", modo === "admin" ? `cal-item cal-${item.tipo}` : "cal-item");
        linha.append(el("span", "cal-hora", horario(item)));
        if (modo === "admin") {
          const link = el("a", null, item.local ? `${item.titulo} · ${item.local}` : item.titulo);
          link.href = `/admin/eventos/${item.id}`;
          linha.append(link);
        } else {
          linha.append(el("span", "cal-ocupado", "Ocupado"));
        }
        lista.append(linha);
      });
      conteudo.push(lista);
      if (selecionado >= dados.hoje || modo === "admin") {
        const acao = el("button", "botao cal-acao",
          modo === "admin" ? "+ Cadastrar evento neste dia" : `Pedir orçamento para ${ddmm(selecionado)}`);
        acao.type = "button";
        acao.addEventListener("click", () => preencher(selecionado));
        conteudo.push(acao);
      }
      painel.replaceChildren(...conteudo);
    }

    function preencher(iso) {
      const campo = document.querySelector(raiz.dataset.alvoData);
      if (campo) campo.value = iso;
      if (modo === "admin") {
        const futuro = campo?.form?.querySelector('input[name="tipo"][value="futuro"]');
        if (futuro) futuro.checked = true;
      }
      const destino = document.querySelector(raiz.dataset.rolarPara);
      destino?.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
      campo?.focus({ preventScroll: true });
    }

    carregar(null);
  }

  document.querySelectorAll(".calendario").forEach(iniciar);
})();
