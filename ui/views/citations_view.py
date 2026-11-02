#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Aba: Referências, citações, citações diretas, índice onomástico, conceitos e KWIC."""

import copy
import html as html_lib
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMessageBox,
    QPushButton, QSpinBox, QTabWidget, QTextBrowser, QVBoxLayout, QWidget, QFileDialog,
)

from core import onomastic as onomastic_core
from core import quotes as quotes_core
from core import reference_format
from core.kwic import kwic as run_kwic
from ui.widgets.common import DataTable
from ui.widgets.help_panel import HelpPanel


def _safe_html(text: str) -> str:
    """Escapa o texto e reativa apenas as marcas de itálico do formatador."""
    escaped = html_lib.escape(str(text or ""))
    return escaped.replace("&lt;i&gt;", "<i>").replace("&lt;/i&gt;", "</i>")


def _confidence_label(item: dict) -> str:
    from reports import exporters
    return exporters.confidence_text(item) or "—"


def _review_label(item: dict) -> str:
    from reports import exporters
    return exporters.reference_review(item) or "—"


class CitationsView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._text = ""
        self._result = None
        self._onomastic = []
        self._onomastic_original = []
        self._references_items = []
        self._quotes_items = []
        self._quotes_filtered = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        self.help_panel = HelpPanel("citations")
        layout.addWidget(self.help_panel)

        self.tabs = QTabWidget()

        # Referências bibliográficas
        ref_widget = QWidget()
        ref_layout = QVBoxLayout(ref_widget)
        ref_layout.setContentsMargins(8, 8, 8, 8)
        self.ref_help = HelpPanel("citations_references", expanded=False)
        ref_layout.addWidget(self.ref_help)
        from core import explanations as _expl
        self.ref_info = QLabel(_expl.ANALYSIS_EXPLANATIONS.get('citacoes_referencias', ''))
        self.ref_info.setWordWrap(True)
        self.ref_info.setStyleSheet("color:#5b6673;")
        ref_layout.addWidget(self.ref_info)
        self.ref_summary = QLabel("—")
        self.ref_summary.setStyleSheet("color:#5b6673;")
        ref_layout.addWidget(self.ref_summary)
        ref_ctrl = QHBoxLayout()
        self.btn_import_bib = QPushButton("Importar BibTeX/RIS")
        self.btn_import_bib.clicked.connect(self._import_references)
        ref_ctrl.addWidget(self.btn_import_bib)
        self.btn_export_refs = QPushButton("Exportar BibTeX/RIS")
        self.btn_export_refs.setToolTip(
            "Salva as referências atuais em BibTeX (.bib) ou RIS (.ris)."
        )
        self.btn_export_refs.clicked.connect(self._export_references)
        self.btn_export_refs.setEnabled(False)
        ref_ctrl.addWidget(self.btn_export_refs)
        self.btn_dedup = QPushButton("Detectar duplicatas")
        self.btn_dedup.clicked.connect(self._detect_duplicates)
        ref_ctrl.addWidget(self.btn_dedup)
        ref_ctrl.addWidget(QLabel("Estilo:"))
        self.ref_style = QComboBox()
        for key, label in reference_format.STYLES.items():
            self.ref_style.addItem(label, key)
        self.ref_style.setToolTip(
            "Estilo usado apenas na pré-visualização; o texto extraído e os "
            "metadados não são alterados."
        )
        self.ref_style.currentIndexChanged.connect(self._refresh_reference_preview)
        self.ref_style.setMinimumWidth(180)
        ref_ctrl.addWidget(self.ref_style)
        ref_ctrl.addStretch()
        ref_layout.addLayout(ref_ctrl)
        self.ref_table = DataTable(
            ["Autor", "Ano", "Título", "Fonte", "Tipo", "Confiança", "Revisão"],
            search=True,
        )
        self.ref_table.itemSelectionChanged.connect(self._refresh_reference_detail)
        self.ref_table.pageChanged.connect(self._sync_reference_roles)
        ref_layout.addWidget(self.ref_table, 3)

        self.ref_detail_tabs = QTabWidget()
        self.ref_preview = QTextBrowser()
        self.ref_preview.setOpenExternalLinks(True)
        self.ref_detail = QTextBrowser()
        self.ref_detail_tabs.addTab(self.ref_preview, "Pré-visualização")
        self.ref_detail_tabs.addTab(self.ref_detail, "Detalhes da extração")
        ref_layout.addWidget(self.ref_detail_tabs, 2)
        self.tabs.addTab(ref_widget, "📚 Referências")

        # Citações no corpo
        cit_widget = QWidget()
        cit_layout = QVBoxLayout(cit_widget)
        cit_layout.setContentsMargins(8, 8, 8, 8)
        self.cit_help = HelpPanel("citations_body", expanded=False)
        cit_layout.addWidget(self.cit_help)
        self.cit_summary = QLabel("—")
        self.cit_summary.setStyleSheet("color:#5b6673;")
        cit_layout.addWidget(self.cit_summary)
        self.cit_table = DataTable(["Tipo", "Citação", "Contexto"])
        cit_layout.addWidget(self.cit_table)
        self.tabs.addTab(cit_widget, "📑 Citações")

        # Citações diretas do autor
        quote_widget = QWidget()
        quote_layout = QVBoxLayout(quote_widget)
        quote_layout.setContentsMargins(8, 8, 8, 8)
        self.quote_help = HelpPanel("citations_direct", expanded=False)
        quote_layout.addWidget(self.quote_help)
        self.quote_info = QLabel(_expl.ANALYSIS_EXPLANATIONS.get('citacoes_diretas', ''))
        self.quote_info.setWordWrap(True)
        self.quote_info.setStyleSheet("color:#5b6673;")
        quote_layout.addWidget(self.quote_info)
        self.quote_summary = QLabel("—")
        self.quote_summary.setStyleSheet("color:#5b6673;")
        quote_layout.addWidget(self.quote_summary)
        quote_ctrl = QHBoxLayout()
        quote_ctrl.addWidget(QLabel("Mínimo de palavras entre aspas:"))
        self.quote_min_words = QSpinBox()
        self.quote_min_words.setRange(1, 50)
        self.quote_min_words.setValue(6)
        quote_ctrl.addWidget(self.quote_min_words)
        self.quote_update = QPushButton("🔄  Atualizar")
        self.quote_update.clicked.connect(self._update_quotes)
        quote_ctrl.addWidget(self.quote_update)
        quote_ctrl.addStretch()
        quote_layout.addLayout(quote_ctrl)

        quote_filters = QHBoxLayout()
        quote_filters.addWidget(QLabel("Filtrar:"))
        self.quote_filter_text = QLineEdit()
        self.quote_filter_text.setPlaceholderText("trecho, autor ou contexto…")
        self.quote_filter_text.textChanged.connect(self._filter_quotes)
        quote_filters.addWidget(self.quote_filter_text, 1)
        quote_filters.addWidget(QLabel("Tipo:"))
        self.quote_filter_type = QComboBox()
        for label, value in (
            ("Todos", ""), ("Curtas", "curta"), ("Longas", "longa"),
        ):
            self.quote_filter_type.addItem(label, value)
        self.quote_filter_type.currentIndexChanged.connect(self._filter_quotes)
        quote_filters.addWidget(self.quote_filter_type)
        quote_filters.addWidget(QLabel("Autor:"))
        self.quote_filter_author = QComboBox()
        self.quote_filter_author.addItem("Todos", "")
        self.quote_filter_author.currentIndexChanged.connect(self._filter_quotes)
        quote_filters.addWidget(self.quote_filter_author)
        self.btn_export_quotes = QPushButton("Exportar selecionadas…")
        self.btn_export_quotes.clicked.connect(self._export_quotes)
        self.btn_export_quotes.setEnabled(False)
        quote_filters.addWidget(self.btn_export_quotes)
        quote_layout.addLayout(quote_filters)

        self.quote_table = DataTable(
            ["Citação", "Autor", "Ano", "Página", "Tipo", "Contexto"]
        )
        try:
            from PySide6.QtWidgets import QAbstractItemView
            self.quote_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        except Exception:
            pass
        quote_layout.addWidget(self.quote_table)
        self.tabs.addTab(quote_widget, "❝ Citações diretas")

        # Índice onomástico (editável)
        onom_widget = QWidget()
        onom_layout = QVBoxLayout(onom_widget)
        onom_layout.setContentsMargins(8, 8, 8, 8)
        self.onom_help = HelpPanel("citations_onomastic", expanded=False)
        onom_layout.addWidget(self.onom_help)
        self.onom_info = QLabel(_expl.ANALYSIS_EXPLANATIONS.get('onomastico', ''))
        self.onom_info.setWordWrap(True)
        self.onom_info.setStyleSheet("color:#5b6673;")
        onom_layout.addWidget(self.onom_info)
        self.onom_summary = QLabel("—")
        self.onom_summary.setStyleSheet("color:#5b6673;")
        onom_layout.addWidget(self.onom_summary)
        self.onom_table = DataTable(
            ["Nome", "Tipo", "Ocorrências", "Confiança"]
        )
        onom_layout.addWidget(self.onom_table, 1)
        onom_buttons = QHBoxLayout()
        self.button_rename = QPushButton("✏️  Renomear…")
        self.button_rename.clicked.connect(self._rename_entry)
        onom_buttons.addWidget(self.button_rename)
        self.button_retype = QPushButton("🏷️  Alterar tipo…")
        self.button_retype.clicked.connect(self._retype_entry)
        onom_buttons.addWidget(self.button_retype)
        self.button_delete = QPushButton("🗑️  Excluir")
        self.button_delete.clicked.connect(self._delete_entry)
        onom_buttons.addWidget(self.button_delete)
        self.button_restore = QPushButton("↺  Restaurar automático")
        self.button_restore.clicked.connect(self._restore_onomastic)
        onom_buttons.addWidget(self.button_restore)
        onom_buttons.addStretch()
        onom_layout.addLayout(onom_buttons)
        self.tabs.addTab(onom_widget, "👤 Índice onomástico")

        # Conceitos
        concept_widget = QWidget()
        concept_layout = QVBoxLayout(concept_widget)
        concept_layout.setContentsMargins(8, 8, 8, 8)
        self.concept_help = HelpPanel("citations_concepts", expanded=False)
        concept_layout.addWidget(self.concept_help)
        from core import explanations as _expl
        self.concept_info = QLabel(_expl.ANALYSIS_EXPLANATIONS.get('conceitos', ''))
        self.concept_info.setWordWrap(True)
        self.concept_info.setStyleSheet("color:#5b6673;")
        concept_layout.addWidget(self.concept_info)
        self.concept_table = DataTable(
            ["Conceito", "Tipo", "Ocorrências", "Score"]
        )
        concept_layout.addWidget(self.concept_table)
        concept_btns = QHBoxLayout()
        self.concept_edit = QPushButton("✏️  Editar seleção")
        self.concept_edit.clicked.connect(self._edit_concept)
        concept_btns.addWidget(self.concept_edit)
        self.concept_add = QPushButton("➕  Adicionar")
        self.concept_add.clicked.connect(self._add_concept)
        concept_btns.addWidget(self.concept_add)
        self.concept_remove = QPushButton("🗑️  Remover")
        self.concept_remove.clicked.connect(self._remove_concept)
        concept_btns.addWidget(self.concept_remove)
        concept_btns.addStretch()
        concept_layout.addLayout(concept_btns)
        self.tabs.addTab(concept_widget, "💡 Conceitos")

        # KWIC
        kwic_widget = QWidget()
        kwic_layout = QVBoxLayout(kwic_widget)
        kwic_layout.setContentsMargins(8, 8, 8, 8)
        self.kwic_help = HelpPanel("citations_kwic", expanded=False)
        kwic_layout.addWidget(self.kwic_help)
        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Termo:"))
        self.kwic_input = QLineEdit()
        self.kwic_input.setPlaceholderText(
            "Digite uma palavra e pressione Enter"
        )
        search_row.addWidget(self.kwic_input, 1)
        self.kwic_button = QPushButton("Buscar")
        search_row.addWidget(self.kwic_button)
        kwic_layout.addLayout(search_row)
        self.kwic_output = QTextBrowser()
        kwic_layout.addWidget(self.kwic_output, 1)
        self.tabs.addTab(kwic_widget, "🔍 Concordância (KWIC)")

        layout.addWidget(self.tabs, 1)

        self.kwic_button.clicked.connect(self._run_kwic_search)
        self.kwic_input.returnPressed.connect(self._run_kwic_search)

    # ------------------------------------------------------------------
    def clear(self) -> None:
        self._text = ""
        self._result = None
        self._onomastic = []
        self._onomastic_original = []
        self._references_items = []
        self._quotes_items = []
        self._quotes_filtered = []
        self.ref_table.set_rows([])
        self.cit_table.set_rows([])
        self.quote_table.set_rows([])
        self.onom_table.set_rows([])
        self.concept_table.set_rows([])
        self.ref_summary.setText("—")
        self.cit_summary.setText("—")
        self.quote_summary.setText("—")
        self.onom_summary.setText("—")
        self.kwic_output.clear()
        try:
            self.quote_min_words.setValue(6)
        except Exception:
            pass
        for widget in (getattr(self, "quote_filter_text", None),):
            if widget is not None:
                widget.blockSignals(True)
                widget.clear()
                widget.blockSignals(False)
        for widget in (
            getattr(self, "quote_filter_type", None),
            getattr(self, "quote_filter_author", None),
        ):
            if widget is not None:
                widget.blockSignals(True)
                widget.setCurrentIndex(0)
                widget.blockSignals(False)
        if hasattr(self, "btn_export_quotes"):
            self.btn_export_quotes.setEnabled(False)
        if hasattr(self, "btn_export_refs"):
            self.btn_export_refs.setEnabled(False)
        for widget in (getattr(self, "ref_preview", None),
                       getattr(self, "ref_detail", None)):
            if widget is not None:
                widget.clear()

    def update_results(self, result: dict, text: str = "") -> None:
        self._text = text
        self._result = result

        self._references_items = list((result.get("references") or {}).get("items") or [])
        self._render_references(result.get("references") or {})
        self._render_citations(result.get("citations") or {})
        quotes_data = result.get("quotes") or {}
        try:
            if "min_words" in quotes_data:
                self.quote_min_words.setValue(int(quotes_data["min_words"]))
            elif "summary" in quotes_data and isinstance(quotes_data["summary"], dict):
                if "min_words" in quotes_data["summary"]:
                    self.quote_min_words.setValue(int(quotes_data["summary"]["min_words"]))
        except Exception:
            pass
        self._render_quotes(quotes_data)

        self._onomastic = copy.deepcopy(result.get("onomastic") or [])
        self._onomastic_original = copy.deepcopy(self._onomastic)
        self._render_onomastic()

        self.concept_table.set_rows([
            (c["term"], c["kind"], c["count"], c["score"])
            for c in result.get("concepts", [])
        ])

        self.kwic_output.clear()

    # ------------------------------------------------------------------
    def _render_references(self, references: dict) -> None:
        items = getattr(self, "_references_items", None)
        if items is None:
            items = references.get("items") or []
        section = references.get("section_found")
        graph = (self._result or {}).get("citation_graph") or {}
        summary = graph.get("summary") or {}
        if items:
            parts = [f"{len(items)} referências encontradas"]
            if section:
                parts.append("seção de referências detectada")
            if summary:
                parts.append(
                    f"{summary.get('matched', 0)} citações casadas "
                    f"(cobertura {summary.get('coverage', 0)})"
                )
            self.ref_summary.setText(" · ".join(parts) + ".")
        elif section:
            self.ref_summary.setText(
                "Seção de referências detectada, mas nenhuma entrada pôde "
                "ser interpretada."
            )
        else:
            self.ref_summary.setText(
                "Nenhuma seção de referências encontrada no documento."
            )
        self.ref_table.set_rows([
            (
                item.get("authors") or "—",
                item.get("year") or "—",
                item.get("title") or "—",
                item.get("source") or "—",
                item.get("type_label") or item.get("type") or "—",
                _confidence_label(item),
                _review_label(item),
            )
            for item in items
        ])
        for index in range(self.ref_table.rowCount()):
            self._bind_reference_role(index)
        if hasattr(self, "btn_export_refs"):
            self.btn_export_refs.setEnabled(bool(items))
        self._refresh_reference_preview()
        self._refresh_reference_detail()

    def _bind_reference_role(self, row: int) -> None:
        """Guarda no item o índice real mesmo com paginação/ordenação."""
        table = getattr(self, "ref_table", None)
        if table is None or row < 0 or row >= table.rowCount():
            return
        cell = table.item(row, 0)
        if cell is None:
            return
        source = table.source_index(row)
        if source >= 0:
            cell.setData(Qt.UserRole, source)

    def _sync_reference_roles(self) -> None:
        for row in range(self.ref_table.rowCount()):
            self._bind_reference_role(row)

    # ------------------------------------------------------------------
    def _refresh_reference_preview(self, *_) -> None:
        """Mostra a lista no estilo escolhido, sem alterar os dados."""
        browser = getattr(self, "ref_preview", None)
        if browser is None:
            return
        items = list(getattr(self, "_references_items", None) or [])
        if not items:
            browser.setHtml(
                "<p style='color:#5b6673'>Nenhuma referência disponível. "
                "Importe um arquivo BibTeX/RIS ou analise um texto com seção "
                "de referências.</p>"
            )
            return
        style = "abnt"
        if hasattr(self, "ref_style"):
            style = self.ref_style.currentData() or "abnt"
        label = reference_format.STYLES.get(style, style)
        try:
            formatted = reference_format.format_references(
                items, style, markup="html"
            )
        except Exception as exc:  # noqa: BLE001 - não deve quebrar a interface
            browser.setHtml(
                "<p style='color:#a33'>Não foi possível formatar: "
                f"{_safe_html(exc)}</p>"
            )
            return
        parts = [
            f"<p style='color:#5b6673'><b>{_safe_html(label)}</b> · "
            f"{len(items)} referência(s). A pré-visualização é só de leitura; "
            "os metadados extraídos permanecem intactos.</p>"
        ]
        for entry in formatted:
            text = _safe_html(entry.get("text", ""))
            if not text:
                continue
            prefix = ""
            number = entry.get("number")
            if number is not None and style in reference_format.NUMERIC_STYLES:
                prefix = f"[{number}] " if style == "ieee" else f"{number}. "
            parts.append(
                f"<p style='margin:0 0 8px 0'>{prefix}{text}</p>"
            )
        browser.setHtml("".join(parts))

    # ------------------------------------------------------------------
    def _selected_reference(self):
        """Registro correspondente à linha selecionada (mesmo após ordenar)."""
        table = getattr(self, "ref_table", None)
        if table is None:
            return None
        row = table.currentRow()
        if row < 0:
            return None
        cell = table.item(row, 0)
        index = cell.data(Qt.UserRole) if cell is not None else None
        items = getattr(self, "_references_items", None) or []
        if isinstance(index, int) and 0 <= index < len(items):
            return items[index]
        return None

    # ------------------------------------------------------------------
    def _refresh_reference_detail(self, *_) -> None:
        """Mostra campos reconhecidos, confiança e texto original do item."""
        browser = getattr(self, "ref_detail", None)
        if browser is None:
            return
        item = self._selected_reference()
        if item is None:
            browser.setHtml(
                "<p style='color:#5b6673'>Selecione uma referência na tabela "
                "para ver os campos reconhecidos, a confiança de cada campo, "
                "os campos ausentes e o texto original de onde ela veio.</p>"
            )
            return
        from reports import exporters

        detail = exporters.reference_detail(item)
        rows = "".join(
            "<tr><th style='text-align:left;padding:3px 12px 3px 0;"
            f"color:#5b6673;white-space:nowrap'>{_safe_html(label)}</th>"
            f"<td style='padding:3px 0'>{_safe_html(value)}</td></tr>"
            for label, value in detail.items()
        )
        confidence = exporters.confidence_text(item)
        parts = [
            "<p style='color:#5b6673'><b>"
            f"{_safe_html(item.get('title') or 'Referência')}</b>"
            + (f" · confiança {_safe_html(confidence)}" if confidence else "")
            + "</p>"
        ]
        if rows:
            parts.append(f"<table>{rows}</table>")
        field_confidence = item.get("field_confidence") or {}
        if field_confidence:
            chips = ", ".join(
                f"{_safe_html(name)} {float(value):.2f}"
                for name, value in field_confidence.items()
                if isinstance(value, (int, float))
            )
            if chips:
                parts.append(
                    "<p style='color:#5b6673;font-size:11px'>Confiança por "
                    f"campo: {chips}</p>"
                )
        missing = list(item.get("missing_fields") or [])
        if missing:
            parts.append(
                "<p style='color:#a15c00'>Campos ausentes: "
                + _safe_html(", ".join(str(field) for field in missing))
                + "</p>"
            )
        extraction = item.get("extraction_metadata") or {}
        source = extraction.get("source") or extraction.get("rule") or ""
        if source:
            parts.append(
                "<p style='color:#5b6673;font-size:11px'>Origem da extração: "
                f"{_safe_html(source)}</p>"
            )
        original = item.get("original_text") or item.get("raw") or ""
        if original:
            parts.append(
                "<p style='color:#5b6673;margin-bottom:2px'>Texto original</p>"
                "<pre style='white-space:pre-wrap;background:#f6f8fb;"
                "padding:8px;border-radius:6px'>"
                f"{_safe_html(original)}</pre>"
            )
        browser.setHtml("".join(parts))

    # ------------------------------------------------------------------
    def _import_references(self) -> None:
        """Importa referências de arquivos BibTeX (.bib) ou RIS (.ris)."""
        from core import reference_import

        filenames, _ = QFileDialog.getOpenFileNames(
            self,
            "Importar referências",
            "",
            "Referências (*.bib *.bibtex *.ris);;BibTeX (*.bib *.bibtex);;RIS (*.ris);;Todos os arquivos (*)",
        )
        if not filenames:
            return

        imported = []
        errors = []
        for filename in filenames:
            try:
                imported.extend(reference_import.parse_file(filename))
            except Exception as exc:  # pragma: no cover - dependência de I/O
                errors.append(f"{filename}: {exc}")

        if not imported:
            message = "Nenhuma referência pôde ser importada."
            if errors:
                message += "\n\n" + "\n".join(errors)
            QMessageBox.warning(self, "Importação", message)
            return

        existing = getattr(self, "_references_items", None)
        if existing is None:
            existing = list(((self._result or {}).get("references") or {}).get("items") or [])
        merged = reference_import.merge_references(existing, imported)
        added = len(merged) - len(existing)

        self._references_items = merged
        if isinstance(self._result, dict):
            references = self._result.setdefault("references", {})
            references["items"] = merged
            references["count"] = len(merged)
        self._render_references((self._result or {}).get("references") or {})

        message = f"{len(imported)} referência(s) lida(s); {max(0, added)} nova(s) adicionada(s)."
        if errors:
            message += "\n\nAvisos:\n" + "\n".join(errors)
        QMessageBox.information(self, "Importação concluída", message)

    def _export_references(self) -> None:
        """Exporta as referências exibidas em BibTeX (.bib) ou RIS (.ris)."""
        from reports import exporters

        items = list(getattr(self, "_references_items", None) or [])
        if not items:
            fallback = ((self._result or {}).get("references") or {}).get("items")
            items = list(fallback or [])
        if not items:
            QMessageBox.information(
                self,
                "Exportar referências",
                "Nenhuma referência disponível para exportar. Gere o relatório "
                "ou importe um arquivo BibTeX/RIS primeiro.",
            )
            return

        filename, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Exportar referências",
            "referencias.bib",
            "BibTeX (*.bib);;RIS (*.ris)",
        )
        if not filename:
            return

        lower = filename.lower()
        is_ris = selected_filter.startswith("RIS") or lower.endswith(".ris")
        try:
            if is_ris:
                if not lower.endswith(".ris"):
                    filename += ".ris"
                exporters.export_ris(
                    self._result or {}, filename, items=items
                )
                label = "RIS"
            else:
                if not (lower.endswith(".bib") or lower.endswith(".bibtex")):
                    filename += ".bib"
                exporters.export_bibtex(
                    self._result or {}, filename, items=items
                )
                label = "BibTeX"
        except Exception as exc:  # noqa: BLE001 - falha de I/O
            QMessageBox.critical(
                self, "Erro ao exportar", f"Não foi possível salvar:\n{exc}"
            )
            return

        QMessageBox.information(
            self,
            "Exportação concluída",
            f"{len(items)} referência(s) exportada(s) em {label}:\n{filename}",
        )

    def _detect_duplicates(self) -> None:
        """Procura duplicatas e oferece a mesclagem dos registros."""
        from core import bibliography_dedup

        items = getattr(self, "_references_items", None)
        if items is None:
            items = list(((self._result or {}).get("references") or {}).get("items") or [])
        if len(items) < 2:
            QMessageBox.information(
                self, "Duplicatas", "Referências insuficientes para comparar."
            )
            return

        groups = bibliography_dedup.find_duplicates(items)
        stats = bibliography_dedup.summary(items, groups)
        if not groups:
            QMessageBox.information(
                self,
                "Duplicatas",
                f"Nenhuma duplicata encontrada em {stats['total']} referências.",
            )
            return

        lines = []
        for index, group in enumerate(groups, start=1):
            primary = group.get("primary") or {}
            kind = "exata" if group.get("kind") == "exact" else "possível"
            confidence = group.get("confidence")
            signal = f", confiança {confidence:.2f}" if isinstance(confidence, float) else ""
            lines.append(
                f"{index}. [{kind}{signal}] {primary.get('authors', '—')} "
                f"({primary.get('year', '—')}) — {primary.get('title', '—')}"
            )
            for duplicate in group.get("duplicates", []):
                lines.append(
                    f"    · duplicata: {duplicate.get('authors', '—')} "
                    f"({duplicate.get('year', '—')}) — {duplicate.get('title', '—')}"
                )

        preview = "\n".join(lines)
        if len(preview) > 3500:
            preview = preview[:3500] + "\n…"

        answer = QMessageBox.question(
            self,
            "Duplicatas encontradas",
            (
                f"{stats['groups']} grupo(s): "
                f"{stats.get('exact_duplicates', 0)} duplicata(s) exata(s) e "
                f"{stats.get('possible_duplicates', 0)} possível(is); "
                f"{stats['duplicates_removed']} registro(s) redundante(s).\n\n"
                f"{preview}\n\nDeseja mesclar mantendo os registros mais completos? "
                "Nada é excluído sem esta confirmação."
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if answer != QMessageBox.Yes:
            return

        merged = bibliography_dedup.apply_merges(items, groups)
        self._references_items = merged
        if isinstance(self._result, dict):
            references = self._result.setdefault("references", {})
            references["items"] = merged
            references["count"] = len(merged)
        self._render_references((self._result or {}).get("references") or {})
        QMessageBox.information(
            self,
            "Duplicatas",
            f"Mesclagem concluída: {len(items)} → {len(merged)} referências.",
        )

    def _render_citations(self, citations: dict) -> None:
        items = citations.get("items") or []
        summary = citations.get("summary") or {}
        by_type = summary.get("by_type", {})
        type_text = ", ".join(f"{k}: {v}" for k, v in by_type.items()) or "nenhuma"
        self.cit_summary.setText(
            f"{len(items)} citações detectadas ({type_text})."
        )
        self.cit_table.set_rows([
            (c.get("type", ""), c.get("text", ""), c.get("context", "")[:160])
            for c in items
        ])

    def _render_quotes(self, quotes: dict) -> None:
        quotes = quotes or {}
        items = quotes.get("items") or []
        summary = quotes.get("summary") or {}
        min_words = quotes.get("min_words") or summary.get("min_words") or self.quote_min_words.value()
        try:
            self.quote_min_words.setValue(int(min_words))
        except Exception:
            pass
        if items:
            self.quote_summary.setText(
                f"{summary.get('total', len(items))} citações diretas "
                f"({summary.get('curta', summary.get('short', 0))} curtas · "
                f"{summary.get('longa', summary.get('long', 0))} longas) "
                f"· mínimo {min_words} palavras."
            )
        else:
            self.quote_summary.setText(
                f"Nenhuma citação direta (entre aspas ou em bloco) detectada com mínimo de {min_words} palavras. "
                "Ajuste o valor e clique em Atualizar."
            )
        self._quotes_items = list(items)
        self._quotes_filtered = list(items)
        if hasattr(self, "quote_filter_text"):
            self.quote_filter_text.blockSignals(True)
            self.quote_filter_text.clear()
            self.quote_filter_text.blockSignals(False)
        if hasattr(self, "quote_filter_type"):
            self.quote_filter_type.blockSignals(True)
            self.quote_filter_type.setCurrentIndex(0)
            self.quote_filter_type.blockSignals(False)
        self._refresh_quote_authors()
        self._refresh_quote_filter()

    def _refresh_quote_authors(self) -> None:
        combo = getattr(self, "quote_filter_author", None)
        if combo is None:
            return
        current = combo.currentData()
        authors = sorted({
            str(item.get("author") or "").strip()
            for item in getattr(self, "_quotes_items", [])
            if str(item.get("author") or "").strip()
        }, key=str.casefold)
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("Todos", "")
        for author in authors:
            combo.addItem(author, author)
        index = combo.findData(current)
        combo.setCurrentIndex(max(0, index))
        combo.blockSignals(False)

    def _filtered_quotes(self) -> list:
        items = list(getattr(self, "_quotes_items", []))
        kind_widget = getattr(self, "quote_filter_type", None)
        if kind_widget is not None:
            kind = kind_widget.currentData() or ""
            if kind:
                items = [item for item in items if item.get("type") == kind]
        author_widget = getattr(self, "quote_filter_author", None)
        if author_widget is not None:
            author = author_widget.currentData() or ""
            if author:
                items = [
                    item for item in items
                    if str(item.get("author") or "") == author
                ]
        text_widget = getattr(self, "quote_filter_text", None)
        if text_widget is not None:
            needle = text_widget.text().strip().lower()
            if needle:
                items = [
                    item for item in items
                    if needle in " ".join(
                        str(item.get(key) or "")
                        for key in ("quote", "author", "year", "page", "context")
                    ).lower()
                ]
        return items

    def _refresh_quote_filter(self) -> None:
        """Reaplica os filtros e atualiza a tabela/contadores."""
        items = self._filtered_quotes()
        self._quotes_filtered = items
        rows = [
            (
                item.get("quote", ""),
                item.get("author") or "—",
                item.get("year") or "—",
                item.get("page") or "—",
                item.get("type", ""),
                (item.get("context") or "")[:160],
            )
            for item in items
        ]
        table = getattr(self, "quote_table", None)
        if table is not None:
            table.set_rows(rows)
        button = getattr(self, "btn_export_quotes", None)
        if button is not None:
            button.setEnabled(bool(items))
        total = len(getattr(self, "_quotes_items", []))
        summary = getattr(self, "quote_summary", None)
        if summary is not None and total and len(items) != total:
            summary.setText(
                f"{len(items)} de {total} citações diretas exibidas pelos filtros."
            )
        elif summary is not None and total and len(items) == total:
            self._render_quote_summary(total)

    def _render_quote_summary(self, total: int) -> None:
        summary_label = getattr(self, "quote_summary", None)
        if summary_label is None:
            return
        short = sum(1 for item in self._quotes_items if item.get("type") == "curta")
        long_ = sum(1 for item in self._quotes_items if item.get("type") == "longa")
        try:
            minimum = int(self.quote_min_words.value())
        except Exception:
            minimum = 0
        summary_label.setText(
            f"{total} citações diretas ({short} curtas · {long_} longas) "
            f"· mínimo {minimum} palavras."
        )

    def _filter_quotes(self) -> None:
        self._refresh_quote_filter()

    def _selected_quotes(self) -> list:
        """Citações marcadas na tabela; se nada estiver marcado, as filtradas."""
        items = list(getattr(self, "_quotes_filtered", []))
        if not items:
            return []
        table = getattr(self, "quote_table", None)
        if table is None:
            return items
        try:
            rows = sorted({index.row() for index in table.selectedIndexes()})
        except Exception:
            rows = []
        if not rows:
            return items
        selected = []
        for row in rows:
            source = table.source_index(row)
            if source < 0 or source >= len(items):
                continue
            selected.append(items[source])
        return selected or items

    def _export_quotes(self) -> None:
        """Exporta as citações diretas (selecionadas ou filtradas) em CSV/TXT/HTML."""
        items = self._selected_quotes()
        if not items:
            QMessageBox.information(
                self, "Citações diretas", "Nenhuma citação para exportar."
            )
            return
        filename, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Exportar citações diretas",
            "citacoes_diretas.csv",
            "CSV (*.csv);;Texto (*.txt);;HTML (*.html)",
        )
        if not filename:
            return
        suffix = Path(filename).suffix.lower()
        if not suffix:
            if "TXT" in (selected_filter or ""):
                suffix = ".txt"
            elif "HTML" in (selected_filter or ""):
                suffix = ".html"
            else:
                suffix = ".csv"
            filename = str(Path(filename).with_suffix(suffix))

        try:
            if suffix == ".txt":
                lines = []
                for index, item in enumerate(items, start=1):
                    lines.append(f"{index}. “{str(item.get('quote') or '').strip()}”")
                    attribution = " — ".join(
                        str(part) for part in (
                            item.get("author"), item.get("year"), item.get("page"),
                        ) if part
                    )
                    if attribution:
                        lines.append(f"   {attribution}")
                    if item.get("context"):
                        lines.append(f"   Contexto: {item.get('context')}")
                    lines.append("")
                Path(filename).write_text("\n".join(lines), encoding="utf-8")
            elif suffix == ".html":
                import html as html_lib
                rows = "".join(
                    "<tr>"
                    f"<td>{html_lib.escape(str(item.get('quote') or ''))}</td>"
                    f"<td>{html_lib.escape(str(item.get('author') or ''))}</td>"
                    f"<td>{html_lib.escape(str(item.get('year') or ''))}</td>"
                    f"<td>{html_lib.escape(str(item.get('page') or ''))}</td>"
                    f"<td>{html_lib.escape(str(item.get('type') or ''))}</td>"
                    f"<td>{html_lib.escape(str(item.get('context') or ''))}</td>"
                    "</tr>"
                    for item in items
                )
                document = (
                    "<!DOCTYPE html><html lang='pt-BR'><head><meta charset='utf-8'>"
                    "<title>Citações diretas</title><style>"
                    "body{font-family:Segoe UI,sans-serif;margin:2rem;color:#1b1f24}"
                    "table{border-collapse:collapse;width:100%}"
                    "th,td{border:1px solid #c9d6ea;padding:6px;text-align:left;"
                    "vertical-align:top}th{background:#eaf1ff}</style></head><body>"
                    "<h1>Citações diretas</h1><table><thead><tr>"
                    "<th>Citação</th><th>Autor</th><th>Ano</th><th>Página</th>"
                    "<th>Tipo</th><th>Contexto</th></tr></thead><tbody>"
                    f"{rows}</tbody></table></body></html>"
                )
                Path(filename).write_text(document, encoding="utf-8")
            else:
                import csv
                with open(filename, "w", encoding="utf-8", newline="") as handle:
                    writer = csv.writer(handle)
                    writer.writerow(
                        ["Citação", "Autor", "Ano", "Página", "Tipo", "Contexto"]
                    )
                    for item in items:
                        writer.writerow([
                            item.get("quote", ""), item.get("author", ""),
                            item.get("year", ""), item.get("page", ""),
                            item.get("type", ""), item.get("context", ""),
                        ])
            QMessageBox.information(
                self, "Citações diretas",
                f"{len(items)} citação(ões) exportada(s):\n{filename}",
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Erro ao exportar", str(exc))

    def _update_quotes(self) -> None:
        if not self._text:
            return
        try:
            min_words = int(self.quote_min_words.value())
        except Exception:
            min_words = 6
        quotes = quotes_core.detect_direct_quotes(self._text, min_words=min_words)
        if self._result is not None:
            self._result["quotes"] = quotes
        self._render_quotes(quotes)

    def _render_onomastic(self) -> None:
        counts = onomastic_core.type_counts(self._onomastic)
        types = " · ".join(f"{k}: {v}" for k, v in counts.items()) or "nenhum"
        self.onom_summary.setText(
            f"{len(self._onomastic)} entradas · {types}. "
            "Selecione uma linha para renomear, alterar o tipo ou excluir."
        )
        self.onom_table.set_rows([
            (
                item.get("name", ""),
                item.get("type", ""),
                item.get("count", 0),
                item.get("confidence", ""),
            )
            for item in self._onomastic
        ])

    def _get_concept_row(self):
        row = self.concept_table.currentRow()
        if row < 0:
            return -1, None
        row = self.concept_table.source_index(row)
        concepts = (self._result or {}).get("concepts") or []
        if row < 0 or row >= len(concepts):
            return row, None
        return row, concepts[row]

    def _edit_concept(self) -> None:
        row, concept = self._get_concept_row()
        if concept is None or row < 0 or self._result is None:
            return
        concepts = self._result.setdefault("concepts", [])
        term, ok = QInputDialog.getText(self, "Editar conceito", "Conceito:", text=str(concept.get("term", "")))
        if not ok or not term.strip():
            return
        kind, ok2 = QInputDialog.getText(self, "Editar conceito", "Tipo:", text=str(concept.get("kind", "")))
        if not ok2:
            kind = concept.get("kind", "")
        count_s, ok3 = QInputDialog.getText(self, "Editar conceito", "Ocorrências:", text=str(concept.get("count", 0)))
        if not ok3:
            count_s = str(concept.get("count", 0))
        try:
            count = int(count_s.strip())
        except Exception:
            count = concept.get("count", 0)
        concepts[row] = dict(concept)
        concepts[row]["term"] = term.strip()
        concepts[row]["kind"] = (kind or "").strip() or concepts[row].get("kind", "")
        concepts[row]["count"] = count
        self.concept_table.set_rows([
            (c["term"], c["kind"], c["count"], c["score"])
            for c in concepts
        ])

    def _add_concept(self) -> None:
        if self._result is None:
            return
        term, ok = QInputDialog.getText(self, "Adicionar conceito", "Conceito:")
        if not ok or not term.strip():
            return
        kind, ok2 = QInputDialog.getText(self, "Adicionar conceito", "Tipo:", text="conceito")
        if not ok2:
            kind = "conceito"
        count_s, ok3 = QInputDialog.getText(self, "Adicionar conceito", "Ocorrências:", text="1")
        if not ok3:
            count_s = "1"
        try:
            count = int(count_s.strip())
        except Exception:
            count = 1
        concepts = self._result.setdefault("concepts", [])
        concepts.append({"term": term.strip(), "kind": (kind or "conceito").strip(), "count": count, "score": round(count * 0.1, 3)})
        self.concept_table.set_rows([
            (c["term"], c["kind"], c["count"], c["score"])
            for c in concepts
        ])

    def _remove_concept(self) -> None:
        row, concept = self._get_concept_row()
        if concept is None or row < 0 or self._result is None:
            return
        if QMessageBox.question(self, "Remover conceito", f"Remover '{concept.get('term')}'?") != QMessageBox.Yes:
            return
        concepts = self._result.get("concepts") or []
        if 0 <= row < len(concepts):
            concepts.pop(row)
            self.concept_table.set_rows([
                (c["term"], c["kind"], c["count"], c["score"])
                for c in concepts
            ])

    # ------------------------------------------------------------------
    def _selected_name(self) -> str:
        row = self.onom_table.currentRow()
        if row < 0 or not self.onom_table.item(row, 0):
            return ""
        return self.onom_table.item(row, 0).text()

    def _rename_entry(self) -> None:
        name = self._selected_name()
        if not name:
            return
        new_name, ok = QInputDialog.getText(
            self, "Renomear entrada", f"Novo nome para “{name}”:", text=name
        )
        if not ok or not new_name.strip() or new_name.strip() == name:
            return
        self._onomastic = onomastic_core.rename_entry(
            self._onomastic, name, new_name.strip()
        )
        self._persist_onomastic()

    def _retype_entry(self) -> None:
        name = self._selected_name()
        if not name:
            return
        current = next(
            (item.get("type", "") for item in self._onomastic
             if item.get("name") == name),
            onomastic_core.TYPE_LABELS[0],
        )
        index = (
            onomastic_core.TYPE_LABELS.index(current)
            if current in onomastic_core.TYPE_LABELS else 0
        )
        new_type, ok = QInputDialog.getItem(
            self, "Alterar tipo",
            f"Nova classificação para “{name}”:",
            onomastic_core.TYPE_LABELS, index, False,
        )
        if not ok or not new_type:
            return
        self._onomastic = onomastic_core.retype_entry(
            self._onomastic, name, new_type
        )
        self._persist_onomastic()

    def _delete_entry(self) -> None:
        name = self._selected_name()
        if not name:
            return
        answer = QMessageBox.question(
            self, "Excluir entrada",
            f"Remover “{name}” do índice onomástico?",
        )
        if answer != QMessageBox.Yes:
            return
        self._onomastic = onomastic_core.delete_entry(self._onomastic, name)
        self._persist_onomastic()

    def _restore_onomastic(self) -> None:
        self._onomastic = copy.deepcopy(self._onomastic_original)
        self._persist_onomastic()

    def _persist_onomastic(self) -> None:
        if self._result is not None:
            self._result["onomastic"] = copy.deepcopy(self._onomastic)
            self._result["onomastic_types"] = onomastic_core.type_counts(
                self._onomastic
            )
        self._render_onomastic()

    # ------------------------------------------------------------------
    def _run_kwic_search(self) -> None:
        term = self.kwic_input.text().strip()
        if not term or not self._text:
            return
        hits = run_kwic(self._text, term, window=60, max_results=80)
        if not hits:
            self.kwic_output.setPlainText(f"Nenhuma ocorrência de “{term}”.")
            return
        rows = []
        for hit in hits:
            rows.append(
                f"<tr><td style='color:#5b6673;white-space:nowrap'>…{hit['left']}</td>"
                f"<td style='background:#eaf1ff;color:#1c53b8;font-weight:600'>"
                f"{hit['match']}</td>"
                f"<td style='color:#5b6673'>{hit['right']}…</td></tr>"
            )
        self.kwic_output.setHtml(
            f"<p><b>{len(hits)} ocorrências de “{term}”</b></p>"
            "<table width='100%' cellspacing='0' cellpadding='3' "
            "style='font-size:12px'>" + "".join(rows) + "</table>"
        )
