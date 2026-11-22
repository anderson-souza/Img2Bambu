# Preview 3D Specification

## Problem Statement

Hoje o usuário só vê uma prévia 2D das cores (`segment.preview`). Espessura da base, altura do relevo, efeito de `min_detail_mm`/`simplify_mm` e tamanho final só aparecem depois de gerar o 3MF e abrir no Bambu Studio — ciclo lento (CLI do Bambu Studio + opcional fatiamento). Queremos ver o objeto 3D final dentro do app e ajustar antes de gerar.

## Goals

- [ ] Usuário vê, numa aba "3D", exatamente as malhas que `pipeline.export` gravaria (mesmo `geometry.build_parts`, mesmos parâmetros).
- [ ] Qualquer ajuste nos controles existentes reflete na vista 3D sem clicar em gerar.
- [ ] Usuário sabe tamanho final (X×Y×Z) e se cabe na mesa da impressora selecionada antes de gerar.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Novos controles de geometria (relevo por cor, chanfro, etc.) | Usuário escolheu "controles existentes"; mudaria pipeline e 3MF |
| Mostrar/ocultar partes individuais | Não escolhido |
| Vistas prontas (frente/topo/iso) e botões de câmera | Não escolhido; só orbitar/zoom/pan |
| Prévia de fatiamento / camadas / G-code | Responsabilidade do Bambu Studio |
| Reaproveitar malhas da prévia no export (cache) | Otimização; export continua recalculando |
| Preview 3D na CLI (`__main__.py`) | Funcionalidade só da GUI |
| Edição direta da malha na vista | Fora do propósito do app |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Local do preview | Nova aba "3D" junto de "Cores (prévia)" e "Original" | Escolha do usuário | y |
| Quando recalcular | Automático (mesmo debounce de 350 ms da prévia 2D), só quando aba 3D visível; ao abrir a aba com dados desatualizados, recalcula | Escolha do usuário; evita custo de malha com aba oculta | y |
| Ajustes | Só controles existentes do painel lateral | Escolha do usuário | y |
| Interação | Orbitar (arrastar esquerdo), zoom (roda), pan (botão do meio ou direito) | Escolha do usuário; mapeamento de botões é convenção comum | y (mapeamento: n) |
| Fonte da geometria | `geometry.build_parts` com `Params`/`Palette` atuais — nunca uma aproximação | Garante WYSIWYG com o export | n |
| Cores na vista | Cor de cada `Part.color` (RGB da paleta), iluminação simples para leitura de relevo | Parte i = filamento i | n |
| Câmera ao atualizar | Mantém posição em ajustes de parâmetros; reenquadra ao abrir nova imagem | Usuário não perde o ângulo que está inspecionando | n |
| Mesa sem presets | Se `PresetDB` indisponível ou impressora sem `printable_area`: não desenha mesa, mostra "Mesa indisponível" | Presets são opcionais no app (modo só STL) | n |
| Modelo vazio | N/A: `build_parts` lança `ValueError` ("Silhueta vazia após limpeza.") antes de existir modelo vazio; tratado por P1 AC9 | Caminho inalcançável; registrado pelo Verifier (L-003) | y |
| Posição do modelo na mesa | Centro do bbox no centro de `printable_area` (mesma lógica de `PresetDB.bed_center`) | Coincide com posicionamento do export | n |
| "Cabe na mesa" | Compara bbox XYZ do modelo com bbox de `printable_area` + `printable_height`; Z ignorado se campo ausente | `printable_height` confirmado no Design (A1 = 256) | y |
| OpenGL indisponível | Aba 3D mostra mensagem de erro; resto do app funciona igual | Falha visível, sem quebrar fluxo de export | n |
| Tecnologia de render | Decidir no Design (PySide6 6.12 já tem Qt3D, QtQuick3D, QtOpenGLWidgets); preferência: nenhuma dependência nova | Convenção: manter bundle PyInstaller enxuto | n |
| Performance | Sem meta numérica; malha calculada em `Task` no thread pool, UI nunca bloqueia | Custo em imagem grande não medido (imagem da abelha ausente) | n |

