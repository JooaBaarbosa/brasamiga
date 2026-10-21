# Pasta de conteúdo do Brasamiga

Tudo o que você colocar aqui aparece na landing page ao recarregar o site, sem precisar mexer no código.

| Pasta / arquivo | O que colocar | Onde aparece |
|---|---|---|
| `logo/` | Um arquivo de logo (PNG, SVG, WEBP ou JPG). Se houver mais de um, vale o primeiro em ordem alfabética. | Topo do site e ícone da aba |
| `cardapio/` | O cardápio em **PDF** (vira botão "Baixar") e/ou **fotos** do cardápio. | Seção Cardápio |
| `eventos-realizados/` | Fotos (JPG, PNG, WEBP, GIF, AVIF) e vídeos (MP4, WEBM, MOV) de festas que vocês já fizeram. | Galeria "Eventos que a gente já serviu" |
| `site.toml` | Slogan, cidade, WhatsApp, e-mail, Instagram, lista de serviços e o cardápio em texto. | Página inteira |

## Dicas

- Fotos com até ~2 MB carregam rápido no celular. Fotos de câmera costumam ter 8–15 MB: reduza antes de colocar aqui.
- Os nomes dos arquivos definem a ordem (`01-casamento.jpg`, `02-aniversario.jpg`...).
- Para separar as fotos **por evento**, com nome, data e local, use o painel em `/admin` em vez desta pasta.
- Para trocar o cardápio, edite os blocos `[[cardapio]]` do `site.toml` ou coloque um PDF novo em `cardapio/`.
