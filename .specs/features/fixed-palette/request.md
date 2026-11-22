# Request

## Original message (2026-11-22)

> estou com alguns problemas para fechar uma boa arte utilizando a imagem @workdir/cha-bebe/Gemini_Generated_Image_yah5wqyah5wqyah5.png. Sei que a imagem possui mais de 4 cores e quero fazer com que seja possível utilizar apenas 4 cores. 2 verdes, 1 rosa e 1 branco, mas a visualização não está ficando boa. Alguma sugestão do que podemos fazer para melhorar o software e ajudar na detecção e ajustes mais finos das cores? Aqui está como ficou a imagem [Image #1]

Captures: screenshot of the GUI (Cores (prévia) tab, 4 colors: dark olive base, pink, light green, white; Filtro reflexo checked on pink, light green, white) - pasted in chat, not saved to disk. Source image: `workdir/cha-bebe/Gemini_Generated_Image_yah5wqyah5wqyah5.png`.

## Assistant's proposal the request refers to (item 1)

> 1. **Paleta fixa de filamentos (a maior mudança):** você define as 4 cores dos filamentos (seletor de cor ou as cores dos presets Bambu) e cada pixel vai para a mais próxima em LAB, sem k-means. Resolve diretamente o "2 verdes, 1 rosa, 1 branco", e a prévia passa a mostrar as cores reais.

## This request

> /tlc-spec-lean vamos planejar a melhoria 1
