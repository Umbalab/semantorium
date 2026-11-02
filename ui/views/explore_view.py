#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Aba: Explorar — busca, evidências, conceitos, filtros e painel.

A aba transforma os resultados da análise em uma investigação navegável. Todas
as operações são locais: a busca usa o texto original, o catálogo usa a camada
de evidências e o painel é salvo em JSON no diretório de dados do usuário.
"""

import html
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QFileDialog, QGridLayout, QGroupBox,
    QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea,
    QSpinBox, QSplitter, QTabWidget, QTextBrowser, QVBoxLayout, QWidget,
)

from core import context_search, exploration, investigation, research_panel
from ui.widgets.common import Card, DataTable, KpiTile
from ui.widgets.evidence_panel import EvidencePanel, evidence_html
from ui.widgets.help_panel import HelpPanel

_NATURE_LABELS = {
    "deterministic": "determinístico",
    "probabilistic": "probabilístico",
    "interpretive": "interpretativo",
}

_FACET_LABELS = {
    "authors": "Autor",
    "years": "Ano",
    "concepts": "Conceito",
    "sentiments": "Sentimento",
    "sections": "Seção",
    "natures": "Natureza do resultado",
    "sources": "Fonte",
    "confidences": "Confiança",
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
    return " · ".join(parts)


def _empty_filters() -> dict:
    return {
        "authors": [], "years": [], "concepts": [], "sentiments": [],
        "documents": [], "sections": [], "natures": [], "sources": [],
        "confidences": [], "query": "",
    }


def _match_entry(match: dict) -> dict:
    return {
        "source": "context_search",
        "source_label": "Busca contextual",
        "kind": match.get("kind") or "busca",
        "label": match.get("text") or "Ocorrência",
        "text": match.get("text") or "",
        "start": match.get("start"),
        "end": match.get("end"),
        "page": match.get("page"),
        "section": match.get("section"),
        "paragraph": match.get("paragraph"),
        "sentence": match.get("sentence"),
        "context_before": (match.get("evidence") or {}).get("context_before", ""),
        "context_after": (match.get("evidence") or {}).get("context_after", ""),
        "confidence": "alta",
        "nature": "deterministic",
        "method": "busca contextual 1.0.0",
        "engine": "internal",
        "limitations": [
            "A busca localiza formas textuais; não decide relevância.",
        ],
        "document": "",
        "snippet": match.get("snippet") or "",
    }


class ExploreView(QWidget):
    """Aba completa de exploração e painel de pesquisa."""

    status = Signal(str)
    panel_changed = Signal(dict)
    reveal_requested = Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.result: dict = {}
        self.text: str = ""
        self.exploration: dict = {}
        self.investigation: dict = {}
        self.panel = research_panel.load_panel()
        self.filters = research_panel.load_filters() or dict(
            self.panel.get("filters") or {})
        self._search_matches: list = []
        self._concepts: list = []
        self._filter_lists: dict = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        self.help_panel = HelpPanel("explore")
        layout.addWidget(self.help_panel)

        self.tabs = QTabWidget()
        self._build_search_tab()
        self._build_evidence_tab()
        self._build_concepts_tab()
        self._build_filters_tab()
        self._build_document_tab()
        self._build_panel_tab()
        layout.addWidget(self.tabs, 1)
        self._restore_panel_view()

    # ------------------------------------------------------------------
    # Construção das sub-abas
    # ------------------------------------------------------------------
    def _build_search_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.addWidget(HelpPanel("explore_search", expanded=False))

        row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "ética AND algoritmo · \"transparência algorítmica\" · "
            "NEAR/5(ética, algoritmo) · lemma:algoritmo · /algoritm[oa]s?/i"
        )
        self.search_input.returnPressed.connect(self.run_search)
        row.addWidget(self.search_input, 1)
        self.search_case = QComboBox()
        self.search_case.addItems(["Ignorar caixa", "Diferenciar caixa"])
        row.addWidget(self.search_case)
        self.search_limit = QSpinBox()
        self.search_limit.setRange(1, 500)
        self.search_limit.setValue(100)
        self.search_limit.setPrefix("limite ")
        row.addWidget(self.search_limit)
        self.btn_search = QPushButton("Buscar")
        self.btn_search.clicked.connect(self.run_search)
        row.addWidget(self.btn_search)
        layout.addLayout(row)

        hint = QLabel(
            "Sintaxe: AND implícito · AND/OR/NOT · frases entre aspas · "
            "parênteses · NEAR/n(a,b) · lemma: · variante: · /regex/flags"
        )
        hint.setStyleSheet("color:#5b6673; font-size:11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        splitter = QSplitter(Qt.Vertical)
        self.search_table = DataTable(
            ["#", "Trecho", "Local", "Natureza", "Confiança"]
        )
        self.search_table.itemSelectionChanged.connect(self._on_search_selected)
        splitter.addWidget(self.search_table)
        self.search_detail = QTextBrowser()
        self.search_detail.setOpenExternalLinks(False)
        self.search_detail.setHtml(
            "<p style='color:#5b6673'>Faça uma busca para ver o trecho e o "
            "contexto. A página só aparece quando a extração forneceu "
            "page_spans.</p>"
        )
        splitter.addWidget(self.search_detail)
        splitter.setSizes([250, 280])
        layout.addWidget(splitter, 1)

        actions = QHBoxLayout()
        self.search_status = QLabel("Nenhuma busca executada.")
        self.search_status.setStyleSheet("color:#5b6673;")
        actions.addWidget(self.search_status, 1)
        self.btn_search_add = QPushButton("＋ Adicionar ao painel")
        self.btn_search_add.setEnabled(False)
        self.btn_search_add.clicked.connect(self._add_selected_search)
        actions.addWidget(self.btn_search_add)
        layout.addLayout(actions)
        self.tabs.addTab(page, "🔎 Busca")

    def _build_evidence_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.addWidget(HelpPanel("explore_evidence", expanded=False))

        row = QHBoxLayout()
        self.evidence_query = QLineEdit()
        self.evidence_query.setPlaceholderText(
            "Filtrar os resultados já filtrados por texto, rótulo ou conceito…"
        )
        self.evidence_query.returnPressed.connect(self.refresh_evidence)
        row.addWidget(self.evidence_query, 1)
        self.btn_evidence_apply = QPushButton("Aplicar texto")
        self.btn_evidence_apply.clicked.connect(self.refresh_evidence)
        row.addWidget(self.btn_evidence_apply)
        self.btn_evidence_filters = QPushButton("Filtros cruzados…")
        self.btn_evidence_filters.clicked.connect(
            lambda: self.tabs.setCurrentIndex(3))
        row.addWidget(self.btn_evidence_filters)
        layout.addLayout(row)

        self.evidence_status = QLabel("Nenhum resultado disponível.")
        self.evidence_status.setStyleSheet("color:#5b6673;")
        layout.addWidget(self.evidence_status)
        self.evidence_panel = EvidencePanel("Trechos com evidência")
        self.evidence_panel.add_requested.connect(self.add_evidence)
        self.evidence_panel.reveal_requested.connect(self._reveal_evidence)
        layout.addWidget(self.evidence_panel, 1)
        self.tabs.addTab(page, "📌 Evidências")

    def _build_concepts_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.addWidget(HelpPanel("explore_concepts", expanded=False))

        row = QHBoxLayout()
        self.concept_query = QLineEdit()
        self.concept_query.setPlaceholderText(
            "Buscar conceito por termo, variante ou definição…"
        )
        self.concept_query.textChanged.connect(self._filter_concepts)
        row.addWidget(self.concept_query, 1)
        layout.addLayout(row)

        splitter = QSplitter(Qt.Vertical)
        self.concept_table = DataTable(
            ["Conceito", "Ocorrências", "Evidências", "Seções", "Confiança"]
        )
        self.concept_table.itemSelectionChanged.connect(self._on_concept_selected)
        splitter.addWidget(self.concept_table)
        self.concept_detail = QTextBrowser()
        self.concept_detail.setOpenExternalLinks(False)
        splitter.addWidget(self.concept_detail)
        splitter.setSizes([250, 280])
        layout.addWidget(splitter, 1)

        actions = QHBoxLayout()
        self.concept_status = QLabel("Nenhum conceito disponível.")
        self.concept_status.setStyleSheet("color:#5b6673;")
        actions.addWidget(self.concept_status, 1)
        self.btn_concept_add = QPushButton("＋ Adicionar conceito ao painel")
        self.btn_concept_add.setEnabled(False)
        self.btn_concept_add.clicked.connect(self._add_selected_concept)
        actions.addWidget(self.btn_concept_add)
        self.btn_concept_filter = QPushButton("Filtrar evidências por conceito")
        self.btn_concept_filter.setEnabled(False)
        self.btn_concept_filter.clicked.connect(self._filter_by_concept)
        actions.addWidget(self.btn_concept_filter)
        layout.addLayout(actions)
        self.tabs.addTab(page, "🧩 Conceitos")

    def _build_filters_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.addWidget(HelpPanel("explore_filters", expanded=False))

        row = QHBoxLayout()
        self.filter_query = QLineEdit()
        self.filter_query.setPlaceholderText(
            "Busca textual dentro das evidências (opcional)…"
        )
        self.filter_query.returnPressed.connect(self.apply_filters)
        row.addWidget(self.filter_query, 1)
        self.btn_apply_filters = QPushButton("Aplicar filtros")
        self.btn_apply_filters.clicked.connect(self.apply_filters)
        row.addWidget(self.btn_apply_filters)
        self.btn_clear_filters = QPushButton("Limpar")
        self.btn_clear_filters.clicked.connect(self.clear_filters)
        row.addWidget(self.btn_clear_filters)
        layout.addLayout(row)

        self.filter_status = QLabel(
            "Os filtros são combinados por E entre facetas e por OU dentro "
            "de cada faceta. Ficam salvos em settings.json."
        )
        self.filter_status.setStyleSheet("color:#5b6673;")
        self.filter_status.setWordWrap(True)
        layout.addWidget(self.filter_status)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        grid = QGridLayout(content)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(8)
        for number, (key, label) in enumerate(_FACET_LABELS.items()):
            box = QGroupBox(label)
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(6, 6, 6, 6)
            widget = QListWidget()
            widget.setSelectionMode(QAbstractItemView.ExtendedSelection)
            widget.setMinimumHeight(120)
            widget.setMaximumHeight(170)
            box_layout.addWidget(widget)
            self._filter_lists[key] = widget
            grid.addWidget(box, number // 3, number % 3)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        self.tabs.addTab(page, "🧮 Filtros")

    def _build_document_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.addWidget(HelpPanel("explore_document", expanded=False))

        kpis = QHBoxLayout()
        self.kpi_doc_evidence = KpiTile("Evidências")
        self.kpi_doc_sections = KpiTile("Seções")
        self.kpi_doc_concepts = KpiTile("Conceitos")
        self.kpi_doc_coverage = KpiTile("Cobertura de seção")
        for tile in (self.kpi_doc_evidence, self.kpi_doc_sections,
                     self.kpi_doc_concepts, self.kpi_doc_coverage):
            kpis.addWidget(tile)
        layout.addLayout(kpis)

        splitter = QSplitter(Qt.Vertical)
        self.document_summary = QTextBrowser()
        self.document_summary.setOpenExternalLinks(False)
        splitter.addWidget(self.document_summary)
        self.document_table = DataTable(
            ["Seção", "Papel", "Palavras", "Evidências", "Naturezas", "Anos"]
        )
        self.section_table = self.document_table
        splitter.addWidget(self.document_table)
        splitter.setSizes([260, 260])
        layout.addWidget(splitter, 1)
        self.tabs.addTab(page, "📄 Documento")

    def _build_panel_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.addWidget(HelpPanel("explore_panel", expanded=False))

        kpis = QHBoxLayout()
        self.kpi_panel_items = KpiTile("Itens no painel")
        self.kpi_panel_evidence = KpiTile("Evidências salvas")
        self.kpi_panel_questions = KpiTile("Perguntas salvas")
        self.kpi_panel_queries = KpiTile("Buscas registradas")
        for tile in (self.kpi_panel_items, self.kpi_panel_evidence,
                     self.kpi_panel_questions, self.kpi_panel_queries):
            kpis.addWidget(tile)
        layout.addLayout(kpis)

        splitter = QSplitter(Qt.Vertical)
        upper = QWidget()
        upper_layout = QHBoxLayout(upper)
        upper_layout.setContentsMargins(0, 0, 0, 0)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self.panel_table = DataTable(
            ["#", "Tipo", "Título", "Local", "Nota"]
        )
        self.panel_table.itemSelectionChanged.connect(self._on_panel_selected)
        left_layout.addWidget(self.panel_table, 1)
        upper_layout.addWidget(left, 3)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self.panel_detail = QTextBrowser()
        self.panel_detail.setOpenExternalLinks(False)
        right_layout.addWidget(self.panel_detail, 1)
        self.panel_notes = QPlainTextEdit()
        self.panel_notes.setPlaceholderText(
            "Observações gerais do painel (salvas no JSON)…"
        )
        self.panel_notes.setMaximumHeight(100)
        right_layout.addWidget(self.panel_notes)
        upper_layout.addWidget(right, 2)
        splitter.addWidget(upper)

        self.questions_table = DataTable(
            ["#", "Tipo", "Pergunta", "Base", "Confiança"]
        )
        self.questions_table.itemSelectionChanged.connect(
            self._on_question_selected)
        self.questions_table.cellDoubleClicked.connect(
            lambda *_: self._add_selected_question())
        splitter.addWidget(self.questions_table)
        splitter.setSizes([320, 220])
        layout.addWidget(splitter, 1)

        actions = QHBoxLayout()
        self.panel_status = QLabel("Painel carregado do diretório do usuário.")
        self.panel_status.setStyleSheet("color:#5b6673;")
        actions.addWidget(self.panel_status, 1)
        self.btn_panel_add_note = QPushButton("＋ Nota")
        self.btn_panel_add_note.clicked.connect(self.add_note_dialog)
        actions.addWidget(self.btn_panel_add_note)
        self.btn_panel_add_question = QPushButton("＋ Pergunta selecionada")
        self.btn_panel_add_question.clicked.connect(
            self._add_selected_question)
        actions.addWidget(self.btn_panel_add_question)
        self.btn_panel_remove = QPushButton("Remover item")
        self.btn_panel_remove.clicked.connect(self.remove_selected_panel_item)
        actions.addWidget(self.btn_panel_remove)
        self.btn_panel_save = QPushButton("Salvar painel")
        self.btn_panel_save.clicked.connect(self.save_panel)
        actions.addWidget(self.btn_panel_save)
        layout.addLayout(actions)

        export_row = QHBoxLayout()
        export_row.addWidget(QLabel("Exportar painel:"))
        for label, fmt in (
            ("Markdown", "md"), ("CSV", "csv"), ("JSON", "json"),
        ):
            button = QPushButton(label)
            button.clicked.connect(lambda _=False, value=fmt: self.export_panel(value))
            export_row.addWidget(button)
        export_row.addStretch()
        layout.addLayout(export_row)
        self.tabs.addTab(page, "🗂️ Pesquisa")

    # ------------------------------------------------------------------
    # Dados
    # ------------------------------------------------------------------
    def clear(self) -> None:
        self.result = {}
        self.text = ""
        self.exploration = {}
        self.investigation = {}
        self._search_matches = []
        self.search_table.set_rows([])
        self.search_detail.clear()
        self.search_status.setText("Nenhuma busca executada.")
        self.btn_search_add.setEnabled(False)
        self.evidence_panel.set_entries([])
        self.evidence_status.setText("Nenhum resultado disponível.")
        self.concept_table.set_rows([])
        self.concept_detail.clear()
        self.document_summary.clear()
        self.document_table.set_rows([])
        self.questions_table.set_rows([])
        for tile in (
            self.kpi_doc_evidence, self.kpi_doc_sections,
            self.kpi_doc_concepts, self.kpi_doc_coverage,
            self.kpi_panel_items, self.kpi_panel_evidence,
            self.kpi_panel_questions, self.kpi_panel_queries,
        ):
            tile.set_value("—")

    def update_results(self, result: dict, text: str = "") -> None:
        self.result = result or {}
        self.text = text or self.text or ""
        payload = self.result.get("exploration") or {}
        if not payload:
            try:
                payload = exploration.build(
                    self.text, self.result,
                    meta=self.result.get("meta") or {},
                )
            except Exception as exc:  # noqa: BLE001 - legado não deve quebrar
                payload = {}
                self.status.emit(
                    f"Exploração indisponível: {type(exc).__name__}: {exc}"
                )
        self.exploration = payload
        investigation_payload = self.result.get("investigation") or {}
        if not investigation_payload:
            try:
                investigation_payload = investigation.build(
                    self.text, self.result,
                    meta=self.result.get("meta") or {},
                )
            except Exception as exc:  # noqa: BLE001
                investigation_payload = {}
                self.status.emit(
                    f"Investigação indisponível: {type(exc).__name__}: {exc}"
                )
        self.investigation = investigation_payload
        self.evidence_panel.set_text(self.text)
        self._sync_panel_document()
        self._populate_filters()
        self.refresh_evidence()
        self._populate_concepts()
        self._populate_document()
        self._populate_questions()
        self._restore_panel_view()

    # ------------------------------------------------------------------
    # Busca
    # ------------------------------------------------------------------
    def run_search(self) -> None:
        query = self.search_input.text().strip()
        if not self.text:
            self.status.emit("Carregue e analise um documento para buscar.")
            return
        if not query:
            self.search_status.setText("Digite uma consulta.")
            return
        payload = context_search.search(
            self.text, query,
            case_sensitive=self.search_case.currentIndex() == 1,
            limit=self.search_limit.value(),
            language=str(self.result.get("language") or "PT-BR"),
            page_spans=(self.result.get("meta") or {}).get("page_spans") or [],
        )
        self._search_matches = list(payload.get("matches") or [])
        rows = []
        for number, match in enumerate(self._search_matches, start=1):
            rows.append([
                number,
                (match.get("snippet") or match.get("text") or "")[:160],
                _location(match) or "—",
                "determinístico",
                "alta",
            ])
        self.search_table.set_rows(rows)
        total = int(payload.get("total") or 0)
        shown = len(self._search_matches)
        message = f"{total} ocorrência(s); exibindo {shown}."
        if payload.get("truncated"):
            message += " A lista foi limitada."
        if payload.get("warnings"):
            message += " " + "; ".join(payload["warnings"][:2])
        self.search_status.setText(message)
        if self._search_matches:
            self.search_table.selectRow(0)
            self._on_search_selected()
            self._show_search_detail(self._search_matches[0])
        else:
            self.search_detail.setHtml(
                "<p style='color:#5b6673'>Nenhuma ocorrência encontrada.</p>"
            )
            self.btn_search_add.setEnabled(False)
        try:
            research_panel.record_query(self.panel, query, total)
        except Exception:  # noqa: BLE001
            pass
        self.status.emit(message)

    def _on_search_selected(self) -> None:
        rows = self.search_table.selectionModel().selectedRows()
        if not rows:
            return
        index = self.search_table.source_index(rows[0].row())
        if 0 <= index < len(self._search_matches):
            self._show_search_detail(self._search_matches[index])
            self.btn_search_add.setEnabled(True)

    def _show_search_detail(self, match: dict) -> None:
        entry = _match_entry(match)
        self.search_detail.setHtml(evidence_html(entry, self.text))
        self._current_search = entry

    def _add_selected_search(self) -> None:
        entry = getattr(self, "_current_search", None)
        if not entry:
            return
        self.add_evidence(entry)

    # ------------------------------------------------------------------
    # Evidências
    # ------------------------------------------------------------------
    def refresh_evidence(self) -> None:
        entries = list((self.exploration or {}).get("evidence") or [])
        active = {
            key: value for key, value in (self.filters or {}).items()
            if value not in (None, "", [])
        }
        selected = exploration.filter_evidence(entries, active)
        query = self.evidence_query.text().strip().lower()
        if query:
            selected = [
                entry for entry in selected
                if query in " ".join([
                    str(entry.get("text") or ""),
                    str(entry.get("label") or ""),
                    str(entry.get("source_label") or ""),
                    " ".join(entry.get("authors") or []),
                    " ".join(entry.get("concepts") or []),
                ]).lower()
            ]
        total = len(entries)
        self.evidence_panel.set_entries(selected)
        summary = exploration.summarize_filters(active)
        message = f"{len(selected)} de {total} evidências"
        if summary:
            message += f" · filtros: {summary}"
        if query:
            message += f" · texto: {query}"
        self.evidence_status.setText(message)
        self.filter_status.setText(
            f"{len(selected)} de {total} evidências visíveis."
            + (f" Filtros ativos: {summary}." if summary else "")
        )
        self.status.emit(message)

    def add_evidence(self, entry: dict) -> None:
        try:
            item = research_panel.add_evidence(self.panel, entry)
            self.save_panel(silent=True)
            self.status.emit(f"Evidência adicionada ao painel: {item.get('title')}.")
        except Exception as exc:  # noqa: BLE001
            self.status.emit(f"Falha ao adicionar evidência: {exc}")

    def _reveal_evidence(self, entry: dict) -> None:
        """Pede à janela principal que selecione o trecho no texto original."""
        try:
            start = int(entry.get("start"))
            end = int(entry.get("end"))
        except (TypeError, ValueError):
            self.status.emit("Evidência sem offsets para localizar no texto.")
            return
        if end <= start:
            end = start + 1
        self.reveal_requested.emit(start, end)

    # ------------------------------------------------------------------
    # Conceitos
    # ------------------------------------------------------------------
    def _populate_concepts(self) -> None:
        self._concepts = list((self.exploration or {}).get("concepts") or [])
        self._filter_concepts()

    def _filter_concepts(self) -> None:
        query = self.concept_query.text().strip().lower()
        rows = []
        visible = []
        for concept in self._concepts:
            haystack = " ".join([
                str(concept.get("term") or ""),
                " ".join(concept.get("variants") or []),
                " ".join(
                    str(item.get("text") or "")
                    for item in concept.get("definitions") or []
                    if isinstance(item, dict)
                ),
            ]).lower()
            if query and query not in haystack:
                continue
            visible.append(concept)
            sections = ", ".join(
                str(item.get("value") or "")
                for item in (concept.get("sections") or [])[:3]
            )
            rows.append([
                concept.get("term") or "",
                int(concept.get("occurrences") or 0),
                int(concept.get("evidence_count") or 0),
                sections or "—",
                concept.get("confidence") or "baixa",
            ])
        self._visible_concepts = visible
        self.concept_table.set_rows(rows)
        self.concept_status.setText(f"{len(visible)} conceito(s) no catálogo.")
        self.btn_concept_add.setEnabled(False)
        self.btn_concept_filter.setEnabled(False)
        self.concept_detail.setHtml(
            "<p style='color:#5b6673'>Selecione um conceito para ver "
            "definições, relações e evidências.</p>"
        )

    def _on_concept_selected(self) -> None:
        rows = self.concept_table.selectionModel().selectedRows()
        if not rows:
            return
        index = self.concept_table.source_index(rows[0].row())
        if not (0 <= index < len(getattr(self, "_visible_concepts", []))):
            return
        self._current_concept = self._visible_concepts[index]
        self.concept_detail.setHtml(self._concept_html(self._current_concept))
        self.btn_concept_add.setEnabled(True)
        self.btn_concept_filter.setEnabled(True)

    def _concept_html(self, concept: dict) -> str:
        definitions = "".join(
            f"<li>{html.escape(str(item.get('text') or ''))} "
            f"<span style='color:#5b6673'>({html.escape(str(item.get('source') or ''))})</span></li>"
            for item in concept.get("definitions") or []
            if isinstance(item, dict)
        ) or "<li>Sem definição explícita no texto.</li>"
        relations = "".join(
            f"<li>{html.escape(str(item.get('type') or ''))} → "
            f"{html.escape(str(item.get('target') or ''))}</li>"
            for item in concept.get("relations") or []
        ) or "<li>Sem relações registradas.</li>"
        sections = ", ".join(
            f"{html.escape(str(item.get('value') or ''))} ({item.get('count')})"
            for item in concept.get("sections") or []
        ) or "—"
        years = ", ".join(
            f"{html.escape(str(item.get('value') or ''))} ({item.get('count')})"
            for item in concept.get("years") or []
        ) or "—"
        variants = ", ".join(concept.get("variants") or []) or "—"
        return (
            "<style>body { font-family:'Segoe UI',sans-serif; font-size:12px;"
            " color:#1f2937; } h3 { color:#1c53b8; margin:0 0 6px; }"
            " h4 { margin:10px 0 4px; color:#1c53b8; }"
            " ul { margin:4px 0 0 18px; }</style>"
            f"<h3>{html.escape(str(concept.get('term') or 'Conceito'))}</h3>"
            f"<p><b>Ocorrências:</b> {int(concept.get('occurrences') or 0)} · "
            f"<b>Evidências:</b> {int(concept.get('evidence_count') or 0)} · "
            f"<b>Confiança:</b> {html.escape(str(concept.get('confidence') or ''))}</p>"
            f"<p><b>Variantes:</b> {html.escape(variants)}</p>"
            f"<h4>Definições</h4><ul>{definitions}</ul>"
            f"<h4>Relações</h4><ul>{relations}</ul>"
            f"<h4>Seções</h4><p>{sections}</p>"
            f"<h4>Anos</h4><p>{years}</p>"
        )

    def _add_selected_concept(self) -> None:
        concept = getattr(self, "_current_concept", None)
        if not concept:
            return
        try:
            research_panel.add_concept(self.panel, concept)
            self.save_panel(silent=True)
            self.status.emit(
                f"Conceito adicionado ao painel: {concept.get('term')}.")
        except Exception as exc:  # noqa: BLE001
            self.status.emit(f"Falha ao adicionar conceito: {exc}")

    def _filter_by_concept(self) -> None:
        concept = getattr(self, "_current_concept", None)
        if not concept:
            return
        self.filters = dict(self.filters or _empty_filters())
        self.filters["concepts"] = [concept.get("term") or ""]
        self._populate_filters()
        self._save_filters()
        self.refresh_evidence()
        self.tabs.setCurrentIndex(1)

    # ------------------------------------------------------------------
    # Filtros
    # ------------------------------------------------------------------
    def _populate_filters(self) -> None:
        facets = {}
        entries = list((self.exploration or {}).get("evidence") or [])
        try:
            facets = exploration.facet_options(entries, self.filters)
        except Exception:  # noqa: BLE001
            facets = {}
        for key, widget in self._filter_lists.items():
            selected_values = set(self.filters.get(key) or [])
            widget.blockSignals(True)
            widget.clear()
            for option in facets.get(key) or []:
                value = str(option.get("value") or "")
                label = str(option.get("label") or value)
                count = option.get("count")
                item = QListWidgetItem(f"{label} ({count})")
                item.setData(Qt.UserRole, value)
                widget.addItem(item)
                if value in selected_values:
                    item.setSelected(True)
            widget.blockSignals(False)
        self.filter_query.setText(str(self.filters.get("query") or ""))
        self.filter_status.setText(
            f"{len(entries)} evidências no catálogo. "
            f"Filtros ativos: {exploration.summarize_filters(self.filters) or 'nenhum'}."
        )

    def _read_filters(self) -> dict:
        filters = _empty_filters()
        for key, widget in self._filter_lists.items():
            values = []
            for item in widget.selectedItems():
                value = item.data(Qt.UserRole)
                if value:
                    values.append(str(value))
            filters[key] = values
        filters["query"] = self.filter_query.text().strip()
        return filters

    def apply_filters(self) -> None:
        self.filters = self._read_filters()
        if self.exploration:
            self.exploration = exploration.apply(self.exploration, self.filters)
        self._save_filters()
        self.refresh_evidence()
        self._populate_filters()
        summary = exploration.summarize_filters(self.filters) or "nenhum"
        self.status.emit(f"Filtros aplicados: {summary}.")

    def clear_filters(self) -> None:
        self.filters = _empty_filters()
        for widget in self._filter_lists.values():
            widget.clearSelection()
        self.filter_query.clear()
        if self.exploration:
            self.exploration = exploration.apply(self.exploration, self.filters)
        self._save_filters()
        self.refresh_evidence()
        self._populate_filters()
        self.status.emit("Filtros limpos.")

    def _save_filters(self) -> None:
        try:
            research_panel.save_filters(self.filters)
            research_panel.set_filters(self.panel, self.filters)
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------
    # Documento e seções
    # ------------------------------------------------------------------
    def _populate_document(self) -> None:
        payload = self.exploration or {}
        profile = payload.get("profile") or {}
        document = profile.get("document") or {}
        counts = profile.get("counts") or {}
        coverage = profile.get("coverage") or {}
        self.kpi_doc_evidence.set_value(counts.get("evidence", "—"))
        self.kpi_doc_sections.set_value(counts.get("sections", "—"))
        self.kpi_doc_concepts.set_value(counts.get("concepts", "—"))
        total = max(1, int(counts.get("evidence") or 0))
        self.kpi_doc_coverage.set_value(
            f"{round(100 * int(coverage.get('with_section') or 0) / total)}%"
        )
        natures = ", ".join(
            f"{item.get('label')}: {item.get('count')}"
            for item in counts.get("by_nature") or []
        ) or "—"
        authors = ", ".join(
            f"{item.get('value')} ({item.get('count')})"
            for item in (counts.get("top_authors") or [])[:8]
        ) or "—"
        years = ", ".join(
            f"{item.get('value')} ({item.get('count')})"
            for item in (counts.get("years") or [])[:12]
        ) or "—"
        self.document_summary.setHtml(
            "<style>body { font-family:'Segoe UI',sans-serif; font-size:12px;"
            " color:#1f2937; } h3 { color:#1c53b8; margin:0 0 6px; }"
            " th { text-align:left; color:#5b6673; padding:2px 12px 2px 0; }"
            " td { padding:2px 0; }</style>"
            f"<h3>{html.escape(str(document.get('filename') or 'Documento'))}</h3>"
            "<table>"
            f"<tr><th>Idioma</th><td>{html.escape(str(document.get('language_label') or document.get('language') or '—'))}</td></tr>"
            f"<tr><th>Palavras</th><td>{int(document.get('words') or 0)}</td></tr>"
            f"<tr><th>Sentenças</th><td>{int(document.get('sentences') or 0)}</td></tr>"
            f"<tr><th>Parágrafos</th><td>{int(document.get('paragraphs') or 0)}</td></tr>"
            f"<tr><th>Páginas</th><td>{int(document.get('pages') or 0)}</td></tr>"
            f"<tr><th>Naturezas</th><td>{html.escape(natures)}</td></tr>"
            f"<tr><th>Autores</th><td>{html.escape(authors)}</td></tr>"
            f"<tr><th>Anos</th><td>{html.escape(years)}</td></tr>"
            f"<tr><th>Cobertura</th><td>{html.escape(json_like(coverage))}</td></tr>"
            "</table>"
            "<p style='color:#5b6673'>Página só é mostrada quando veio da "
            "extração (page_spans); nunca é estimada.</p>"
        )
        rows = []
        for section in payload.get("sections") or []:
            natures = ", ".join(
                f"{item.get('value')} ({item.get('count')})"
                for item in section.get("nature_counts") or []
            ) or "—"
            years = ", ".join(
                str(item.get("value") or "")
                for item in section.get("years") or []
            ) or "—"
            rows.append([
                section.get("title") or "Seção",
                section.get("role_label") or section.get("role") or "—",
                int(section.get("words") or 0),
                int(section.get("evidence_count") or 0),
                natures,
                years,
            ])
        self.document_table.set_rows(rows)
        self.document_summary.setAccessibleName("Perfil do documento")
        self.document_table.setAccessibleName("Análise por seção")

    # ------------------------------------------------------------------
    # Pesquisa/perguntas
    # ------------------------------------------------------------------
    def _populate_questions(self) -> None:
        questions = list((self.investigation or {}).get("questions") or [])
        rows = []
        for number, question in enumerate(questions, start=1):
            rows.append([
                number,
                question.get("kind") or "",
                question.get("question") or "",
                question.get("basis") or "",
                question.get("confidence") or "baixa",
            ])
        self._questions = questions
        self.questions_table.set_rows(rows)
        self.questions_table.setAccessibleName("Perguntas investigativas")

    def _on_question_selected(self) -> None:
        rows = self.questions_table.selectionModel().selectedRows()
        if not rows:
            return
        index = self.questions_table.source_index(rows[0].row())
        if not (0 <= index < len(getattr(self, "_questions", []))):
            return
        question = self._questions[index]
        self._current_question = question
        evidence = ""
        for item in question.get("evidence") or []:
            evidence += (
                "<li>" + html.escape(str(item.get("text") or "")) + "</li>"
            )
        self.panel_detail.setHtml(
            "<style>body { font-family:'Segoe UI',sans-serif; font-size:12px;"
            " color:#1f2937; }</style>"
            f"<h3>{html.escape(str(question.get('question') or ''))}</h3>"
            f"<p><b>Base:</b> {html.escape(str(question.get('basis') or ''))} · "
            f"<b>Natureza da base:</b> {html.escape(str(question.get('basis_nature') or ''))} · "
            f"<b>Confiança:</b> {html.escape(str(question.get('confidence') or ''))}</p>"
            f"<p><b>Por que foi gerada:</b> {html.escape(str(question.get('rationale') or '—'))}</p>"
            f"<h4>Evidências de origem</h4><ul>{evidence or '<li>—</li>'}</ul>"
            "<p style='color:#5b6673'>Pergunta gerada por template; exige "
            "revisão humana e não emite veredito.</p>"
        )

    def _add_selected_question(self) -> None:
        rows = self.questions_table.selectionModel().selectedRows()
        if not rows:
            return
        index = self.questions_table.source_index(rows[0].row())
        if not (0 <= index < len(getattr(self, "_questions", []))):
            return
        try:
            research_panel.add_question(self.panel, self._questions[index])
            self.save_panel(silent=True)
            self.status.emit("Pergunta adicionada ao painel.")
        except Exception as exc:  # noqa: BLE001
            self.status.emit(f"Falha ao adicionar pergunta: {exc}")

    def _sync_panel_document(self) -> None:
        document = ((self.exploration or {}).get("profile") or {}).get(
            "document") or {}
        if not document:
            document = self.result.get("meta") or {}
        current = self.panel.get("document") or {}
        filename = document.get("filename") or self.result.get("title") or ""
        if filename and current.get("filename") != filename:
            self.panel["document"] = {
                "filename": filename,
                "path": document.get("path") or "",
                "title": document.get("title") or filename,
                "language": document.get("language") or "",
            }

    # ------------------------------------------------------------------
    # Painel
    # ------------------------------------------------------------------
    def _restore_panel_view(self) -> None:
        if not isinstance(self.panel, dict):
            self.panel = research_panel.new_panel()
        self.panel_notes.blockSignals(True)
        self.panel_notes.setPlainText(str(self.panel.get("notes") or ""))
        self.panel_notes.blockSignals(False)
        self._refresh_panel_table()

    def _refresh_panel_table(self) -> None:
        items = list(self.panel.get("items") or [])
        rows = []
        for number, item in enumerate(items, start=1):
            rows.append([
                number,
                item.get("kind") or "",
                item.get("title") or item.get("label") or "",
                _location(item) or "—",
                (item.get("note") or "")[:120],
            ])
        self.panel_table.set_rows(rows)
        counts = research_panel.summary(self.panel).get("counts") or {}
        self.kpi_panel_items.set_value(len(items))
        self.kpi_panel_evidence.set_value(counts.get("evidence", 0))
        self.kpi_panel_questions.set_value(counts.get("question", 0))
        self.kpi_panel_queries.set_value(len(self.panel.get("queries") or []))
        self.panel_status.setText(
            f"{len(items)} item(ns) no painel · "
            f"atualizado em {self.panel.get('updated_at') or '—'}"
        )

    def _on_panel_selected(self) -> None:
        rows = self.panel_table.selectionModel().selectedRows()
        if not rows:
            return
        index = self.panel_table.source_index(rows[0].row())
        items = self.panel.get("items") or []
        if not (0 <= index < len(items)):
            return
        item = items[index]
        self._current_panel_item = item
        body = [
            f"<h3>{html.escape(str(item.get('title') or item.get('id') or ''))}</h3>",
            f"<p><b>Tipo:</b> {html.escape(str(item.get('kind') or ''))} · "
            f"<b>Adicionado:</b> {html.escape(str(item.get('added_at') or ''))}</p>",
        ]
        if item.get("source_label"):
            body.append(
                f"<p><b>Fonte:</b> {html.escape(str(item.get('source_label')))}</p>")
        if item.get("text"):
            body.append(
                f"<blockquote>{html.escape(str(item.get('text')))}</blockquote>")
        if item.get("question"):
            body.append(
                f"<p><b>Pergunta:</b> {html.escape(str(item.get('question')))}</p>")
        if item.get("note"):
            body.append(
                f"<p><b>Nota:</b> {html.escape(str(item.get('note')))}</p>")
        self.panel_detail.setHtml("".join(body))

    def save_panel(self, silent: bool = False) -> None:
        try:
            research_panel.set_notes(
                self.panel, self.panel_notes.toPlainText())
            research_panel.set_filters(self.panel, self.filters)
            target = research_panel.save_panel(self.panel)
            self._refresh_panel_table()
            self.panel_changed.emit(dict(self.panel))
            if not silent:
                self.status.emit(f"Painel salvo em {target}.")
        except Exception as exc:  # noqa: BLE001
            self.status.emit(f"Falha ao salvar painel: {exc}")

    def add_note_dialog(self) -> None:
        title, ok = QInputDialog.getText(
            self, "Nova nota", "Título da nota:"
        )
        if not ok or not title.strip():
            return
        body, ok = QInputDialog.getMultiLineText(
            self, "Nova nota", "Texto da nota:"
        )
        if not ok:
            return
        try:
            research_panel.add_note(self.panel, title, body)
            self.save_panel(silent=True)
            self.status.emit("Nota adicionada ao painel.")
        except Exception as exc:  # noqa: BLE001
            self.status.emit(f"Falha ao adicionar nota: {exc}")

    def remove_selected_panel_item(self) -> None:
        rows = self.panel_table.selectionModel().selectedRows()
        if not rows:
            return
        index = self.panel_table.source_index(rows[0].row())
        items = self.panel.get("items") or []
        if not (0 <= index < len(items)):
            return
        item = items[index]
        if research_panel.remove_item(self.panel, item.get("id") or ""):
            self.save_panel(silent=True)
            self.status.emit("Item removido do painel.")

    def export_panel(self, fmt: str = "md") -> None:
        extension = {"md": "md", "csv": "csv", "json": "json"}.get(fmt, "md")
        default = research_panel.default_export_path(extension)
        filters = {
            "md": "Markdown (*.md)",
            "csv": "CSV (*.csv)",
            "json": "JSON (*.json)",
        }.get(extension, "Todos (*.*)")
        filename, _ = QFileDialog.getSaveFileName(
            self, f"Exportar painel ({extension})", str(default), filters
        )
        if not filename:
            return
        try:
            target = research_panel.export_panel(self.panel, filename, extension)
            self.status.emit(f"Painel exportado em {target}.")
        except Exception as exc:  # noqa: BLE001
            self.status.emit(f"Falha ao exportar painel: {exc}")
            QMessageBox.warning(self, "Exportar painel", str(exc))


def json_like(value: dict) -> str:
    """Resumo legível da cobertura, sem depender de json na interface."""
    parts = []
    for key in ("with_page", "with_section", "with_author", "with_year",
                "with_concept"):
        if key in (value or {}):
            parts.append(f"{key.replace('with_', '')}: {value[key]}")
    return " · ".join(parts) or "—"


__all__ = ["ExploreView"]
