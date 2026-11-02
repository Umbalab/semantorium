#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Diálogo: histórico de análises e documentos recentes."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QVBoxLayout,
)

from core import userdata
from ui.widgets.common import DataTable


class HistoryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Histórico de análises")
        self.resize(900, 520)
        self.selected_path = ""
        self._items = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        hint = QLabel(
            "Cada análise registra apenas metadados: caminho, idioma, volume, "
            "resumo curto e avisos. O texto não é armazenado."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#5b6673;")
        layout.addWidget(hint)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filtrar:"))
        self.input_filter = QLineEdit()
        self.input_filter.setPlaceholderText("nome, idioma, palavra-chave…")
        self.input_filter.textChanged.connect(self._render)
        filter_row.addWidget(self.input_filter, 1)
        layout.addLayout(filter_row)

        self.table = DataTable([
            "Documento", "Idioma", "Palavras", "Sentenças", "Analisado em",
            "Motor", "Avisos", "Favorito",
        ])
        self.table.cellDoubleClicked.connect(lambda row, col: self._open(row))
        layout.addWidget(self.table, 1)

        self.status = QLabel("—")
        self.status.setStyleSheet("color:#5b6673;")
        layout.addWidget(self.status)

        buttons = QHBoxLayout()
        self.btn_open = QPushButton("Abrir documento")
        self.btn_open.setObjectName("Primary")
        self.btn_open.clicked.connect(lambda: self._open(self.table.currentRow()))
        buttons.addWidget(self.btn_open)
        self.btn_clear = QPushButton("Limpar histórico")
        self.btn_clear.clicked.connect(self._clear)
        buttons.addWidget(self.btn_clear)
        buttons.addStretch()
        self.btn_close = QPushButton("Fechar")
        self.btn_close.clicked.connect(self.reject)
        buttons.addWidget(self.btn_close)
        layout.addLayout(buttons)

        self._render()

    # ------------------------------------------------------------------
    def _render(self) -> None:
        query = self.input_filter.text().strip().lower()
        items = []
        for item in userdata.history():
            haystack = " ".join(str(item.get(key, "")) for key in (
                "name", "language_label", "summary", "keywords", "path",
            )).lower()
            if query and query not in haystack:
                continue
            items.append(item)
        self._items = items
        self.table.set_rows([
            (
                item.get("name", ""),
                item.get("language_label", ""),
                item.get("words", 0),
                item.get("sentences", 0),
                (item.get("at", "") or "").replace("T", " "),
                item.get("engine", ""),
                item.get("warnings", 0),
                "sim" if userdata.is_favorite(item.get("path", "")) else "",
            )
            for item in items
        ])
        self.status.setText(
            f"{len(items)} análise(s) no histórico."
            if items else "Nenhuma análise registrada ainda."
        )
        self.btn_open.setEnabled(bool(items))

    def _open(self, row: int) -> None:
        if row < 0 or row >= len(self._items):
            return
        path = self._items[row].get("path", "")
        if not path:
            return
        if not Path(path).exists():
            QMessageBox.warning(
                self, "Arquivo não encontrado",
                f"O documento não está mais no caminho registrado:\n{path}",
            )
            return
        self.selected_path = path
        self.accept()

    def _clear(self) -> None:
        answer = QMessageBox.question(
            self, "Limpar histórico",
            "Remover todos os registros do histórico? "
            "Os documentos no disco não serão alterados.",
        )
        if answer != QMessageBox.Yes:
            return
        userdata.clear_history()
        self._render()
