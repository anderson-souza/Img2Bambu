# Melhorias sugeridas — geração do 3MF e fidelidade da impressão

Origem: análise de 2026-11-24 (commit `0ae9612`), no Linux, com Bambu Studio 2.9.1 (Flatpak), preset
`Bambu Lab A1 0.4 nozzle` e os padrões dele (`0.20mm Standard @BBL A1`, `Bambu PLA Basic @BBL A1`).
Imagem sintética de 900×900 px com 4 cores; nas malhas, também a abelha. Nenhum código foi alterado.

Estados: `aberto` → `refinado` (pontos decididos) → `feito` (link do PR). Ao atacar um item, crie
`.specs/features/<nome>/` e atualize a tabela.

| # | Item | Prioridade | Evidência | Estado |
|---|---|---|---|---|
| 1 | Presets completos no 3MF | P0 | medido | refinado (implementado, sem PR; falta UAT na GUI) |
| 2 | Posição da prime tower | P0 | medido | refinado (implementado, sem PR) |
| 3 | `--check` que não esconde falhas | P0 | medido + código | refinado (implementado, sem PR) |
| 4 | Alturas múltiplas da camada | P1 | medido | aberto |
| 5 | Conferência pelo gcode | P1 | proposta | aberto |
| 6 | Limites pelo bico real | P1 | código | aberto |
| 7 | Tipo de mesa | P1 | medido | aberto |
| 8 | Filamento por cor e presets do usuário | P2 | código | aberto |
| 9 | 3MF genérico sem Bambu Studio | P2 | código | aberto |
| 10 | Dois bicos e áreas excluídas | P2 | presets + código | aberto |
| 11 | Purga por par de cores | P3 | medido | aberto |
| 12 | Resumo após gerar | P3 | proposta | aberto |
| 13 | Modo face para baixo | P3 | proposta | aberto |

## O que já está bom (não mexer sem motivo)

- Malhas em 60, 150 e 300 mm: fechadas, winding consistente, 0 arestas non-manifold, 0 vértices perdidos
  ao arredondar para 4 casas. Há alguns triângulos de área ~0 (até 126 por parte); o CLI registrou
  `degenerate_facets="0"` no 3MF inspecionado (imagem sintética, 100 mm).
- Cores vizinhas compartilham o mesmo contorno; partes e filamentos chegam corretos ao projeto.

## P0

### 1. Presets completos no 3MF

**Diagnóstico:** `bambu.export_project` passa ao CLI os JSONs de sistema originais (`PresetDB.path`), que
dependem de `inherits`. O CLI não resolve a herança: o herdado vira o padrão genérico do fatiador.
Comparando com `PresetDB.resolve`, diferem 31 chaves de máquina, 64 de processo e 51 de filamento
(algumas só no formato, ex.: `100` × `100%`).

| Configuração | Preset | No 3MF gerado |
|---|---|---|
| `nozzle_temperature` | 220 | 200 |
| `filament_max_volumetric_speed` | 21 | 2 |
| `change_filament_gcode` | ~4000 caracteres | vazio |
| `machine_start_gcode` | o da Bambu | genérico (`G28`) |
| `enable_prime_tower` | 1 | 0 |
| `outer_wall_speed` | 200 | 60 |
| `wall_generator` | classic | arachne |
| `filament_density` / `filament_ids` | 1.26 / GFA00 | 0 / vazio |

**Correção (2026-11-24): resolver só `inherits` não basta, não use o protótipo abaixo.** O gcode da impressora vem de
`include` (A1: início com 577 caracteres sem ele, 12310 com ele). Precedência: herdado < `include` < próprio. Um
projeto da A1 salvo no Bambu Studio confirmou herdado < `include`; próprio > `include` é suposição.
Em A1, A1 mini, P1S, H2S, H2D e X2D 0.4 o 3MF ficou igual ao preset nas chaves comparadas, salvo formato, metadados
e o limite de aceleração do `cli_config.json` (A1 e A1 mini). Só o primeiro valor de cada lista foi comparado no
spike; na A1 o teste compara listas inteiras. Nela, 5 chaves `filament_dev_*drying*` (secagem no AMS) são cortadas
pelo CLI. `pre_start_fan_time` não é erro: vale o do filamento.
Nota: os presets P1P apontam para um filamento padrão que não existe na instalação.

