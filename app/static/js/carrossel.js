// Carrossel das fotos de um evento: arrastar (scroll-snap), setas, contador, bolinhas e teclado.
(() => {
  const suave = () => (matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth");

  document.querySelectorAll(".carrossel").forEach((carrossel) => {
    const trilha = carrossel.querySelector(".trilha");
    const slides = [...trilha.children];
    const contagem = carrossel.querySelector(".contagem");
    const pontos = [...carrossel.querySelectorAll(".pontos i")];
    if (slides.length < 2) return;

    const atual = () => Math.round(trilha.scrollLeft / trilha.clientWidth);
    const ir = (indice) => {
      const alvo = (indice + slides.length) % slides.length;
      trilha.scrollTo({ left: alvo * trilha.clientWidth, behavior: suave() });
    };
    const atualizar = () => {
      const i = atual();
      if (contagem) contagem.textContent = `${i + 1}/${slides.length}`;
      pontos.forEach((ponto, n) => ponto.classList.toggle("on", n === i));
    };

    carrossel.querySelector(".seta-esq").addEventListener("click", () => ir(atual() - 1));
    carrossel.querySelector(".seta-dir").addEventListener("click", () => ir(atual() + 1));
    pontos.forEach((ponto, n) => ponto.addEventListener("click", () => ir(n)));
    carrossel.addEventListener("keydown", (evento) => {
      if (evento.key === "ArrowLeft") { evento.preventDefault(); ir(atual() - 1); }
      if (evento.key === "ArrowRight") { evento.preventDefault(); ir(atual() + 1); }
    });
    let espera;
    trilha.addEventListener("scroll", () => {
      clearTimeout(espera);
      espera = setTimeout(atualizar, 60);
    }, { passive: true });
  });
})();
