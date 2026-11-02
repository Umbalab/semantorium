#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Diálogo de busca global (Ctrl+F) no relatório."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QVBoxLayout,
)

from core import report_search

_SECTION_ORDER = [
    "summary", "keywords", "words", "concepts", "citations", "quotes",
    "references", "onomastic", "text",
]


class GlobalSearchDialog(QDialog):
    """Busca termos em todas as seções do relatório.

    ``selected_section`` indica para qual aba o chamador deve navegar e
    ``selected_index`` aponta a posição da ocorrência no texto (quando houver).
    """

    def __init__(self, result: dict, text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Busca global no relatório")
        self.resize(860, 560)
        self._result = result or {}
        self._text = text or ""
        self._matches = []
        self.selected_section = ""
        self.selected_index = -1

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        hint = QLabel(
            "Procura no resumo, palavras, conceitos, citações, referências, "
            "índice onomástico e no texto integral. Pressione Enter para buscar "
            "e dê duplo clique em um resultado para ir até a seção."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#5b6673;")
        layout.addWidget(hint)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Buscar:"))
        self.input_query = QLineEdit()
        self.input_query.setPlaceholderText("termo, autor, ano, DOI…")
        self.input_query.returnPressed.connect(self._run_search)
        search_row.addWidget(self.input_query, 1)
        self.btn_search = QPushButton("Buscar")
        self.btn_search.setObjectName("Primary")
        self.btn_search.clicked.connect(self._run_search)
        search_row.addWidget(self.btn_search)
        layout.addLayout(search_row)

        self.status = QLabel("Digite um termo e pressione Enter.")
        self.status.setStyleSheet("color:#5b6673;")
        layout.addWidget(self.status)

        self.list_results = QListWidget()
        self.list_results.itemDoubleClicked.connect(lambda _item: self._open_selected())
        layout.addWidget(self.list_results, 1)

        buttons = QHBoxLayout()
        self.btn_open = QPushButton("Ir para a seção")
        self.btn_open.setEnabled(False)
        self.btn_open.clicked.connect(self._open_selected)
        buttons.addWidget(self.btn_open)
        buttons.addStretch()
        self.btn_close = QPushButton("Fechar")
        self.btn_close.clicked.connect(self.reject)
        buttons.addWidget(self.btn_close)
        layout.addLayout(buttons)

        self.input_query.setFocus()

    # ------------------------------------------------------------------
    def _run_search(self) -> None:
        query = self.input_query.text().strip()
        self.list_results.clear()
        self._matches = []
        if not query:
            self.status.setText("Digite um termo para buscar.")
            return

        matches = report_search.search(self._result, self._text, query)
        matches.sort(key=lambda item: _SECTION_ORDER.index(item["section"])
                     if item.get("section") in _SECTION_ORDER else 99)
        self._matches = matches
        self.btn_open.setEnabled(bool(matches))

        if not matches:
            self.status.setText(f"Nenhuma ocorrência para “{query}”.")
            return

        groups = report_search.summarize(matches)
        summary = " · ".join(f"{name}: {count}" for name, count in groups.items())
        self.status.setText(f"{len(matches)} ocorrência(s) — {summary}.")

        for match in matches:
            label = match.get("label") or "—"
            text = (
                f"[{match.get('section_label', '')}] {label}\n"
                f"    {match.get('snippet', '')}"
            )
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, match)
            self.list_results.addItem(item)
        self.list_results.setCurrentRow(0)

    def _open_selected(self) -> None:
        item = self.list_results.currentItem()
        if item is None:
            return
        match = item.data(Qt.UserRole) or {}
        self.selected_section = match.get("section", "")
        try:
            self.selected_index = int(match.get("index", -1))
        except Exception:
            self.selected_index = -1
        self.accept()
