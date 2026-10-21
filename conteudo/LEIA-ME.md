# Pasta de conteúdo do Brasamiga

Textos, logo, PDF e fotos aparecem no site ao recarregar a página. Vídeos novos precisam ser convertidos e aparecem depois de reiniciar o site (`docker compose restart`).

| Pasta / arquivo | O que colocar | Onde aparece |
|---|---|---|
| `site.toml` | Pacotes e preços, condições, FAQ, WhatsApp, Instagram, `[agenda]` (montagem e folga) e `[galeria]` (tipos de evento e faixas de convidados) | Página inteira |
| `logo/` | Arquivos do logo. O `site.toml` indica qual usar nas faixas escuras (`logo_escuro`, hoje `LOGO-03.png`, branco sobre preto) | Topo, abertura e ícone da aba |
| `cardapio/` | O PDF da proposta comercial | Botão "Baixar a proposta completa" |
| `eventos-realizados/` | Fotos (JPG, PNG, WEBP, HEIC) e vídeos (MP4, MOV) de festas já feitas | A foto indicada em `foto_capa` vira a capa. As outras só entram na galeria **depois** de serem adicionadas a um evento no painel `/admin` → "Fotos sem evento". |

## Dicas

- O site cria sozinho versões leves das fotos e tira a localização (GPS) que o celular grava nelas. Os arquivos originais nunca ficam públicos.
- Nenhuma foto fica solta no site: cada foto pertence a um evento, e o evento mostra só o "título para o site" (nome e local reais ficam só no painel).
- A pasta nunca é alterada pelo site; o painel só registra quais fotos já foram adicionadas ou ignoradas.
- Ao editar o `site.toml`, mantenha as aspas e os colchetes. Se algo quebrar, o site mostra a linha do erro.
