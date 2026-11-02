#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Aba: Carregar arquivo e pré-visualizar."""

from PySide6.QtCore import Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QVBoxLayout, QWidget,
)

from core.extractor import SUPPORTED_EXTENSIONS
from ui.widgets.help_panel import HelpPanel

FILE_FILTER = (
    "Todos os suportados (*.txt *.md *.markdown *.pdf *.docx *.odt *.rtf);;"
    "Texto (*.txt);;Markdown (*.md *.markdown);;PDF (*.pdf);;"
    "Word (*.docx);;OpenDocument (*.odt);;RTF (*.rtf);;Todos (*.*)"
)


class LoadView(QWidget):
    file_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        self.help_panel = HelpPanel("load")
        layout.addWidget(self.help_panel)

        top = QHBoxLayout()
        self.btn_open = QPushButton("📁  Carregar arquivo")
        self.btn_open.setObjectName("Primary")
        top.addWidget(self.btn_open)

        top.addWidget(QLabel("Idioma do texto:"))
        self.combo_lang = QComboBox()
        self.combo_lang.addItems(
            ["Auto-detectar", "PT-BR", "EN", "ES", "FR", "IT", "DE"]
        )
        top.addWidget(self.combo_lang)
        top.addStretch()
        layout.addLayout(top)

        self.info = QLabel("Nenhum arquivo carregado.")
        self.info.setStyleSheet("color:#5b6673;")
        self.info.setWordWrap(True)
        layout.addWidget(self.info)

        layout.addWidget(QLabel("<b>Pré-visualização</b>"))
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText(
            "Carregue um arquivo para visualizar o texto extraído."
        )
        layout.addWidget(self.preview, 1)

        self.btn_open.clicked.connect(self._pick)

    def _pick(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "Selecionar arquivo", "", FILE_FILTER
        )
        if filename:
            self.file_selected.emit(filename)

    def show_loading(self, path: str) -> None:
        self.info.setText(f"Carregando {path} ...")
        self.preview.setPlainText("Extraindo texto...")

    def set_result(self, result: dict) -> None:
        meta = result.get("meta", {})
        text = result.get("text", "")
        method = meta.get("method", "—")
        method_label = {"native": "nativo", "ocr": "OCR", "direct": "direto"}.get(
            method, method
        )
        parts = [
            f"<b>{meta.get('filename','—')}</b>",
            f"formato {meta.get('extension','—')}",
            f"método: {method_label}",
            f"{meta.get('words',0):,} palavras".replace(",", "."),
            f"{meta.get('chars',0):,} caracteres".replace(",", "."),
        ]
        if meta.get("pages"):
            parts.insert(3, f"{meta['pages']} páginas")
        self.info.setText(" · ".join(parts))

        warning = meta.get("warning")
        if warning:
            self.info.setText(self.info.text() +
                              f"<br><span style='color:#b06000'>⚠ {warning}</span>")

        # Exibe o texto completo extraído (sem truncar) para conferência.
        self.preview.setPlainText(text)
        self.preview.moveCursor(QTextCursor.Start)

    def reveal_range(self, start: int, end: int | None = None) -> bool:
        """Seleciona e centraliza ``[start, end)`` no texto de pré-visualização."""
        text = self.preview.toPlainText()
        if not text:
            return False
        start = max(0, min(int(start or 0), len(text)))
        stop = len(text) if end is None else int(end)
        stop = max(start, min(stop, len(text)))
        if stop == start and start < len(text):
            stop = start + 1
        cursor = self.preview.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(stop, QTextCursor.KeepAnchor)
        self.preview.setTextCursor(cursor)
        self.preview.centerCursor()
        self.preview.setFocus()
        return True
