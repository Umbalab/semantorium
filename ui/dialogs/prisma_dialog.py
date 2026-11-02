#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Diálogo interativo do fluxo PRISMA: contagens, pré-visualização e exportação."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QGridLayout, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)

from core import prisma

try:  # QtSvgWidgets existe em todas as instalações completas do PySide6
    from PySide6.QtSvgWidgets import QSvgWidget
except Exception:  # pragma: no cover - fallback defensivo
    QSvgWidget = None


class PrismaDialog(QDialog):
    def __init__(self, counts: dict = None, title: str = "Fluxo PRISMA 2020",
                 subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Diagrama PRISMA")
        self.resize(900, 760)
        self._title = title
        self._subtitle = subtitle
        self._svg = ""
        self._spins = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        hint = QLabel(
            "Ajuste as contagens do fluxo: o diagrama e os avisos de "
            "consistência são atualizados na hora. Exporte em SVG (vetorial, "
            "editável) ou PNG (pronto para inserir no relatório)."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#5b6673;")
        layout.addWidget(hint)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        values = prisma.normalize_counts(counts)
        for index, (key, label) in enumerate(prisma.COUNT_LABELS):
            spin = QSpinBox()
            spin.setRange(0, 10_000_000)
            spin.setValue(int(values.get(key, 0)))
            spin.valueChanged.connect(self._refresh)
            grid.addWidget(QLabel(label + ":"), index // 2, (index % 2) * 2)
            grid.addWidget(spin, index // 2, (index % 2) * 2 + 1)
            self._spins[key] = spin
        layout.addLayout(grid)

        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet("color:#1c53b8; font-weight:600;")
        layout.addWidget(self.summary_label)

        self.warning_label = QLabel("")
        self.warning_label.setWordWrap(True)
        self.warning_label.setStyleSheet("color:#b45309;")
        layout.addWidget(self.warning_label)

        if QSvgWidget is not None:
            self.preview = QSvgWidget()
            self.preview.setMinimumSize(840, 690)
            scroll = QScrollArea()
            scroll.setWidgetResizable(False)
            scroll.setAlignment(Qt.AlignCenter)
            scroll.setWidget(self.preview)
            layout.addWidget(scroll, 1)
        else:  # pragma: no cover
            self.preview = None
            layout.addStretch(1)

        buttons = QHBoxLayout()
        self.btn_svg = QPushButton("Salvar SVG…")
        self.btn_svg.clicked.connect(self.save_svg)
        buttons.addWidget(self.btn_svg)
        self.btn_png = QPushButton("Salvar PNG…")
        self.btn_png.clicked.connect(self.save_png)
        buttons.addWidget(self.btn_png)
        buttons.addStretch()
        close = QPushButton("Fechar")
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        layout.addLayout(buttons)

        self._refresh()

    # ------------------------------------------------------------------
    def counts(self) -> dict:
        return {key: spin.value() for key, spin in self._spins.items()}

    def svg(self) -> str:
        return prisma.to_svg(self.counts(), self._title, self._subtitle)

    def _refresh(self) -> None:
        data = prisma.flow_counts(self.counts())
        self._svg = prisma.to_svg(self.counts(), self._title, self._subtitle)
        if self.preview is not None:
            from ui import theme
            self.preview.load(
                theme.adapt_svg(self._svg).encode("utf-8")
            )
            self.preview.setFixedSize(840, 690)
        values = data["counts"]
        self.summary_label.setText(
            f"{values['identified']} identificados → "
            f"{values['screened']} triados → "
            f"{data['eligible']} elegíveis → "
            f"{values['included']} incluídos"
        )
        self.warning_label.setText(
            "\n".join(f"⚠ {warning}" for warning in data["warnings"])
        )
        self.warning_label.setVisible(bool(data["warnings"]))

    # ------------------------------------------------------------------
    def save_svg(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self, "Salvar diagrama PRISMA (SVG)",
            "prisma.svg", "SVG (*.svg)",
        )
        if not filename:
            return
        if Path(filename).suffix.lower() != ".svg":
            filename = str(Path(filename).with_suffix(".svg"))
        try:
            Path(filename).write_text(self.svg(), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Erro ao salvar", str(exc))
            return
        QMessageBox.information(
            self, "Diagrama PRISMA", f"SVG salvo:\n{filename}"
        )

    def save_png(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self, "Salvar diagrama PRISMA (PNG)",
            "prisma.png", "PNG (*.png)",
        )
        if not filename:
            return
        if Path(filename).suffix.lower() != ".png":
            filename = str(Path(filename).with_suffix(".png"))
        try:
            from ui.prisma_export import svg_to_png
            svg_to_png(self.svg(), filename, scale=2.0)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Erro ao salvar", str(exc))
            return
        QMessageBox.information(
            self, "Diagrama PRISMA", f"PNG salvo:\n{filename}"
        )
