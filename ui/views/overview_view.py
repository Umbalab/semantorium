#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Aba: Visão geral (KPIs, resumo, palavras-chave)."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea,
    QSizePolicy, QTextBrowser, QVBoxLayout, QWidget,
)

from ui.widgets.common import Card, Chip, KpiTile
from ui.widgets.help_panel import HelpPanel
from reports import exporters


class OverviewView(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        self.layout = QVBoxLayout(container)
        self.layout.setContentsMargins(14, 14, 14, 14)
        self.layout.setSpacing(12)

        # Explicações detalhadas da aba
        self.help_panel = HelpPanel("overview")
        self.layout.addWidget(self.help_panel)

        # KPIs
        kpi_card = Card("Indicadores")
        self.kpi_grid = QGridLayout()
        self.kpi_grid.setSpacing(10)
        self.kpis = {}
        specs = [
            ("words", "Palavras"), ("unique_words", "Palavras únicas"),
            ("sentences", "Sentenças"), ("paragraphs", "Parágrafos"),
            ("avg_words_per_sentence", "Média palavras/frase"),
            ("reading", "Tempo de leitura (min)"),
        ]
        for index, (key, label) in enumerate(specs):
            tile = KpiTile(label)
            self.kpis[key] = tile
            self.kpi_grid.addWidget(tile, index // 3, index % 3)
        kpi_card.add_layout(self.kpi_grid)
        self.layout.addWidget(kpi_card)

        # Resumo
        self.summary_card = Card("Resumo automático")
        self.summary_text = QTextBrowser()
        self.summary_text.setOpenExternalLinks(True)
        self.summary_text.setMinimumHeight(160)
        self.summary_card.add(self.summary_text)
        self.layout.addWidget(self.summary_card)

        # Palavras-chave
        self.keywords_card = Card("Palavras-chave")
        self.keywords_container = QWidget()
        self.keywords_layout = QHBoxLayout(self.keywords_container)
        self.keywords_layout.setContentsMargins(0, 0, 0, 0)
        self.keywords_layout.setSpacing(6)
        self.keywords_layout.addStretch()
        self.keywords_card.add(self.keywords_container)
        self.layout.addWidget(self.keywords_card)

        # Resultados e evidências (Fase 14)
        self.evidence_card = Card("Resultados e evidências")
        self.evidence_help = HelpPanel(
            "evidence", expanded=False, max_height=180
        )
        self.evidence_card.add(self.evidence_help)
        self.evidence_text = QTextBrowser()
        self.evidence_text.setOpenExternalLinks(False)
        self.evidence_text.setMinimumHeight(160)
        self.evidence_card.add(self.evidence_text)
        self.evidence_card.setVisible(False)
        self.layout.addWidget(self.evidence_card)

        # Metadados
        self.meta_card = Card("Detalhes da análise")
        self.meta_text = QLabel("—")
        self.meta_text.setWordWrap(True)
        self.meta_text.setStyleSheet("color:#5b6673;")
        self.meta_card.add(self.meta_text)
        self.layout.addWidget(self.meta_card)

        self.layout.addStretch()
        self.setWidget(container)

    def clear(self) -> None:
        for tile in self.kpis.values():
            tile.set_value("—")
        self.summary_text.clear()
        self._clear_keywords()
        self.evidence_text.clear()
        self.evidence_card.setVisible(False)
        self.meta_text.setText("—")

    def _clear_keywords(self) -> None:
        while self.keywords_layout.count() > 1:
            item = self.keywords_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def update_results(self, result: dict) -> None:
        stats = result.get("stats", {})
        for key, tile in self.kpis.items():
            if key == "reading":
                reading = result.get("readability", {}).get("reading_time_min")
                tile.set_value(f"{reading:.1f}" if isinstance(reading, (int, float)) else "—")
            else:
                value = stats.get(key, "—")
                if isinstance(value, (int, float)):
                    tile.set_value(f"{value:,}".replace(",", "."))
                else:
                    tile.set_value(value)

        self.summary_text.setPlainText(
            result.get("summary") or "Resumo não disponível."
        )

        self._clear_keywords()
        for keyword in result.get("keywords", [])[:25]:
            term = keyword.get("keyword")
            if term:
                self.keywords_layout.insertWidget(
                    self.keywords_layout.count() - 1, Chip(term)
                )

        evidence_html = exporters.result_evidence_html(result)
        if evidence_html:
            self.evidence_text.setHtml(evidence_html)
            self.evidence_card.setVisible(True)
        else:
            self.evidence_text.clear()
            self.evidence_card.setVisible(False)

        meta = result.get("meta", {})
        engine = result.get("engine")
        engine_label = "spaCy" if engine == "spacy" else "interno (fallback)"
        summary_detail = result.get("summary_detail") or {}
        sentiment_data = result.get("sentiment") or {}
        domain_label = sentiment_data.get("domain_label") or "geral"
        details = [
            f"<b>Idioma:</b> {result.get('language_label', '—')}",
            f"<b>Motor NLP:</b> {engine_label}",
            f"<b>Resumo:</b> {summary_detail.get('size', 'auto')} "
            f"({summary_detail.get('target_sentences', 0)} sentenças)",
            f"<b>Sentimento:</b> {sentiment_data.get('label', '—')} "
            f"({domain_label})",
            f"<b>Arquivo:</b> {meta.get('filename', '—')}",
            f"<b>Método de extração:</b> {meta.get('method', '—')}",
            f"<b>Tempo de análise:</b> {result.get('duration_seconds', 0)} s",
        ]
        warnings = result.get("warnings") or []
        if warnings:
            details.append(
                "<span style='color:#b45309'><b>Avisos:</b> "
                + "; ".join(str(w) for w in warnings)
                + "</span>"
            )
        self.meta_text.setText(" &nbsp;·&nbsp; ".join(details))