**Protótipo original (sem `include`):** gravar o resultado de `resolve` como JSON temporário, sem `inherits` e
`include`, com `name`, `type` e `from: system`, e passar esse arquivo ao CLI. Restaram diferentes 6, 10 e 2
chaves, quase todas de formato; o tempo estimado caiu de 4h07 para 1h03; peso e `filament_id` apareceram.

**A verificar:**
- A GUI do Bambu Studio recupera valores pelo nome do preset ao abrir o projeto? Abrir um 3MF atual e
  olhar temperatura, prime tower e gcode de troca. Define a gravidade para quem imprime pela GUI;
  o `--check` usa os valores errados com certeza.
- Diferenças que sobraram sem ser de formato: `machine_max_acceleration_x/y` e `_travel`
  (12000/12000/9000 → 6000) e `pre_start_fan_time` (0 → 2).
- `resolve` ignora `include`, usado por muitos presets de filamento: ver o que se perde.
- As correções de `patch_project` ("arrays com tamanho 1") continuam necessárias? Não remover sem testar a
  GUI (`.claude/rules/bambu-cli.md`).
- Outras impressoras, inclusive de dois bicos, e Windows.

**Aceite:** teste que compara o 3MF com o preset resolvido, chave a chave, normalizando formato. Os testes
atuais não pegaram o defeito.

**Onde mexe:** `bambu.PresetDB`, `bambu.export_project`.

### 2. Posição da prime tower

**Diagnóstico:** com o item 1 corrigido a torre liga, e a posição padrão (15, 220) na A1 falha com "Found
G-code outside of the printable area" (código -104). Peça de 100 mm: (15, 200), (25, 190) e (210, 20) passam;
com a torre desligada também (54 min contra 1h03). Com 240 mm de largura: "G-code conflicts detected".

**Resolvido (2026-11-24):** a torre é quase quadrada e cresce com o número de cores e com camadas finas (camada 0,2,
com brim: 2 cores ≈ 30 mm, 3 ≈ 37, 4 ≈ 44, 6 ≈ 55; 8 ≈ 64, na H2S). Na A1, em y = 220, cabe com 3 cores e não com 4;
na A1 mini nunca cabe. `tower.place` mantém a posição padrão se estiver livre, senão escolhe a livre mais próxima
(contorno real da peça, `bed_exclude_area`). Sem espaço: só avisa (decisão do usuário). Fatiado: A1, A1 mini, P1S, X1C
e H2S; a H2D e a X2D seguem falhando ao fatiar (item 10).

**O quê:** escolher um canto livre a partir da mesa, do tamanho da peça, da largura da torre e da margem;
avisar quando não couber.

**Pontos a decidir:** sem espaço, desligar a torre, reduzir a peça ou só avisar; mover a peça do centro;
oferecer a opção ao usuário. As dimensões reais da torre (com brim) precisam ser medidas.

**Onde mexe:** `bambu.patch_project`, `pipeline._export_bambu`.

### 3. `--check` que não esconde falhas

**Resolvido (2026-11-24):** o `result.json` sumia porque a pasta `slice` não existia. Falha do fatiamento, nenhuma
troca ou peça maior que a mesa: o projeto é gravado, o motivo aparece, a CLI sai com 1 e a GUI só avisa (decisão do
usuário). O `--check` da CLI continua opcional. A H2D agora mostra o motivo genérico do CLI (-100); causa em aberto (item 10).

**Diagnóstico:**
- `slice_check` descarta `error_string` e `warning_message` do `result.json`.
- `pipeline` só avisa quando não há trocas; `ok: False` sozinho não gera aviso.
- Sem `result.json` o erro é genérico e, na CLI, um traceback. Reproduzido com 300 mm na A1 e com
  `Bambu Lab H2D 0.4 nozzle` a 100 mm (causa não investigada). O projeto é gravado mesmo assim.
