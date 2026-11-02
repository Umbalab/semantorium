#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Painel recolhível de explicações detalhadas de uma aba."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QSizePolicy, QTextBrowser, QToolButton, QVBoxLayout, QWidget,
)

from core import explanations


class HelpPanel(QWidget):
    """Mostra o guia da aba/sub-aba e pode ser recolhido pelo usuário.

    O texto vem de :mod:`core.explanations`, a mesma fonte usada no relatório
    exportado, para que a interface e o arquivo final nunca divirjam.
    """

    def __init__(self, guide_key: str, title: str = "",
                 parent=None, expanded: bool = False,
                 max_height: int = 210):
        super().__init__(parent)
        self.guide_key = guide_key
        self._expanded = bool(expanded)
        self.setObjectName("HelpPanel")
        self.setStyleSheet(
            "#HelpPanel { background:#f4f8ff; border:1px solid #d6e2f7;"
            " border-radius:8px; }"
        )
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 8)
        layout.setSpacing(4)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        self.toggle = QToolButton()
        self.toggle.setObjectName("HelpToggle")
        self.toggle.setCheckable(True)
        self.toggle.setChecked(self._expanded)
        self.toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle.setArrowType(
            Qt.DownArrow if self._expanded else Qt.RightArrow
        )
        self.toggle.setStyleSheet(
            "QToolButton { border:none; color:#1c53b8; font-weight:600;"
            " background:transparent; padding:2px 0; }"
        )
        header.addWidget(self.toggle)
        header.addStretch()
        layout.addLayout(header)

        self.browser = QTextBrowser()
        self.browser.setObjectName("HelpBrowser")
        self.browser.setOpenExternalLinks(False)
        self.browser.setFrameShape(QTextBrowser.NoFrame)
        self.browser.setStyleSheet(
            "QTextBrowser { background:transparent; border:none;"
            " color:#33404f; font-size:12px; }"
        )
        self.browser.setMaximumHeight(max_height)
        self.browser.setMinimumHeight(60)
        layout.addWidget(self.browser)

        label = title or (explanations.guide_title(guide_key)
                          or "Sobre esta aba")
        self.toggle.setText(f"❓ {label} — o que esta aba faz e como ler os índices")
        self.toggle.setAccessibleName(
            f"Ajuda detalhada: {explanations.guide_title(guide_key) or guide_key}"
        )
        self.browser.setAccessibleName(
            f"Explicações da aba {explanations.guide_title(guide_key) or guide_key}"
        )
        self.set_guide(guide_key, label)
        self.toggle.toggled.connect(self._on_toggled)
        self._on_toggled(self._expanded)

    # ------------------------------------------------------------------
    def set_guide(self, guide_key: str, title: str = "") -> None:
        """Troca o conteúdo do painel sem recriar o widget."""
        self.guide_key = guide_key
        html = explanations.guide_html(guide_key)
        self.browser.setHtml(html or "<p>Sem explicação disponível.</p>")
        if title:
            self.toggle.setText(
                f"❓ {title} — o que esta aba faz e como ler os índices"
            )

    def is_expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = bool(expanded)
        self.toggle.setChecked(self._expanded)

    def _on_toggled(self, checked: bool) -> None:
        self._expanded = bool(checked)
        self.browser.setVisible(self._expanded)
        self.toggle.setArrowType(
            Qt.DownArrow if self._expanded else Qt.RightArrow
        )
        self.setSizePolicy(
            QSizePolicy.Preferred,
            QSizePolicy.Maximum if self._expanded else QSizePolicy.Fixed,
        )


def add_help(layout, guide_key: str, title: str = "",
             expanded: bool = False) -> HelpPanel:
    """Cria um :class:`HelpPanel` e o adiciona ao layout informado."""
    panel = HelpPanel(guide_key, title=title, expanded=expanded)
    layout.addWidget(panel)
    return panel
