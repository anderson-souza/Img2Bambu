# Request

faça a leitura do arquivo @.specs/melhorias-cores.md e vamos especificar a melhoria 4

## Answers (2026-11-22)

- Control: new "Filamentos" field (spin 0–8 under "Nº de cores"; 0 = "desligado", default, behaves as today; N ≥ 2 merges closest colors until N remain; N ≥ Nº de cores merges nothing).
- Criterion: LAB distance only (merge two closest groups repeatedly; centroid = area-weighted mean).
- Survivor: larger area survives; base may be merged (base moves to surviving row, like manual merge).
- Edited rows: never merged away (can absorb others). Auto-merge runs only on (re)analysis; manual "—" changes stand until next re-analysis. More edited rows than Filamentos → stop early with a message.
- CLI: `--filaments N` (0–8, default 0, same rule; out of range → argparse exit 2); CLI prints the merges.
- Feedback: existing "—" combos show the merges, plus log line "Mesclagem automática: 8 cores → 4 filamentos."
- Persistence: no (like Nº de cores and Suavização).
