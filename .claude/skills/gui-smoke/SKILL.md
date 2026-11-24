---
name: gui-smoke
description: Use when a change touches the PySide6 GUI (img2bambu/gui/, main_window.py, worker.py, view3d) or anything the GUI drives, and you need to confirm the real window still analyzes, previews and exports — not just that unit tests pass. Runs tests/gui_smoke.py headless and checks its log and screenshot.
---

# GUI smoke check

Drives `MainWindow` end to end offscreen: load image → analyze → preview → 3D tab → generate. Run it after the unit tests pass, never instead of them.

## 1. Pick an image

- Use the image the user gave you, if any.
- Otherwise make the synthetic sage/green disc the GUI tests use (3 colors, deterministic). Write it to the scratchpad, never into the repo:

```bash
python -c "import sys; sys.path.insert(0, 'tests'); from test_core import sage_green; from PIL import Image; Image.fromarray(sage_green()).save(sys.argv[1])" <scratch>/sg.png
```

## 2. Run

```bash
python tests/gui_smoke.py <image> <home>/.cache/i2b-smoke <scratch>/shot.png
```

The script sets `QT_QPA_PLATFORM=offscreen` itself. It polls every 100 ms and prints `TIMEOUT at step N` after 60 s.

## 3. Judge the result

Read the output, not only the exit code:

| Output | Meaning |
|---|---|
| `palette [...]` line with the expected number of swatches | analysis + color preview worked |
| `3D part_count N` with N = active colors | geometry built for the 3D tab |
| `STL: ...` line per part, files present in `<home>/.cache/i2b-smoke` | export ran |
| `TIMEOUT at step N` | stuck: 0 = presets never loaded, 1 = preview never finished ("Prévia pronta"), 2 = 3D never built, 3 = export never finished |
| Python traceback | real failure — report it with the trace |

Exit codes: `0` = Bambu project (3MF) written; `1` = flow finished but no project.

- hazard: without Bambu Studio installed (e.g. CI) exit is **1** even when everything worked; the log says `Projeto Bambu não gerado (Bambu Studio ausente ou desativado)`. That is expected — judge by the STL lines. With Bambu Studio installed (Windows or Linux), exit 1 is a failure.
- hazard: offscreen Qt cannot render Qt Quick 3D. Warnings about `QRhi` / "View3D item is not going to display anything" are expected, and the 3D tab is blank in the screenshot. `part_count` is the evidence for 3D, not the picture.

## 4. Look at the screenshot

Read `<scratch>/shot.png` and check what the change was about: the right panel (palette rows, Base radio, Filtro reflexo, dimensions), status bar `Concluído.`, Portuguese labels intact. Say what you checked.

## 5. Report

State: image used, exit code, the palette / part_count / STL evidence, what the screenshot showed, and anything skipped (e.g. no Bambu Studio → 3MF and slice check not exercised). Do not report the GUI as verified if any step timed out.
