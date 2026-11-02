#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Aba: análise de corpus (vários documentos, N×N, agrupamentos e duplicatas)."""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QFileDialog, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QProgressBar, QPushButton, QSpinBox, QTabWidget, QTableWidget,
    QTableWidgetItem, QTextBrowser, QVBoxLayout, QWidget,
)

from core import extraction_matrix, prisma, prisma_checklist, userdata
from core.extractor import SUPPORTED_EXTENSIONS
from reports import checklist_export, exporters, extraction_export
from ui.widgets.common import Card, DataTable
from ui.widgets.help_panel import HelpPanel
from ui.worker import CorpusWorker

FILE_FILTER = (
    "Todos os suportados (*.txt *.md *.markdown *.pdf *.docx *.odt *.rtf);;"
    "Texto (*.txt);;Markdown (*.md *.markdown);;PDF (*.pdf);;"
    "Word (*.docx);;OpenDocument (*.odt);;RTF (*.rtf);;Todos (*.*)"
)

LANGUAGES = ["Auto-detectar", "PT-BR", "EN", "ES", "FR", "IT", "DE"]


class CorpusView(QWidget):
    status = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._paths = []
        self._result = None
        self._worker = None
        self._extraction_guard = False
        self._checklist_guard = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        try:
            from core import explanations
            ci = QLabel(explanations.ANALYSIS_EXPLANATIONS.get('corpus', ''))
            ci.setWordWrap(True)
            ci.setStyleSheet('color:#5b6673;')
            layout.addWidget(ci)
        except Exception:
            pass

        self.help_panel = HelpPanel("corpus")
        layout.addWidget(self.help_panel)

        review_card = Card('Modo: Revisao bibliografica (sistematica / integrativa / narrativa)')
        review_layout = QVBoxLayout()
        review_row = QHBoxLayout()
        review_row.addWidget(QLabel('Tipo de revisao:'))
        from core.corpus import REVIEW_TYPES
        self.review_type = QComboBox()
        self.review_type.addItem('-')
        for rt in REVIEW_TYPES:
            self.review_type.addItem(rt)
        review_row.addWidget(self.review_type)
        review_row.addWidget(QLabel('Bases/motores:'))
        self.search_engines = QLineEdit()
        review_row.addWidget(self.search_engines)
        review_row.addWidget(QLabel('String de busca:'))
        self.search_string = QLineEdit()
        review_row.addWidget(self.search_string)
        review_layout.addLayout(review_row)
        crit_row = QHBoxLayout()
        crit_row.addWidget(QLabel('Inclusao:'))
        self.inclusion = QLineEdit()
        crit_row.addWidget(self.inclusion)
        crit_row.addWidget(QLabel('Exclusao:'))
        self.exclusion = QLineEdit()
        crit_row.addWidget(self.exclusion)
        crit_row.addWidget(QLabel('Data/coleta:'))
        self.collection_date = QLineEdit()
        crit_row.addWidget(self.collection_date)
        review_layout.addLayout(crit_row)
        review_card.setLayout(review_layout)
        layout.addWidget(review_card)

        prisma_card = Card('Fluxo PRISMA')
        prisma_layout = QVBoxLayout()
        prisma_row = QHBoxLayout()
        self.prisma_spins = {}
        short_labels = {
            "identified": "Identificados", "duplicates": "Duplicatas",
            "screened": "Triados", "excluded": "Excluídos",
            "included": "Incluídos",
        }
        for key, _ in prisma.COUNT_LABELS:
            box = QVBoxLayout()
            label = QLabel(short_labels.get(key, key))
            label.setStyleSheet('color:#5b6673;')
            box.addWidget(label)
            spin = QSpinBox()
            spin.setRange(0, 10_000_000)
            spin.valueChanged.connect(self._on_prisma_changed)
            box.addWidget(spin)
            self.prisma_spins[key] = spin
            prisma_row.addLayout(box)
        self.btn_prisma = QPushButton('📊  Gerar diagrama…')
        self.btn_prisma.clicked.connect(self._open_prisma)
        prisma_row.addWidget(self.btn_prisma)
        prisma_row.addStretch()
        prisma_layout.addLayout(prisma_row)
        self.prisma_summary = QLabel('0 identificados → 0 triados → 0 incluídos')
        self.prisma_summary.setStyleSheet('color:#1c53b8;')
        prisma_layout.addWidget(self.prisma_summary)
        prisma_card.setLayout(prisma_layout)
        layout.addWidget(prisma_card)

        intro = QLabel(
            "Compare vários documentos de uma vez: volume, vocabulário "
            "compartilhado e exclusivo, matriz de similaridade N×N, pares "
            "mais e menos parecidos, agrupamentos e duplicatas. Nada sai do "
            "computador."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color:#5b6673;")
        layout.addWidget(intro)

        controls = QHBoxLayout()
        self.btn_add = QPushButton("📁  Adicionar documentos")
        self.btn_add.setObjectName("Primary")
        self.btn_add.clicked.connect(self.add_files)
        controls.addWidget(self.btn_add)

        self.btn_remove = QPushButton("Remover selecionado")
        self.btn_remove.clicked.connect(self.remove_selected)
        controls.addWidget(self.btn_remove)

        self.btn_clear_files = QPushButton("Limpar lista")
        self.btn_clear_files.clicked.connect(self.reset)
        controls.addWidget(self.btn_clear_files)

        controls.addStretch()
        controls.addWidget(QLabel("Idioma:"))
        self.combo_language = QComboBox()
        self.combo_language.addItems(LANGUAGES)
        controls.addWidget(self.combo_language)
        controls.addWidget(QLabel("Agrupamentos:"))
        self.spin_clusters = QSpinBox()
        self.spin_clusters.setRange(2, 12)
        self.spin_clusters.setValue(4)
        controls.addWidget(self.spin_clusters)
        self.btn_run = QPushButton("🔎  Analisar corpus")
        self.btn_run.setObjectName("Primary")
        self.btn_run.clicked.connect(self.run_analysis)
        controls.addWidget(self.btn_run)
        layout.addLayout(controls)

        files_card = Card("Documentos do corpus")
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.file_list.setMaximumHeight(120)
        files_card.add(self.file_list)
        self.files_hint = QLabel("Nenhum documento adicionado.")
        self.files_hint.setStyleSheet("color:#5b6673;")
        files_card.add(self.files_hint)
        layout.addWidget(files_card)

        progress_row = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        progress_row.addWidget(self.progress, 1)
        self.btn_export_html = QPushButton("Exportar HTML")
        self.btn_export_html.setEnabled(False)
        self.btn_export_html.clicked.connect(lambda: self.export("html"))
        progress_row.addWidget(self.btn_export_html)
        self.btn_export_csv = QPushButton("Exportar CSV")
        self.btn_export_csv.setEnabled(False)
        self.btn_export_csv.clicked.connect(lambda: self.export("csv"))
        progress_row.addWidget(self.btn_export_csv)
        layout.addLayout(progress_row)

        self.tabs = QTabWidget()

        panorama_widget = QWidget()
        panorama_layout = QVBoxLayout(panorama_widget)
        panorama_layout.setContentsMargins(8, 8, 8, 8)
        self.panorama_help = HelpPanel("corpus_panorama", expanded=False)
        panorama_layout.addWidget(self.panorama_help)
        self.panorama = QTextBrowser()
        self.panorama.setHtml(
            "<p style='color:#5b6673'>Adicione ao menos dois documentos e "
            "clique em <b>Analisar corpus</b>.</p>"
        )
        panorama_layout.addWidget(self.panorama, 1)
        self.tabs.addTab(panorama_widget, "📊 Panorama")

        documents_widget = QWidget()
        documents_layout = QVBoxLayout(documents_widget)
        documents_layout.setContentsMargins(8, 8, 8, 8)
        self.documents_help = HelpPanel("corpus_documents", expanded=False)
        documents_layout.addWidget(self.documents_help)
        self.documents_table = DataTable([
            "Documento", "Idioma", "Palavras", "Sentenças", "Únicas",
            "TTR", "Flesch", "Sentimento", "Domínio",
        ], search=True)
        documents_layout.addWidget(self.documents_table, 1)
        self.tabs.addTab(documents_widget, "📄 Documentos")

        matrix_widget = QWidget()
        matrix_layout = QVBoxLayout(matrix_widget)
        matrix_layout.setContentsMargins(8, 8, 8, 8)
        self.matrix_help = HelpPanel("corpus_similarity", expanded=False)
        matrix_layout.addWidget(self.matrix_help)
        self.matrix_hint = QLabel(
            "Cosseno sobre TF-IDF; 1,00 indica documentos idênticos."
        )
        self.matrix_hint.setStyleSheet("color:#5b6673;")
        matrix_layout.addWidget(self.matrix_hint)
        self.matrix_table = QTableWidget(0, 0)
        self.matrix_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.matrix_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents
        )
        self.matrix_table.verticalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents
        )
        matrix_layout.addWidget(self.matrix_table)
        self.tabs.addTab(matrix_widget, "🧮 Similaridade")

        self.pairs_table = DataTable(["Documento A", "Documento B", "Similaridade"])
        self.pairs_widget = QWidget()
        pairs_layout = QVBoxLayout(self.pairs_widget)
        pairs_layout.setContentsMargins(8, 8, 8, 8)
        self.pairs_help = HelpPanel("corpus_pairs", expanded=False)
        pairs_layout.addWidget(self.pairs_help)
        pairs_layout.addWidget(self.pairs_table, 1)
        self.tabs.addTab(self.pairs_widget, "🔗 Pares")

        clusters_widget = QWidget()
        clusters_layout = QVBoxLayout(clusters_widget)
        clusters_layout.setContentsMargins(8, 8, 8, 8)
        self.clusters_help = HelpPanel("corpus_clusters", expanded=False)
        clusters_layout.addWidget(self.clusters_help)
        self.clusters_browser = QTextBrowser()
        clusters_layout.addWidget(self.clusters_browser, 1)
        self.tabs.addTab(clusters_widget, "🧩 Agrupamentos")

        self.duplicates_table = DataTable([
            "Documento A", "Documento B", "Similaridade", "Tipo",
        ])
        duplicates_widget = QWidget()
        duplicates_layout = QVBoxLayout(duplicates_widget)
        duplicates_layout.setContentsMargins(8, 8, 8, 8)
        self.duplicates_help = HelpPanel("corpus_duplicates", expanded=False)
        duplicates_layout.addWidget(self.duplicates_help)
        duplicates_layout.addWidget(self.duplicates_table, 1)
        self.tabs.addTab(duplicates_widget, "👥 Duplicatas")

        self.extraction_widget = QWidget()
        extraction_layout = QVBoxLayout(self.extraction_widget)
        extraction_layout.setContentsMargins(8, 8, 8, 8)
        self.extraction_help = HelpPanel("corpus_extraction", expanded=False)
        extraction_layout.addWidget(self.extraction_help)
        extraction_hint = QLabel(
            "Matriz de extração da revisão: uma linha por documento. As "
            "sugestões são heurísticas (objetivo, amostra, método, "
            "resultados e limitações) — revise e edite livremente. As "
            "alterações ficam salvas nas preferências."
        )
        extraction_hint.setWordWrap(True)
        extraction_hint.setStyleSheet("color:#5b6673;")
        extraction_layout.addWidget(extraction_hint)

        extraction_controls = QHBoxLayout()
        self.btn_extract_suggest = QPushButton("✨  Sugerir do corpus")
        self.btn_extract_suggest.clicked.connect(self._suggest_extraction)
        extraction_controls.addWidget(self.btn_extract_suggest)
        self.btn_extract_add = QPushButton("➕  Adicionar linha")
        self.btn_extract_add.clicked.connect(self._add_extraction_row)
        extraction_controls.addWidget(self.btn_extract_add)
        self.btn_extract_remove = QPushButton("➖  Remover selecionadas")
        self.btn_extract_remove.clicked.connect(self._remove_extraction_rows)
        extraction_controls.addWidget(self.btn_extract_remove)
        extraction_controls.addStretch()
        self.btn_extract_export = QPushButton("💾  Exportar matriz…")
        self.btn_extract_export.clicked.connect(self._export_extraction)
        extraction_controls.addWidget(self.btn_extract_export)
        extraction_layout.addLayout(extraction_controls)

        self.extraction_table = QTableWidget(0, len(extraction_matrix.COLUMNS))
        self.extraction_table.setHorizontalHeaderLabels(
            extraction_matrix.COLUMN_LABELS
        )
        self.extraction_table.setAlternatingRowColors(True)
        self.extraction_table.setWordWrap(True)
        self.extraction_table.setSelectionBehavior(
            QAbstractItemView.SelectRows
        )
        self.extraction_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Interactive
        )
        for index, column in enumerate(extraction_matrix.COLUMNS):
            self.extraction_table.setColumnWidth(index, column["width"])
        self.extraction_table.itemChanged.connect(self._on_extraction_edited)
        extraction_layout.addWidget(self.extraction_table, 1)
        self.tabs.addTab(self.extraction_widget, "🧾 Matriz de extração")

        # Checklist PRISMA 2020
        self.checklist_widget = QWidget()
        checklist_layout = QVBoxLayout(self.checklist_widget)
        checklist_layout.setContentsMargins(8, 8, 8, 8)
        self.checklist_help = HelpPanel("corpus_prisma", expanded=False)
        checklist_layout.addWidget(self.checklist_help)
        checklist_hint = QLabel(
            "Acompanhe os itens da declaração PRISMA 2020. Marque o status, "
            "informe a página e registre observações; os alertas cruzam o "
            "checklist com os dados da revisão (bases, string de busca, fluxo "
            "e matriz de extração). Tudo fica salvo nas preferências."
        )
        checklist_hint.setWordWrap(True)
        checklist_hint.setStyleSheet("color:#5b6673;")
        checklist_layout.addWidget(checklist_hint)

        checklist_top = QHBoxLayout()
        self.checklist_summary = QLabel("—")
        self.checklist_summary.setWordWrap(True)
        self.checklist_summary.setStyleSheet(
            "color:#1c53b8;font-weight:600;"
        )
        checklist_top.addWidget(self.checklist_summary, 1)
        self.checklist_progress = QProgressBar()
        self.checklist_progress.setRange(0, 100)
        self.checklist_progress.setValue(0)
        self.checklist_progress.setMaximumWidth(220)
        checklist_top.addWidget(self.checklist_progress)
        checklist_layout.addLayout(checklist_top)

        self.checklist_issues = QLabel("")
        self.checklist_issues.setWordWrap(True)
        self.checklist_issues.setStyleSheet("color:#b45309;")
        checklist_layout.addWidget(self.checklist_issues)

        self.checklist_table = QTableWidget(
            len(prisma_checklist.ITEMS), 6
        )
        self.checklist_table.setHorizontalHeaderLabels([
            "Item", "Parte", "Título", "Status", "Página", "Observações",
        ])
        self.checklist_table.setAlternatingRowColors(True)
        self.checklist_table.setWordWrap(True)
        self.checklist_table.verticalHeader().setVisible(False)
        self.checklist_table.setSelectionBehavior(
            QAbstractItemView.SelectRows
        )
        for index, width in enumerate((56, 120, 330, 130, 70, 240)):
            self.checklist_table.setColumnWidth(index, width)
        self.checklist_table.itemChanged.connect(self._on_checklist_edited)
        checklist_layout.addWidget(self.checklist_table, 1)

        checklist_buttons = QHBoxLayout()
        checklist_buttons.addStretch()
        self.btn_checklist_export = QPushButton("💾  Exportar checklist…")
        self.btn_checklist_export.clicked.connect(self._export_checklist)
        checklist_buttons.addWidget(self.btn_checklist_export)
        checklist_layout.addLayout(checklist_buttons)
        self.tabs.addTab(self.checklist_widget, "✅ PRISMA 2020")

        self.vocabulary_browser = QTextBrowser()
        vocabulary_widget = QWidget()
        vocabulary_layout = QVBoxLayout(vocabulary_widget)
        vocabulary_layout.setContentsMargins(8, 8, 8, 8)
        self.vocabulary_help = HelpPanel("corpus_vocabulary", expanded=False)
        vocabulary_layout.addWidget(self.vocabulary_help)
        vocabulary_layout.addWidget(self.vocabulary_browser, 1)
        self.tabs.addTab(vocabulary_widget, "📚 Vocabulário")

        layout.addWidget(self.tabs, 1)

        self._load_extraction_matrix()
        self._load_prisma()
        self._load_checklist()
        for widget in (
            self.search_engines, self.search_string, self.inclusion,
            self.exclusion, self.collection_date,
        ):
            widget.editingFinished.connect(self._refresh_checklist)
        self.review_type.currentIndexChanged.connect(
            lambda *_: self._refresh_checklist()
        )

    # ------------------------------------------------------------------
    def add_files(self) -> None:
        filenames, _ = QFileDialog.getOpenFileNames(
            self, "Adicionar documentos ao corpus", "", FILE_FILTER
        )
        if not filenames:
            return
        added = 0
        for filename in filenames:
            suffix = Path(filename).suffix.lower()
            if suffix not in SUPPORTED_EXTENSIONS:
                continue
            if filename not in self._paths:
                self._paths.append(filename)
                added += 1
        self._refresh_files()
        if added:
            self.status.emit(
                f"{added} documento(s) adicionado(s) ao corpus."
            )

    def remove_selected(self) -> None:
        selected = {
            item.data(Qt.UserRole) for item in self.file_list.selectedItems()
        }
        if not selected:
            return
        self._paths = [
            path for path in self._paths if path not in selected
        ]
        self._refresh_files()

    def _refresh_files(self) -> None:
        self.file_list.clear()
        for path in self._paths:
            item = QListWidgetItem(Path(path).name)
            item.setData(Qt.UserRole, path)
            self.file_list.addItem(item)
        if not self._paths:
            self.files_hint.setText("Nenhum documento adicionado.")
        else:
            self.files_hint.setText(
                f"{len(self._paths)} documento(s) na lista. "
                "A ordem da matriz segue esta lista."
            )

    # ------------------------------------------------------------------
    def run_analysis(self) -> None:
        if len(self._paths) < 2:
            QMessageBox.warning(
                self, "Corpus pequeno",
                "Adicione pelo menos dois documentos para comparar.",
            )
            return
        if self._worker and self._worker.isRunning():
            return
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.btn_run.setEnabled(False)
        self.btn_add.setEnabled(False)
        self.btn_export_html.setEnabled(False)
        self.btn_export_csv.setEnabled(False)
        self.status.emit("Analisando corpus…")

        self._worker = CorpusWorker(
            self._paths,
            clusters=self.spin_clusters.value(),
            language=self.combo_language.currentText(),
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_ok.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_progress(self, pct: int, message: str) -> None:
        self.progress.setValue(pct)
        self.status.emit(message)

    def _on_done(self, result: dict) -> None:
        self._result = result
        self.progress.setVisible(False)
        self.btn_run.setEnabled(True)
        self.btn_add.setEnabled(True)
        self.btn_export_html.setEnabled(True)
        self.btn_export_csv.setEnabled(True)
        self._render(result)
        self._refresh_checklist()
        totals = result.get("totals") or {}
        self.status.emit(
            f"Corpus analisado: {totals.get('documents', 0)} documentos · "
            f"{totals.get('words', 0)} palavras · "
            f"{totals.get('pairs', 0)} pares."
        )

    def _on_failed(self, message: str) -> None:
        self.progress.setVisible(False)
        self.btn_run.setEnabled(True)
        self.btn_add.setEnabled(True)
        self.status.emit("Erro na análise do corpus.")
        QMessageBox.critical(self, "Erro no corpus", message)

    # ------------------------------------------------------------------
    def _render(self, result: dict) -> None:
        totals = result.get("totals") or {}
        summary = result.get("summary") or {}
        languages = ", ".join(summary.get("languages") or []) or "—"
        warnings = result.get("warnings") or []
        warning_html = ""
        if warnings:
            warning_html = (
                "<div style='background:#fffaf0;border:1px solid #f0c987;"
                "border-radius:8px;padding:10px;margin-top:10px'>"
                "<b>Avisos</b><ul>"
                + "".join(f"<li>{message}</li>" for message in warnings)
                + "</ul></div>"
            )
        self.panorama.setHtml(
            "<h2 style='margin:0 0 8px'>Panorama do corpus</h2>"
            f"<p><b>{totals.get('documents', 0)}</b> documentos · "
            f"<b>{totals.get('words', 0)}</b> palavras · "
            f"<b>{totals.get('sentences', 0)}</b> sentenças · "
            f"<b>{totals.get('unique_terms', 0)}</b> termos únicos.</p>"
            f"<p>Idiomas: {languages}. Média de "
            f"{totals.get('avg_words', 0)} palavras por documento.</p>"
            f"<p>Similaridade média <b>{totals.get('avg_similarity', 0)}</b>; "
            f"máxima {totals.get('max_similarity', 0)} e mínima "
            f"{totals.get('min_similarity', 0)} em "
            f"{totals.get('pairs', 0)} pares.</p>"
            f"<p><b>{totals.get('clusters', 0)}</b> agrupamentos e "
            f"<b>{totals.get('duplicates', 0)}</b> duplicata(s) ou "
            "quase-duplicata(s).</p>"
            + warning_html
        )

        rows = []
        for item in result.get("documents") or []:
            stats = item.get("stats") or {}
            tone = item.get("sentiment") or {}
            readability = item.get("readability") or {}
            rows.append((
                item.get("name", ""),
                item.get("language_label", ""),
                stats.get("words", 0),
                stats.get("sentences", 0),
                stats.get("unique_words", 0),
                stats.get("ttr", 0),
                readability.get("flesch_reading_ease", ""),
                tone.get("label", "—"),
                tone.get("domain", "") or "—",
            ))
        self.documents_table.set_rows(rows)

        self._render_matrix(result)

        self.pairs_table.set_rows([
            (pair.get("a", ""), pair.get("b", ""), pair.get("similarity", 0))
            for pair in result.get("pairs") or []
        ])

        clusters = result.get("clusters") or []
        if not clusters:
            self.clusters_browser.setPlainText(
                "Nenhum agrupamento disponível."
            )
        else:
            blocks = []
            for cluster in clusters:
                blocks.append(
                    f"<h3>Grupo {cluster.get('id')} · "
                    f"{cluster.get('size')} documento(s) "
                    f"(coesão {cluster.get('cohesion')})</h3>"
                    f"<p><b>Documentos:</b> "
                    f"{', '.join(cluster.get('documents') or [])}</p>"
                    f"<p><em>{', '.join(cluster.get('top_terms') or [])}</em></p>"
                )
            self.clusters_browser.setHtml("".join(blocks))

        duplicates = result.get("duplicates") or []
        self.duplicates_table.set_rows([
            (
                item.get("a", ""), item.get("b", ""),
                item.get("similarity", 0),
                "texto idêntico" if item.get("exact") else "conteúdo próximo",
            )
            for item in duplicates
        ])

        vocabulary = result.get("vocabulary") or {}
        shared = vocabulary.get("shared") or []
        top_df = vocabulary.get("top_df") or []
        exclusive = vocabulary.get("exclusive") or {}
        shared_html = ", ".join(
            item.get("term", "") for item in shared[:40]
        ) or "nenhum termo presente em todos os documentos"
        df_html = ", ".join(
            f"{item.get('term')} ({item.get('documents')})"
            for item in top_df[:30]
        ) or "—"
        exclusive_html = "".join(
            f"<p><b>{label}</b>: {', '.join(terms) or '—'}</p>"
            for label, terms in exclusive.items()
        ) or "<p>—</p>"
        self.vocabulary_browser.setHtml(
            f"<h3>Compartilhado por todos</h3><p>{shared_html}</p>"
            f"<h3>Frequência documental</h3><p>{df_html}</p>"
            f"<h3>Exclusivos por documento</h3>{exclusive_html}"
        )

        if self.extraction_table.rowCount() == 0:
            suggested = extraction_matrix.build_rows(result)
            if suggested:
                self._write_extraction_rows(suggested)

    def _render_matrix(self, result: dict) -> None:
        labels = result.get("labels") or []
        matrix = result.get("matrix") or []
        self.matrix_table.clear()
        self.matrix_table.setRowCount(len(labels))
        self.matrix_table.setColumnCount(len(labels))
        self.matrix_table.setHorizontalHeaderLabels(labels)
        self.matrix_table.setVerticalHeaderLabels(labels)
        for i in range(len(labels)):
            for j in range(len(labels)):
                value = matrix[i][j] if i < len(matrix) and j < len(matrix[i]) \
                    else 0
                item = QTableWidgetItem(f"{value:.2f}")
                item.setTextAlignment(Qt.AlignCenter)
                if i == j:
                    item.setBackground(Qt.GlobalColor.lightGray)
                self.matrix_table.setItem(i, j, item)

    # ------------------------------------------------------------------
    # Checklist PRISMA 2020
    # ------------------------------------------------------------------
    def _load_checklist(self) -> None:
        state = {}
        try:
            state = userdata.load_settings().get("prisma_checklist") or {}
        except Exception:  # pragma: no cover - preferências são best-effort
            state = {}
        state = prisma_checklist.normalize_state(state)
        self._checklist_guard = True
        try:
            self.checklist_table.setRowCount(len(prisma_checklist.ITEMS))
            for row, item in enumerate(prisma_checklist.ITEMS):
                entry = state[item["id"]]
                for column, value in (
                    (0, item["id"]), (1, item["part"]), (2, item["title"]),
                ):
                    cell = QTableWidgetItem(value)
                    cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)
                    cell.setToolTip(item["description"])
                    self.checklist_table.setItem(row, column, cell)
                combo = QComboBox()
                for value, label in prisma_checklist.STATUS_OPTIONS:
                    combo.addItem(label, value)
                combo.setCurrentIndex(
                    max(0, combo.findData(entry["status"]))
                )
                combo.setToolTip(item["description"])
                combo.currentIndexChanged.connect(self._on_checklist_edited)
                self.checklist_table.setCellWidget(row, 3, combo)
                page_item = QTableWidgetItem(entry.get("page", ""))
                page_item.setToolTip("Página do relatório em que o item é "
                                     "atendido.")
                self.checklist_table.setItem(row, 4, page_item)
                self.checklist_table.setItem(
                    row, 5, QTableWidgetItem(entry.get("note", ""))
                )
        finally:
            self._checklist_guard = False
        self._refresh_checklist()

    def _checklist_state(self) -> dict:
        state = {}
        for row, item in enumerate(prisma_checklist.ITEMS):
            combo = self.checklist_table.cellWidget(row, 3)
            status = combo.currentData() if combo is not None else "pending"
            page_item = self.checklist_table.item(row, 4)
            note_item = self.checklist_table.item(row, 5)
            state[item["id"]] = {
                "status": status or "pending",
                "page": page_item.text() if page_item is not None else "",
                "note": note_item.text() if note_item is not None else "",
            }
        return state

    def _save_checklist(self) -> None:
        try:
            userdata.update_settings({
                "prisma_checklist": self._checklist_state()
            })
        except Exception:  # pragma: no cover - best effort
            pass

    def _on_checklist_edited(self, *_args) -> None:
        if self._checklist_guard:
            return
        self._save_checklist()
        self._refresh_checklist()

    def _checklist_context(self) -> dict:
        result = self._result or {}
        references = result.get("references") or {}
        if isinstance(references, dict):
            reference_count = len(references.get("items") or [])
        else:
            reference_count = len(references or [])
        counts = self._prisma_counts()
        try:
            extraction_rows = len(self._read_extraction_rows(keep_empty=False))
        except Exception:  # pragma: no cover - tabela ainda não montada
            extraction_rows = 0
        return {
            "documents": len(result.get("documents") or []),
            "references": reference_count,
            "extraction_rows": extraction_rows,
            "review_type": self.review_type.currentText().strip(),
            "search_engines": self.search_engines.text(),
            "search_string": self.search_string.text(),
            "inclusion": self.inclusion.text(),
            "exclusion": self.exclusion.text(),
            "collection_date": self.collection_date.text(),
            "identified": counts.get("identified", 0),
            "duplicates": counts.get("duplicates", 0),
            "screened": counts.get("screened", 0),
            "excluded": counts.get("excluded", 0),
            "included": counts.get("included", 0),
        }

    def _refresh_checklist(self) -> None:
        if not hasattr(self, "checklist_summary"):
            return
        state = self._checklist_state()
        context = self._checklist_context()
        data = prisma_checklist.evaluate(state, context)
        progress = data["progress"]
        self.checklist_summary.setText(
            prisma_checklist.summary(state, context)
        )
        self.checklist_progress.setValue(int(round(progress["percent"])))
        issues = data["warnings"]
        if issues:
            self.checklist_issues.setText(
                "\n".join(
                    f"⚠ Item {issue['item']}: {issue['message']}"
                    for issue in issues
                )
            )
        else:
            self.checklist_issues.setText(
                "Nenhuma lacuna detectada nos dados atuais da revisão."
            )
        self.checklist_issues.setToolTip("\n".join(
            f"Item {issue['item']}: {issue['message']}"
            for issue in data["issues"]
        ))

    def _export_checklist(self) -> None:
        state = self._checklist_state()
        context = self._checklist_context()
        filename, selected_filter = QFileDialog.getSaveFileName(
            self, "Exportar checklist PRISMA 2020",
            "checklist_prisma.csv",
            "CSV (*.csv);;Markdown (*.md);;HTML (*.html)",
        )
        if not filename:
            return
        suffix = Path(filename).suffix.lower()
        if suffix not in {".csv", ".md", ".markdown", ".html"}:
            if "Markdown" in (selected_filter or ""):
                suffix = ".md"
            elif "HTML" in (selected_filter or ""):
                suffix = ".html"
            else:
                suffix = ".csv"
            filename = str(Path(filename).with_suffix(suffix))
        try:
            if suffix in {".md", ".markdown"}:
                checklist_export.export_markdown(
                    state, filename, context
                )
            elif suffix == ".html":
                checklist_export.export_html(state, filename, context)
            else:
                checklist_export.export_csv(state, filename, context)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Erro ao exportar checklist", str(exc))
            return
        self.status.emit(
            f"Checklist PRISMA exportado: {Path(filename).name}"
        )

    # ------------------------------------------------------------------
    # Fluxo PRISMA
    # ------------------------------------------------------------------
    def _load_prisma(self) -> None:
        counts = {}
        try:
            counts = userdata.load_settings().get("prisma_counts") or {}
        except Exception:  # pragma: no cover
            counts = {}
        values = prisma.normalize_counts(counts)
        for key, spin in self.prisma_spins.items():
            spin.blockSignals(True)
            spin.setValue(int(values.get(key, 0)))
            spin.blockSignals(False)
        self._update_prisma_summary()

    def _prisma_counts(self) -> dict:
        return {key: spin.value() for key, spin in self.prisma_spins.items()}

    def _on_prisma_changed(self, _value=None) -> None:
        self._update_prisma_summary()
        try:
            userdata.update_settings({"prisma_counts": self._prisma_counts()})
        except Exception:  # pragma: no cover - best effort
            pass
        self._refresh_checklist()

    def _update_prisma_summary(self) -> None:
        data = prisma.flow_counts(self._prisma_counts())
        values = data["counts"]
        self.prisma_summary.setText(
            f"{values['identified']} identificados → "
            f"{values['screened']} triados → "
            f"{data['eligible']} elegíveis → "
            f"{values['included']} incluídos"
        )
        self.prisma_summary.setToolTip("\n".join(data["warnings"]))

    def _open_prisma(self) -> None:
        from ui.dialogs.prisma_dialog import PrismaDialog

        subtitle_parts = []
        review_type = self.review_type.currentText().strip()
        if review_type and review_type != "-":
            subtitle_parts.append(f"Revisão {review_type}")
        engines = self.search_engines.text().strip()
        if engines:
            subtitle_parts.append(f"Bases: {engines}")
        search = self.search_string.text().strip()
        if search:
            subtitle_parts.append(f"Busca: {search}")
        dialog = PrismaDialog(
            self._prisma_counts(),
            subtitle=" · ".join(subtitle_parts),
            parent=self,
        )
        try:
            dialog.exec()
            counts = dialog.counts()
            for key, spin in self.prisma_spins.items():
                spin.blockSignals(True)
                spin.setValue(int(counts.get(key, 0)))
                spin.blockSignals(False)
            self._on_prisma_changed()
        finally:
            dialog.deleteLater()

    # ------------------------------------------------------------------
    # Matriz de extração (revisão sistemática)
    # ------------------------------------------------------------------
    def _write_extraction_rows(self, rows, persist: bool = True) -> None:
        self._extraction_guard = True
        try:
            self.extraction_table.setRowCount(0)
            for row in extraction_matrix.normalize_rows(rows, keep_empty=True):
                index = self.extraction_table.rowCount()
                self.extraction_table.insertRow(index)
                for column_index, column_id in enumerate(
                        extraction_matrix.COLUMN_IDS):
                    value = str(row.get(column_id, ""))
                    item = QTableWidgetItem(value)
                    item.setToolTip(value)
                    self.extraction_table.setItem(
                        index, column_index, item
                    )
        finally:
            self._extraction_guard = False
        if persist:
            self._save_extraction_matrix()

    def _read_extraction_rows(self, keep_empty: bool = True):
        rows = []
        for index in range(self.extraction_table.rowCount()):
            row = {}
            for column_index, column_id in enumerate(
                    extraction_matrix.COLUMN_IDS):
                item = self.extraction_table.item(index, column_index)
                row[column_id] = item.text() if item is not None else ""
            rows.append(row)
        return extraction_matrix.normalize_rows(rows, keep_empty=keep_empty)

    def _save_extraction_matrix(self) -> None:
        try:
            userdata.update_settings({
                "extraction_matrix": extraction_matrix.rows_to_lists(
                    self._read_extraction_rows(keep_empty=False)
                )
            })
        except Exception:  # pragma: no cover - preferências são best-effort
            pass

    def _load_extraction_matrix(self) -> None:
        rows = []
        try:
            rows = userdata.load_settings().get("extraction_matrix") or []
        except Exception:  # pragma: no cover
            rows = []
        self._write_extraction_rows(rows, persist=False)

    def _on_extraction_edited(self, item) -> None:
        if self._extraction_guard or item is None:
            return
        item.setToolTip(item.text())
        self._save_extraction_matrix()

    def _suggest_extraction(self) -> None:
        if not self._result:
            QMessageBox.information(
                self, "Matriz de extração",
                "Analise o corpus primeiro para gerar as sugestões.",
            )
            return
        suggested = extraction_matrix.build_rows(self._result)
        if not suggested:
            QMessageBox.information(
                self, "Matriz de extração",
                "O corpus analisado não tem documentos para sugerir.",
            )
            return
        merged = extraction_matrix.merge_suggestions(
            self._read_extraction_rows(), suggested
        )
        self._write_extraction_rows(merged)
        self.tabs.setCurrentWidget(self.extraction_widget)
        self.status.emit(
            f"Matriz de extração atualizada: {len(merged)} documento(s)."
        )

    def _add_extraction_row(self) -> None:
        rows = self._read_extraction_rows()
        rows.append(extraction_matrix.empty_row())
        self._write_extraction_rows(rows)
        last = self.extraction_table.rowCount() - 1
        if last >= 0:
            self.extraction_table.setCurrentCell(last, 0)
            self.extraction_table.editItem(
                self.extraction_table.item(last, 0)
            )

    def _remove_extraction_rows(self) -> None:
        selected = sorted({
            index.row() for index in self.extraction_table.selectedIndexes()
        }, reverse=True)
        if not selected:
            QMessageBox.information(
                self, "Matriz de extração",
                "Selecione ao menos uma linha para remover.",
            )
            return
        rows = self._read_extraction_rows()
        for row_index in selected:
            if 0 <= row_index < len(rows):
                rows.pop(row_index)
        self._write_extraction_rows(rows)

    def _export_extraction(self) -> None:
        rows = self._read_extraction_rows(keep_empty=False)
        if not rows:
            QMessageBox.information(
                self, "Matriz de extração",
                "A matriz está vazia. Use “Sugerir do corpus” ou adicione "
                "uma linha.",
            )
            return
        base = Path(self._paths[0]).parent if self._paths else Path.cwd()
        filename, selected_filter = QFileDialog.getSaveFileName(
            self, "Exportar matriz de extração",
            str(base / "matriz_extracao.csv"),
            "CSV (*.csv);;Planilha XLSX (*.xlsx);;HTML (*.html);;"
            "Markdown (*.md)",
        )
        if not filename:
            return
        suffix = Path(filename).suffix.lower()
        if suffix not in {".csv", ".xlsx", ".html", ".md", ".markdown"}:
            if "XLSX" in (selected_filter or ""):
                suffix = ".xlsx"
            elif "HTML" in (selected_filter or ""):
                suffix = ".html"
            elif "Markdown" in (selected_filter or ""):
                suffix = ".md"
            else:
                suffix = ".csv"
            filename = str(Path(filename).with_suffix(suffix))
        try:
            if suffix == ".xlsx":
                extraction_export.export_xlsx(rows, filename)
            elif suffix == ".html":
                extraction_export.export_html(rows, filename)
            elif suffix in {".md", ".markdown"}:
                extraction_export.export_markdown(rows, filename)
            else:
                extraction_export.export_csv(rows, filename)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(
                self, "Erro ao exportar matriz",
                f"Não foi possível exportar:\n{exc}",
            )
            return
        self.status.emit(
            f"Matriz de extração exportada: {Path(filename).name}"
        )

    # ------------------------------------------------------------------
    def clear(self) -> None:
        self._result = None
        self.btn_export_html.setEnabled(False)
        self.btn_export_csv.setEnabled(False)
        self.panorama.setHtml(
            "<p style='color:#5b6673'>Adicione ao menos dois documentos e "
            "clique em <b>Analisar corpus</b>.</p>"
        )
        self.documents_table.set_rows([])
        self.pairs_table.set_rows([])
        self.duplicates_table.set_rows([])
        self.clusters_browser.clear()
        self.vocabulary_browser.clear()
        self.matrix_table.clear()
        self.matrix_table.setRowCount(0)
        self.matrix_table.setColumnCount(0)

    def reset(self) -> None:
        self.clear()
        self._paths = []
        self._refresh_files()
        self.status.emit("Lista do corpus esvaziada.")

    def export(self, kind: str) -> None:
        if not self._result:
            return
        base = Path(self._paths[0]).parent if self._paths else Path.cwd()
        stem = "corpus"
        if kind == "html":
            filename, _ = QFileDialog.getSaveFileName(
                self, "Exportar corpus (HTML)",
                str(base / f"{stem}.html"), "HTML (*.html)",
            )
            if not filename:
                return
            exporters.export_corpus_html(self._result, filename)
        else:
            filename, _ = QFileDialog.getSaveFileName(
                self, "Exportar corpus (CSV)",
                str(base / f"{stem}.csv"), "CSV (*.csv)",
            )
            if not filename:
                return
            exporters.export_corpus_csv(self._result, filename)
        self.status.emit(f"Corpus exportado: {Path(filename).name}")
