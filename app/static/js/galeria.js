// Busca e filtros da galeria de eventos realizados. A URL guarda o filtro (?tipo=&pessoas=&q=).
(() => {
  const secao = document.getElementById("eventos");
  if (!secao) return;
  const filtros = secao.querySelector(".filtros");
  const busca = secao.querySelector(".busca");
  const cards = [...secao.querySelectorAll(".evento-card")];
  const contador = secao.querySelector(".contador");
  const vazio = secao.querySelector(".sem-resultado");
  const grupos = {
    tipo: secao.querySelector('[data-filtro="tipo"]'),
    pessoas: secao.querySelector('[data-filtro="pessoas"]'),
  };
  filtros.hidden = false; // sem JavaScript, todos os cards aparecem e os filtros ficam escondidos

  const normalizar = (texto) => texto.normalize("NFKD").replace(/[̀-ͯ]/g, "")
    .toLowerCase().replace(/\s+/g, " ").trim();

  function escolher(grupo, valor) {
    let achou = false;
    grupo.querySelectorAll(".chip").forEach((chip) => {
      const ativo = chip.dataset.valor === valor;
      achou ||= ativo;
      chip.classList.toggle("on", ativo);
      chip.setAttribute("aria-pressed", String(ativo));
    });
    if (!achou) escolher(grupo, "");
  }

  const ativo = (grupo) => grupo.querySelector(".chip.on");

  function aplicar() {
    const termos = normalizar(busca.value).split(" ").filter(Boolean);
    const tipo = ativo(grupos.tipo).dataset.valor;
    const faixa = ativo(grupos.pessoas);
    const minimo = faixa.dataset.min ? Number(faixa.dataset.min) : null;
    const maximo = faixa.dataset.max ? Number(faixa.dataset.max) : null;
    let visiveis = 0;
    cards.forEach((card) => {
      const convidados = card.dataset.convidados ? Number(card.dataset.convidados) : null;
      const ok = termos.every((termo) => card.dataset.busca.includes(termo))
        && (!tipo || card.dataset.categoria === tipo)
        && (minimo === null || (convidados !== null && convidados >= minimo && (maximo === null || convidados <= maximo)));
      card.hidden = !ok;
      if (ok) visiveis++;
    });
    contador.textContent = visiveis === 1 ? "1 evento" : `${visiveis} eventos`;
    vazio.hidden = visiveis > 0;

    const url = new URL(location.href);
    const params = { q: busca.value.trim(), tipo, pessoas: faixa.dataset.valor };
    Object.entries(params).forEach(([chave, valor]) => (valor ? url.searchParams.set(chave, valor) : url.searchParams.delete(chave)));
    history.replaceState(null, "", url);
  }

  Object.values(grupos).forEach((grupo) => {
    grupo.addEventListener("click", (evento) => {
      const chip = evento.target.closest(".chip");
      if (!chip) return;
      escolher(grupo, chip.dataset.valor);
      aplicar();
    });
  });
  let espera;
  busca.addEventListener("input", () => {
    clearTimeout(espera);
    espera = setTimeout(aplicar, 150);
  });
  secao.querySelector(".limpar").addEventListener("click", () => {
    busca.value = "";
    escolher(grupos.tipo, "");
    escolher(grupos.pessoas, "");
    aplicar();
    busca.focus();
  });

  // Abrir um link com filtros já aplica os filtros.
  const inicial = new URLSearchParams(location.search);
  busca.value = inicial.get("q") || "";
  escolher(grupos.tipo, normalizar(inicial.get("tipo") || ""));
  escolher(grupos.pessoas, inicial.get("pessoas") || "");
  if (inicial.has("q") || inicial.has("tipo") || inicial.has("pessoas")) aplicar();
})();
