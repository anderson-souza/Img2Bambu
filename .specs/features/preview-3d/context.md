# Preview 3D Context

**Gathered:** 2026-10-22
**Spec:** `.specs/features/preview-3d/spec.md`
**Status:** Ready for design

---

## Feature Boundary

Aba "3D" na GUI mostrando as malhas reais de `geometry.build_parts` para os parâmetros atuais, atualizando automaticamente com os controles existentes; câmera orbit/zoom/pan; dimensões do modelo; mesa da impressora selecionada com aviso se não couber.

---

## Implementation Decisions

### Local
- Nova aba "3D" no `QTabWidget` existente, ao lado de "Cores (prévia)" e "Original".

### Atualização
- Automática com o mesmo debounce da prévia 2D, mas só calcula malhas com a aba 3D visível. Ao voltar para a aba com modelo desatualizado, recalcula uma vez.

### Ajustes
- Apenas os controles existentes do painel lateral. Nenhum controle de geometria novo.

### Vista
- Orbitar / zoom / pan.
- Mesa da impressora (de `printable_area` do preset).
- Dimensões X×Y×Z.

### Agent's Discretion
- Tecnologia de render (Qt3D / QtQuick3D / QOpenGLWidget) — decidir no Design, preferindo zero dependência nova.
- Mapeamento exato de botões do mouse, iluminação, cor de fundo.

### Declined / Undiscussed Gray Areas → Assumptions
- Vistas prontas/reset de câmera: não escolhidas → fora de escopo (reenquadra só ao abrir nova imagem).
- Mostrar/ocultar partes: não escolhido → fora de escopo.
- Demais defaults registrados na tabela de Assumptions do spec.

---

## Specific References

Nenhuma referência específica — comportamento da prévia 2D atual (`run_preview`/`preview_done`, debounce, `tag`) é o modelo a seguir.

---

## Deferred Ideas

- Vistas prontas (frente/topo/iso).
- Toggle de visibilidade por parte.
- Relevo por cor.
- Reaproveitar malhas da prévia no export.