- `export` não bloqueia modelo maior que a mesa; só a prévia 3D avisa (`preview3d.fits`).

**Pontos a decidir:** peça maior que a mesa é erro ou aviso; código de saída da CLI quando a verificação
falha; ligar a verificação por padrão (na imagem sintética levou poucos segundos).

**Onde mexe:** `bambu.slice_check`, `pipeline`, `__main__`, `gui/main_window.py`.

## P1

### 4. Alturas múltiplas da camada

**Diagnóstico** (camada 0,2 mm; sobre presets já resolvidos):

| Pedido | Impresso |
|---|---|
| base 10 + relevo 0,5 | 10,6 (relevo 0,6) |
| base 2 + relevo 0,3 | 2,2 (relevo 0,2) |
| base 1,1 + relevo 0,2 | 1,2 no total |

Relevo 0,1 mm, pela linha de comando e com os presets atuais: 2 trocas para 4 cores, sinal de cor perdida.

**O quê:** ajustar base e relevo à camada do processo (a primeira pode ter altura própria) e mostrar
"1,0 mm = 5 camadas".

**Pontos a decidir:** ajustar sozinho ou avisar; mínimo de camadas de relevo para a cor cobrir a base; o que
fazer sem Bambu Studio; validar `LIMITS` também na CLI (larguras e alturas hoje não são checadas).

**Onde mexe:** `params.py`, `geometry.build_parts`, `gui/main_window.py`, `__main__`.

### 5. Conferência pelo gcode

**O quê:** após fatiar, desenhar as extrusões por filamento, comparar com as máscaras e mostrar o que sumiu
("vermelho: 3% da área não será impressa"), com destaque visual.

**Por quê:** única conferência que inclui as decisões do fatiador. O gcode traz `; Z_HEIGHT:`, `; FEATURE:`,
`T<n>` e as extrusões. Depende dos itens 1 a 3; sem o 1 o gcode nem traz `T<n>`.

**Pontos a decidir:** tolerância de área; só a camada do topo ou todas as de relevo; onde exibir (aba nova ou
sobreposta à prévia); excluir a prime tower; tratar arcos (`G2`/`G3`).

**Onde mexe:** módulo novo, `bambu.slice_check`, GUI.

### 6. Limites pelo bico real

**Diagnóstico:** `segment.LINE_MM = 0.42` é fixo, mas há presets de outros bicos.

**O quê:** usar a largura de linha do processo e avisar sobre ilhas e vãos estreitos entre cores.

**Pontos a decidir:** `segment` não conhece o preset (novo campo em `Params`? salvar no `.i2b`, AD-003);
valor sem Bambu Studio; se trocar de impressora refaz a prévia. Avaliar `classic` × `arachne` em traço fino.

**Onde mexe:** `segment.py`, `params.py`, `project.py`, GUI.

### 7. Tipo de mesa

**Diagnóstico:** o projeto sai com `curr_bed_type = Cool Plate` (gcode: `M190 S35`); na Textured PEI seria 65 °C.

**O quê:** seletor de mesa, gravado em `curr_bed_type`. Trocar o valor no 3MF para `Textured PEI Plate`
fatiou sem erro.

**Pontos a decidir:** padrão por impressora (há chave no preset?); lista de mesas válidas; salvar no `.i2b`
(AD-003) e nas preferências.

**Onde mexe:** `bambu.patch_project`, `pipeline.BambuChoice`, `project.py`, GUI, CLI.

## P2

### 8. Filamento por cor e presets do usuário

**O quê:** escolher o preset de cada filamento e oferecer também os presets do usuário
(`BambuStudio/user/<id>/filament/`, no Linux Flatpak sob `~/.var/app/...`).

**Por quê:** hoje todas as cores usam o mesmo preset. A regra "o CLI só carrega presets de sistema" pode cair
com o item 1 (JSON já resolvido); precisa de teste.

