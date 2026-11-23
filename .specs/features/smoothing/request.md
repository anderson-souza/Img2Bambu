# Request

> faça a leitura do arquivo @.specs/melhorias-cores.md e vamos especificar a melhoria 3

Source referenced: `.specs/melhorias-cores.md` §3 "Suavizar antes de agrupar (mean-shift / bilateral)":

> **O quê:** pré-filtro opcional na imagem antes do k-means e da atribuição — `cv2.pyrMeanShiftFiltering`
> ou `cv2.bilateralFilter` —, com um controle "Suavização" (0 = desligado).
>
> **Por quê:** achata degradês e remove pixels de transição entre cores, gerando regiões mais limpas e
> menos ilhas que a limpeza morfológica precisa apagar (e que às vezes leva detalhe junto).
>
> **Pontos a decidir:** valor padrão (desligado vs. leve); aplicar só dentro da silhueta; custo em
> imagens grandes (mean-shift é lento — talvez rodar em resolução reduzida ou só no `analyze`).
>
> **Onde mexe:** `segment.analyze` (antes de `kmeans_palette`), `Params` (novo campo), GUI (spin box).
> Testável com imagem sintética com degradê: menos componentes conexos após o filtro.

No captures.