**Open questions:** none — all resolved or logged above.

---

## User Stories

### P1: Ver modelo 3D e ajustar ⭐ MVP

**User Story**: Como usuário do Img2Bambu, quero ver o objeto 3D que será impresso e girá-lo, para ajustar cores/dimensões antes de gerar o 3MF.

**Why P1**: É a funcionalidade pedida; sem ela nada do resto faz sentido.

**Acceptance Criteria**:

1. WHEN imagem analisada e usuário abre a aba "3D" THEN sistema SHALL exibir uma parte por item de `geometry.build_parts(...)` com os `Params`/`Palette` atuais, cada uma com sua `Part.color`.
2. WHEN modelo exibido THEN base SHALL ocupar z ∈ [0, `base_mm`] e partes de cor z ∈ [`base_mm`, `base_mm + relief_mm`] (mesmas malhas do export, em mm).
3. WHEN aba "3D" visível e usuário altera qualquer controle que hoje dispara a prévia 2D (cor, base, mesclar, filtro reflexo, nº de cores, detalhe, largura, base, relevo, fundo, tolerância) THEN sistema SHALL recalcular e substituir o modelo após o debounce.
4. WHEN aba "3D" NÃO visível e controles mudam THEN sistema SHALL NÃO chamar `build_parts` para a vista 3D; WHEN aba volta a ficar visível com modelo desatualizado THEN SHALL recalcular uma vez.
5. WHEN vários ajustes disparam recálculos sobrepostos THEN sistema SHALL exibir só o resultado do pedido mais recente (resultados com `tag` antigo descartados).
6. WHEN usuário arrasta com botão esquerdo / gira roda / arrasta com botão do meio ou direito THEN câmera SHALL orbitar / dar zoom / transladar.
7. WHEN parâmetros mudam THEN câmera SHALL manter posição; WHEN nova imagem é aberta THEN câmera SHALL reenquadrar o modelo inteiro.
8. WHEN nenhuma imagem carregada THEN aba "3D" SHALL mostrar estado vazio ("Abra uma imagem para ver o modelo 3D.").
9. WHEN `build_parts` lança erro (silhueta vazia, malha não watertight) THEN aba SHALL mostrar a mensagem de erro em português, remover o modelo anterior e registrar no log; app SHALL continuar utilizável.

**Independent Test**: Abrir imagem sintética, ir à aba 3D, verificar nº de partes = `len(build_parts(...))` e bounds Z; alterar relevo e ver Z máximo mudar.

---

### P2: Dimensões do modelo

**User Story**: Como usuário, quero ver o tamanho final e quantas partes o modelo tem, para saber se é o que espero.

**Why P2**: Informação útil, mas o preview já tem valor sem ela.

**Acceptance Criteria**:

1. WHEN modelo 3D exibido THEN aba SHALL mostrar texto "X × Y × Z mm" do bbox combinado de todas as partes (1 casa decimal) e nº de partes.
2. WHEN modelo recalculado THEN texto SHALL refletir o novo bbox.

**Independent Test**: Largura 150 mm, base 10, relevo 1 → texto mostra X = 150.0 (± `simplify_mm` + 1 pixel upsampled, perda inerente de `to_polys` igual ao export) e Z = 11.0.

---

### P2: Mesa da impressora

**User Story**: Como usuário, quero ver o modelo sobre a mesa da impressora selecionada, para saber se cabe.

**Why P2**: Evita gerar 3MF que não cabe; depende de presets (opcionais).

**Acceptance Criteria**:

1. WHEN presets carregados e impressora selecionada tem `printable_area` THEN vista SHALL desenhar a mesa (plano retangular do tamanho da `printable_area`, logo abaixo de z=0) com modelo centrado nela.
2. WHEN usuário troca impressora THEN mesa SHALL ser redesenhada com a nova área (sem recalcular malhas).
3. WHEN bbox X, Y ou Z do modelo excede largura/profundidade da `printable_area` ou `printable_height` THEN aba SHALL mostrar aviso "⚠ Modelo maior que a mesa (W × D × H mm)."; WHEN `printable_height` ausente THEN Z SHALL ser ignorado e aviso SHALL mostrar "(W × D mm)".
4. WHEN presets indisponíveis ou sem `printable_area` THEN vista SHALL omitir mesa e mostrar "Mesa indisponível"; modelo continua exibido.

**Independent Test**: Selecionar A1 (256×256) com largura 300 mm → aviso aparece; largura 150 → sem aviso.

---

## Edge Cases

- WHEN contexto OpenGL/3D falha ao iniciar (driver, VM, offscreen) THEN aba 3D SHALL mostrar mensagem de erro e o restante da GUI (prévia 2D, export) SHALL funcionar.
- WHEN export em andamento THEN preview 3D SHALL continuar funcionando (tarefas independentes; export não usa o resultado do preview).
- WHEN todas as cores mescladas na base THEN modelo SHALL mostrar só a base (1 parte).
- WHEN modelo tem muitas partes (> 4) THEN preview SHALL exibir todas (aviso de AMS já existe no painel; nada novo).

---

## Implicit-Requirement Dimensions Sweep

| Dimension | Resolution |
| --------- | ---------- |
| Input validation & bounds | Coberto pelos ranges dos spinboxes existentes; nada novo |
| Failure / partial-failure | P1-AC9, edge case OpenGL |
| Idempotency / retry / duplicates | P1-AC4 (recalcula uma vez), P1-AC5 |
| Auth / rate limits | N/A because app desktop local sem usuários |
| Concurrency / ordering | P1-AC5 (`tag`), edge case export simultâneo |
| Data lifecycle | N/A because nada persistido; malhas só em memória |
| Observability | Erros vão para log da GUI (P1-AC9) |
| External-dependency failure | Presets ausentes (P2 mesa AC4); OpenGL indisponível |
| State-transition integrity | Estados da aba: vazio → calculando → pronto/erro; desatualizado ao ocultar (P1-AC4) |

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| PREV3D-01 | P1: geometria = `build_parts` (AC1, AC2) | Tasks | Verified (auto; UAT pending) |
| PREV3D-02 | P1: auto-update só com aba visível (AC3, AC4) | Tasks | Verified (auto; UAT pending) |
| PREV3D-03 | P1: descarte de resultado obsoleto (AC5) | Tasks | Verified (auto; UAT pending) |
| PREV3D-04 | P1: câmera orbit/zoom/pan + reenquadrar (AC6, AC7) | Tasks | Verified (auto; UAT pending) |
| PREV3D-05 | P1: estados vazio/erro (AC8, AC9, edge OpenGL) | Tasks | Verified (auto; UAT pending) |
| PREV3D-06 | P2: dimensões e nº de partes | Tasks | Verified (auto; UAT pending) |
| PREV3D-07 | P2: mesa + aviso de tamanho | Tasks | Verified (auto; UAT pending) |

**Coverage:** 7 total, 7 mapped to tasks (T1–T11), 0 unmapped

---

## Success Criteria

- [ ] Bounds e nº de partes exibidos na vista 3D batem com `pipeline.export` para mesmos parâmetros (teste automatizado).
- [ ] Ajustar relevo/base/largura com aba 3D aberta atualiza o modelo sem clicar em gerar.
- [ ] Com aba 3D oculta, ajustes não disparam `build_parts` (teste automatizado).
- [ ] `tests/gui_smoke.py` continua passando; screenshot da aba 3D em offscreen mostra o modelo (ou mensagem de erro clara se offscreen não suportar 3D).
- [ ] Nenhuma dependência nova em `requirements.txt` (meta; revisar no Design se inviável).