**Pontos a decidir:** vários `<id>` de usuário; mistura de materiais (temperaturas incompatíveis); sugerir
filamento pela cor mais próxima; `patch_project` expande chaves supondo um preset só.

**Onde mexe:** `bambu.py`, `pipeline.BambuChoice`, `gui/color_row.py`, `project.py`.

### 9. 3MF genérico sem Bambu Studio

**O quê:** gravar um 3MF padrão com `basematerials` quando só há STLs.

**Pontos a decidir:** programas alvo a testar (OrcaSlicer, PrusaSlicer, visualizadores); um arquivo à parte ou
em vez dos STLs. Não reaproveitar o 3MF mínimo sem cuidado: a GUI ignora a configuração dele.

**Onde mexe:** `export3mf.py`, `pipeline.py`.

### 10. Dois bicos e áreas excluídas

**Diagnóstico:** H2D, H2D Pro, H2C e X2D têm dois bicos com `extruder_printable_area` distintas; P1P, P1S e X1
têm `bed_exclude_area` (canto 18×28 mm). `PresetDB.bed` só lê `printable_area` e `printable_height`.

**Pontos a decidir:** quais impressoras suportar e como testar; investigar a falha da H2D (item 3);
`filament_map` para dois bicos; formato da matriz de purga.

**Onde mexe:** `bambu.PresetDB`, `bambu.patch_project`, `preview3d.py`.

## P3

### 11. Purga por par de cores

**Diagnóstico:** `flush_volumes_matrix` usa 280 mm³ em qualquer troca.

**O quê:** calcular por par (escuro → claro purga mais). Invariante: N×N, diagonal zero, vetor 2N.

**Pontos a decidir:** fórmula e limites (comparar com o cálculo automático do Bambu Studio); `flush_into_infill`.

### 12. Resumo após gerar

**O quê:** gramas por cor, purga, trocas e tempo, a partir do `result.json` e do cabeçalho do gcode. Depende
do item 1 (hoje a densidade é 0). **A decidir:** exibir custo (`filament_cost`).

### 13. Modo face para baixo

**O quê:** imagem espelhada na primeira camada, topo liso com a textura da mesa e cores embutidas na base.
**A decidir:** se vale a pena; muda `geometry.build_parts` (a base precisa de recortes), prévias e `.i2b`.

## Ordem sugerida

1. **PR 1:** 1 + 2 + 3 (juntos: só o 1 faz o `--check` falhar na A1 com 4 cores e na A1 mini).
2. **PR 2:** 4 + 7.
3. **PR 3:** 5.
4. Depois 8, 11, 6; os demais conforme a necessidade.

## Como reproduzir

Comparar o projeto com o preset resolvido (na raiz do repositório, `python <script> <projeto.3mf>` com
`PYTHONPATH=.`). Com o Flatpak, gere em uma pasta sob o home:

```python
import json, sys, zipfile
from img2bambu import bambu

db = bambu.PresetDB()
d = json.loads(zipfile.ZipFile(sys.argv[1]).read("Metadata/project_settings.config"))
m = "Bambu Lab A1 0.4 nozzle"
p, f = db.defaults(m)
first = lambda v: str((v if isinstance(v, list) else [v])[:1])
for kind, name in (("machine", m), ("process", p), ("filament", f)):
    for k, v in db.resolve(kind, name).items():
        if k in d and first(d[k]) != first(v):
            print(kind, k, "preset =", str(v)[:60], "| projeto =", str(d[k])[:60])
```

Essa saída inclui alguns metadados (`name`, `from`, `inherits`), que não contam como diferença.

Protótipo do item 1: substituir `bambu.PresetDB.path` por esta função antes de chamar `__main__.main`:

```python
def path(self, kind, name):
    d = dict(self.resolve(kind, name), name=name, type=kind, instantiation="true")
    d["from"] = "system"
    d.pop("inherits", None)
    d.pop("include", None)
    out = os.path.join(FOLDER_UNDER_HOME, kind + ".json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(d, fh)
    return out
```

Erro do fatiamento: ler `error_string` do `result.json` após `bambu.slice_check(exe, projeto, pasta)`.
