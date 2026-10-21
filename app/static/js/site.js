// Visor em tela cheia: navega só pelas fotos do evento que foi clicado.
const visor = document.getElementById("visor");
const palco = visor.querySelector(".visor-conteudo");
let galeriaAtual = [];
let posicao = 0;

function mostrar(indice) {
  posicao = (indice + galeriaAtual.length) % galeriaAtual.length;
  const botao = galeriaAtual[posicao];
  const { src, tipo, legenda } = botao.dataset;
  let midia;
  if (tipo === "video") {
    midia = document.createElement("video");
    midia.controls = true;
    midia.autoplay = true;
    midia.playsInline = true;
    midia.setAttribute("aria-label", legenda);
  } else {
    midia = document.createElement("img");
    midia.alt = legenda;
  }
  midia.src = src;
  const titulo = botao.closest(".evento-card")?.querySelector(".evento-titulo")?.textContent || "";
  const rodape = document.createElement("p");
  rodape.className = "visor-legenda";
  rodape.textContent = galeriaAtual.length > 1 ? `${posicao + 1} de ${galeriaAtual.length} · ${titulo}` : titulo;
  palco.replaceChildren(midia, rodape);
  visor.classList.toggle("visor-varias", galeriaAtual.length > 1);
}

visor.addEventListener("close", () => palco.replaceChildren());
visor.querySelector(".visor-fechar").addEventListener("click", () => visor.close());
visor.querySelector(".visor-anterior").addEventListener("click", () => mostrar(posicao - 1));
visor.querySelector(".visor-proxima").addEventListener("click", () => mostrar(posicao + 1));
visor.addEventListener("click", (evento) => {
  if (evento.target === visor) visor.close();
});
visor.addEventListener("keydown", (evento) => {
  if (galeriaAtual.length < 2) return;
  if (evento.key === "ArrowLeft") mostrar(posicao - 1);
  if (evento.key === "ArrowRight") mostrar(posicao + 1);
});

document.querySelectorAll(".foto").forEach((botao) => {
  botao.addEventListener("click", () => {
    const card = botao.closest(".carrossel");
    galeriaAtual = card ? [...card.querySelectorAll(".foto")] : [botao];
    mostrar(galeriaAtual.indexOf(botao));
    visor.showModal();
  });
});

// "Quero o Nelore" já escolhe o pacote no formulário.
const seletor = document.getElementById("pacote");
document.querySelectorAll("[data-pacote]").forEach((link) => {
  link.addEventListener("click", () => {
    if (seletor) seletor.value = link.dataset.pacote;
  });
});
