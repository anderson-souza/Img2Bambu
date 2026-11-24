# Project File Specification

**Approved**: 2026-11-23 - user: "aprovado, podemos seguir para o design"

## Problem Statement

Everything adjusted in the window is lost when it closes: colors, merges, dimensions, printer presets.
The user cannot return to a piece to iterate on it, nor hand the work to someone else.

## Goals

- [ ] A project saved and reopened produces the same masks, pixel for pixel, and the same control values
- [ ] One `.i2b` file opens on another computer without the original image

## Out of Scope

| Feature | Reason |
| --- | --- |
| Opening by command line, file association, CLI export, recent projects, drag and drop | user chose "Nenhum" for extras |
| Output folder and Bambu Studio executable path in the file | user chose; they belong to each computer |
| Undo history, tab, zoom, 3D camera and log in the file | they are not settings of the project |
| Autosave and crash recovery | not asked |
| Embedding Bambu Studio preset contents | only names are stored; only system presets are offered by the app |

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| Place of the actions | menu Arquivo | user chose it | y |
| Unsaved changes | ask only with a project open | user chose it | y |
| Another image | detaches from the project file | user chose it | y |
| Missing presets | default in their place, with a warning | user chose it | y |
| Output folder | not saved | user chose it | y |
| Colors on opening | identical, no detection | user chose it | y |
| Extension | `.i2b` | user chose it | y |
| No presets installed at all | the file's preset names are kept on the next save | there is no substitute to write; a person without Bambu Studio must not erase the sender's choice | y |
| Substituted preset | does not count as an unsaved change | opening and closing a received file should not ask anything | y |
| Undoing back to the saved values | removes the `*` | the mark compares values with the last save | y |
| Saving during color detection | refused with a message | palette and values on screen do not match until it ends | y |
| Image bytes | original file as loaded, metadata included | no quality loss; a photo's EXIF travels with it | y |
| `upsample` and `simplify_mm` | not saved | no control in the window changes them | y |

**Open questions:** none - all resolved or logged above.

---

## User Stories

### P1: Save and reopen a project ⭐ MVP

**User Story**: As a user, I want to save my work to a file and reopen it so that I can iterate on it.

**Why P1**: It is the request.

**Acceptance Criteria**:

1. The window SHALL have a menu "Arquivo" with "Abrir projeto…" (Ctrl+O), "Salvar projeto" (Ctrl+S) and "Salvar projeto como…" (Ctrl+Shift+S)
2. WHEN the user saves and then opens the project in a new window THEN the system SHALL restore these values: Fundo, Tolerância do fundo, Nº de cores, Filamentos, Suavização, Detalhe mínimo, Filtro reflexo (raio), Proteger traços finos, Largura, Espessura da base, Relevo das cores, Impressora, Processo, Filamento, Verificar fatiando, Nome do arquivo
3. WHEN a project is opened THEN the system SHALL restore each color row's cor na imagem, cor do filamento, base, Filtro reflexo, Contorno, mesclagem and edited mark
4. WHEN a project is opened THEN the system SHALL produce the same masks, pixel for pixel, as the session that saved it
5. WHEN a project is opened THEN the system SHALL NOT run color detection
   - also with Suavização 5
6. WHEN the user edits a row's "cor na imagem" after opening a project THEN the masks SHALL equal those of the same edit in the session that saved it
   - also with Suavização 5
7. WHEN the user changes Nº de cores after opening a project THEN the edited rows SHALL be carried to the new detection as in the session that saved it
8. WHEN the user uses "Salvar projeto" with a project file associated THEN the system SHALL overwrite that file without asking for a name
9. WHEN the user uses "Salvar projeto" with no project file associated THEN the system SHALL ask for a name, suggesting `<image name>.i2b` in the image's folder
10. WHEN the user uses "Salvar projeto como…" THEN the system SHALL ask for a name and associate the window with the new file
11. IF the chosen name lacks `.i2b` THEN the system SHALL append it
12. IF the name with the appended `.i2b` already exists THEN the system SHALL ask before overwriting it
13. WHEN a project is opened THEN "Pasta de saída" SHALL become `img2bambu_saida` beside the project file
14. WHEN a project is opened THEN Ctrl+Z SHALL show "Nada para desfazer."
15. WHEN a project is opened THEN the previous image's running detection, preview and 3D results SHALL be discarded
16. WHEN a project is opened THEN "Original", "Cores (prévia)", "3D" and the image name SHALL show the project's image
17. IF there is no image THEN saving SHALL show "Abra uma imagem primeiro." and write nothing
18. WHILE colors are being detected, WHEN the user saves the system SHALL show "Aguarde a detecção de cores terminar para salvar." in the status bar and write nothing
19. IF the detection of the current image failed and none succeeded for it THEN saving SHALL show "As cores desta imagem não foram detectadas." and write nothing
20. WHEN a save succeeds THEN the status bar SHALL show "Projeto salvo: <file name>."

**Independent Test**: Adjust every control, save, close, reopen: controls and preview are the same.

---

### P1: Transfer the project to another person ⭐ MVP

**User Story**: As a user, I want one self-contained file so that another person can open my work.

**Why P1**: It is the request.

**Acceptance Criteria**:

1. The project file SHALL contain the original image's bytes as they were when the image was loaded
   - the image on disk was edited or deleted before saving → the loaded bytes are saved
2. WHEN a project is opened and the original image does not exist on disk THEN it SHALL open and save normally
3. The project file SHALL NOT contain the image's folder, the output folder or the executable path
4. IF Impressora is not installed THEN the system SHALL select "Bambu Lab A1 0.4 nozzle", or the first printer when that one is missing
5. IF Processo or Filamento is not available for the selected printer THEN the system SHALL select that printer's default
6. IF any preset was substituted THEN the system SHALL name each missing preset and its substitute in one warning dialog
7. IF any preset was substituted THEN the system SHALL write one log line per substitution
8. IF a substituted project is saved THEN the file SHALL hold the substitutes
9. WHERE no presets are installed the system SHALL keep the file's preset names when it saves
10. WHERE no presets are installed the system SHALL name the file's presets as missing in one warning dialog
11. IF the project was saved with no printer selected THEN opening SHALL keep the current selection without a warning
12. WHEN a project is opened THEN the system SHALL NOT change the presets, check option or executable remembered in `QSettings`

**Independent Test**: Delete the image, use another preset folder and open the file: the work loads and the warning names the missing presets.

---

### P1: Bad files and failures never cost work ⭐ MVP

**User Story**: As a user, I want failures to be visible so that I do not lose work.

**Why P1**: Files come from other people and other versions.

**Acceptance Criteria**:

1. IF the file is not a project, is truncated, or lacks a required part THEN opening SHALL show the error dialog "Não foi possível abrir o projeto:" with the cause
2. IF the file's format version is newer than the app's THEN opening SHALL show "Este projeto foi salvo por uma versão mais nova do Img2Bambu."
3. IF a value has the wrong type or is outside its control's range, or a color row reference does not exist THEN opening SHALL fail as in criterion 1
4. IF the stored detection does not match the stored image's dimensions THEN opening SHALL fail as in criterion 1
5. IF opening fails THEN every control, the image, the palette, the undo steps and the associated file SHALL stay as they were
6. IF a save fails THEN the existing file SHALL stay intact
7. IF a save fails THEN the system SHALL show the error dialog "Não foi possível salvar o projeto:" with the cause
8. IF a file of the current format lacks a setting THEN opening SHALL use that setting's default and write its name in the log
9. The system SHALL read the project file without executing or extracting its content to disk

**Independent Test**: Open a truncated file with work on screen: an error appears and nothing changes.

---

### P2: Unsaved changes are visible and guarded

**User Story**: As a user, I want to know what is not saved so that I do not lose it by accident.

**Why P2**: Saving works without it.

**Acceptance Criteria**:

1. WHILE a project file is associated the window title SHALL be `<file name> — Img2Bambu`
2. WHILE any value the file holds differs from the last save or opening the title SHALL be `<file name>* — Img2Bambu`
3. WHEN the user undoes back to the saved values THEN the `*` SHALL disappear
4. WHILE no project file is associated the title SHALL be today's and no question SHALL be asked
5. WHILE the project has unsaved changes, WHEN the user closes the window, opens a project or opens an image the system SHALL ask with "Salvar", "Descartar" and "Cancelar"
6. WHEN the user chooses "Salvar" THEN the system SHALL save and continue with the action
7. WHEN the user chooses "Descartar" THEN the system SHALL continue without saving
8. WHEN the user chooses "Cancelar" THEN the system SHALL abandon the action and change nothing
9. IF "Salvar" in that question does not save THEN the system SHALL abandon the action
10. IF the user cancels the file dialog, or the file fails to open, after "Descartar" THEN the current work and its `*` SHALL stay
11. WHEN another image is opened with a project associated THEN the window SHALL lose the association and keep the control values as today
12. WHEN only the output folder, the executable, the tab or the zoom changes THEN the `*` SHALL NOT appear

**Independent Test**: Open a project, change Largura, close: the question appears; undo, close: it does not.

---

## Edge Cases

- WHEN the project already open is opened again THEN the system SHALL load the values of the file
- IF the project file was deleted while open THEN "Salvar projeto" SHALL recreate it
- WHEN an export is running and a project is opened THEN the export SHALL finish with the values it started with

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| --- | --- | --- | --- |
| PROJ-01 | P1: Save and reopen a project | Tasks | In Tasks |
| PROJ-02 | P1: Transfer the project to another person | Tasks | In Tasks |
| PROJ-03 | P1: Bad files and failures never cost work | Tasks | In Tasks |
| PROJ-04 | P2: Unsaved changes are visible and guarded | Tasks | In Tasks |
| PROJ-05 | Edge Cases | Tasks | In Tasks |

**Dimensions:** validation, failure and external dependency → stories 2 and 3; state transitions and concurrency → P1 saving during detection, P2 guards; idempotency → Edge Cases; data lifecycle → format version; auth N/A because the app is local; observability → log lines for substitutions and defaults.

**Coverage:** 5 total, 5 mapped to tasks, 0 unmapped

## Sources

- User request and answers, `context.md`

## Success Criteria

- [ ] Reopened masks equal the saved ones pixel for pixel, with and without Suavização
- [ ] A file opens with the original image deleted and with other presets installed
