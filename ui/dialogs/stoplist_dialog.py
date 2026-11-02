#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Diálogo de gerenciamento da stoplist.

A stoplist efetiva combina três camadas:

  1. a lista padrão do idioma (embutida);
  2. palavras acrescentadas pelo usuário;
  3. palavras removidas da lista padrão pelo usuário.

Tudo é persistido em ``%APPDATA%\\Semantorium\\stoplist.json`` (ou no caminho
indicado por ``LEXIMA_STOPLIST``). O diálogo permite adicionar, remover,
restaurar o padrão, importar e exportar listas.
"""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QMessageBox, QPushButton, QVBoxLayout,
)

from core import stopwords


LANGUAGES = [
    ("PT-BR", "Português (Brasil)"),
    ("EN", "Inglês"),
    ("ES", "Espanhol"),
    ("FR", "Francês"),
    ("IT", "Italiano"),
    ("DE", "Alemão"),
]


class StoplistDialog(QDialog):
    """Editor da stoplist por idioma."""

    def __init__(self, language: str = "PT-BR", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Stoplist · palavras ignoradas")
        self.resize(620, 620)
        self.changed = False
        self._language = language if language in dict(LANGUAGES) else "PT-BR"

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        intro = QLabel(
            "As palavras abaixo são ignoradas em <b>todas</b> as análises "
            "(frequência, nuvem, palavras-chave, conceitos, tópicos, "
            "agrupamentos, similaridade e redes). A lista é salva "
            "automaticamente e pode ser importada/exportada."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color:#5b6673;")
        layout.addWidget(intro)

        top = QHBoxLayout()
        top.addWidget(QLabel("Idioma:"))
        self.combo_language = QComboBox()
        for code, label in LANGUAGES:
            self.combo_language.addItem(label, code)
        index = max(0, self.combo_language.findData(self._language))
        self.combo_language.setCurrentIndex(index)
        top.addWidget(self.combo_language)
        top.addStretch()
        self.count_label = QLabel("—")
        self.count_label.setStyleSheet("color:#5b6673;")
        top.addWidget(self.count_label)
        layout.addLayout(top)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Filtrar:"))
        self.input_filter = QLineEdit()
        self.input_filter.setPlaceholderText("Digite para localizar uma palavra…")
        search_row.addWidget(self.input_filter, 1)
        layout.addLayout(search_row)

        self.list_words = QListWidget()
        self.list_words.setSelectionMode(QListWidget.ExtendedSelection)
        self.list_words.setAlternatingRowColors(True)
        self.list_words.setStyleSheet(
            "QListWidget { background:#ffffff; border:1px solid #e2e8f0;"
            " border-radius:8px; padding:4px; }"
        )
        layout.addWidget(self.list_words, 1)

        add_row = QHBoxLayout()
        self.input_add = QLineEdit()
        self.input_add.setPlaceholderText(
            "Nova(s) palavra(s) — separe por vírgula ou espaço"
        )
        self.input_add.returnPressed.connect(self._add_words)
        add_row.addWidget(self.input_add, 1)
        self.button_add = QPushButton("＋ Adicionar")
        self.button_add.clicked.connect(self._add_words)
        add_row.addWidget(self.button_add)
        layout.addLayout(add_row)

        buttons_row = QHBoxLayout()
        self.button_remove = QPushButton("－ Remover selecionadas")
        self.button_remove.clicked.connect(self._remove_selected)
        buttons_row.addWidget(self.button_remove)

        self.button_reset = QPushButton("↺ Restaurar padrão do idioma")
        self.button_reset.clicked.connect(self._reset_language)
        buttons_row.addWidget(self.button_reset)

        self.button_import = QPushButton("📥 Importar…")
        self.button_import.clicked.connect(self._import)
        buttons_row.addWidget(self.button_import)

        self.button_export = QPushButton("📤 Exportar…")
        self.button_export.clicked.connect(self._export)
        buttons_row.addWidget(self.button_export)
        buttons_row.addStretch()
        layout.addLayout(buttons_row)

        close_box = QDialogButtonBox(QDialogButtonBox.Close)
        close_box.rejected.connect(self.accept)
        layout.addWidget(close_box)

        self.combo_language.currentIndexChanged.connect(self._language_changed)
        self.input_filter.textChanged.connect(self._refresh)
        self._refresh()

    # ------------------------------------------------------------------
    @property
    def language(self) -> str:
        return self.combo_language.currentData() or "PT-BR"

    def _language_changed(self) -> None:
        self._language = self.language
        self._refresh()

    def _refresh(self) -> None:
        words = sorted(stopwords.effective_stopwords(self.language))
        needle = stopwords.normalize(self.input_filter.text())
        if needle:
            words = [w for w in words if needle in w]
        self.list_words.clear()
        self.list_words.addItems(words)
        total = len(stopwords.effective_stopwords(self.language))
        custom = stopwords.custom_words(self.language)
        self.count_label.setText(
            f"{total} palavras · +{len(custom['add'])} / −{len(custom['remove'])}"
        )

    def _mark_changed(self) -> None:
        self.changed = True
        self._refresh()

    def _add_words(self) -> None:
        raw = self.input_add.text().strip()
        if not raw:
            return
        words = [
            part for part in stopwords.parse_word_list(raw) if part.strip()
        ]
        if not words:
            return
        stopwords.add_words(self.language, words)
        self.input_add.clear()
        self._mark_changed()

    def _remove_selected(self) -> None:
        items = self.list_words.selectedItems()
        if not items:
            QMessageBox.information(
                self, "Nada selecionado",
                "Selecione uma ou mais palavras na lista para remover.",
            )
            return
        stopwords.remove_words(self.language, [item.text() for item in items])
        self._mark_changed()

    def _reset_language(self) -> None:
        answer = QMessageBox.question(
            self, "Restaurar padrão",
            f"Descartar as personalizações de {self.language} e voltar à "
            "lista padrão do idioma?",
        )
        if answer != QMessageBox.Yes:
            return
        stopwords.reset_language(self.language)
        self._mark_changed()

    def _import(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "Importar stoplist", "",
            "Listas de palavras (*.txt *.csv *.json);;Todos os arquivos (*.*)",
        )
        if not filename:
            return
        try:
            stopwords.import_file(filename, self.language)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Erro ao importar", str(exc))
            return
        self._mark_changed()

    def _export(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self, "Exportar stoplist",
            f"stoplist_{self.language.lower().replace('-', '_')}.txt",
            "Texto (*.txt);;JSON (*.json)",
        )
        if not filename:
            return
        if not Path(filename).suffix:
            filename += ".txt"
        try:
            stopwords.export_file(filename, self.language)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Erro ao exportar", str(exc))
            return
        QMessageBox.information(
            self, "Stoplist exportada", f"Arquivo salvo em:\n{filename}"
        )
