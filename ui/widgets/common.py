#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Widgets reutilizáveis."""

import unicodedata

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)


class Card(QFrame):
    """Cartão com título e conteúdo."""

    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setFrameShape(QFrame.StyledPanel)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(14, 12, 14, 12)
        self._layout.setSpacing(8)
        if title:
            label = QLabel(title)
            font = QFont()
            font.setPointSize(11)
            font.setBold(True)
            label.setFont(font)
            self._layout.addWidget(label)

    def add(self, widget: QWidget) -> None:
        self._layout.addWidget(widget)

    def add_layout(self, layout) -> None:
        self._layout.addLayout(layout)


class KpiTile(QFrame):
    def __init__(self, label: str, value: str = "—", parent=None):
        super().__init__(parent)
        self.setObjectName("Kpi")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(2)
        self.value_label = QLabel(value)
        self.value_label.setObjectName("KpiValue")
        vf = QFont()
        vf.setPointSize(18)
        vf.setBold(True)
        self.value_label.setFont(vf)
        self.name_label = QLabel(label.upper())
        self.name_label.setObjectName("KpiName")
        nf = QFont()
        nf.setPointSize(8)
        self.name_label.setFont(nf)
        layout.addWidget(self.value_label)
        layout.addWidget(self.name_label)

    def set_value(self, value) -> None:
        self.value_label.setText(str(value))


class _SortItem(QTableWidgetItem):
    """Item que ordena números corretamente quando o cabeçalho é clicado."""

    def __init__(self, value):
        super().__init__(str(value))
        self._number = float(value) if isinstance(value, (int, float)) else None

    def __lt__(self, other):
        # Não usar super().__lt__: no PySide6 ele reentra no override Python
        # deste método e provoca RecursionError (crash da interface).
        other_number = getattr(other, "_number", None)
        if self._number is not None and other_number is not None:
            return self._number < other_number
        other_text = other.text() if hasattr(other, "text") else str(other)
        return self.text().casefold() < str(other_text).casefold()


