#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Diálogo de figuras e tabelas extraídas de um PDF."""

import shutil
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QDialog, QFileDialog, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton, QSplitter,
    QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from core import pdf_assets


class PdfAssetsDialog(QDialog):
    """Lista figuras/tabelas do PDF com pré-visualização e exportação."""

    def __init__(self, filepath: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Figuras e tabelas do PDF")
        self.resize(980, 660)
        self._filepath = filepath
        self._data = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        self.hint = QLabel(
            "Imagens e tabelas detectadas no PDF, com as legendas próximas. "
            "A extração é offline; revise as legendas associadas antes de "
            "reutilizar o material."
        )
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet("color:#5b6673;")
        layout.addWidget(self.hint)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)

        # Figuras
        figures_widget = QWidget()
        figures_layout = QVBoxLayout(figures_widget)
        figures_layout.setContentsMargins(6, 6, 6, 6)
        figure_splitter = QSplitter(Qt.Horizontal)
        self.figure_list = QListWidget()
        self.figure_list.currentRowChanged.connect(self._show_figure)
        figure_splitter.addWidget(self.figure_list)
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setContentsMargins(6, 6, 6, 6)
        self.figure_preview = QLabel("Selecione uma figura para visualizar.")
        self.figure_preview.setAlignment(Qt.AlignCenter)
        self.figure_preview.setWordWrap(True)
        self.figure_preview.setMinimumSize(320, 240)
        self.figure_preview.setStyleSheet(
            "background:#f6f9ff;border:1px solid #d7e0ee;border-radius:6px;"
            "color:#5b6673;"
        )
        preview_layout.addWidget(self.figure_preview, 1)
        self.figure_caption = QLabel("—")
        self.figure_caption.setWordWrap(True)
        self.figure_caption.setStyleSheet("color:#5b6673;")
        preview_layout.addWidget(self.figure_caption)
        figure_splitter.addWidget(preview_widget)
        figure_splitter.setStretchFactor(1, 1)
        figures_layout.addWidget(figure_splitter, 1)
        self.tabs.addTab(figures_widget, "🖼 Figuras")

        # Tabelas
        tables_widget = QWidget()
        tables_layout = QVBoxLayout(tables_widget)
        tables_layout.setContentsMargins(6, 6, 6, 6)
        self.table_caption = QLabel("—")
        self.table_caption.setWordWrap(True)
        self.table_caption.setStyleSheet("color:#5b6673;")
        tables_layout.addWidget(self.table_caption)
        self.table_preview = QTableWidget(0, 0)
        self.table_preview.setAlternatingRowColors(True)
        self.table_preview.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tables_layout.addWidget(self.table_preview, 1)
        self.tabs.addTab(tables_widget, "📊 Tabelas")

        self.summary = QLabel("Extraindo…")
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet("color:#1c53b8;font-weight:600;")
        layout.addWidget(self.summary)

        self.warning = QLabel("")
        self.warning.setWordWrap(True)
        self.warning.setStyleSheet("color:#b45309;")
        layout.addWidget(self.warning)

        buttons = QHBoxLayout()
        self.btn_images = QPushButton("Salvar imagens…")
        self.btn_images.clicked.connect(self._save_images)
        buttons.addWidget(self.btn_images)
        self.btn_html = QPushButton("Exportar HTML…")
        self.btn_html.clicked.connect(self._save_html)
        buttons.addWidget(self.btn_html)
        self.btn_json = QPushButton("Exportar JSON…")
        self.btn_json.clicked.connect(self._save_json)
        buttons.addWidget(self.btn_json)
        buttons.addStretch()
        close = QPushButton("Fechar")
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        layout.addLayout(buttons)

        self._extract()

    # ------------------------------------------------------------------
    def _extract(self) -> None:
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self._data = pdf_assets.extract_assets(self._filepath)
        except Exception as exc:  # noqa: BLE001
            QApplication.restoreOverrideCursor()
            self._data = {}
            self.summary.setText("Não foi possível extrair figuras/tabelas.")
            self.warning.setText(str(exc))
            for button in (self.btn_images, self.btn_html, self.btn_json):
                button.setEnabled(False)
            return
        finally:
            QApplication.restoreOverrideCursor()

        data = self._data
        summary = data.get("summary") or {}
        self.summary.setText(
            f"{summary.get('figures', 0)} figura(s) · "
            f"{summary.get('tables', 0)} tabela(s) · "
            f"{summary.get('captions', 0)} legenda(s) · "
            f"{summary.get('pages', 0)} página(s) · "
            f"{summary.get('captioned', 0)} com legenda associada"
        )
        warnings = data.get("warnings") or []
        self.warning.setText("\n".join(f"⚠ {warning}" for warning in warnings))
        self.warning.setVisible(bool(warnings))
        self.btn_images.setEnabled(bool(data.get("figures")))

        for index, figure in enumerate(data.get("figures") or []):
            caption = figure.get("caption") or {}
            title = caption.get("title") or "sem legenda associada"
            item = QListWidgetItem(
                f"Página {figure.get('page', '?')} · "
                f"{caption.get('label', f'Imagem {index + 1}')} — {title}"
            )
            item.setToolTip(figure.get("path", ""))
            self.figure_list.addItem(item)
        if self.figure_list.count():
            self.figure_list.setCurrentRow(0)
        else:
            self.figure_preview.setText("Nenhuma figura encontrada no PDF.")

        tables = data.get("tables") or []
        if tables:
            first = tables[0]
            self._show_table(first)
            # Navegação simples entre tabelas na parte superior da aba.
            self.table_selector = QListWidget()
            self.table_selector.setMaximumHeight(88)
            for index, table in enumerate(tables):
                caption = table.get("caption") or {}
                self.table_selector.addItem(
                    f"Página {table.get('page', '?')} · "
                    f"{caption.get('label', f'Tabela {index + 1}')} — "
                    f"{caption.get('title') or 'sem legenda'}"
                )
            self.table_selector.currentRowChanged.connect(self._select_table)
            self.tabs.widget(1).layout().insertWidget(0, self.table_selector)
            self.table_selector.setCurrentRow(0)
        else:
            self.table_caption.setText("Nenhuma tabela encontrada no PDF.")

    def _show_figure(self, row: int) -> None:
        figures = self._data.get("figures") or []
        if row < 0 or row >= len(figures):
            return
        figure = figures[row]
        path = Path(figure.get("path") or "")
        if path.exists():
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                self.figure_preview.setPixmap(
                    pixmap.scaled(
                        520, 380, Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                )
            else:
                self.figure_preview.setText("Imagem não pôde ser lida.")
        else:
            self.figure_preview.setText("Arquivo da imagem não encontrado.")
        caption = figure.get("caption") or {}
        self.figure_caption.setText(
            f"Página {figure.get('page', '?')} · "
            f"{caption.get('label', 'Sem rótulo')} · "
            f"{caption.get('title') or 'sem legenda'} · "
            f"{figure.get('width', 0)}×{figure.get('height', 0)} px · "
            f"{Path(figure.get('path') or '').name}"
        )

    def _select_table(self, row: int) -> None:
        tables = self._data.get("tables") or []
        if row < 0 or row >= len(tables):
            return
        self._show_table(tables[row])

    def _show_table(self, table: dict) -> None:
        caption = table.get("caption") or {}
        self.table_caption.setText(
            f"Página {table.get('page', '?')} · "
            f"{caption.get('label', 'Sem rótulo')} · "
            f"{caption.get('title') or 'sem legenda'} · "
            f"{table.get('rows', 0)} linha(s) × "
            f"{table.get('columns', 0)} coluna(s)"
        )
        rows = table.get("data") or []
        columns = max((len(row) for row in rows), default=0)
        self.table_preview.clear()
        self.table_preview.setRowCount(0)
        self.table_preview.setColumnCount(columns)
        self.table_preview.setHorizontalHeaderLabels(
            [str(cell) for cell in (rows[0] if rows else [])]
            or [f"Coluna {index + 1}" for index in range(columns)]
        )
        body = rows[1:] if len(rows) > 1 else rows
        self.table_preview.setRowCount(len(body))
        for row_index, row in enumerate(body):
            for column_index, value in enumerate(row):
                self.table_preview.setItem(
                    row_index, column_index, QTableWidgetItem(str(value))
                )
        self.table_preview.resizeColumnsToContents()

    # ------------------------------------------------------------------
    def _save_images(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Salvar imagens extraídas", ""
        )
        if not directory:
            return
        saved = 0
        try:
            for figure in self._data.get("figures") or []:
                source = Path(figure.get("path") or "")
                if not source.exists():
                    continue
                shutil.copy2(source, Path(directory) / source.name)
                saved += 1
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Erro ao salvar", str(exc))
            return
        QMessageBox.information(
            self, "Figuras e tabelas",
            f"{saved} imagem(ns) salva(s) em:\n{directory}",
        )

    def _save_html(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self, "Exportar figuras e tabelas (HTML)",
            "figuras_tabelas.html", "HTML (*.html)",
        )
        if not filename:
            return
        if Path(filename).suffix.lower() != ".html":
            filename = str(Path(filename).with_suffix(".html"))
        try:
            pdf_assets.export_html(self._data, filename)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Erro ao exportar", str(exc))
            return
        QMessageBox.information(
            self, "Figuras e tabelas", f"HTML salvo:\n{filename}"
        )

    def _save_json(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self, "Exportar metadados (JSON)",
            "figuras_tabelas.json", "JSON (*.json)",
        )
        if not filename:
            return
        if Path(filename).suffix.lower() != ".json":
            filename = str(Path(filename).with_suffix(".json"))
        try:
            pdf_assets.export_json(self._data, filename)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Erro ao exportar", str(exc))
            return
        QMessageBox.information(
            self, "Figuras e tabelas", f"JSON salvo:\n{filename}"
        )
