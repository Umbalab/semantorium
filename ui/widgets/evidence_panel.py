#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Painel reutilizável de evidências (Fase 20).

Mostra uma lista de trechos e, ao selecionar, o texto com destaque, a
localização (página, seção, parágrafo, sentença), o método, a confiança e as
limitações. O widget não conhece a análise: recebe entradas já normalizadas
pelo catálogo de exploração ou pela busca contextual.
"""

import html

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QSplitter, QTextBrowser, QVBoxLayout,
    QWidget,
)

from core.context_search import highlight_html
from ui.widgets.common import DataTable

_NATURE_LABELS = {
    "deterministic": "determinístico",
    "probabilistic": "probabilístico",
    "interpretive": "interpretativo",
}


def _location(entry: dict) -> str:
    parts = []
    if entry.get("page") is not None:
        parts.append(f"p. {entry.get('page')}")
    if entry.get("section"):
        parts.append(str(entry.get("section")))
    if entry.get("paragraph") is not None:
        parts.append(f"§ {entry.get('paragraph')}")
    if entry.get("sentence") is not None:
        parts.append(f"s. {entry.get('sentence')}")
    if entry.get("start") is not None and entry.get("end") is not None:
        parts.append(f"{entry.get('start')}–{entry.get('end')}")
    return " · ".join(parts)


def evidence_html(entry: dict, text: str = "", context: int = 260) -> str:
    """HTML de um trecho com destaque, contexto e metadados."""
    entry = entry or {}
    start = int(entry.get("start") or 0)
    end = int(entry.get("end") or start)
    prefix = html.escape(str(entry.get("context_before") or "")[-context:])
    suffix = html.escape(str(entry.get("context_after") or "")[:context])
    if text and 0 <= start < end <= len(text):
        body = highlight_html(text[start:end], [(0, end - start)])
        if not prefix:
            prefix = html.escape(text[max(0, start - context):start])
        if not suffix:
            suffix = html.escape(text[end:end + context])
    else:
        body = f"<mark class='lexima-hit'>{html.escape(str(entry.get('text') or ''))}</mark>"
    nature = _NATURE_LABELS.get(str(entry.get("nature") or ""),
                                str(entry.get("nature") or ""))
    limitations = "".join(
        f"<li>{html.escape(str(item))}</li>"
        for item in (entry.get("limitations") or [])[:8]
    )
    authors = ", ".join(entry.get("authors") or [])
    years = ", ".join(entry.get("years") or [])
    concepts = ", ".join(entry.get("concepts") or [])
    meta = [
        ("Fonte", entry.get("source_label") or entry.get("source") or "—"),
        ("Rótulo", entry.get("label") or "—"),
        ("Local", _location(entry) or "sem localização estruturada"),
        ("Natureza", nature or "—"),
        ("Confiança", entry.get("confidence") or "—"),
        ("Método", entry.get("method") or "—"),
    ]
    if authors:
        meta.append(("Autores", authors))
    if years:
        meta.append(("Anos", years))
    if concepts:
        meta.append(("Conceitos", concepts))
    rows = "".join(
        f"<tr><th align='left'>{html.escape(label)}</th>"
        f"<td>{html.escape(str(value))}</td></tr>"
        for label, value in meta
    )
    return (
        "<style>"
        "body { font-family:'Segoe UI',sans-serif; color:#1f2937; font-size:12px; }"
        ".lexima-hit { background:#fff2a8; color:#111827; padding:1px 2px; }"
        ".snippet { background:#f8fafc; border:1px solid #e2e8f0;"
        " border-radius:8px; padding:10px; line-height:1.55; }"
        "table { border-collapse:collapse; margin-top:10px; }"
        "th { color:#5b6673; font-weight:600; padding:2px 10px 2px 0; }"
        "td { color:#1f2937; padding:2px 0; }"
        "h4 { margin:10px 0 4px; color:#1c53b8; }"
        "ul { margin:4px 0 0 18px; padding:0; color:#4b5563; }"
        "</style>"
        f"<div class='snippet'>{prefix}{body}{suffix}</div>"
        f"<table>{rows}</table>"
        + (f"<h4>Limitações</h4><ul>{limitations}</ul>" if limitations else "")
    )


class EvidencePanel(QWidget):
    """Tabela + detalhe de evidências, com ação de adicionar ao painel."""

    evidence_selected = Signal(dict)
    add_requested = Signal(dict)
    reveal_requested = Signal(dict)

    def __init__(self, title: str = "Evidências", parent=None,
                 show_add: bool = True):
        super().__init__(parent)
        self._entries: list = []
        self._text = ""
        self._current = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        header = QHBoxLayout()
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(
            "font-weight:600; font-size:13px; color:#1b1f24;")
        header.addWidget(self.title_label)
        header.addStretch()
        self.count_label = QLabel("0 evidências")
        self.count_label.setStyleSheet("color:#5b6673;")
        header.addWidget(self.count_label)
        self.btn_reveal = QPushButton("🔎 Ver no documento")
        self.btn_reveal.setEnabled(False)
        self.btn_reveal.setToolTip(
            "Abre o texto original e seleciona o trecho desta evidência"
        )
        self.btn_reveal.clicked.connect(self._emit_reveal)
        header.addWidget(self.btn_reveal)
        self.btn_add = QPushButton("＋ Adicionar ao painel")
        self.btn_add.setEnabled(False)
        self.btn_add.clicked.connect(self._emit_add)
        self.btn_add.setVisible(bool(show_add))
        header.addWidget(self.btn_add)
        layout.addLayout(header)

        splitter = QSplitter(Qt.Vertical)
        self.table = DataTable(
            ["#", "Fonte", "Rótulo", "Local", "Natureza", "Confiança"]
        )
        self.table.setMinimumHeight(150)
        self.table.itemSelectionChanged.connect(self._on_selection)
        self.table.cellDoubleClicked.connect(lambda *_: self._emit_add())
        splitter.addWidget(self.table)

        self.detail = QTextBrowser()
        self.detail.setOpenExternalLinks(False)
        self.detail.setPlaceholderText(
            "Selecione uma evidência para ver o trecho e o contexto."
        )
        splitter.addWidget(self.detail)
        splitter.setSizes([260, 300])
        layout.addWidget(splitter, 1)

    # ------------------------------------------------------------------
    def set_text(self, text: str) -> None:
        self._text = text or ""

    def set_entries(self, entries, *, limit: int = 500) -> None:
        self._entries = list(entries or [])[:max(0, int(limit))]
        self.table.blockSignals(True)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        for entry in self._entries:
            row = self.table.rowCount()
            self.table.insertRow(row)
            nature = _NATURE_LABELS.get(
                str(entry.get("nature") or ""), str(entry.get("nature") or "")
            )
            values = [
                row + 1,
                entry.get("source_label") or entry.get("source") or "",
                entry.get("label") or entry.get("text") or "",
                _location(entry),
                nature,
                entry.get("confidence") or "",
            ]
            for column, value in enumerate(values):
                from PySide6.QtWidgets import QTableWidgetItem

                item = QTableWidgetItem(str(value))
                if column == 0:
                    item.setData(Qt.UserRole, row)
                self.table.setItem(row, column, item)
        self.table.setSortingEnabled(True)
        self.table.blockSignals(False)
        self.table.resizeColumnsToContents()
        self.count_label.setText(f"{len(self._entries)} evidência(s)")
        self._current = {}
        self.btn_add.setEnabled(False)
        self.btn_reveal.setEnabled(False)
        self.detail.setHtml(
            "<p style='color:#5b6673'>Selecione uma evidência na lista.</p>"
        )

    def entries(self) -> list:
        return list(self._entries)

    def current_entry(self) -> dict:
        return dict(self._current)

    def select_index(self, index: int) -> None:
        if 0 <= index < self.table.rowCount():
            self.table.selectRow(index)
            self._on_selection()

    def _on_selection(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        item = self.table.item(row, 0)
        source = item.data(Qt.UserRole) if item is not None else None
        source = source if isinstance(source, int) else row
        if not (0 <= source < len(self._entries)):
            return
        entry = self._entries[source]
        self._current = dict(entry)
        self.detail.setHtml(evidence_html(entry, self._text))
        self.btn_add.setEnabled(True)
        self.btn_reveal.setEnabled(
            entry.get("start") is not None and entry.get("end") is not None
        )
        self.evidence_selected.emit(dict(entry))

    def _emit_add(self) -> None:
        if self._current:
            self.add_requested.emit(dict(self._current))

    def _emit_reveal(self) -> None:
        if self._current:
            self.reveal_requested.emit(dict(self._current))


__all__ = ["EvidencePanel", "evidence_html"]
