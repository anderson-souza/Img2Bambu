# Melhorias sugeridas — detecção e ajuste fino de cores

Origem: análise da imagem `workdir/cha-bebe/Gemini_Generated_Image_yah5wqyah5wqyah5.png` (2026-11-22),
alvo de 4 filamentos ("2 verdes, 1 rosa e 1 branco"). A melhoria 1 (paleta fixa: *cor na imagem* →
*cor do filamento*) já foi feita em `.specs/features/fixed-palette/`. As demais estão abaixo, em
ordem de prioridade sugerida.

## Diagnóstico (por que a prévia fica ruim)

- **k-means decide sozinho os grupos.** Com k=4 a imagem vira `(92,90,55) 14%`, `(222,142,148) 11%`,
  `(171,171,107) 30%`, `(215,213,179) 46%`: os dois rosas da borboleta se fundem, a barriga creme cai
  junto com o fundo sálvia, manchas do dino e contornos das folhas viram um só verde escuro.
- **Filtro reflexo em cores que não são brilho.** Ele remove regiões com "raio" < 1 mm (antenas,
  caules, contornos finos). Só faz sentido em branco/realce.
- **Limpeza morfológica apaga traços finos.** `segment.clean` (`img2bambu/segment.py`) faz abertura
  do tamanho de "Detalhe mínimo" em cada máscara de cor.
- **Degradês e antialiasing** de imagens geradas por IA criam pixels intermediários que viram ruído
  e ilhas pequenas.

## Dicas de uso (sem mudar código)

- Desmarque **Filtro reflexo** no rosa e nos verdes; deixe só no branco.
- Teste **Detalhe mínimo 0,3 mm** (bico 0,4 mm ainda imprime bem).
- Use **Nº de cores 6–8** e mescle as sobras pelo menu "—" (ex.: creme → branco, rosa escuro → rosa).
- Com a paleta fixa: ajuste a **cor na imagem** de cada linha para puxar tons; o diálogo do Qt tem
  "Pick Screen Color" onde a plataforma permite.

## 2. Conta-gotas na aba Original

**O quê:** clicar num ponto da aba *Original* define a *cor na imagem* de uma linha (a linha
selecionada, ou um menu "usar como cor na imagem de… / nova cor").

**Por quê:** é o ajuste fino mais natural — o usuário aponta o tom que quer em cada filamento, sem
adivinhar RGB. Complementa a paleta fixa.

**Pontos a decidir:** amostra de 1 pixel ou média de uma vizinhança (ex.: 5×5, mais robusta a
antialiasing); se o clique cria uma linha nova quando há menos de 8; atalho para alternar o modo
conta-gotas; funcionar também na aba *Cores (prévia)*.

**Onde mexe:** `gui/main_window.py` (`ImageView` recebe clique → coordenada no `rgba`), reaproveita
`ColorRow.pick`/`palette_changed`.

## 3. Suavizar antes de agrupar (mean-shift / bilateral)

**O quê:** pré-filtro opcional na imagem antes do k-means e da atribuição — `cv2.pyrMeanShiftFiltering`
ou `cv2.bilateralFilter` —, com um controle "Suavização" (0 = desligado).

**Por quê:** achata degradês e remove pixels de transição entre cores, gerando regiões mais limpas e
menos ilhas que a limpeza morfológica precisa apagar (e que às vezes leva detalhe junto).

**Pontos a decidir:** valor padrão (desligado vs. leve); aplicar só dentro da silhueta; custo em
imagens grandes (mean-shift é lento — talvez rodar em resolução reduzida ou só no `analyze`).

**Onde mexe:** `segment.analyze` (antes de `kmeans_palette`), `Params` (novo campo), GUI (spin box).
Testável com imagem sintética com degradê: menos componentes conexos após o filtro.

## 4. Mesclagem automática por distância

**O quê:** detectar mais cores (ex.: 8) e juntar automaticamente as mais parecidas (agrupamento
hierárquico em LAB) até chegar ao número de filamentos desejado; a mesclagem manual continua para
corrigir.

**Por quê:** separa "quantos tons existem" de "quantos filamentos tenho". Com k pequeno o k-means
mistura tons distintos; com k grande e merge por proximidade, tons parecidos (dois verdes escuros)
se juntam e tons distintos (rosa claro vs. creme) não.

**Pontos a decidir:** novo campo "Filamentos" separado de "Nº de cores"; critério de fusão
(distância entre centros ponderada pela área?); se a base pode ser fundida; interação com a paleta
fixa (linhas editadas nunca são fundidas automaticamente?).

**Onde mexe:** `segment.analyze` gera `Palette.merges` iniciais; GUI já exibe merges no combo "—".

## 5. Proteger traços finos

**O quê:** não aplicar a abertura morfológica (ou aplicar com kernel menor) a componentes finos e
alongados, ou permitir marcar uma cor como **contorno** que tem prioridade e limpeza própria.

**Por quê:** contornos, antenas, nervuras e caules são o que dá leitura à arte; hoje somem quando
ficam abaixo de "Detalhe mínimo" ou do raio do filtro reflexo.

**Pontos a decidir:** largura mínima imprimível (≈ 1 linha de extrusão, ~0,42 mm com bico 0,4);
como detectar "linha" (esqueleto + transformada de distância); se a prioridade de contorno altera a
ordem das máscaras disjuntas em `build_masks`.

**Onde mexe:** `segment.clean` / `segment.build_masks`. Testável com sintético: linha de 0,6 mm
sobrevive, ruído de 0,6 mm² some.

## 6. Prévia comparativa

**O quê:** na aba *Cores (prévia)*: alternar/sobrepor com a imagem original (slider de opacidade ou
tecla segurada), e destacar uma cor por vez (clicar na linha → só aquela máscara em evidência).

**Por quê:** mostra rapidamente o que se perdeu (detalhes apagados, tons que foram para a cor
errada), o que hoje exige alternar abas e comparar de cabeça.

**Pontos a decidir:** sobreposição vs. lado a lado; como sinalizar pixels removidos pela limpeza
(ex.: em vermelho).

**Onde mexe:** só GUI (`ImageView`, `preview_done`); as máscaras já voltam de `pipeline.render`.

## Ordem sugerida

1. **2 – Conta-gotas** (pequeno, completa a paleta fixa)
2. **3 – Suavização** (melhora todas as imagens geradas por IA)
3. **6 – Prévia comparativa** (só GUI, ajuda a avaliar 3 e 5)
4. **5 – Traços finos**
5. **4 – Mesclagem automática**
