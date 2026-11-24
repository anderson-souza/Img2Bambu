# Project file Context

**Gathered:** 2026-11-23
**Spec:** `.specs/features/project-file/spec.md`
**Status:** Ready for design

## Feature Boundary

Save the image and everything set in the window to one file, and open it later or on another computer.

Request: "vamos planejar uma feature que seja possível salvar os parâmetros de um projeto, como a imagem usada, as cores, configurações da impressora, etc. Quero que seja possível abrir um arquivo e carregar tudo o que eu havia modificado na interface, para ir iterando sobre as mudanças e até poder transferir esse arquivo para outras pessoas"

## Implementation Decisions

Each line quotes the option the user chose, 2026-11-23.

- Place of the actions: "Menu Arquivo" - Abrir projeto (Ctrl+O), Salvar (Ctrl+S), Salvar como (Ctrl+Shift+S)
- Unsaved changes: "Perguntar, só com projeto" - name and `*` in the title; Salvar/Descartar/Cancelar only when a project is open or was saved
- Another image: "Vira projeto novo" - settings stay, the next Salvar asks for a name
- Missing presets: "Abrir com padrão e avisar" - saving over writes the substitute
- Output folder: "Não salvar" - becomes `img2bambu_saida` beside the project; the output name is saved; the executable path stays out
- Colors: "Idênticas, sem redetectar" - the file also holds the detection result
- Extras: "Nenhum"
- Extension: ".i2b" - ZIP with the original image and the settings

## Deferred Ideas

Offered and left out: opening by command line / file association, generating by CLI, recent projects, drag and drop.