class DataTable(QTableWidget):
    """Tabela padrão somente leitura, ordenável e paginada.

    Acima de ``page_size`` linhas a tabela exibe apenas uma página por vez,
    com um paginador abaixo do viewport. Isso evita o congelamento da
    interface ao renderizar milhares de linhas de uma só vez, sem alterar
    ``rowCount()``/``item()`` para as tabelas pequenas (que continuam
    totalmente visíveis e ordenáveis pelo cabeçalho nativo).
    """

    PAGE_SIZE = 500

    #: Emitido quando a página renderizada muda (paginação ou ordenação).
    pageChanged = Signal()

    def __init__(self, headers, parent=None, page_size: int | None = None,
                 search: bool = False):
        super().__init__(0, len(headers), parent)
        self.setObjectName("DataTable")
        self.setHorizontalHeaderLabels(headers)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)

        self._page_size = max(1, int(page_size or self.PAGE_SIZE))
        self._all_rows: list[tuple] = []
        self._order: list[int] = []
        self._filtered: list[int] = []
        self._filter = ""
        self._page = 0
        self._paged = False
        self._sort_column = -1
        self._sort_order = Qt.AscendingOrder
        self._search: QLineEdit | None = None
        self._search_height = 0

        self._pager = QWidget(self)
        self._pager.setObjectName("TablePager")
        pager_layout = QHBoxLayout(self._pager)
        pager_layout.setContentsMargins(6, 2, 6, 2)
        pager_layout.setSpacing(8)
        pager_layout.addStretch(1)
        self._pager_prev = QPushButton("‹")
        self._pager_prev.setObjectName("TablePagerButton")
        self._pager_prev.setToolTip("Página anterior")
        self._pager_prev.setAccessibleName("Página anterior")
        self._pager_prev.setAutoDefault(False)
        self._pager_prev.clicked.connect(self.previous_page)
        self._pager_label = QLabel("")
        self._pager_label.setObjectName("TablePagerLabel")
        self._pager_label.setAlignment(Qt.AlignCenter)
        self._pager_next = QPushButton("›")
        self._pager_next.setObjectName("TablePagerButton")
        self._pager_next.setToolTip("Próxima página")
        self._pager_next.setAccessibleName("Próxima página")
        self._pager_next.setAutoDefault(False)
        self._pager_next.clicked.connect(self.next_page)
        pager_layout.addWidget(self._pager_prev)
        pager_layout.addWidget(self._pager_label)
        pager_layout.addWidget(self._pager_next)
        self._pager.hide()

        self.horizontalHeader().sectionClicked.connect(self._on_header_clicked)
        if search:
            self.enable_search()

    # -- busca ---------------------------------------------------------
    def enable_search(self, placeholder: str = "Filtrar linhas…") -> None:
        """Ativa o filtro incremental opcional acima do cabeçalho."""
        if self._search is not None:
            return
        self._search = QLineEdit(self)
        self._search.setObjectName("TableSearch")
        self._search.setPlaceholderText(placeholder)
        self._search.setClearButtonEnabled(True)
        self._search.setToolTip(
            "Filtra as linhas pelo texto de qualquer coluna (sem alterar os dados)"
        )
        self._search.textChanged.connect(self._on_filter_changed)
        self._search.show()
        self._apply_pager_geometry()

    @property
    def search_box(self) -> QLineEdit | None:
        return self._search

    @property
    def filter_text(self) -> str:
        return self._filter

    def set_filter(self, text: str) -> None:
        """Filtra por substring (sem diferenciar maiúsculas/acentos)."""
        self._filter = str(text or "").strip()
        self._recompute_filter()
        self._page = 0
        self._render()
        self.pageChanged.emit()

    def _on_filter_changed(self, text: str) -> None:
        self.set_filter(text)

    def _recompute_filter(self) -> None:
        if not self._filter:
            self._filtered = list(self._order)
            return
        needle = _fold_text(self._filter)
        self._filtered = [
            index for index in self._order
            if any(needle in _fold_text(value)
                   for value in self._all_rows[index])
        ]

    def _active_positions(self) -> list[int]:
        return self._filtered if self._filter else self._order

    # -- paginação -----------------------------------------------------
    @property
    def row_offset(self) -> int:
        """Posição da primeira linha visível na ordem atual da tabela."""
        return self._page * self._page_size if self._paged else 0

    @property
    def total_rows(self) -> int:
        return len(self._all_rows)

    @property
    def is_paged(self) -> bool:
        return self._paged

    def source_index(self, row: int) -> int:
        """Índice original da linha visível ``row`` (ordem/página atuais).

        Nas tabelas pequenas o Qt ordena as linhas nativas quando o cabeçalho
        é clicado; por isso o índice de origem é gravado em ``Qt.UserRole`` e
        lido de volta, em vez de assumir que a linha visual é a original.
        """
        if row is None or row < 0 or row >= self.rowCount():
            return -1
        if not self._paged:
            item = self.item(row, 0)
            if item is not None:
                stored = item.data(Qt.UserRole)
                if isinstance(stored, int) and stored >= 0:
                    return stored
            return row
        position = self._page * self._page_size + int(row)
        positions = self._active_positions()
        if 0 <= position < len(positions):
            return positions[position]
        return -1

    def page_count(self) -> int:
        total = len(self._active_positions())
        if total <= 0:
            return 1
        return (total + self._page_size - 1) // self._page_size

    def set_page(self, page: int) -> None:
        if not self._paged:
            return
        page = max(0, min(int(page), self.page_count() - 1))
        if page == self._page:
            self._update_pager()
            return
        self._page = page
        self._render()
        self.pageChanged.emit()

    def next_page(self) -> None:
        self.set_page(self._page + 1)

    def previous_page(self) -> None:
        self.set_page(self._page - 1)

    # -- dados ---------------------------------------------------------
    def set_rows(self, rows) -> None:
        self._all_rows = [tuple(row) for row in rows]
        self._order = list(range(len(self._all_rows)))
        self._page = 0
        self._paged = (
            len(self._all_rows) > self._page_size
            or (self._search is not None and bool(self._all_rows))
        )
        self._recompute_filter()
        self._render()
        if self._paged:
            self.pageChanged.emit()

    def sortItems(self, column, order=Qt.AscendingOrder):  # noqa: N802
        """Ordena o conjunto completo (não apenas a página visível)."""
        if not self._paged:
            super().sortItems(column, order)
            return
        self._sort_column = int(column)
        self._sort_order = order
        reverse = order == Qt.DescendingOrder
        self._order.sort(
            key=lambda index: _sort_key(self._row_value(index, column)),
            reverse=reverse,
        )
        self._recompute_filter()
        self.horizontalHeader().setSortIndicator(column, order)
        self._page = 0
        self._render()
        self.pageChanged.emit()

    # -- renderização --------------------------------------------------
    def _row_value(self, index: int, column: int):
        row = self._all_rows[index]
        if 0 <= column < len(row):
            return row[column]
        return ""

    def _render(self) -> None:
        positions_all = self._active_positions()
        total = len(positions_all)
        start = self.row_offset
        end = min(start + self._page_size, total) if self._paged else total
        positions = positions_all[start:end]

        self.blockSignals(True)
        self.setSortingEnabled(False)
        self.setRowCount(len(positions))
        for view_row, source in enumerate(positions):
            for col, value in enumerate(self._all_rows[source]):
                item = _SortItem(value)
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                if col == 0:
                    item.setData(Qt.UserRole, source)
                self.setItem(view_row, col, item)
        if self._paged:
            self._update_pager()
            header = self.horizontalHeader()
            header.setSortIndicatorShown(True)
            if self._sort_column >= 0:
                header.setSortIndicator(self._sort_column, self._sort_order)
            self._apply_pager_geometry()
        else:
            self.setSortingEnabled(True)
        self.blockSignals(False)
        self.resizeColumnsToContents()

    def _update_pager(self) -> None:
        total = len(self._active_positions())
        start = self.row_offset + 1 if total else 0
        end = min(self.row_offset + self._page_size, total)
        self._pager_label.setText(f"{start}–{end} de {total}")
        self._pager_prev.setEnabled(self._page > 0)
        self._pager_next.setEnabled(end < total)

    def _apply_pager_geometry(self) -> None:
        top = 0
        if self._search is not None and not self._search.isHidden():
            top = self._search.sizeHint().height()
            self._search_height = top
        show_pager = self._paged and self.page_count() > 1
        bottom = self._pager.sizeHint().height() if show_pager else 0
        if (self.viewportMargins().top() != top
                or self.viewportMargins().bottom() != bottom):
            self.setViewportMargins(0, top, 0, bottom)
        viewport = self.viewport().geometry()
        if self._search is not None:
            self._search.setGeometry(
                viewport.left(), max(0, viewport.top() - top),
                viewport.width(), top,
            )
            self._search.raise_()
        if show_pager:
            self._pager.setGeometry(
                viewport.left(), viewport.bottom() + 1,
                viewport.width(), bottom,
            )
            self._pager.show()
            self._pager.raise_()
        else:
            self._pager.hide()

    def _on_header_clicked(self, column: int) -> None:
        if not self._paged:
            return
        if self._sort_column == column:
            order = (
                Qt.DescendingOrder
                if self._sort_order == Qt.AscendingOrder
                else Qt.AscendingOrder
            )
        else:
            order = Qt.AscendingOrder
        self.sortItems(column, order)

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._apply_pager_geometry()


def _sort_key(value):
    """Chave de ordenação que compara números numericamente e texto de forma estável."""
    if isinstance(value, bool):
        return (1, 0.0, str(value).casefold())
    if isinstance(value, (int, float)):
        return (0, float(value), "")
    return (1, 0.0, str(value if value is not None else "").casefold())


def _fold_text(value) -> str:
    """Texto em minúsculas e sem acentos, para a busca incremental."""
    text = unicodedata.normalize("NFKD", str(value if value is not None else ""))
    return "".join(char for char in text if not unicodedata.combining(char)).casefold()



class SectionHeader(QLabel):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setObjectName("SectionHeader")
        font = QFont()
        font.setPointSize(13)
        font.setBold(True)
        self.setFont(font)


class Chip(QLabel):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setObjectName("Chip")
        self.setWordWrap(False)


def hline() -> QFrame:
    line = QFrame()
    line.setObjectName("HLine")
    line.setFrameShape(QFrame.HLine)
    return line


def row(*widgets, stretch=True) -> QWidget:
    wrapper = QWidget()
    layout = QHBoxLayout(wrapper)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    for widget in widgets:
        layout.addWidget(widget)
    if stretch:
        layout.addStretch()
    return wrapper
