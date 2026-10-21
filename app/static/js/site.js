// Visor de fotos e vídeos.
const visor = document.getElementById("visor");
const palco = visor.querySelector(".visor-conteudo");

visor.addEventListener("close", () => palco.replaceChildren());
visor.querySelector(".visor-fechar").addEventListener("click", () => visor.close());
visor.addEventListener("click", (evento) => {
  if (evento.target === visor) visor.close();
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
      midia.alt = botao.getAttribute("aria-label").replace(/^Ampliar: /, "");
    }
    midia.src = src;
    palco.replaceChildren(midia);
    visor.showModal();
  });
});

// "Ver todas as fotos" mostra o resto da galeria.
document.querySelectorAll(".ver-mais").forEach((botao) => {
  const alvo = document.getElementById(botao.getAttribute("aria-controls"));
  botao.addEventListener("click", () => {
    alvo.hidden = false;
    botao.setAttribute("aria-expanded", "true");
    botao.hidden = true;
  });
});

// "Quero o Nelore" já escolhe o pacote no formulário.
const seletor = document.getElementById("pacote");
document.querySelectorAll("[data-pacote]").forEach((link) => {
  link.addEventListener("click", () => {
    if (seletor) seletor.value = link.dataset.pacote;
  });
});
