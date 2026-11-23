# Request

Verbatim (2026-11-22):

> faça a leitura do arquivo @.specs/melhorias-cores.md e vamos planejar o item 2

Referenced source: `.specs/melhorias-cores.md`, section "## 2. Conta-gotas na aba Original":

> **O quê:** clicar num ponto da aba *Original* define a *cor na imagem* de uma linha (a linha
> selecionada, ou um menu "usar como cor na imagem de… / nova cor").
>
> **Por quê:** é o ajuste fino mais natural — o usuário aponta o tom que quer em cada filamento, sem
> adivinhar RGB. Complementa a paleta fixa.
>
> **Pontos a decidir:** amostra de 1 pixel ou média de uma vizinhança (ex.: 5×5, mais robusta a
> antialiasing); se o clique cria uma linha nova quando há menos de 8; atalho para alternar o modo
> conta-gotas; funcionar também na aba *Cores (prévia)*.
>
> **Onde mexe:** `gui/main_window.py` (`ImageView` recebe clique → coordenada no `rgba`), reaproveita
> `ColorRow.pick`/`palette_changed`.

Captures: none.
