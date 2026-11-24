# Request (verbatim, 2026-11-23)

1. user: "existe alguma forma de melhorar a qualidade final do objeto exportado através de alguma técnica de modelagem 3d?"
2. user: "vamos planejar a feature 1 e 2 com /tlc-spec-lean"

"1 e 2" are these items of the assistant's answer to the first message, quoted:

> 1. **Contorno subpixel e suavização vetorial:** é a maior melhoria visual.
>    - Extrair o contorno por *marching squares* a partir da máscara borrada, antes do limiar, e suavizar com Taubin ou spline, que não encolhem como o Laplaciano.
>    - Preservar cantos acima de certo ângulo, para não arredondar pontas de letras.
>    - **Cuidado:** suavizar cada cor isoladamente faz vizinhas se sobreporem ou se afastarem. O certo é suavizar a **fronteira compartilhada** uma única vez.
> 2. **Eliminar a fresta:** é a correção mais barata.
>    - Traçar o contorno pela borda do pixel e fazer as cores dividirem exatamente a mesma linha.
>    - Sai naturalmente do item 1, se ele usar fronteiras compartilhadas.

> Eu faria **1 e 2 juntos** como uma feature ("contornos suaves e sem fresta") [...]. Os critérios de sucesso seriam:
> - fresta entre vizinhas ≤ 0,005 mm;
> - giro do disco próximo de 1 volta;
> - largura de 150 ± 0,02 mm;
> - cantos retos preservados;
> - malhas fechadas e linhas finas com pelo menos 0,42 mm.

No captures came with the request. Answers to the plan's questions are recorded in plan.md.
