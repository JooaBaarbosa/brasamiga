// Visor de fotos e vídeos da galeria.
const visor = document.getElementById("visor");
const palco = visor.querySelector(".visor-conteudo");

function fechar() {
  visor.close();
}

visor.addEventListener("close", () => palco.replaceChildren());
visor.querySelector(".visor-fechar").addEventListener("click", fechar);
visor.addEventListener("click", (evento) => {
  if (evento.target === visor) fechar();
});

document.querySelectorAll(".foto").forEach((botao) => {
  botao.addEventListener("click", () => {
    const { src, tipo } = botao.dataset;
    let midia;
    if (tipo === "video") {
      midia = document.createElement("video");
      midia.controls = true;
      midia.autoplay = true;
      midia.playsInline = true;
    } else {
      midia = document.createElement("img");
      midia.alt = botao.getAttribute("aria-label").replace(/^Ampliar /, "");
    }
    midia.src = src;
    palco.replaceChildren(midia);
    visor.showModal();
  });
});
