# Review: Linux support (0876df7..e9e10d7 + uncommitted plan.md line)

## Verdict

All 14 criteria are implemented. The main problem is outside the letter of criterion 9 but inside the request: **with the settings currently saved on this machine, `python app.py` does not use Bambu Studio** (problem 1). Not verified: Windows, and the CI jobs (no run was looked up).

## Problems

### 1. High - an invalid saved "Executável" beats detection; this user's GUI gives STLs only
`main_window.py:266` is `settings.value("exe") or find_exe()`. The user's `~/.config/img2bambu/img2bambu.conf` (read, not changed) holds `exe=~/.local/share/flatpak/exports/bin/com.bambulab.BambuStudio`. The literal `~` is never expanded, so `os.path.isfile` is false in `generate`.

Evidence: same value put in a throwaway settings file, real GUI export: field shows `~/.local/...`, log `⚠ Projeto Bambu não gerado (Bambu Studio ausente ou desativado): apenas STLs.`, `last_project` empty.

I do not know who wrote the value; the file last changed at 19:17, during this session, and another session's pytest was running around then. Criterion 9 only covers "no saved exe", and the line is older than this branch, but item 1 of the request is not met here. Possible fix: fall back to `find_exe()` when the saved path is not a file, and/or expand `~`. Any stale path hits the same case.

### 2. Medium - CLI crashes with `KeyError: None` if Bambu Studio is found but its presets are not
For example a Flatpak installed and never opened (I assume it creates `system/BBL` on first run). Stub: `presets_root` -> missing folder, then the CLI: 3 STLs and the preview are written, then a `KeyError: None` traceback. The GUI handles this case with a message. The code is older than this branch, but Linux detection now reaches it. The README does not say Bambu Studio must be opened once.

### 3. Low - Flatpak behind a wrapper script is not recognized
`is_flatpak` compares the resolved file name. A `bambu-studio` script on `PATH` doing `exec flatpak run com.bambulab.BambuStudio "$@"` (throwaway) skips the folder check: with the output in `/tmp`, STLs and the 3mf are written and the run does not finish the slice check. Symlinks to the launcher are recognized. Criterion 6 says "the exe is the Flatpak", so this is arguable.

### 4. Low - probe errors are raw English or misleading
- `flatpak` not on `PATH`: `FileNotFoundError: ... 'flatpak'` (reproduced).
- By reading: a probe over 60 s gives a raw `TimeoutExpired`, and any other `flatpak run` failure is reported as "não acessa a pasta".

### 5. Low - test gaps
20 mutations on a scratchpad copy, run against the two new test files: 15 killed, 5 survived.
- `FLATPAK_SYSTEM_BIN` set to `/wrong`: tests replace the constant (criterion 1).
- Cleanup enabled on Windows: the exclusion "Cleaning work folders on Windows" is unprotected.
- Slice `workdir` moved out of the work folder: no Linux test uses `check=True` (criteria 4/5); by reading, on Linux the slice would then run in `/tmp`.
- Probe command negated (`! -r`): only the first 4 arguments are asserted (criterion 6).
- `realpath` dropped: the symlinked-launcher case is untested.

### 6. Low - stale docs
`CLAUDE.md:7` still says "Windows-only in practice" and `:47` gives only `%APPDATA%`. Not asked by a criterion.

### 7. Note - the test suite writes to the user's settings
The saved `dir` is `/tmp/pytest-of-.../test_new_image_starts_fresh0`; that test (`test_gui_palette.py:131`, not in this diff) goes through the real `QSettings`. `test_refused_folder...` guards its own writes.

### 8. Note - a refused folder that did not exist is left created, empty
`makedirs` runs before the probe. Criterion 6 forbids only STL, preview and project, so it complies.

## Request

| Sentence | Result |
| --- | --- |
| Linux equivalent of the executable; found with presets and no env vars (1) | CLI yes; GUI yes with no saved exe, **no with the user's saved settings** (problem 1) |
| Separate worktree | yes |
| Project generated and sliced with the Flatpak (2) | yes: `ok: True`, 5 changes in CLI; 5 changes in GUI; relative `--out` also works |
| Picker and folder button (3) | yes with stubbed dialog/desktop calls; native dialogs not clicked |
| Windows unchanged, tests on detection (4) | by reading, yes; "Abrir pasta" now uses `QDesktopServices` instead of `os.startfile`, per criterion 11. Not run on Windows |

## Criteria and their tests

| # | Works | Would its test fail if the rule were wrong? |
| --- | --- | --- |
| 1 | yes, real (user Flatpak); order by test | order yes; system path no (problem 5) |
| 2 | yes, real (60 printers in the GUI) | yes |
| 3 | by reading | temp folder yes; `ProgramFiles` and `APPDATA` asserted; other folder candidates, registry and `PATH` not covered |
| 4 | yes: `~/.cache/img2bambu` empty after real exports and failures | location and cleanup yes; slice folder no |
| 5 | yes, real `--check` run | no test for it; the `slow` test was skipped here |
| 6 | yes: `/tmp` and a symlink to it refused; home and `/media` (manifest grant) accepted; `flatpak override` not exercised | refusal, message, timing, no leftovers yes; probe arguments no |
| 7 | yes | yes |
| 8 | yes, real sandbox and GUI: message shown, retry succeeded | message and re-enable yes; a second attempt is not made |
| 9 | yes, real with throwaway settings | field yes; printer list uses stubbed presets |
| 10 | by test and reading | Linux filter yes (mutated); Windows filter asserted |
| 11 | yes, `openUrl` stubbed | yes |
| 12 | yes, `Popen` stubbed (launcher + project path) | yes |
| 13 | by reading; not run | n/a |
| 14 | yes | n/a |

## How it was checked

- `pytest`: 158 passed, 1 skipped (slow). `ruff check .`: clean. There are no captures to compare.
- `gui_smoke.py` and a driver script ran offscreen with the real Flatpak CLI. Qt Quick 3D does not draw offscreen; screenshots were saved but not inspected.
- Settings were isolated with `QSettings.setPath` in a scratchpad launcher, because the session guard refused a command setting `XDG_CONFIG_HOME`.
- Stubs: `QMessageBox.critical`, `Popen`, `openUrl`, `presets_root` (problem 2), `PATH` (problem 4), wrapper script (problem 3).
- Outside the repository: two mutation runs left one empty folder each in `~/.cache/img2bambu`, removed with `rmdir`; real exports ran the Flatpak CLI, which may write its own config. `.specs/_rv` (my temporary files) was removed.
- The open Bambu Studio window and the user's settings were not touched. No code changed, no commit.
