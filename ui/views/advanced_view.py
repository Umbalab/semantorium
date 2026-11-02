#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Aba: Legibilidade, riqueza lexical, tópicos, agrupamentos e análises profundas.

As páginas Lexicometria, Linguística, Estilo, Pesquisa, Discurso, Conhecimento
e Consistência são expostas como abas de topo pelo MainWindow; este widget
continua responsável por preenchê-las e limpá-las.
"""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QGridLayout, QHBoxLayout, QInputDialog, QLabel,
    QMessageBox, QPushButton, QScrollArea, QTabWidget, QTextBrowser,
    QVBoxLayout, QWidget,
)

import copy
import html

from core import (
    charts_svg, explanations, extraction_matrix, lexicometry_chart,
    model_layer, ontology, paraphrase, temporal_chart, versions,
)
from ui.widgets.common import Card, DataTable, KpiTile
from ui.widgets.help_panel import HelpPanel

try:  # QtSvgWidgets acompanha o PySide6 completo
    from PySide6.QtSvgWidgets import QSvgWidget
except Exception:  # pragma: no cover - fallback defensivo
    QSvgWidget = None


def _with_help(widget: QWidget, guide_key: str) -> QWidget:
    """Envolve uma sub-aba com o painel de ajuda recolhido no topo."""
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(4, 4, 4, 4)
    layout.addWidget(HelpPanel(guide_key, expanded=False))
    layout.addWidget(widget, 1)
    return container


def _chart_tab(height: int, guide_key: str):
    """Cria uma sub-aba de gráfico SVG com botões de exportação.

    Devolve ``(container, view, browser, btn_svg, btn_png)``. ``view`` é
    ``None`` quando ``QSvgWidget`` não está disponível; nesse caso ``browser``
    recebe uma mensagem textual.
    """
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(4, 4, 4, 4)
    bar = QHBoxLayout()
    bar.addStretch(1)
    btn_svg = QPushButton("💾 SVG")
    btn_svg.setEnabled(False)
    bar.addWidget(btn_svg)
    btn_png = QPushButton("💾 PNG")
    btn_png.setEnabled(False)
    bar.addWidget(btn_png)
    layout.addLayout(bar)

    if QSvgWidget is not None:
        view = QSvgWidget()
        view.setFixedSize(900, height)
        scroll = QScrollArea()
        scroll.setWidgetResizable(False)
        scroll.setAlignment(Qt.AlignCenter)
        scroll.setWidget(view)
        layout.addWidget(scroll, 1)
        browser = None
    else:  # pragma: no cover - fallback defensivo
        view = None
        browser = QTextBrowser()
        layout.addWidget(browser, 1)
    return _with_help(widget, guide_key), view, browser, btn_svg, btn_png


class AdvancedView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)

        self.help_panel = HelpPanel("advanced")
        layout.addWidget(self.help_panel)

        self.tabs = QTabWidget()

        # Legibilidade
        read_widget = QWidget()
        read_layout = QVBoxLayout(read_widget)
        read_layout.setContentsMargins(10, 10, 10, 10)
        self.read_help = HelpPanel("advanced_readability", expanded=False)
        read_layout.addWidget(self.read_help)
        self.read_info = QLabel(explanations.ANALYSIS_EXPLANATIONS.get('legibilidade', ''))
        self.read_info.setWordWrap(True)
        self.read_info.setStyleSheet("color:#5b6673;")
        read_layout.addWidget(self.read_info)
        grid = QGridLayout()
        self.read_tiles = {}
        specs = [
            ("flesch_reading_ease", "Flesch (facilidade)"),
            ("flesch_kincaid_grade", "Flesch-Kincaid"),
            ("gunning_fog", "Gunning Fog"),
            ("smog_index", "SMOG"),
            ("automated_readability_index", "ARI"),
            ("coleman_liau_index", "Coleman-Liau"),
            ("dale_chall_readability_score", "Dale-Chall"),
            ("reading_time_min", "Leitura (min)"),
        ]
        for index, (key, label) in enumerate(specs):
            tile = KpiTile(label)
            self.read_tiles[key] = tile
            grid.addWidget(tile, index // 4, index % 4)
        read_layout.addLayout(grid)
        read_layout.addStretch()
        self.tabs.addTab(read_widget, "📈 Legibilidade")

        # Riqueza lexical
        lex_widget = QWidget()
        lex_layout = QVBoxLayout(lex_widget)
        lex_layout.setContentsMargins(8, 8, 8, 8)
        self.lex_help = HelpPanel("advanced_lexical", expanded=False)
        lex_layout.addWidget(self.lex_help)
        self.lex_info = QLabel(explanations.ANALYSIS_EXPLANATIONS.get('riqueza_lexical', ''))
        self.lex_info.setWordWrap(True)
        self.lex_info.setStyleSheet("color:#5b6673;")
        lex_layout.addWidget(self.lex_info)
        self.lex_table = DataTable(["Métrica", "Valor"])
        lex_layout.addWidget(self.lex_table)
        self.tabs.addTab(lex_widget, "🧮 Riqueza lexical")

        # Lexicometria, n-gramas e colocações
        lexm_widget = QWidget()
        lexm_layout = QVBoxLayout(lexm_widget)
        lexm_layout.setContentsMargins(8, 8, 8, 8)
        self.lexm_help = HelpPanel("advanced_lexicometry", expanded=False)
        lexm_layout.addWidget(self.lexm_help)
        self.lexm_summary = QLabel("—")
        self.lexm_summary.setStyleSheet("color:#5b6673;")
        self.lexm_summary.setWordWrap(True)
        lexm_layout.addWidget(self.lexm_summary)
        self.lexm_warnings = QLabel("")
        self.lexm_warnings.setStyleSheet("color:#8a5a00;")
        self.lexm_warnings.setWordWrap(True)
        lexm_layout.addWidget(self.lexm_warnings)
        self.lexm_tabs = QTabWidget()

        # Gráfico dos termos mais frequentes
        chart_widget = QWidget()
        chart_layout = QVBoxLayout(chart_widget)
        chart_layout.setContentsMargins(4, 4, 4, 4)
        bar = QHBoxLayout()
        bar.addStretch()
        self.btn_lexm_svg = QPushButton("💾 SVG")
        self.btn_lexm_svg.setEnabled(False)
        self.btn_lexm_svg.clicked.connect(lambda: self._save_lexm("svg"))
        bar.addWidget(self.btn_lexm_svg)
        self.btn_lexm_png = QPushButton("💾 PNG")
        self.btn_lexm_png.setEnabled(False)
        self.btn_lexm_png.clicked.connect(lambda: self._save_lexm("png"))
        bar.addWidget(self.btn_lexm_png)
        chart_layout.addLayout(bar)
        self._lexm_svg = ""
        if QSvgWidget is not None:
            self.lexm_view = QSvgWidget()
            self.lexm_view.setFixedSize(900, 660)
            lexm_scroll = QScrollArea()
            lexm_scroll.setWidgetResizable(False)
            lexm_scroll.setAlignment(Qt.AlignCenter)
            lexm_scroll.setWidget(self.lexm_view)
            chart_layout.addWidget(lexm_scroll, 1)
        else:  # pragma: no cover
            self.lexm_view = None
            self.lexm_browser = QTextBrowser()
            chart_layout.addWidget(self.lexm_browser, 1)
        self.lexm_tabs.addTab(
            _with_help(chart_widget, "advanced_lexicometry_chart"),
            "📊 Gráfico",
        )

        (disp_widget, self.lexm_dispersion_view,
         self.lexm_dispersion_browser, self.btn_lexm_dispersion_svg,
         self.btn_lexm_dispersion_png) = _chart_tab(
            620, "advanced_lexicometry_chart"
        )
        self.btn_lexm_dispersion_svg.clicked.connect(
            lambda: self._save_chart(
                "_lexm_dispersion_svg", "svg", "Exportar dispersão lexical",
                "dispersao_lexical",
            )
        )
        self.btn_lexm_dispersion_png.clicked.connect(
            lambda: self._save_chart(
                "_lexm_dispersion_svg", "png", "Exportar dispersão lexical",
                "dispersao_lexical",
            )
        )
        self._lexm_dispersion_svg = ""
        self.lexm_tabs.addTab(disp_widget, "🧭 Dispersão")

        (zipf_widget, self.lexm_zipf_view, self.lexm_zipf_browser,
         self.btn_lexm_zipf_svg, self.btn_lexm_zipf_png) = _chart_tab(
            580, "advanced_lexicometry_chart"
        )
        self.btn_lexm_zipf_svg.clicked.connect(
            lambda: self._save_chart(
                "_lexm_zipf_svg", "svg", "Exportar curva de Zipf",
                "zipf",
            )
        )
        self.btn_lexm_zipf_png.clicked.connect(
            lambda: self._save_chart(
                "_lexm_zipf_svg", "png", "Exportar curva de Zipf",
                "zipf",
            )
        )
        self._lexm_zipf_svg = ""
        self.lexm_tabs.addTab(zipf_widget, "📈 Zipf")

        (heaps_widget, self.lexm_heaps_view, self.lexm_heaps_browser,
         self.btn_lexm_heaps_svg, self.btn_lexm_heaps_png) = _chart_tab(
            560, "advanced_lexicometry_chart"
        )
        self.btn_lexm_heaps_svg.clicked.connect(
            lambda: self._save_chart(
                "_lexm_heaps_svg", "svg", "Exportar curva de Heaps",
                "heaps",
            )
        )
        self.btn_lexm_heaps_png.clicked.connect(
            lambda: self._save_chart(
                "_lexm_heaps_svg", "png", "Exportar curva de Heaps",
                "heaps",
            )
        )
        self._lexm_heaps_svg = ""
        self.lexm_tabs.addTab(heaps_widget, "🌱 Heaps")

        self.lexm_metrics = DataTable(["Métrica", "Valor", "Unidade"])
        self.lexm_tabs.addTab(
            _with_help(self.lexm_metrics, "advanced_lexicometry_metrics"),
            "📐 Métricas",
        )

        self.lexm_terms = DataTable([
            "Termo", "Ocorrências", "Por 1k", "Por 10k", "DP", "DP norm.",
            "Juilland D",
        ], search=True)
        self.lexm_tabs.addTab(
            _with_help(self.lexm_terms, "advanced_lexicometry_terms"),
            "🔤 Termos",
        )

        self.lexm_ngrams = DataTable(
            ["N-grama", "N", "Ocorrências", "Por 10k"], search=True
        )
        self.lexm_tabs.addTab(
            _with_help(self.lexm_ngrams, "advanced_lexicometry_ngrams"),
            "🔗 N-gramas",
        )

        self.lexm_collocations = DataTable([
            "Par", "Ocorrências", "PMI", "G²", "t-score", "Dice", "Direção",
        ], search=True)
        self.lexm_tabs.addTab(
            _with_help(
                self.lexm_collocations, "advanced_lexicometry_collocations"
            ),
            "🧷 Colocações",
        )

        self.lexm_variation = DataTable([
            "Tipo", "Seção/Termo", "Tokens/Início", "Tipos/Fim", "TTR/Δ",
            "Termos",
        ])
        self.lexm_tabs.addTab(
            _with_help(self.lexm_variation, "advanced_lexicometry_variation"),
            "🔀 Variação",
        )

        self.lexm_periods = DataTable(
            ["Período", "Data", "Tokens", "Tipos", "Termos"]
        )
        self.lexm_tabs.addTab(
            _with_help(self.lexm_periods, "advanced_lexicometry_periods"),
            "🗓️ Períodos",
        )

        lexm_layout.addWidget(self.lexm_tabs, 1)
        # Página promovida a aba de topo pelo MainWindow.
        self.page_lexicometry = lexm_widget

        # Linguística estrutural (Fase 16)
        ling_widget = QWidget()
        ling_layout = QVBoxLayout(ling_widget)
        ling_layout.setContentsMargins(8, 8, 8, 8)
        self.ling_help = HelpPanel("advanced_linguistics", expanded=False)
        ling_layout.addWidget(self.ling_help)
        self.ling_summary = QLabel("—")
        self.ling_summary.setStyleSheet("color:#5b6673;")
        self.ling_summary.setWordWrap(True)
        ling_layout.addWidget(self.ling_summary)
        self.ling_section = QComboBox()
        self.ling_section.addItem("Todas as seções", -1)
        self.ling_section.currentIndexChanged.connect(
            self._filter_ling_sections
        )
        ling_layout.addWidget(self.ling_section)
        self.ling_tabs = QTabWidget()
        self.ling_overview = DataTable(["Métrica", "Valor", "Unidade"])
        self.ling_tabs.addTab(
            _with_help(self.ling_overview, "advanced_linguistics_overview"),
            "🔎 Resumo",
        )
        self.ling_pos = DataTable(
            ["Classe", "Rótulo", "Ocorrências", "Proporção", "Origem"]
        )
        self.ling_tabs.addTab(
            _with_help(self.ling_pos, "advanced_linguistics_pos"),
            "🔤 Classes",
        )
        self.ling_syntax = DataTable(
            ["Tipo", "Trecho", "Marcador", "Confiança"]
        )
        self.ling_tabs.addTab(
            _with_help(self.ling_syntax, "advanced_linguistics_syntax"),
            "🧩 Sintaxe",
        )
        self.ling_fields = DataTable(
            ["Campo", "Ocorrências", "Por 1k", "Proporção", "Termos"]
        )
        self.ling_tabs.addTab(
            _with_help(self.ling_fields, "advanced_linguistics_fields"),
            "🗂️ Campos semânticos",
        )
        self.ling_markers = DataTable(
            ["Categoria", "Marcador", "Ocorrências"]
        )
        self.ling_tabs.addTab(
            _with_help(self.ling_markers, "advanced_linguistics_markers"),
            "🔗 Marcadores",
        )
        self.ling_coref = DataTable(
            ["Nome", "Tipo", "Menções", "Confiança", "Aliases"]
        )
        self.ling_tabs.addTab(
            _with_help(self.ling_coref, "advanced_linguistics_coreference"),
            "👥 Correferência",
        )
        self.ling_sections = DataTable([
            "Seção", "Papel", "POS principal", "Sentença média", "Passiva",
            "Campos", "Marcadores", "Menções",
        ])
        self.ling_tabs.addTab(
            _with_help(self.ling_sections, "advanced_linguistics_sections"),
            "📑 Por seção",
        )
        ling_layout.addWidget(self.ling_tabs, 1)
        # Página promovida a aba de topo pelo MainWindow.
        self.page_linguistics = ling_widget

        # Estilo e estilometria (Fase 16)
        style_widget = QWidget()
        style_layout = QVBoxLayout(style_widget)
        style_layout.setContentsMargins(8, 8, 8, 8)
        self.style_help = HelpPanel("advanced_stylometry", expanded=False)
        style_layout.addWidget(self.style_help)
        self.style_summary = QLabel("—")
        self.style_summary.setStyleSheet("color:#5b6673;")
        self.style_summary.setWordWrap(True)
        style_layout.addWidget(self.style_summary)
        self.style_section = QComboBox()
        self.style_section.addItem("Todas as seções", -1)
        self.style_section.currentIndexChanged.connect(
            self._filter_style_sections
        )
        style_layout.addWidget(self.style_section)
        self.style_tabs = QTabWidget()
        self.style_metrics = DataTable(["Medida", "Valor", "Unidade"])
        self.style_tabs.addTab(
            _with_help(self.style_metrics, "advanced_stylometry_metrics"),
            "📐 Métricas",
        )
        self.style_punct = DataTable(["Marca", "Ocorrências"])
        self.style_tabs.addTab(
            _with_help(self.style_punct, "advanced_stylometry_punctuation"),
            "✒️ Pontuação",
        )
        self.style_function = DataTable(
            ["Termo", "Ocorrências", "Por 1k", "Proporção"]
        )
        self.style_tabs.addTab(
            _with_help(self.style_function, "advanced_stylometry_function"),
            "🧱 Palavras funcionais",
        )
        self.style_repetition = DataTable(
            ["Termo", "Ocorrências", "Por 1k"]
        )
        self.style_tabs.addTab(
            _with_help(
                self.style_repetition, "advanced_stylometry_repetition"
            ),
            "🔁 Repetição",
        )
        self.style_sections = DataTable([
            "Seção", "Papel", "Palavras", "Sentenças", "Frase média",
            "Funcionais", "Pontuação/1k", "Termos",
        ])
        self.style_tabs.addTab(
            _with_help(self.style_sections, "advanced_stylometry_sections"),
            "📑 Por seção",
        )
        style_layout.addWidget(self.style_tabs, 1)
        # Página promovida a aba de topo pelo MainWindow.
        self.page_style = style_widget

        # Pesquisa e documentos acadêmicos (Fase 17)
        research_widget = QWidget()
        research_layout = QVBoxLayout(research_widget)
        research_layout.setContentsMargins(8, 8, 8, 8)
        self.research_help = HelpPanel("advanced_research", expanded=False)
        research_layout.addWidget(self.research_help)
        self.research_summary = QLabel("—")
        self.research_summary.setStyleSheet("color:#5b6673;")
        self.research_summary.setWordWrap(True)
        research_layout.addWidget(self.research_summary)
        self.research_tabs = QTabWidget()
        self.research_imrad = DataTable([
            "Parte", "Situação", "Origem", "Confiança", "Ambígua",
            "Observação",
        ])
        self.research_tabs.addTab(
            _with_help(self.research_imrad, "advanced_research_imrad"),
            "🗺️ IMRaD",
        )
        (ribbon_widget, self.research_ribbon_view,
         self.research_ribbon_browser, self.btn_research_ribbon_svg,
         self.btn_research_ribbon_png) = _chart_tab(
            260, "advanced_research_imrad"
        )
        self.btn_research_ribbon_svg.clicked.connect(
            lambda: self._save_chart(
                "_research_ribbon_svg", "svg", "Exportar faixa IMRaD",
                "faixa_imrad",
            )
        )
        self.btn_research_ribbon_png.clicked.connect(
            lambda: self._save_chart(
                "_research_ribbon_svg", "png", "Exportar faixa IMRaD",
                "faixa_imrad",
            )
        )
        self._research_ribbon_svg = ""
        self.research_tabs.addTab(ribbon_widget, "📏 Faixa IMRaD")
        self.research_citations = DataTable([
            "Citação", "Função", "Polaridade", "Confiança", "Trecho",
        ])
        self.research_tabs.addTab(
            _with_help(
                self.research_citations, "advanced_research_citations"
            ),
            "🧭 Função das citações",
        )
        (donut_widget, self.research_citation_view,
         self.research_citation_browser,
         self.btn_research_citation_svg,
         self.btn_research_citation_png) = _chart_tab(
            470, "advanced_research_citations"
        )
        self.btn_research_citation_svg.clicked.connect(
            lambda: self._save_chart(
                "_research_citation_svg", "svg",
                "Exportar função das citações", "funcao_citacoes",
            )
        )
        self.btn_research_citation_png.clicked.connect(
            lambda: self._save_chart(
                "_research_citation_svg", "png",
                "Exportar função das citações", "funcao_citacoes",
            )
        )
        self._research_citation_svg = ""
        self.research_tabs.addTab(
            donut_widget, "🍩 Função das citações"
        )
        self.research_method = DataTable([
            "Categoria", "Valor", "Confiança", "Trecho",
        ])
        self.research_tabs.addTab(
            _with_help(self.research_method, "advanced_research_methodology"),
            "🧪 Metodologia",
        )
        self.research_gaps = DataTable([
            "Natureza", "Descrição", "Confiança", "Observação",
        ])
        self.research_tabs.addTab(
            _with_help(self.research_gaps, "advanced_research_gaps"),
            "🧩 Lacunas",
        )
        self.research_matrix = DataTable(
            list(extraction_matrix.COLUMN_LABELS)
        )
        self.research_tabs.addTab(
            _with_help(self.research_matrix, "advanced_research_matrix"),
            "📋 Matriz",
        )
        research_layout.addWidget(self.research_tabs, 1)
        # Página promovida a aba de topo pelo MainWindow.
        self.page_research = research_widget

        # Discurso, retórica e argumentação (Fase 18)
        disc_widget = QWidget()
        disc_layout = QVBoxLayout(disc_widget)
        disc_layout.setContentsMargins(8, 8, 8, 8)
        self.disc_help = HelpPanel("advanced_discourse", expanded=False)
        disc_layout.addWidget(self.disc_help)
        self.disc_warning = QLabel(
            "Leitura interpretativa: os itens abaixo descrevem marcas do "
            "texto. Não são veredito sobre o autor, sua ideologia ou a "
            "qualidade do argumento."
        )
        self.disc_warning.setWordWrap(True)
        self.disc_warning.setStyleSheet(
            "color:#8a4b00; background:#fff4e0; padding:6px; "
            "border:1px solid #e0b060; border-radius:4px;"
        )
        disc_layout.addWidget(self.disc_warning)
        self.disc_summary = QLabel("—")
        self.disc_summary.setStyleSheet("color:#5b6673;")
        self.disc_summary.setWordWrap(True)
        disc_layout.addWidget(self.disc_summary)
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Confiança:"))
        self.disc_confidence = QComboBox()
        self.disc_confidence.addItem("Todas", "")
        for level in ("alta", "media", "baixa"):
            self.disc_confidence.addItem(level, level)
        self.disc_confidence.currentIndexChanged.connect(
            self._filter_discourse_confidence
        )
        filter_row.addWidget(self.disc_confidence)
        filter_row.addStretch(1)
        disc_layout.addLayout(filter_row)
        self.disc_tabs = QTabWidget()
        (rhet_widget, self.rhetoric_view, self.rhetoric_browser,
         self.btn_rhetoric_svg, self.btn_rhetoric_png) = _chart_tab(
            620, "advanced_discourse_rhetoric"
        )
        self.btn_rhetoric_svg.clicked.connect(
            lambda: self._save_chart(
                "_rhetoric_svg", "svg", "Exportar triângulo retórico",
                "triangulo_retorico",
            )
        )
        self.btn_rhetoric_png.clicked.connect(
            lambda: self._save_chart(
                "_rhetoric_svg", "png", "Exportar triângulo retórico",
                "triangulo_retorico",
            )
        )
        self._rhetoric_svg = ""
        self.disc_tabs.addTab(rhet_widget, "△ Retórica")

        (stance_widget, self.stance_view, self.stance_browser,
         self.btn_stance_svg, self.btn_stance_png) = _chart_tab(
            700, "advanced_discourse_stance"
        )
        self.btn_stance_svg.clicked.connect(
            lambda: self._save_chart(
                "_stance_svg", "svg", "Exportar posicionamento",
                "posicionamento",
            )
        )
        self.btn_stance_png.clicked.connect(
            lambda: self._save_chart(
                "_stance_svg", "png", "Exportar posicionamento",
                "posicionamento",
            )
        )
        self._stance_svg = ""
        self.disc_tabs.addTab(stance_widget, "📊 Posicionamento")

        self.disc_rhetoric = DataTable([
            "Eixo", "Indicador", "Termo", "Confiança", "Trecho",
        ])
        self.disc_tabs.addTab(
            _with_help(self.disc_rhetoric, "advanced_discourse_rhetoric"),
            "🗣️ Retórica",
        )
        self.disc_toulmin = DataTable([
            "Claim", "Confiança", "Lacunas",
        ])
        self.disc_tabs.addTab(
            _with_help(self.disc_toulmin, "advanced_discourse_toulmin"),
            "🧱 Toulmin",
        )
        self.disc_cda = DataTable([
            "Tipo", "Marcador", "Confiança", "Trecho",
        ])
        self.disc_tabs.addTab(
            _with_help(self.disc_cda, "advanced_discourse_cda"),
            "🔍 CDA",
        )
        self.disc_stance = DataTable([
            "Alvo", "Posição", "Confiança", "Trecho",
        ])
        self.disc_tabs.addTab(
            _with_help(self.disc_stance, "advanced_discourse_stance"),
            "⚖️ Posicionamento",
        )
        self.disc_framing = DataTable([
            "Eixo", "Termos", "Ocorrências", "Confiança",
        ])
        self.disc_tabs.addTab(
            _with_help(self.disc_framing, "advanced_discourse_framing"),
            "🖼️ Enquadramento",
        )
        disc_layout.addWidget(self.disc_tabs, 1)
        # Página promovida a aba de topo pelo MainWindow.
        self.page_discourse = disc_widget

        # Conhecimento, entidades e documentos (Fase 19)
        know_widget = QWidget()
        know_layout = QVBoxLayout(know_widget)
        know_layout.setContentsMargins(8, 8, 8, 8)
        self.know_help = HelpPanel("advanced_knowledge", expanded=False)
        know_layout.addWidget(self.know_help)
        self.know_warning = QLabel(
            "Leitura probabilística e interpretativa: relações, ontologia, "
            "terminologia e eventos descrevem o que o texto declara. "
            "Afirmações não são verificadas automaticamente e nenhum item "
            "julga a verdade do documento."
        )
        self.know_warning.setWordWrap(True)
        self.know_warning.setStyleSheet(
            "color:#8a4b00; background:#fff4e0; padding:6px; "
            "border:1px solid #e0b060; border-radius:4px;"
        )
        know_layout.addWidget(self.know_warning)
        self.know_summary = QLabel("—")
        self.know_summary.setStyleSheet("color:#5b6673;")
        self.know_summary.setWordWrap(True)
        know_layout.addWidget(self.know_summary)
        self.know_tabs = QTabWidget()
        self.know_relations = DataTable([
            "Tipo", "Sujeito", "Verbo", "Objeto", "Confiança",
        ])
        self.know_tabs.addTab(
            _with_help(self.know_relations, "advanced_knowledge_relations"),
            "🔗 Relações",
        )

        ontology_widget = QWidget()
        ontology_layout = QVBoxLayout(ontology_widget)
        ontology_layout.setContentsMargins(4, 4, 4, 4)
        ontology_buttons = QHBoxLayout()
        self.btn_onto_add = QPushButton("➕ Adicionar conceito")
        self.btn_onto_add.clicked.connect(self._add_ontology_concept)
        ontology_buttons.addWidget(self.btn_onto_add)
        self.btn_onto_remove = QPushButton("➖ Remover selecionado")
        self.btn_onto_remove.clicked.connect(self._remove_ontology_concept)
        ontology_buttons.addWidget(self.btn_onto_remove)
        self.btn_onto_undo = QPushButton("↶ Desfazer")
        self.btn_onto_undo.setToolTip(
            "Desfaz a última inclusão ou remoção de conceito"
        )
        self.btn_onto_undo.setEnabled(False)
        self.btn_onto_undo.clicked.connect(self._undo_ontology)
        ontology_buttons.addWidget(self.btn_onto_undo)
        self.btn_onto_export = QPushButton("💾 Exportar ontologia")
        self.btn_onto_export.clicked.connect(self._export_ontology)
        ontology_buttons.addWidget(self.btn_onto_export)
        ontology_buttons.addStretch(1)
        ontology_layout.addLayout(ontology_buttons)
        self.know_ontology = DataTable([
            "Conceito", "Pai", "Nível", "Ocorrências", "Confiança", "Editado",
        ])
        ontology_layout.addWidget(self.know_ontology, 1)
        self.know_tabs.addTab(
            _with_help(ontology_widget, "advanced_knowledge_ontology"),
            "🌳 Ontologia",
        )

        self.know_terms = DataTable([
            "Termo", "Tipo", "Definição", "Ocorrências", "Confiança",
        ])
        self.know_tabs.addTab(
            _with_help(self.know_terms, "advanced_knowledge_terms"),
            "📖 Terminologia",
        )
        self.know_events = DataTable([
            "Evento", "Data", "Relação", "Base", "Confiança",
        ])
        self.know_tabs.addTab(
            _with_help(self.know_events, "advanced_knowledge_events"),
            "🗓️ Eventos",
        )
        self.know_claims = DataTable([
            "Tipo", "Sujeito", "Valor", "Período", "Confiança", "Trecho",
        ])
        self.know_tabs.addTab(
            _with_help(self.know_claims, "advanced_knowledge_claims"),
            "📌 Afirmações",
        )
        know_layout.addWidget(self.know_tabs, 1)
        # Página promovida a aba de topo pelo MainWindow.
        self.page_knowledge = know_widget

        # Consistência interna, paráfrase e versões (Fase 19)
        consist_widget = QWidget()
        consist_layout = QVBoxLayout(consist_widget)
        consist_layout.setContentsMargins(8, 8, 8, 8)
        self.consist_help = HelpPanel("advanced_consistency", expanded=False)
        consist_layout.addWidget(self.consist_help)
        self.consist_warning = QLabel(
            "Os achados são suspeitas para revisão humana. Nenhuma regra "
            "decide se o documento está certo ou errado; não há veredito "
            "automático nem fact-checking."
        )
        self.consist_warning.setWordWrap(True)
        self.consist_warning.setStyleSheet(
            "color:#8a4b00; background:#fff4e0; padding:6px; "
            "border:1px solid #e0b060; border-radius:4px;"
        )
        consist_layout.addWidget(self.consist_warning)
        self.consist_summary = QLabel("—")
        self.consist_summary.setStyleSheet("color:#5b6673;")
        self.consist_summary.setWordWrap(True)
        consist_layout.addWidget(self.consist_summary)
        self.consist_tabs = QTabWidget()
        self.consist_findings = DataTable([
            "Regra", "Descrição", "Confiança", "Evidências",
        ])
        self.consist_tabs.addTab(
            _with_help(
                self.consist_findings, "advanced_consistency_findings"
            ),
            "🔎 Achados",
        )

        paraphrase_widget = QWidget()
        paraphrase_layout = QVBoxLayout(paraphrase_widget)
        paraphrase_layout.setContentsMargins(4, 4, 4, 4)
        paraphrase_buttons = QHBoxLayout()
        self.btn_paraphrase_load = QPushButton(
            "📄 Carregar segundo documento..."
        )
        self.btn_paraphrase_load.clicked.connect(
            self._compare_paraphrase_file
        )
        paraphrase_buttons.addWidget(self.btn_paraphrase_load)
        paraphrase_buttons.addStretch(1)
        paraphrase_layout.addLayout(paraphrase_buttons)
        self.para_summary = QLabel(
            "Carregue um segundo documento para comparar níveis de paráfrase."
        )
        self.para_summary.setStyleSheet("color:#5b6673;")
        self.para_summary.setWordWrap(True)
        paraphrase_layout.addWidget(self.para_summary)
        self.para_table = DataTable([
            "Nível", "Documento A", "Documento B", "Similaridade",
            "Confiança",
        ])
        paraphrase_layout.addWidget(self.para_table, 1)
        self.consist_tabs.addTab(
            _with_help(
                paraphrase_widget, "advanced_consistency_paraphrase"
            ),
            "🪞 Paráfrase",
        )

        versions_widget = QWidget()
        versions_layout = QVBoxLayout(versions_widget)
        versions_layout.setContentsMargins(4, 4, 4, 4)
        versions_buttons = QHBoxLayout()
        self.btn_versions_load = QPushButton("📄 Carregar versão B...")
        self.btn_versions_load.clicked.connect(self._compare_versions_file)
        versions_buttons.addWidget(self.btn_versions_load)
        versions_buttons.addStretch(1)
        versions_layout.addLayout(versions_buttons)
        self.vers_summary = QLabel(
            "Carregue outra versão para comparar inclusões, exclusões e "
            "modificações."
        )
        self.vers_summary.setStyleSheet("color:#5b6673;")
        self.vers_summary.setWordWrap(True)
        versions_layout.addWidget(self.vers_summary)
        self.vers_table = DataTable([
            "Mudança", "Versão A", "Versão B", "Similaridade", "Confiança",
        ])
        versions_layout.addWidget(self.vers_table, 1)
        self.consist_tabs.addTab(
            _with_help(versions_widget, "advanced_consistency_versions"),
            "🕓 Versões",
        )
        consist_layout.addWidget(self.consist_tabs, 1)
        # Página promovida a aba de topo pelo MainWindow.
        self.page_consistency = consist_widget

        self._disc_rows: dict = {}
        self._onto_data: dict = {}
        self._onto_history: list = []
        self._source_text: str = ""

        self._ling_section_rows: list = []
        self._style_section_rows: list = []

        # Tópicos
        topics_widget = QWidget()
        topics_layout = QVBoxLayout(topics_widget)
        topics_layout.setContentsMargins(8, 8, 8, 8)
        self.topics_help = HelpPanel("advanced_topics", expanded=False)
        topics_layout.addWidget(self.topics_help)
        self.topics_info = QLabel(explanations.ANALYSIS_EXPLANATIONS.get('topicos', ''))
        self.topics_info.setWordWrap(True)
        self.topics_info.setStyleSheet('color:#5b6673;')
        topics_layout.addWidget(self.topics_info)
        self.topics_browser = QTextBrowser()
        topics_layout.addWidget(self.topics_browser)
        self.tabs.addTab(topics_widget, "🗂️ Tópicos (LDA)")

        # Clusters
        clusters_widget = QWidget()
        clusters_layout = QVBoxLayout(clusters_widget)
        clusters_layout.setContentsMargins(8, 8, 8, 8)
        self.clusters_help = HelpPanel("advanced_clusters", expanded=False)
        clusters_layout.addWidget(self.clusters_help)
        self.clusters_info = QLabel(explanations.ANALYSIS_EXPLANATIONS.get('agrupamentos', ''))
        self.clusters_info.setWordWrap(True)
        self.clusters_info.setStyleSheet('color:#5b6673;')
        clusters_layout.addWidget(self.clusters_info)
        self.clusters_browser = QTextBrowser()
        clusters_layout.addWidget(self.clusters_browser)
        self.tabs.addTab(clusters_widget, "🧩 Agrupamentos")

        # Sentimentos
        sent_widget = QWidget()
        sent_layout = QVBoxLayout(sent_widget)
        sent_layout.setContentsMargins(8, 8, 8, 8)
        self.sent_help = HelpPanel("advanced_sentiment", expanded=False)
        sent_layout.addWidget(self.sent_help)
        self.sent_summary = QLabel("—")
        self.sent_summary.setStyleSheet("color:#5b6673;")
        sent_layout.addWidget(self.sent_summary)
        self.sent_table = DataTable([
            "Sentença", "Polaridade", "Score", "Intensidade", "Domínio",
            "Explicação",
        ])
        sent_layout.addWidget(self.sent_table)
        self.tabs.addTab(sent_widget, "🙂 Sentimentos")

        # Argumentos
        arg_widget = QWidget()
        arg_layout = QVBoxLayout(arg_widget)
        arg_layout.setContentsMargins(8, 8, 8, 8)
        self.arg_help = HelpPanel("advanced_argument", expanded=False)
        arg_layout.addWidget(self.arg_help)
        self.arg_summary = QLabel("—")
        self.arg_summary.setStyleSheet("color:#5b6673;")
        self.arg_summary.setWordWrap(True)
        arg_layout.addWidget(self.arg_summary)
        self.arg_table = DataTable(["Tipo", "Trecho", "Conectores", "Score"])
        arg_layout.addWidget(self.arg_table)
        self.tabs.addTab(arg_widget, "⚖️ Argumentos")

        # Definições
        def_widget = QWidget()
        def_layout = QVBoxLayout(def_widget)
        def_layout.setContentsMargins(8, 8, 8, 8)
        self.def_help = HelpPanel("advanced_definitions", expanded=False)
        def_layout.addWidget(self.def_help)
        self.def_summary = QLabel("—")
        self.def_summary.setStyleSheet("color:#5b6673;")
        def_layout.addWidget(self.def_summary)
        self.def_table = DataTable(["Termo", "Definição", "Padrão", "Confiança"])
        def_layout.addWidget(self.def_table)
        self.tabs.addTab(def_widget, "📔 Definições")

        # Linha do tempo
        time_widget = QWidget()
        time_layout = QVBoxLayout(time_widget)
        time_layout.setContentsMargins(8, 8, 8, 8)
        self.time_help = HelpPanel("advanced_timeline", expanded=False)
        time_layout.addWidget(self.time_help)
        self.time_summary = QLabel("—")
        self.time_summary.setStyleSheet("color:#5b6673;")
        time_layout.addWidget(self.time_summary)
        self.time_table = DataTable([
            "Data", "Normalizada", "Precisão", "Trecho", "Outras datas",
            "Parágrafo",
        ])
        time_layout.addWidget(self.time_table)
        self.tabs.addTab(time_widget, "🕰️ Linha do tempo")

        # Análise temporal (gráfico por ano)
        temporal_widget = QWidget()
        temporal_layout = QVBoxLayout(temporal_widget)
        temporal_layout.setContentsMargins(8, 8, 8, 8)
        self.temporal_help = HelpPanel("advanced_temporal", expanded=False)
        temporal_layout.addWidget(self.temporal_help)
        self.temporal_label = QLabel("—")
        self.temporal_label.setStyleSheet("color:#5b6673;")
        self.temporal_label.setWordWrap(True)
        temporal_layout.addWidget(self.temporal_label)
        bar = QHBoxLayout()
        bar.addStretch()
        self.btn_temporal_svg = QPushButton("💾 SVG")
        self.btn_temporal_svg.setEnabled(False)
        self.btn_temporal_svg.clicked.connect(
            lambda: self._save_temporal("svg")
        )
        bar.addWidget(self.btn_temporal_svg)
        self.btn_temporal_png = QPushButton("💾 PNG")
        self.btn_temporal_png.setEnabled(False)
        self.btn_temporal_png.clicked.connect(
            lambda: self._save_temporal("png")
        )
        bar.addWidget(self.btn_temporal_png)
        temporal_layout.addLayout(bar)
        if QSvgWidget is not None:
            self.temporal_view = QSvgWidget()
            self.temporal_view.setFixedSize(900, 440)
            scroll = QScrollArea()
            scroll.setWidgetResizable(False)
            scroll.setAlignment(Qt.AlignCenter)
            scroll.setWidget(self.temporal_view)
            temporal_layout.addWidget(scroll, 1)
        else:  # pragma: no cover
            self.temporal_view = None
            self.temporal_browser = QTextBrowser()
            temporal_layout.addWidget(self.temporal_browser, 1)
        self._temporal_svg = ""
        self.tabs.addTab(temporal_widget, "📈 Temporal")

        # Modelos opcionais e IA local (Fase 21)
        models_widget = QWidget()
        models_layout = QVBoxLayout(models_widget)
        models_layout.setContentsMargins(8, 8, 8, 8)
        self.models_help = HelpPanel("advanced_models", expanded=False)
        models_layout.addWidget(self.models_help)
        self.models_summary = QLabel("—")
        self.models_summary.setWordWrap(True)
        self.models_summary.setStyleSheet("color:#5b6673;")
        models_layout.addWidget(self.models_summary)
        models_bar = QHBoxLayout()
        models_bar.addStretch()
        self.btn_models_caps = QPushButton("🔄 Verificar capacidades")
        self.btn_models_caps.clicked.connect(self._refresh_model_caps)
        models_bar.addWidget(self.btn_models_caps)
        self.btn_models_ollama = QPushButton("🩺 Verificar Ollama")
        self.btn_models_ollama.clicked.connect(self._check_ollama_status)
        models_bar.addWidget(self.btn_models_ollama)
        self.btn_models_export = QPushButton("💾 Exportar divergências")
        self.btn_models_export.setEnabled(False)
        self.btn_models_export.clicked.connect(self._export_models_report)
        models_bar.addWidget(self.btn_models_export)
        models_layout.addLayout(models_bar)
        self.models_caps = DataTable(
            ["Motor", "Tipo", "Disponível", "Versão", "Observação"]
        )
        self.models_caps.setMaximumHeight(190)
        models_layout.addWidget(self.models_caps)
        self.models_results = DataTable(["Bloco", "Métrica", "Valor"])
        self.models_results.setMaximumHeight(160)
        models_layout.addWidget(self.models_results)
        self.models_compare = DataTable(
            ["Comparação", "Status", "Métrica", "Valor"]
        )
        self.models_compare.setMaximumHeight(190)
        models_layout.addWidget(self.models_compare)
        self.models_notes = QTextBrowser()
        self.models_notes.setOpenExternalLinks(False)
        models_layout.addWidget(self.models_notes, 1)
        self._models_payload: dict = {}
        self.tabs.addTab(models_widget, "🤖 Modelos (opcional)")
        self._refresh_model_caps()

        # As sete páginas abaixo são abas de topo no MainWindow. Elas deixaram
        # de ser sub-abas de Análise avançada, mas continuam sendo preenchidas
        # e limpas por este widget (update_results/clear).
        self.promoted_tabs = [
            (self.page_lexicometry, "tab.lexicometry", "📊 Lexicometria"),
            (self.page_linguistics, "tab.linguistics", "🔤 Linguística"),
            (self.page_style, "tab.style", "🎨 Estilo"),
            (self.page_research, "tab.research", "🎓 Pesquisa"),
            (self.page_discourse, "tab.discourse", "🗣️ Discurso"),
            (self.page_knowledge, "tab.knowledge", "🧠 Conhecimento"),
            (self.page_consistency, "tab.consistency", "🧭 Consistência"),
        ]

        layout.addWidget(self.tabs, 1)

    def clear(self) -> None:
        for tile in self.read_tiles.values():
            tile.set_value("—")
        self.lex_table.set_rows([])
        self.lexm_summary.setText("—")
        self.lexm_warnings.setText("")
        self.lexm_metrics.set_rows([])
        self.lexm_terms.set_rows([])
        self.lexm_ngrams.set_rows([])
        self.lexm_collocations.set_rows([])
        self.lexm_variation.set_rows([])
        self.lexm_periods.set_rows([])
        self._lexm_svg = ""
        if self.lexm_view is not None:
            self.lexm_view.load(b"")
        self.btn_lexm_svg.setEnabled(False)
        self.btn_lexm_png.setEnabled(False)
        self._lexm_dispersion_svg = ""
        if self.lexm_dispersion_view is not None:
            self.lexm_dispersion_view.load(b"")
        self.btn_lexm_dispersion_svg.setEnabled(False)
        self.btn_lexm_dispersion_png.setEnabled(False)
        for attr, view, btn_svg, btn_png in (
            ("_lexm_zipf_svg", self.lexm_zipf_view,
             self.btn_lexm_zipf_svg, self.btn_lexm_zipf_png),
            ("_lexm_heaps_svg", self.lexm_heaps_view,
             self.btn_lexm_heaps_svg, self.btn_lexm_heaps_png),
        ):
            setattr(self, attr, "")
            if view is not None:
                view.load(b"")
            btn_svg.setEnabled(False)
            btn_png.setEnabled(False)
        self.ling_summary.setText("—")
        for table in (
            self.ling_overview, self.ling_pos, self.ling_syntax,
            self.ling_fields, self.ling_markers, self.ling_coref,
            self.ling_sections,
        ):
            table.set_rows([])
        self.ling_section.blockSignals(True)
        self.ling_section.clear()
        self.ling_section.addItem("Todas as seções", -1)
        self.ling_section.blockSignals(False)
        self._ling_section_rows = []
        self.style_summary.setText("—")
        for table in (
            self.style_metrics, self.style_punct, self.style_function,
            self.style_repetition, self.style_sections,
        ):
            table.set_rows([])
        self.style_section.blockSignals(True)
        self.style_section.clear()
        self.style_section.addItem("Todas as seções", -1)
        self.style_section.blockSignals(False)
        self._style_section_rows = []
        self.research_summary.setText("—")
        for table in (
            self.research_imrad, self.research_citations,
            self.research_method, self.research_gaps, self.research_matrix,
        ):
            table.set_rows([])
        self._research_ribbon_svg = ""
        if self.research_ribbon_view is not None:
            self.research_ribbon_view.load(b"")
        self.btn_research_ribbon_svg.setEnabled(False)
        self.btn_research_ribbon_png.setEnabled(False)
        self._research_citation_svg = ""
        if self.research_citation_view is not None:
            self.research_citation_view.load(b"")
        self.btn_research_citation_svg.setEnabled(False)
        self.btn_research_citation_png.setEnabled(False)
        self.disc_summary.setText("—")
        for table in (
            self.disc_rhetoric, self.disc_toulmin, self.disc_cda,
            self.disc_stance, self.disc_framing,
        ):
            table.set_rows([])
        self._rhetoric_svg = ""
        if self.rhetoric_view is not None:
            self.rhetoric_view.load(b"")
        self.btn_rhetoric_svg.setEnabled(False)
        self.btn_rhetoric_png.setEnabled(False)
        self._stance_svg = ""
        if self.stance_view is not None:
            self.stance_view.load(b"")
        self.btn_stance_svg.setEnabled(False)
        self.btn_stance_png.setEnabled(False)
        self._disc_rows = {}
        self.disc_confidence.blockSignals(True)
        self.disc_confidence.setCurrentIndex(0)
        self.disc_confidence.blockSignals(False)
        self.know_summary.setText("—")
        for table in (
            self.know_relations, self.know_ontology, self.know_terms,
            self.know_events, self.know_claims,
        ):
            table.set_rows([])
        self._onto_data = {}
        self._onto_history = []
        self._update_onto_undo()
        self.consist_summary.setText("—")
        for table in (
            self.consist_findings, self.para_table, self.vers_table,
        ):
            table.set_rows([])
        self.para_summary.setText(
            "Carregue um segundo documento para comparar níveis de paráfrase."
        )
        self.vers_summary.setText(
            "Carregue outra versão para comparar inclusões, exclusões e "
            "modificações."
        )
        self._source_text = ""
        self.topics_browser.clear()
        self.clusters_browser.clear()
        self.sent_summary.setText("—")
        self.sent_table.set_rows([])
        self.arg_summary.setText("—")
        self.arg_table.set_rows([])
        self.def_summary.setText("—")
        self.def_table.set_rows([])
        self.time_summary.setText("—")
        self.time_table.set_rows([])
        self.temporal_label.setText("—")
        self._temporal_svg = ""
        if self.temporal_view is not None:
            self.temporal_view.load(b"")
        self.btn_temporal_svg.setEnabled(False)
        self.btn_temporal_png.setEnabled(False)
        self._models_payload = {}
        self.btn_models_export.setEnabled(False)
        self.models_summary.setText("—")
        self.models_results.set_rows([])
        self.models_compare.set_rows([])
        self.models_notes.clear()

    def update_results(self, result: dict, text: str = "") -> None:
        self._source_text = text or ""
        self._render_readability(result.get("readability", {}))
        self._render_lexical(result.get("lexical", {}))
        self._render_lexicometry(result.get("lexicometry") or {})
        self._render_linguistics(result.get("linguistics") or {})
        self._render_stylometry(result.get("linguistics") or {})
        self._render_research(result.get("academic") or {})
        self._render_discourse(result.get("discourse") or {})
        self._render_knowledge(result.get("knowledge") or {})
        self._render_consistency(result.get("knowledge") or {})
        self._render_topics(result.get("topics", []))
        self._render_clusters(result.get("clusters", []))
        self._render_sentiment(result.get("sentiment") or {})
        self._render_arguments(result.get("argument_map") or {})
        self._render_definitions(result.get("definitions") or {})
        self._render_timeline(result.get("timeline") or {})
        self._render_temporal(result.get("timeline") or {})
        self._render_models(result.get("models") or {})

    # ------------------------------------------------------------------
    def _refresh_model_caps(self) -> None:
        try:
            caps = model_layer.capabilities()
        except Exception as exc:  # noqa: BLE001 - painel nunca derruba a UI
            self.models_notes.setPlainText(
                f"Falha ao detectar modelos opcionais: {exc}"
            )
            return
        rows = []
        for engine in caps.get("engines") or []:
            rows.append((
                engine.get("name", ""),
                engine.get("kind", ""),
                "Sim" if engine.get("available") else "Não",
                engine.get("version") or "—",
                engine.get("note", ""),
            ))
        self.models_caps.set_rows(rows)
        if not self._models_payload:
            self.models_summary.setText(
                "Camada opcional desativada. Ative em Configurações → "
                "“Ativar camada de modelos opcionais” para comparar modelos "
                "locais com a análise determinística. Nenhum modelo é "
                "necessário para o relatório."
            )

    def _check_ollama_status(self) -> None:
        status = model_layer.ollama_status()
        running = status.get("running")
        installed = status.get("installed")
        details = []
        if status.get("version"):
            details.append(f"versão {status['version']}")
        if status.get("models"):
            details.append(f"{len(status['models'])} modelo(s) listado(s)")
        if status.get("error"):
            details.append(str(status["error"]))
        message = (
            "Ollama em execução." if running
            else ("Ollama instalado, mas o servidor não respondeu."
                  if installed else "Ollama não encontrado.")
        )
        if details:
            message += "\n\n" + "; ".join(details)
        QMessageBox.information(self, "Ollama local", message)

    def _export_models_report(self) -> None:
        if not self._models_payload:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Salvar relatório de divergências",
            "modelos_opcionais.md", "Markdown (*.md)",
        )
        if not path:
            return
        try:
            saved = model_layer.export_markdown(self._models_payload, path)
            QMessageBox.information(
                self, "Relatório de divergências",
                f"Relatório salvo em:\n{saved}",
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(
                self, "Relatório de divergências", str(exc))

    def _render_models(self, payload: dict) -> None:
        self._models_payload = payload or {}
        self.btn_models_export.setEnabled(bool(payload))
        if not payload:
            self._refresh_model_caps()
            self.models_results.set_rows([])
            self.models_compare.set_rows([])
            self.models_notes.clear()
            return

        caps = payload.get("capabilities") or {}
        rows = []
        for engine in caps.get("engines") or []:
            rows.append((
                engine.get("name", ""),
                engine.get("kind", ""),
                "Sim" if engine.get("available") else "Não",
                engine.get("version") or "—",
                engine.get("note", ""),
            ))
        self.models_caps.set_rows(rows)

        results = payload.get("results") or {}
        self.models_summary.setText(
            f"Camada opcional ativa · motor: "
            f"{payload.get('engine') or 'nenhum'} · "
            f"{len(results)} bloco(s) gerado(s) · "
            f"{len(payload.get('warnings') or [])} aviso(s). "
            "Resultados de modelo são hipóteses e não substituem a análise "
            "determinística."
        )

        result_rows = []
        syntax = results.get("syntax") or {}
        if syntax:
            coverage = syntax.get("coverage") or {}
            result_rows.append((
                "Sintaxe", "Tokens",
                coverage.get("tokens", 0),
            ))
            result_rows.append((
                "Sintaxe", "Dependências",
                coverage.get("dependencies", 0),
            ))
            result_rows.append((
                "Sintaxe", "Modelo",
                f"{syntax.get('model', '')} {syntax.get('version', '')}".strip(),
            ))
        coref = results.get("coreference") or {}
        if coref:
            coverage = coref.get("coverage") or {}
            result_rows.append(("Correferência", "Cadeias",
                                coverage.get("chains", 0)))
            result_rows.append(("Correferência", "Menções",
                                coverage.get("mentions", 0)))
        similarity = results.get("similarity") or {}
        if similarity:
            coverage = similarity.get("coverage") or {}
            pairs = similarity.get("pairs") or []
            result_rows.append(("Similaridade", "Sentenças",
                                coverage.get("sentences", 0)))
            result_rows.append(("Similaridade", "Pares", len(pairs)))
            result_rows.append((
                "Similaridade", "Pares divergentes",
                sum(1 for pair in pairs if pair.get("divergent")),
            ))
        interpretation = results.get("interpretation") or {}
        if interpretation:
            result_rows.append((
                "Interpretação", "Modelo",
                interpretation.get("model", ""),
            ))
            result_rows.append((
                "Interpretação", "Hipóteses",
                len(interpretation.get("hypotheses") or []),
            ))
        self.models_results.set_rows(result_rows)

        comparison = payload.get("comparison") or {}
        sections = comparison.get("sections") or {}
        labels = {
            "syntax": "POS",
            "similarity": "Similaridade",
            "coreference": "Correferência",
            "interpretation": "Interpretação",
        }
        compare_rows = []
        for key, label in labels.items():
            section = sections.get(key) or {}
            status = section.get("status") or "sem dados"
            metrics = []
            if section.get("compared"):
                metrics.append(("Tokens comparados", section["compared"]))
                metrics.append(("Concordância", section.get("agreement")))
            if key == "similarity" and section.get("pairs"):
                metrics.append(("Pares", section["pairs"]))
                metrics.append(("Divergentes", section.get("divergent", 0)))
            if key == "coreference" and section.get("model_mentions"):
                metrics.append(("Menções do modelo",
                                section["model_mentions"]))
                metrics.append(("Coincidentes", section.get("matched", 0)))
            if key == "interpretation" and section.get("hypotheses"):
                metrics.append(("Hipóteses", section["hypotheses"]))
                metrics.append(("Fora das perguntas",
                                section.get("novel", 0)))
            if not metrics:
                compare_rows.append((label, status, "—", "—"))
            for metric, value in metrics:
                compare_rows.append((
                    label, status, metric,
                    "—" if value is None else value,
                ))
        self.models_compare.set_rows(compare_rows)

        notes = []
        warnings = payload.get("warnings") or []
        if warnings:
            notes.append("<b>Avisos</b><ul>")
            notes.extend(
                f"<li>{html.escape(str(text))}</li>" for text in warnings
            )
            notes.append("</ul>")
        limitations = payload.get("limitations") or []
        if limitations:
            notes.append("<b>Limitações</b><ul>")
            notes.extend(
                f"<li>{html.escape(str(text))}</li>" for text in limitations
            )
            notes.append("</ul>")
        interpretation = results.get("interpretation") or {}
        if interpretation:
            notes.append(
                "<p><b>Hipóteses do modelo:</b> texto interpretativo, sem "
                "fact-checking e sem veredito. Revise antes de usar.</p>"
            )
            hypotheses = interpretation.get("hypotheses") or []
            if hypotheses:
                notes.append("<ul>")
                notes.extend(
                    f"<li>{html.escape(str(line))}</li>"
                    for line in hypotheses
                )
                notes.append("</ul>")
        self.models_notes.setHtml("".join(notes))

    # ------------------------------------------------------------------
    def _render_readability(self, readability: dict) -> None:
        for key, tile in self.read_tiles.items():
            value = readability.get(key)
            if isinstance(value, (int, float)):
                tile.set_value(
                    f"{value:.1f}" if isinstance(value, float) else value
                )
            else:
                tile.set_value("—")

    def _render_lexical(self, lexical: dict) -> None:
        labels = {
            "total_tokens": "Total de tokens",
            "unique_tokens": "Tokens únicos",
            "ttr": "Type-Token Ratio",
            "root_ttr": "Root TTR",
            "maas_index": "Índice de Maas",
            "lexical_density": "Densidade lexical (%)",
        }
        self.lex_table.set_rows([
            (labels.get(k, k), v) for k, v in lexical.items()
        ])

    def _render_lexicometry(self, data: dict) -> None:
        if not data:
            self.lexm_summary.setText(
                "Lexicometria não disponível neste relatório."
            )
            self.lexm_warnings.setText("")
            for table in (
                self.lexm_metrics, self.lexm_terms, self.lexm_ngrams,
                self.lexm_collocations, self.lexm_variation,
                self.lexm_periods,
            ):
                table.set_rows([])
            self._lexm_svg = ""
            if self.lexm_view is not None:
                self.lexm_view.load(b"")
            self.btn_lexm_svg.setEnabled(False)
            self.btn_lexm_png.setEnabled(False)
            self._apply_chart(
                "_lexm_dispersion_svg", self.lexm_dispersion_view,
                self.lexm_dispersion_browser,
                self.btn_lexm_dispersion_svg,
                self.btn_lexm_dispersion_png, "",
                "Lexicometria não disponível neste relatório.",
            )
            for attr, view, browser, btn_svg, btn_png in (
                ("_lexm_zipf_svg", self.lexm_zipf_view,
                 self.lexm_zipf_browser, self.btn_lexm_zipf_svg,
                 self.btn_lexm_zipf_png),
                ("_lexm_heaps_svg", self.lexm_heaps_view,
                 self.lexm_heaps_browser, self.btn_lexm_heaps_svg,
                 self.btn_lexm_heaps_png),
            ):
                self._apply_chart(
                    attr, view, browser, btn_svg, btn_png, "",
                    "Lexicometria não disponível neste relatório.",
                )
            return

        from reports import exporters

        shell = {"lexicometry": data}
        metrics = data.get("metrics") or {}
        self.lexm_summary.setText(
            f"{metrics.get('tokens', 0)} tokens · "
            f"{metrics.get('types', 0)} tipos · "
            f"TTR {metrics.get('ttr', '—')} · "
            f"hapax {metrics.get('hapax', 0)} · "
            f"{len((data.get('ngrams') or {}).get('items') or [])} n-gramas · "
            f"{len((data.get('collocations') or {}).get('items') or [])} "
            "colocações."
        )
        warnings = [str(item) for item in data.get("warnings") or []]
        for key in ("ngrams", "collocations", "variation", "periods"):
            warnings.extend(
                str(item)
                for item in (data.get(key) or {}).get("warnings") or []
            )
        self.lexm_warnings.setText(" · ".join(dict.fromkeys(warnings)))
        self.lexm_metrics.set_rows(exporters.lexicometry_metric_rows(shell))
        self.lexm_terms.set_rows(exporters.lexicometry_type_rows(shell, 200))
        self.lexm_ngrams.set_rows(exporters.ngram_rows(shell, 300))
        self.lexm_collocations.set_rows(exporters.collocation_rows(shell, 300))
        self.lexm_variation.set_rows(exporters.variation_rows(shell, 200))
        self.lexm_periods.set_rows(exporters.period_rows(shell, 100))
        self._lexm_svg = lexicometry_chart.render_svg(shell)
        has_chart = bool(self._lexm_svg)
        if self.lexm_view is not None:
            from ui import theme
            self.lexm_view.load(
                theme.adapt_svg(self._lexm_svg).encode("utf-8")
            )
        else:  # pragma: no cover
            self.lexm_browser.setPlainText(self.lexm_summary.text())
        self.btn_lexm_svg.setEnabled(has_chart)
        self.btn_lexm_png.setEnabled(has_chart)
        dispersion_svg = charts_svg.lexical_dispersion(data)
        self._apply_chart(
            "_lexm_dispersion_svg", self.lexm_dispersion_view,
            self.lexm_dispersion_browser,
            self.btn_lexm_dispersion_svg, self.btn_lexm_dispersion_png,
            dispersion_svg,
            "Posições de ocorrência indisponíveis para a dispersão.",
        )
        zipf_svg = charts_svg.zipf_chart(data)
        self._apply_chart(
            "_lexm_zipf_svg", self.lexm_zipf_view, self.lexm_zipf_browser,
            self.btn_lexm_zipf_svg, self.btn_lexm_zipf_png, zipf_svg,
            "Série de Zipf indisponível; abra uma análise nova para "
            "calcular os pontos.",
        )
        heaps_svg = charts_svg.heaps_chart(data)
        self._apply_chart(
            "_lexm_heaps_svg", self.lexm_heaps_view,
            self.lexm_heaps_browser, self.btn_lexm_heaps_svg,
            self.btn_lexm_heaps_png, heaps_svg,
            "Série de Heaps indisponível para este texto.",
        )

    def _render_linguistics(self, data: dict) -> None:
        from reports import exporters

        if not data:
            self.ling_summary.setText(
                "Linguística estrutural não disponível neste relatório."
            )
            for table in (
                self.ling_overview, self.ling_pos, self.ling_syntax,
                self.ling_fields, self.ling_markers, self.ling_coref,
                self.ling_sections,
            ):
                table.set_rows([])
            self.ling_section.blockSignals(True)
            self.ling_section.clear()
            self.ling_section.addItem("Todas as seções", -1)
            self.ling_section.blockSignals(False)
            self._ling_section_rows = []
            return

        shell = {"linguistics": data}
        summary = data.get("summary") or {}
        engine = "spaCy" if data.get("engine") == "spacy" else "fallback"
        self.ling_summary.setText(
            f"Motor: {engine} · {summary.get('segments', 0)} seção(ões) · "
            f"passiva {summary.get('passive_ratio', 0)} · "
            f"frase média {summary.get('mean_sentence_length', 0)} palavras · "
            f"campos {summary.get('semantic_coverage', 0)} · "
            f"{summary.get('markers', 0)} marcador(es) · "
            f"{summary.get('coreference_chains', 0)} cadeia(s)."
        )
        self.ling_overview.set_rows(exporters.linguistics_metric_rows(shell))
        self.ling_pos.set_rows(exporters.pos_rows(shell, 40))
        self.ling_syntax.set_rows(exporters.syntax_item_rows(shell, 80))
        self.ling_fields.set_rows(exporters.semantic_field_rows(shell, 30))
        self.ling_markers.set_rows(exporters.discourse_marker_rows(shell, 60))
        self.ling_coref.set_rows(exporters.coreference_rows(shell, 60))
        self._ling_section_rows = exporters.linguistics_section_rows(
            shell, 80
        )
        self.ling_sections.set_rows(self._ling_section_rows)
        self.ling_section.blockSignals(True)
        self.ling_section.clear()
        self.ling_section.addItem("Todas as seções", -1)
        for index, row in enumerate(self._ling_section_rows):
            self.ling_section.addItem(str(row[0] or "Seção"), index)
        self.ling_section.blockSignals(False)

    def _filter_ling_sections(self, _index: int) -> None:
        target = self.ling_section.currentData()
        if target is None or target < 0:
            self.ling_sections.set_rows(self._ling_section_rows)
            return
        rows = [
            row for index, row in enumerate(self._ling_section_rows)
            if index == target
        ]
        self.ling_sections.set_rows(rows)

    def _render_stylometry(self, data: dict) -> None:
        from reports import exporters

        style = (data or {}).get("stylometry") or {}
        if not style:
            self.style_summary.setText(
                "Estilometria não disponível neste relatório."
            )
            for table in (
                self.style_metrics, self.style_punct, self.style_function,
                self.style_repetition, self.style_sections,
            ):
                table.set_rows([])
            self.style_section.blockSignals(True)
            self.style_section.clear()
            self.style_section.addItem("Todas as seções", -1)
            self.style_section.blockSignals(False)
            self._style_section_rows = []
            return

        shell = {"linguistics": data}
        sentences = style.get("sentences") or {}
        functions = style.get("function_words") or {}
        self.style_summary.setText(
            f"Motor: {'spaCy' if style.get('engine') == 'spacy' else 'fallback'}"
            f" · {sentences.get('count', 0)} sentença(s) · "
            f"média {sentences.get('mean', 0)} palavras · "
            f"funcionais {functions.get('share', 0)} · "
            f"{style.get('repetition', {}).get('repeated_ratio', 0)} "
            "de repetição."
        )
        self.style_metrics.set_rows(
            exporters.stylometry_metric_rows(shell)
        )
        self.style_punct.set_rows(exporters.punctuation_rows(shell, 40))
        self.style_function.set_rows(
            exporters.function_word_rows(shell, 60)
        )
        self.style_repetition.set_rows(
            exporters.repetition_rows(shell, 60)
        )
        rows = []
        for item in style.get("sections") or []:
            rows.append((
                item.get("section", ""),
                item.get("role", ""),
                item.get("words", 0),
                item.get("sentences", 0),
                item.get("mean_sentence_length", 0.0),
                item.get("function_word_share", 0.0),
                item.get("punctuation_per_1k", 0.0),
                ", ".join(
                    term.get("term", "")
                    for term in (item.get("top_terms") or [])[:5]
                ),
            ))
        self._style_section_rows = rows
        self.style_sections.set_rows(rows)
        self.style_section.blockSignals(True)
        self.style_section.clear()
        self.style_section.addItem("Todas as seções", -1)
        for index, row in enumerate(rows):
            self.style_section.addItem(str(row[0] or "Seção"), index)
        self.style_section.blockSignals(False)

    def _filter_style_sections(self, _index: int) -> None:
        target = self.style_section.currentData()
        if target is None or target < 0:
            self.style_sections.set_rows(self._style_section_rows)
            return
        rows = [
            row for index, row in enumerate(self._style_section_rows)
            if index == target
        ]
        self.style_sections.set_rows(rows)

    def _render_research(self, data: dict) -> None:
        if not data:
            self.research_summary.setText("—")
            for table in (
                self.research_imrad, self.research_citations,
                self.research_method, self.research_gaps,
                self.research_matrix,
            ):
                table.set_rows([])
            self._apply_chart(
                "_research_ribbon_svg", getattr(self, "research_ribbon_view", None),
                getattr(self, "research_ribbon_browser", None),
                self.btn_research_ribbon_svg, self.btn_research_ribbon_png,
                "", "Nenhuma seção IMRaD disponível.",
            )
            self._apply_chart(
                "_research_citation_svg",
                getattr(self, "research_citation_view", None),
                getattr(self, "research_citation_browser", None),
                self.btn_research_citation_svg,
                self.btn_research_citation_png, "",
                "Nenhuma citação classificada disponível.",
            )
            return
        summary = data.get("summary") or {}
        self.research_summary.setText(
            f"Modelo IMRaD: {summary.get('imrad_model', '—')} · "
            f"{summary.get('imrad_present', 0)} parte(s) presente(s) · "
            f"{summary.get('imrad_absent', 0)} ausente(s) · "
            f"{summary.get('imrad_ambiguous', 0)} ambígua(s) · "
            f"{summary.get('citations_classified', 0)} citação(ões) "
            "classificada(s) · "
            f"metodologia {summary.get('methodology_confidence', '—')} · "
            f"{summary.get('observed_gaps', 0)} lacuna(s) observada(s) · "
            f"{summary.get('suggested_gaps', 0)} hipótese(s) · "
            "qualidade científica não calculada."
        )
        imrad = data.get("imrad") or {}
        self.research_imrad.set_rows([
            (
                item.get("label", ""),
                item.get("status", ""),
                item.get("source", ""),
                item.get("confidence", ""),
                "sim" if item.get("ambiguous") else "não",
                item.get("note", ""),
            )
            for item in imrad.get("entries") or []
        ])
        ribbon_svg = charts_svg.imrad_ribbon(
            imrad, total_chars=len(self._source_text or "")
        )
        self._apply_chart(
            "_research_ribbon_svg", self.research_ribbon_view,
            self.research_ribbon_browser, self.btn_research_ribbon_svg,
            self.btn_research_ribbon_png, ribbon_svg,
            "Nenhuma seção IMRaD com offsets disponíveis.",
        )

        citations = data.get("citation_function") or {}
        self.research_citations.set_rows([
            (
                item.get("text", ""),
                item.get("function_label", ""),
                item.get("polarity", ""),
                item.get("confidence", ""),
                (item.get("sentence") or "")[:220],
            )
            for item in citations.get("items") or []
        ])
        donut_svg = charts_svg.citation_function_donut(citations)
        self._apply_chart(
            "_research_citation_svg", self.research_citation_view,
            self.research_citation_browser,
            self.btn_research_citation_svg, self.btn_research_citation_png,
            donut_svg, "Nenhuma distribuição por função de citação disponível.",
        )

        methodology = data.get("methodology") or {}
        labels = (
            ("approach", "Tipo de pesquisa"),
            ("design", "Desenho"),
            ("data_collection", "Coleta"),
            ("instruments", "Instrumentos"),
            ("sampling", "Amostragem"),
            ("validation", "Validação"),
        )
        method_rows = []
        for key, label in labels:
            for item in methodology.get(key) or []:
                method_rows.append((
                    label,
                    item.get("label", ""),
                    item.get("confidence", ""),
                    (item.get("sentence") or "")[:220],
                ))
        sample = methodology.get("sample") or {}
        if sample:
            method_rows.append((
                "Amostra", sample.get("value", ""),
                sample.get("confidence", ""), "",
            ))
        for item in methodology.get("stated_limitations") or []:
            method_rows.append((
                "Limitação declarada", item.get("text", ""),
                item.get("confidence", ""), "",
            ))
        self.research_method.set_rows(method_rows)

        gaps = data.get("research_gaps") or {}
        gap_rows = [
            (
                "observada", item.get("label", ""),
                item.get("confidence", ""), item.get("note", ""),
            )
            for item in gaps.get("observed") or []
        ]
        gap_rows.extend(
            (
                "hipótese", item.get("label", ""), item.get("confidence", ""),
                "revisão humana obrigatória",
            )
            for item in gaps.get("suggested") or []
        )
        self.research_gaps.set_rows(gap_rows)

        lit = data.get("lit_review") or {}
        ids = lit.get("column_ids") or []
        self.research_matrix.set_rows([
            tuple(row.get(column_id, "") for column_id in ids)
            for row in lit.get("rows") or []
        ])

    def _render_discourse(self, data: dict) -> None:
        self._disc_rows = {
            "rhetoric": [], "toulmin": [], "cda": [],
            "stance": [], "framing": [],
        }
        if not data:
            self.disc_summary.setText("—")
            for table in (
                self.disc_rhetoric, self.disc_toulmin, self.disc_cda,
                self.disc_stance, self.disc_framing,
            ):
                table.set_rows([])
            self._apply_chart(
                "_rhetoric_svg", getattr(self, "rhetoric_view", None),
                getattr(self, "rhetoric_browser", None),
                self.btn_rhetoric_svg, self.btn_rhetoric_png,
                "", "Nenhum dado retórico disponível.",
            )
            self._apply_chart(
                "_stance_svg", getattr(self, "stance_view", None),
                getattr(self, "stance_browser", None),
                self.btn_stance_svg, self.btn_stance_png,
                "", "Nenhum dado de posicionamento disponível.",
            )
            return
        summary = data.get("summary") or {}
        self.disc_summary.setText(
            f"Retórica: {summary.get('rhetoric_total', 0)} indicador(es) · "
            f"eixo {summary.get('dominant_axis_label', '—')} · "
            f"{summary.get('arguments', 0)} argumento(s) Toulmin · "
            f"CDA: {summary.get('cda_total', 0)} indicador(es) · "
            f"{summary.get('targets', 0)} alvo(s) de posicionamento "
            f"({summary.get('determined_stances', 0)} determinado(s)) · "
            f"enquadramento {summary.get('dominant_frame_label', '—')}. "
            "Leitura interpretativa."
        )
        rhetoric_svg = charts_svg.rhetoric_triangle(
            data.get("rhetoric") or {}
        )
        stance_svg = charts_svg.stance_diverging_bars(
            data.get("stance") or {}
        )
        self._apply_chart(
            "_rhetoric_svg", self.rhetoric_view, self.rhetoric_browser,
            self.btn_rhetoric_svg, self.btn_rhetoric_png, rhetoric_svg,
            "Indicadores insuficientes para o triângulo retórico.",
        )
        self._apply_chart(
            "_stance_svg", self.stance_view, self.stance_browser,
            self.btn_stance_svg, self.btn_stance_png, stance_svg,
            "Nenhum alvo declarado com marcador avaliativo.",
        )
        for item in (data.get("rhetoric") or {}).get("items") or []:
            self._disc_rows["rhetoric"].append((
                (
                    item.get("axis_label", ""),
                    item.get("label", ""),
                    item.get("cue", ""),
                    item.get("confidence", ""),
                    (item.get("sentence") or "")[:220],
                ),
                item.get("confidence", ""),
            ))
        for item in (data.get("toulmin") or {}).get("arguments") or []:
            claim = item.get("claim") or {}
            self._disc_rows["toulmin"].append((
                (
                    (claim.get("text") or "")[:220],
                    item.get("confidence", ""),
                    "; ".join(item.get("gaps") or []) or "sem lacunas",
                ),
                item.get("confidence", ""),
            ))
        for item in (data.get("cda") or {}).get("items") or []:
            self._disc_rows["cda"].append((
                (
                    item.get("label", ""),
                    item.get("cue", ""),
                    item.get("confidence", ""),
                    (item.get("sentence") or "")[:220],
                ),
                item.get("confidence", ""),
            ))
        for item in (data.get("stance") or {}).get("items") or []:
            self._disc_rows["stance"].append((
                (
                    item.get("target", ""),
                    item.get("stance", ""),
                    item.get("confidence", ""),
                    (item.get("sentence") or "")[:220],
                ),
                item.get("confidence", ""),
            ))
        for axis in (data.get("framing") or {}).get("axes") or []:
            if not axis.get("count"):
                continue
            confidence = "media" if axis.get("count", 0) >= 3 else "baixa"
            self._disc_rows["framing"].append((
                (
                    axis.get("label", ""),
                    ", ".join(axis.get("terms") or []),
                    axis.get("count", 0),
                    confidence,
                ),
                confidence,
            ))
        self._filter_discourse_confidence()

    def _filter_discourse_confidence(self, _index: int = -1) -> None:
        wanted = self.disc_confidence.currentData() or ""
        tables = {
            "rhetoric": self.disc_rhetoric,
            "toulmin": self.disc_toulmin,
            "cda": self.disc_cda,
            "stance": self.disc_stance,
            "framing": self.disc_framing,
        }
        for key, table in tables.items():
            rows = [
                row for row, confidence in self._disc_rows.get(key, [])
                if not wanted or confidence == wanted
            ]
            table.set_rows(rows)

    def _render_knowledge(self, data: dict) -> None:
        if not data:
            self.know_summary.setText("—")
            for table in (
                self.know_relations, self.know_ontology, self.know_terms,
                self.know_events, self.know_claims,
            ):
                table.set_rows([])
            self._onto_data = {}
            self._onto_history = []
            self._update_onto_undo()
            return
        summary = data.get("summary") or {}
        self.know_summary.setText(
            f"Relações: {summary.get('relations_total', 0)} · "
            f"conceitos: {summary.get('concepts_total', 0)} · "
            f"termos: {summary.get('terms_total', 0)} "
            f"({summary.get('defined_terms', 0)} definidos) · "
            f"eventos: {summary.get('events_total', 0)} "
            f"({summary.get('dated_events', 0)} datados) · "
            f"afirmações: {summary.get('claims_total', 0)} "
            "(não verificadas). Nada aqui atesta veracidade."
        )
        relations = data.get("relations") or {}
        self.know_relations.set_rows([
            (
                item.get("type_label", ""),
                item.get("subject", ""),
                item.get("verb", ""),
                item.get("object", ""),
                item.get("confidence", ""),
            )
            for item in relations.get("items") or []
        ])
        ontology_data = data.get("ontology") or {}
        self._onto_data = copy.deepcopy(ontology_data) if ontology_data else {}
        self._onto_history = []
        self._update_onto_undo()
        self._render_ontology()
        terminology = data.get("terminology") or {}
        self.know_terms.set_rows([
            (
                item.get("term", ""),
                item.get("kind", ""),
                (item.get("definition") or "—")[:220],
                item.get("occurrences", 0),
                item.get("confidence", ""),
            )
            for item in terminology.get("items") or []
        ])
        events_data = data.get("events") or {}
        outgoing = {
            relation.get("from"): relation
            for relation in events_data.get("relations") or []
        }
        labels = events_data.get("labels") or {}
        event_rows = []
        for event in events_data.get("events") or []:
            relation = outgoing.get(event.get("id")) or {}
            relation_type = relation.get("type", "")
            event_rows.append((
                (event.get("description") or "")[:220],
                event.get("date") or "—",
                labels.get(relation_type, relation_type) or "—",
                relation.get("basis") or "—",
                event.get("confidence", ""),
            ))
        self.know_events.set_rows(event_rows)
        claims_data = data.get("claims") or {}
        self.know_claims.set_rows([
            (
                item.get("kind", ""),
                item.get("subject", "") or "—",
                item.get("value", ""),
                item.get("period", "") or "—",
                item.get("confidence", ""),
                (item.get("text") or "")[:220],
            )
            for item in claims_data.get("items") or []
        ])

    def _render_ontology(self) -> None:
        nodes = (self._onto_data or {}).get("nodes") or []
        self.know_ontology.set_rows([
            (
                node.get("label", ""),
                node.get("parent", "") or "—",
                node.get("level", 0),
                node.get("occurrences", 0),
                node.get("confidence", ""),
                "sim" if node.get("edited") else "não",
            )
            for node in nodes
        ])

    def _snapshot_ontology(self) -> None:
        """Guarda o estado atual antes de uma edição manual (limite de 20)."""
        self._onto_history.append(copy.deepcopy(self._onto_data or {}))
        if len(self._onto_history) > 20:
            del self._onto_history[0]
        self._update_onto_undo()

    def _update_onto_undo(self) -> None:
        button = getattr(self, "btn_onto_undo", None)
        if button is not None:
            button.setEnabled(bool(self._onto_history))

    def _undo_ontology(self) -> None:
        """Restaura o estado anterior à última inclusão/remoção."""
        if not self._onto_history:
            return
        self._onto_data = self._onto_history.pop()
        self._update_onto_undo()
        self._render_ontology()

    def _add_ontology_concept(self) -> None:
        label, ok = QInputDialog.getText(
            self, "Novo conceito", "Conceito:"
        )
        if not ok or not label.strip():
            return
        parent, parent_ok = QInputDialog.getText(
            self, "Conceito pai", "Pai (opcional):"
        )
        self._add_ontology_node(
            label.strip(), parent.strip() if parent_ok else ""
        )
        self._render_ontology()

    def _add_ontology_node(self, label: str, parent_label: str = "") -> None:
        self._snapshot_ontology()
        if not self._onto_data:
            self._onto_data = {
                "nodes": [], "edges": [], "roots": [], "manual": [],
                "total": 0, "editable": True, "nature": "interpretive",
            }
        nodes = self._onto_data.setdefault("nodes", [])
        key = "_".join(label.lower().split())
        node = next(
            (item for item in nodes if item.get("id") == key), None
        )
        if node is None:
            node = {
                "id": key,
                "label": label,
                "parent": "",
                "parent_id": "",
                "level": 0,
                "definition": "",
                "confidence": "alta",
                "start": None,
                "end": None,
                "sentence": "",
                "sentence_start": 0,
                "sentence_end": 0,
                "occurrences": 0,
                "edited": False,
                "nature": "interpretive",
                "rationale": "Conceito acrescentado na edição manual.",
            }
            nodes.append(node)
        node["edited"] = True
        if parent_label:
            parent_key = "_".join(parent_label.lower().split())
            parent = next(
                (item for item in nodes if item.get("id") == parent_key),
                None,
            )
            if parent is None:
                parent = {
                    "id": parent_key,
                    "label": parent_label,
                    "parent": "",
                    "parent_id": "",
                    "level": 0,
                    "definition": "",
                    "confidence": "alta",
                    "start": None,
                    "end": None,
                    "sentence": "",
                    "sentence_start": 0,
                    "sentence_end": 0,
                    "occurrences": 0,
                    "edited": True,
                    "nature": "interpretive",
                    "rationale": "Conceito acrescentado na edição manual.",
                }
                nodes.append(parent)
            if parent.get("id") != node.get("id"):
                node["parent_id"] = parent.get("id", "")
                node["parent"] = parent.get("label", parent_label)
                edges = self._onto_data.setdefault("edges", [])
                edges.append({
                    "child": node.get("label", label),
                    "child_id": node.get("id", key),
                    "parent": parent.get("label", parent_label),
                    "parent_id": parent.get("id", parent_key),
                    "pattern": "manual",
                    "confidence": "alta",
                    "start": None,
                    "end": None,
                    "text": "",
                    "rationale": "Relação criada na edição manual.",
                    "nature": "interpretive",
                })
        self._recompute_ontology()

    def _recompute_ontology(self) -> None:
        nodes = (self._onto_data or {}).get("nodes") or []
        by_id = {node.get("id"): node for node in nodes}
        for node in nodes:
            seen = {node.get("id")}
            level = 0
            current = node
            while current.get("parent_id"):
                parent = by_id.get(current.get("parent_id"))
                if parent is None or parent.get("id") in seen:
                    break
                seen.add(parent.get("id"))
                level += 1
                current = parent
                if level > 10:
                    break
            node["level"] = level
        for node in nodes:
            node["children"] = [
                other.get("id") for other in nodes
                if other.get("parent_id") == node.get("id")
            ]
        self._onto_data["roots"] = [
            node.get("id") for node in nodes if not node.get("parent_id")
        ]
        self._onto_data["manual"] = [
            node.get("id") for node in nodes if node.get("edited")
        ]
        self._onto_data["total"] = len(nodes)

    def _remove_ontology_concept(self) -> None:
        row = self.know_ontology.currentRow()
        if row < 0:
            return
        item = self.know_ontology.item(row, 0)
        label = item.text() if item is not None else ""
        nodes = (self._onto_data or {}).get("nodes") or []
        target = next(
            (node for node in nodes if node.get("label") == label), None
        )
        if target is None:
            return
        answer = QMessageBox.question(
            self,
            "Remover conceito",
            f"Remover “{target.get('label', label)}” da ontologia?\n"
            "Os conceitos filhos passam a ser raízes. A remoção pode ser "
            "desfeita pelo botão “Desfazer”.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self._snapshot_ontology()
        nodes.remove(target)
        for node in nodes:
            if node.get("parent_id") == target.get("id"):
                node["parent_id"] = ""
                node["parent"] = ""
        edges = [
            edge for edge in (self._onto_data.get("edges") or [])
            if edge.get("child_id") != target.get("id")
            and edge.get("parent_id") != target.get("id")
        ]
        self._onto_data["edges"] = edges
        self._recompute_ontology()
        self._render_ontology()

    def _export_ontology(self) -> None:
        if not (self._onto_data or {}).get("nodes"):
            QMessageBox.information(
                self, "Ontologia vazia",
                "Não há conceitos para exportar neste documento.",
            )
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar ontologia", "ontologia.ttl",
            "Turtle (*.ttl);;JSON-LD (*.jsonld);;OWL (*.owl);;CSV (*.csv)",
        )
        if not path:
            return
        suffix = Path(path).suffix.lower()
        fmt = {
            ".ttl": "turtle", ".jsonld": "jsonld", ".owl": "owl",
            ".csv": "csv",
        }.get(suffix, "turtle")
        try:
            content = ontology.export(self._onto_data, fmt)
            Path(path).write_text(content, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Falha na exportação", str(exc))

    def _render_consistency(self, knowledge: dict) -> None:
        data = knowledge.get("consistency") or {}
        if not data:
            self.consist_summary.setText("—")
            self.consist_findings.set_rows([])
            return
        counts = data.get("counts") or {}
        detail = ", ".join(
            f"{rule}: {count}" for rule, count in counts.items()
        ) or "nenhuma regra disparou"
        self.consist_summary.setText(
            f"{data.get('total', 0)} achado(s) para revisão ({detail}). "
            "Sem veredito automático."
        )
        rows = []
        for finding in data.get("findings") or []:
            evidences = "; ".join(
                f"{(entry.get('text') or '')[:80]}"
                for entry in finding.get("evidence") or []
            )
            rows.append((
                finding.get("label") or finding.get("rule", ""),
                (finding.get("detail") or "")[:280],
                finding.get("confidence", ""),
                evidences[:320] or "—",
            ))
        self.consist_findings.set_rows(rows)

    def _load_comparison_document(self, title: str):
        path, _ = QFileDialog.getOpenFileName(
            self, title, "",
            "Documentos (*.txt *.md *.pdf *.docx *.odt *.rtf);;Todos (*)",
        )
        if not path:
            return None
        try:
            from core.extractor import extract_text

            payload = extract_text(path)
            text = str(payload.get("text") or "")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Falha ao abrir", str(exc))
            return None
        if not text.strip():
            QMessageBox.warning(
                self, "Documento vazio",
                "Nenhum texto foi extraído do arquivo escolhido.",
            )
            return None
        return Path(path).name, text

    def _compare_paraphrase_file(self) -> None:
        loaded = self._load_comparison_document("Segundo documento")
        if loaded is None:
            return
        name, text = loaded
        self.compare_paraphrase(text, name)

    def compare_paraphrase(
        self, text_b: str, name_b: str = "documento B"
    ) -> None:
        if not self._source_text.strip():
            self.para_summary.setText(
                "Texto de origem indisponível; abra o documento atual antes "
                "de comparar."
            )
            self.para_table.set_rows([])
            return
        data = paraphrase.compare(
            self._source_text, text_b or "",
            name_a="documento atual", name_b=name_b,
        )
        self._render_paraphrase(data)

    def _render_paraphrase(self, data: dict) -> None:
        summary = data.get("summary") or {}
        self.para_summary.setText(
            f"{summary.get('pairs', 0)} par(es) · "
            f"idênticos: {summary.get('literal', 0)} · "
            f"paráfrase próxima: {summary.get('parafrase_proxima', 0)} · "
            f"semântica: {summary.get('semantica', 0)} · "
            f"conceitual: {summary.get('conceitual', 0)}. "
            "Similaridade lexical; não prova equivalência de sentido."
        )
        self.para_table.set_rows([
            (
                pair.get("level_label", ""),
                (pair.get("a") or "")[:220],
                (pair.get("b") or "")[:220],
                f"{pair.get('ratio', 0):.2f}",
                pair.get("confidence", ""),
            )
            for pair in data.get("pairs") or []
        ])

    def _compare_versions_file(self) -> None:
        loaded = self._load_comparison_document("Versão B")
        if loaded is None:
            return
        name, text = loaded
        self.compare_versions(text, name)

    def compare_versions(
        self, text_b: str, name_b: str = "versão B"
    ) -> None:
        if not self._source_text.strip():
            self.vers_summary.setText(
                "Texto de origem indisponível; abra o documento atual antes "
                "de comparar."
            )
            self.vers_table.set_rows([])
            return
        data = versions.compare(
            self._source_text, text_b or "",
            name_a="versão atual", name_b=name_b,
        )
        self._render_versions(data)

    def _render_versions(self, data: dict) -> None:
        summary = data.get("summary") or {}
        self.vers_summary.setText(
            f"inclusões: {summary.get('inclusions', 0)} · "
            f"exclusões: {summary.get('exclusions', 0)} · "
            f"modificações: {summary.get('modifications', 0)} · "
            f"conceitos novos: {summary.get('concepts_appeared', 0)} · "
            f"referências +{summary.get('references_added', 0)}"
            f"/-{summary.get('references_removed', 0)}. "
            "O diff não decide qual versão é melhor."
        )
        rows = []
        for item in data.get("changes") or []:
            change = item.get("change", "")
            if change == "inclusao":
                rows.append((
                    "Inclusão", "—", (item.get("text") or "")[:220],
                    "—", item.get("confidence", ""),
                ))
            elif change == "exclusao":
                rows.append((
                    "Exclusão", (item.get("text") or "")[:220], "—",
                    "—", item.get("confidence", ""),
                ))
            else:
                rows.append((
                    "Modificação", (item.get("a") or "")[:220],
                    (item.get("b") or "")[:220],
                    f"{item.get('similarity', 0):.2f}",
                    item.get("confidence", ""),
                ))
        self.vers_table.set_rows(rows)

    def _render_topics(self, topics: list) -> None:
        if not topics:
            self.topics_browser.setPlainText(
                "Tópicos não gerados (texto insuficiente ou scikit-learn ausente)."
            )
            return
        blocks = []
        for topic in topics:
            words = " · ".join(w["word"] for w in topic["words"])
            blocks.append(
                f"<div style='margin-bottom:10px'>"
                f"<b>Tópico {topic['id']}</b><br>"
                f"<span style='color:#5b6673'>{words}</span></div>"
            )
        self.topics_browser.setHtml("".join(blocks))

    def _render_clusters(self, clusters: list) -> None:
        if not clusters:
            self.clusters_browser.setPlainText(
                "Agrupamentos não gerados (texto insuficiente)."
            )
            return
        blocks = []
        for cluster in clusters:
            terms = ", ".join(cluster["top_terms"])
            members = "".join(
                f"<li style='margin-bottom:4px'>{m['excerpt']}</li>"
                for m in cluster["members"][:5]
            )
            blocks.append(
                f"<h3>Grupo {cluster['id']} · {cluster['size']} trechos "
                f"(coesão {cluster['cohesion']})</h3>"
                f"<p><em>{terms}</em></p><ul>{members}</ul>"
            )
        self.clusters_browser.setHtml("".join(blocks))

    def _render_sentiment(self, sentiment: dict) -> None:
        if not sentiment:
            self.sent_summary.setText("Análise de sentimentos indisponível.")
            self.sent_table.set_rows([])
            return
        summary = sentiment.get("summary") or {}
        label = sentiment.get("label") or summary.get("label") or "—"
        score = sentiment.get("score", 0)
        tone = summary.get("tone", "")
        domain_label = sentiment.get("domain_label") or ""
        domains = sentiment.get("domains") or []
        domain_text = ""
        if domain_label:
            domain_text = f" · domínio {domain_label}"
        elif domains:
            domain_text = " · domínios detectados: " + ", ".join(
                item.get("label", "") for item in domains[:3]
            )
        self.sent_summary.setText(
            f"Tom {label.lower() if label != '—' else '—'} "
            f"(escore {score}, polaridade {sentiment.get('polarity', 0)})"
            f"{domain_text} · {tone} · "
            f"{sentiment.get('positive_sentences', 0)} sentenças positivas, "
            f"{sentiment.get('negative_sentences', 0)} negativas, "
            f"{sentiment.get('mixed_sentences', 0)} mistas, "
            f"{sentiment.get('neutral_sentences', 0)} neutras."
        )
        self.sent_table.set_rows([
            (
                item.get("sentence", ""),
                item.get("label", ""),
                item.get("score", 0),
                item.get("intensity", 0),
                domain_label or "—",
                item.get("explanation", "") or "—",
            )
            for item in (sentiment.get("sentences") or [])
        ])

    def _render_arguments(self, argument: dict) -> None:
        if not argument:
            self.arg_summary.setText("Mapa de argumentos indisponível.")
            self.arg_table.set_rows([])
            return
        summary = argument.get("summary") or {}
        types = summary.get("types") or {}
        types_text = " · ".join(f"{k}: {v}" for k, v in types.items()) or "—"
        self.arg_summary.setText(
            f"{summary.get('nodes', 0)} peças argumentativas · "
            f"{summary.get('edges', 0)} relações · {types_text}. "
            f"Tese: {'sim' if summary.get('has_thesis') else 'não'} · "
            f"Conclusão: {'sim' if summary.get('has_conclusion') else 'não'}."
        )
        self.arg_table.set_rows([
            (
                node.get("type_label", node.get("type", "")),
                node.get("text", ""),
                ", ".join(node.get("connectors") or []) or "—",
                node.get("score", 0),
            )
            for node in (argument.get("nodes") or [])
        ])

    def _render_definitions(self, definitions: dict) -> None:
        items = definitions.get("items") or []
        if not items:
            self.def_summary.setText("Nenhuma definição explícita encontrada.")
            self.def_table.set_rows([])
            return
        patterns = definitions.get("by_pattern") or {}
        patterns_text = " · ".join(f"{k}: {v}" for k, v in patterns.items())
        self.def_summary.setText(
            f"{len(items)} definições identificadas ({patterns_text})."
        )
        self.def_table.set_rows([
            (
                item.get("term", ""),
                item.get("definition", ""),
                item.get("pattern", ""),
                item.get("confidence", 0),
            )
            for item in items
        ])

    def _render_timeline(self, timeline: dict) -> None:
        events = timeline.get("events") or []
        if not events:
            self.time_summary.setText("Nenhuma data ou período identificado.")
            self.time_table.set_rows([])
            return
        summary = timeline.get("summary") or {}
        gaps = timeline.get("gaps") or []
        self.time_summary.setText(
            f"{summary.get('total', len(events))} eventos · "
            f"intervalo {summary.get('range', '—')} "
            f"({summary.get('span', 0)} anos) · "
            f"datas completas {summary.get('full_dates', 0)}, "
            f"mês-ano {summary.get('month_dates', 0)}, "
            f"séculos {summary.get('centuries', 0)}, "
            f"décadas {summary.get('decades', 0)} · "
            f"{len(gaps)} lacuna(s) de década."
        )
        self.time_table.set_rows([
            (
                event.get("date", ""),
                event.get("normalized", ""),
                event.get("precision", ""),
                event.get("sentence", ""),
                ", ".join(event.get("other_dates") or []) or "—",
                event.get("paragraph", ""),
            )
            for event in events
        ])

    # ------------------------------------------------------------------
    def _render_temporal(self, timeline: dict) -> None:
        timeline = timeline or {}
        self._temporal_svg = temporal_chart.render_svg(timeline)
        self.temporal_label.setText(temporal_chart.summary(timeline))
        has_data = bool(timeline.get("events"))
        if self.temporal_view is not None:
            from ui import theme
            self.temporal_view.load(
                theme.adapt_svg(self._temporal_svg).encode("utf-8")
            )
        else:  # pragma: no cover
            self.temporal_browser.setPlainText(self.temporal_label.text())
        self.btn_temporal_svg.setEnabled(has_data)
        self.btn_temporal_png.setEnabled(has_data)

    def _apply_chart(self, attr: str, view, browser, btn_svg, btn_png,
                     svg: str, empty_text: str = "") -> None:
        """Carrega um SVG (ou mensagem de ausência) em uma sub-aba."""
        setattr(self, attr, svg or "")
        if view is not None:
            if svg:
                from ui import theme
                view.load(theme.adapt_svg(svg).encode("utf-8"))
            else:
                view.load(b"")
        elif browser is not None:  # pragma: no cover - fallback defensivo
            browser.setPlainText("" if svg else empty_text)
        btn_svg.setEnabled(bool(svg))
        btn_png.setEnabled(bool(svg))

    def _save_chart(self, attr: str, kind: str, title: str,
                    default_name: str) -> None:
        """Salva um gráfico SVG/PNG gerado por ``core.charts_svg``."""
        svg = getattr(self, attr, "")
        if not svg:
            return
        filters = {"svg": "SVG (*.svg)", "png": "PNG (*.png)"}
        filename, _ = QFileDialog.getSaveFileName(
            self, title, f"{default_name}.{kind}",
            filters.get(kind, "Todos (*.*)"),
        )
        if not filename:
            return
        if Path(filename).suffix.lower() != f".{kind}":
            filename = str(Path(filename).with_suffix(f".{kind}"))
        try:
            if kind == "png":
                from ui.prisma_export import svg_to_png
                svg_to_png(svg, filename, scale=2.0)
            else:
                Path(filename).write_text(svg, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Erro ao exportar", str(exc))
            return
        QMessageBox.information(self, title, f"Arquivo salvo:\n{filename}")

    def _save_lexm(self, kind: str) -> None:
        if not self._lexm_svg:
            return
        filters = {"svg": "SVG (*.svg)", "png": "PNG (*.png)"}
        filename, _ = QFileDialog.getSaveFileName(
            self, "Exportar gráfico de lexicometria",
            f"lexicometria.{kind}", filters.get(kind, "Todos (*.*)"),
        )
        if not filename:
            return
        if Path(filename).suffix.lower() != f".{kind}":
            filename = str(Path(filename).with_suffix(f".{kind}"))
        try:
            if kind == "png":
                from ui.prisma_export import svg_to_png
                svg_to_png(self._lexm_svg, filename, scale=2.0)
            else:
                Path(filename).write_text(self._lexm_svg, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Erro ao exportar", str(exc))
            return
        QMessageBox.information(
            self, "Gráfico de lexicometria", f"Arquivo salvo:\n{filename}"
        )

    def _save_temporal(self, kind: str) -> None:
        if not self._temporal_svg:
            return
        filters = {"svg": "SVG (*.svg)", "png": "PNG (*.png)"}
        filename, _ = QFileDialog.getSaveFileName(
            self, "Exportar gráfico temporal",
            f"temporal.{kind}", filters.get(kind, "Todos (*.*)"),
        )
        if not filename:
            return
        if Path(filename).suffix.lower() != f".{kind}":
            filename = str(Path(filename).with_suffix(f".{kind}"))
        try:
            if kind == "png":
                from ui.prisma_export import svg_to_png
                svg_to_png(self._temporal_svg, filename, scale=2.0)
            else:
                Path(filename).write_text(self._temporal_svg, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Erro ao exportar", str(exc))
            return
        QMessageBox.information(
            self, "Gráfico temporal", f"Arquivo salvo:\n{filename}"
        )

