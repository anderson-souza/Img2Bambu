# Img2Bambu

Imagem (PNG/JPG) → projeto 3MF multicor para Bambu Studio: base com a silhueta (padrão 10 mm) na cor dominante da borda + demais cores em relevo (padrão 1 mm). Cada cor vira uma parte já atribuída ao filamento 1..N.

## Usar
- Executável: `dist\Img2Bambu\Img2Bambu.exe` (copie a pasta inteira `Img2Bambu`).
- Fonte: `pip install -r requirements.txt` e `python app.py`.
- Linha de comando: `python -m img2bambu imagem.png --width 150 --colors 3 --check`
  (no exe: `Img2Bambu.exe --cli imagem.png ...`, saída em arquivo via variável `IMG2BAMBU_LOG`).

Fluxo na interface: Abrir imagem → ajustar nº de cores / base / mesclar / filtro de reflexo → dimensões → impressora, processo e filamento → **Gerar 3MF** → **Abrir no Bambu Studio**.

### Projetos
**Arquivo → Salvar projeto** (Ctrl+S) grava um `.i2b` com a imagem original, as cores e mesclagens, as dimensões, os presets escolhidos e o nome do arquivo gerado. **Arquivo → Abrir projeto…** (Ctrl+O) traz tudo de volta, com as cores idênticas, também em outro computador.

- A pasta de saída e o executável do Bambu Studio não vão no arquivo; ao abrir, a saída vira `img2bambu_saida` ao lado do projeto.
- Presets que não existem no computador são trocados pelo padrão, com aviso. Sem nenhum preset instalado, os nomes originais são mantidos.
- A imagem vai como foi aberta, com os metadados (uma foto pode conter a localização).

## Requisitos
Bambu Studio instalado (usa o CLI dele e os presets de sistema em `%APPDATA%\BambuStudio\system\BBL`). Sem ele, o app gera só os STLs por cor (importe todos juntos e responda "Sim" para objeto único com várias partes).

### Linux
Rode pela fonte (`python app.py`). O Bambu Studio é procurado nesta ordem: `bambu-studio` no `PATH`, Flatpak do usuário, Flatpak do sistema (`com.bambulab.BambuStudio`). AppImage e outros: escolha o arquivo em "Executável". Os presets vêm de `~/.var/app/com.bambulab.BambuStudio/config/BambuStudio/system/BBL` ou `~/.config/BambuStudio/system/BBL`; abra o Bambu Studio uma vez para criá-los.

Com o Flatpak, a pasta de saída precisa ser visível para ele (a pasta pessoal serve, `/tmp` não); senão o app a recusa antes de gerar.

## Notas técnicas
- O 3MF final é exportado pelo próprio CLI do Bambu Studio e depois corrigido (`bambu.patch_project`): o CLI deixa os parâmetros por filamento com 1 valor, o que faz a GUI rejeitar com "invalid config".
- O código de saída do CLI não é confiável (crasha ao sair mesmo com sucesso); o app verifica os arquivos gerados.

## Testes
`python -m pytest` (o teste `slow` fatia a abelha via CLI e exige Bambu Studio).
`python tests/gui_smoke.py <imagem> <pasta_saida> <screenshot.png>` dirige a GUI sem diálogos.

## Build
`python -m PyInstaller --noconfirm img2bambu.spec`
