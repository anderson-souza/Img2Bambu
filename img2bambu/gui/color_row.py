from PySide6.QtWidgets import QCheckBox, QComboBox, QHBoxLayout, QLabel, QPushButton, QRadioButton, QWidget

from ..params import hex_color


class ColorRow(QWidget):
    def __init__(self, idx):
        super().__init__()
        self.idx = idx
        lay = QHBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0)
        self.sample = QPushButton(); self.sample.setFixedSize(42, 24)
        self.sample.setToolTip("Cor na imagem: define quais pixels vão para esta cor (clique para alterar)")
        self.drop = QPushButton("💧"); self.drop.setFixedSize(28, 24); self.drop.setCheckable(True)
        self.drop.setToolTip("Conta-gotas: clique e depois clique na imagem (Original ou Prévia) "
                             "para definir a cor na imagem (Esc cancela)")
        self.swatch = QPushButton(); self.swatch.setFixedSize(42, 24)
        self.swatch.setToolTip("Cor do filamento (clique para alterar)")
        self.base = QRadioButton("Base")
        self.base.setToolTip("Cor da base de trás (silhueta inteira)")
        self.streak = QCheckBox("Filtro reflexo")
        self.streak.setToolTip("Remove listras finas desta cor (reflexos de brilho)")
        self.outline = QCheckBox("Contorno")
        self.outline.setToolTip("Mantém os traços finos desta cor, com largura imprimível (mínimo 0,42 mm)")
        self.merge = QComboBox(); self.merge.setToolTip("Mesclar esta cor em outra")
        self.pct = QLabel()
        for w in (self.drop, self.sample, QLabel("→"), self.swatch, self.base, self.streak, self.outline,
                  self.merge, self.pct):
            lay.addWidget(w)
        lay.addStretch()

    def refresh(self, pal):
        c = pal.colors[self.idx]
        self.swatch.setStyleSheet(f"background:{hex_color(c)}; border:1px solid #555;")
        self.swatch.setText("")
        self.sample.setStyleSheet(f"background:{hex_color(pal.samples[self.idx])}; border:1px solid #555;")
        self.base.setChecked(pal.base_index == self.idx)
        self.streak.blockSignals(True); self.streak.setChecked(self.idx in pal.streak); self.streak.blockSignals(False)
        self.outline.blockSignals(True); self.outline.setChecked(self.idx in pal.outline)
        self.outline.blockSignals(False)
        self.merge.blockSignals(True)
        self.merge.clear(); self.merge.addItem("—", -1)
        for j, cj in enumerate(pal.colors):
            if j != self.idx:
                self.merge.addItem(f"→ {hex_color(cj)}", j)
        target = pal.merges.get(self.idx, -1)
        self.merge.setCurrentIndex(max(0, self.merge.findData(target)))
        self.merge.blockSignals(False)
        merged = pal.resolve(self.idx) != self.idx
        for w in (self.base, self.streak, self.outline):
            w.setEnabled(not merged)
