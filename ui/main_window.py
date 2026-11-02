#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Janela principal do Semantorium.
"""

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog,
    QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QMainWindow, QMessageBox, QProgressBar, QPushButton,
    QSpinBox, QStatusBar, QTabWidget, QVBoxLayout, QWidget,
)

from core import __version__ as APP_VERSION
from core import i18n, userdata
from core import ollama as ollama_client
from core.analysis import AnalysisConfig
from core.ner import discover_models
from core.sentiment import DOMAINS
from core.wordcloud_gen import available_palettes
from ui.dialogs.history_dialog import HistoryDialog
from ui.dialogs.stoplist_dialog import StoplistDialog
from ui.views.advanced_view import AdvancedView
from ui.views.ai_reports_view import AiReportsView
from ui.views.citations_view import CitationsView
from ui.views.compare_view import CompareView
from ui.views.corpus_view import CorpusView
from ui.views.explore_view import ExploreView
from ui.views.export_view import ExportView
from ui.views.graphs_view import GraphsView
from ui.views.load_view import LoadView
from ui.views.overview_view import OverviewView
from ui.views.words_view import WordsView
from ui.worker import AnalysisWorker, LoadWorker


class SettingsDialog(QDialog):
    def __init__(self, config: AnalysisConfig, parent=None):
        super().__init__(parent)
        self.setWindowTitle(
            i18n.t("settings.title", "Configurações da análise")
        )
        self.config = config

        form = QFormLayout(self)

        self.combo_method = QComboBox()
        self.combo_method.addItems(["text_rank", "lsa", "lex_rank"])
        self.combo_method.setCurrentText(config.summary_method)
        form.addRow("Algoritmo de resumo:", self.combo_method)

        self.spin_ratio = QDoubleSpinBox()
        self.spin_ratio.setRange(0.05, 0.6)
        self.spin_ratio.setSingleStep(0.05)
        self.spin_ratio.setValue(config.summary_ratio)
        form.addRow("Proporção do resumo (automático):", self.spin_ratio)

        self.combo_size = QComboBox()
        for label, value in (
            ("Automático (pela proporção)", "auto"),
            ("Curto (3–5 sentenças)", "curto"),
            ("Médio (5–9 sentenças)", "medio"),
            ("Longo (8–16 sentenças)", "longo"),
        ):
            self.combo_size.addItem(label, value)
        index = self.combo_size.findData(config.summary_size)
        self.combo_size.setCurrentIndex(max(0, index))
        form.addRow("Tamanho do resumo:", self.combo_size)

        self.combo_sentiment = QComboBox()
        self.combo_sentiment.addItem("Detecção automática de domínio", "auto")
        self.combo_sentiment.addItem("Nenhum (apenas léxico geral)", "nenhum")
        for key, data in DOMAINS.items():
            self.combo_sentiment.addItem(data["label"], key)
        index = self.combo_sentiment.findData(config.sentiment_domain)
        self.combo_sentiment.setCurrentIndex(max(0, index))
        form.addRow("Domínio do sentimento:", self.combo_sentiment)

        self.combo_ner = QComboBox()
        for label, value in (
            ("Automático (usa spaCy se disponível)", "auto"),
            ("Forçar spaCy (avisa se ausente)", "spacy"),
            ("Somente heurísticas (sem spaCy)", "fallback"),
        ):
            self.combo_ner.addItem(label, value)
        index = self.combo_ner.findData(config.ner_mode)
        self.combo_ner.setCurrentIndex(max(0, index))
        form.addRow("Reconhecimento de nomes (NER):", self.combo_ner)

        self.check_models = QCheckBox(
            "Ativar camada de modelos opcionais (Fase 21)"
        )
        self.check_models.setChecked(bool(config.models_v1))
        self.check_models.setToolTip(
            "Usa spaCy/Stanza, embeddings e correferência neural quando "
            "estiverem instalados. Nada muda se não houver modelos."
        )
        form.addRow("Modelos opcionais:", self.check_models)

        self.check_models_ollama = QCheckBox(
            "Permitir reinterpretação pelo Ollama local"
        )
        self.check_models_ollama.setChecked(bool(config.models_ollama))
        self.check_models_ollama.setToolTip(
            "Opt-in explícito: o texto é enviado apenas para o servidor "
            "Ollama em 127.0.0.1. A saída é interpretativa e não vira "
            "resultado determinístico."
        )
        form.addRow("Hipóteses (Ollama):", self.check_models_ollama)

        self.combo_ui_lang = QComboBox()
        try:
            for code, name in i18n.SUPPORTED.items():
                self.combo_ui_lang.addItem(name, code)
            cur = i18n.get_locale()
            idx = self.combo_ui_lang.findData(cur)
            if idx >= 0:
                self.combo_ui_lang.setCurrentIndex(idx)
        except Exception:
            pass
        form.addRow("Idioma da interface:", self.combo_ui_lang)

        self.combo_embedding_model = QComboBox()
        self.combo_embedding_model.setEditable(True)
        for model_name in (
            "paraphrase-multilingual-MiniLM-L12-v2",
            "paraphrase-multilingual-mpnet-base-v2",
            "all-MiniLM-L6-v2",
            "neuralmind/bert-base-portuguese-cased",
        ):
            self.combo_embedding_model.addItem(model_name)
        try:
            from core import embeddings as _emb
            _settings = userdata.load_settings()
            current_model = _settings.get("embedding_model") or _emb.DEFAULT_MODEL
            idx = self.combo_embedding_model.findText(current_model)
            if idx >= 0:
                self.combo_embedding_model.setCurrentIndex(idx)
            else:
                self.combo_embedding_model.setEditText(current_model)
        except Exception:
            pass
        form.addRow("Modelo de embeddings:", self.combo_embedding_model)

        cache_row = QWidget()
        cache_layout = QHBoxLayout(cache_row)
        cache_layout.setContentsMargins(0, 0, 0, 0)
        self.embedding_cache_label = QLabel("")
        self.embedding_cache_label.setStyleSheet("color:#5b6673; font-size:11px;")
        cache_layout.addWidget(self.embedding_cache_label, 1)
        self.button_clear_cache = QPushButton("Limpar cache")
        self.button_clear_cache.clicked.connect(self._clear_embedding_cache)
        cache_layout.addWidget(self.button_clear_cache)
        form.addRow("Cache de embeddings:", cache_row)
        self._refresh_embedding_cache_label()

        self.combo_theme = QComboBox()
        from ui import theme as _theme
        for code, label in _theme.THEMES:
            self.combo_theme.addItem(label, code)
        try:
            current_theme = _theme.normalize(
                userdata.load_settings().get("theme", _theme.DEFAULT_THEME)
            )
            idx = self.combo_theme.findData(current_theme)
            if idx >= 0:
                self.combo_theme.setCurrentIndex(idx)
        except Exception:
            pass
        form.addRow("Tema:", self.combo_theme)


        models = discover_models(config.language if config.language != "Auto-detectar"
                                 else "PT-BR")
        if models:
            model_text = ", ".join(item["name"] for item in models[:4])
        else:
            model_text = "nenhum modelo localizado; heurísticas internas serão usadas"
        ner_hint = QLabel(model_text)
        ner_hint.setWordWrap(True)
        ner_hint.setStyleSheet("color:#5b6673; font-size:11px;")
        form.addRow("Modelos NER:", ner_hint)

        self.spin_keywords = QSpinBox()
        self.spin_keywords.setRange(5, 60)
        self.spin_keywords.setValue(config.max_keywords)
        form.addRow("Palavras-chave:", self.spin_keywords)

        self.spin_top = QSpinBox()
        self.spin_top.setRange(10, 300)
        self.spin_top.setValue(config.top_words)
        form.addRow("Palavras na listagem:", self.spin_top)

        self.spin_window = QSpinBox()
        self.spin_window.setRange(2, 12)
        self.spin_window.setValue(config.cooc_window)
        form.addRow("Janela de coocorrência:", self.spin_window)

        self.spin_minfreq = QSpinBox()
        self.spin_minfreq.setRange(1, 50)
        self.spin_minfreq.setValue(config.cooc_min_freq)
        form.addRow("Frequência mínima (nó):", self.spin_minfreq)

        self.spin_minedge = QSpinBox()
        self.spin_minedge.setRange(1, 50)
        self.spin_minedge.setValue(config.cooc_min_edge)
        form.addRow("Peso mínimo (aresta):", self.spin_minedge)

        self.spin_topics = QSpinBox()
        self.spin_topics.setRange(2, 15)
        self.spin_topics.setValue(config.topics)
        form.addRow("Tópicos (LDA):", self.spin_topics)

        self.spin_clusters = QSpinBox()
        self.spin_clusters.setRange(2, 12)
        self.spin_clusters.setValue(config.clusters)
        form.addRow("Agrupamentos:", self.spin_clusters)

        self.combo_palette = QComboBox()
        self.combo_palette.addItems(available_palettes())
        if self.combo_palette.findText(config.wordcloud_palette) >= 0:
            self.combo_palette.setCurrentText(config.wordcloud_palette)
        form.addRow("Paleta da nuvem:", self.combo_palette)

        self.combo_background = QComboBox()
        self.combo_background.addItems(["Branco", "Preto", "Transparente"])
        if config.wordcloud_transparent:
            self.combo_background.setCurrentText("Transparente")
        elif config.wordcloud_background == "black":
            self.combo_background.setCurrentText("Preto")
        form.addRow("Fundo da nuvem:", self.combo_background)

        mask_row = QWidget()
        mask_layout = QHBoxLayout(mask_row)
        mask_layout.setContentsMargins(0, 0, 0, 0)
        self.input_mask = QLineEdit(config.wordcloud_mask or "")
        self.input_mask.setPlaceholderText("Opcional: PNG, JPG ou SVG")
        mask_layout.addWidget(self.input_mask, 1)
        button_mask = QPushButton("Escolher…")
        button_mask.clicked.connect(self._pick_mask)
        mask_layout.addWidget(button_mask)
        form.addRow("Máscara da nuvem:", mask_row)

        self.input_exclude = QLineEdit(", ".join(config.exclude_terms or []))
        self.input_exclude.setPlaceholderText(
            "Termos retirados apenas de redes e árvore, separados por vírgula"
        )
        form.addRow("Excluir das redes:", self.input_exclude)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _pick_mask(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "Escolher máscara da nuvem", "",
            "Imagens (*.png *.jpg *.jpeg *.svg);;Todos os arquivos (*.*)",
        )
        if filename:
            self.input_mask.setText(filename)

    def _refresh_embedding_cache_label(self) -> None:
        if not hasattr(self, "embedding_cache_label"):
            return
        try:
            from core import embeddings
            stats = embeddings.cache_stats()
            size_kb = stats.get("bytes", 0) / 1024
            if stats.get("enabled"):
                self.embedding_cache_label.setText(
                    f"{stats.get('files', 0)} vetor(es) em cache · {size_kb:.0f} KB"
                )
            else:
                self.embedding_cache_label.setText("Cache desativado")
            self.button_clear_cache.setEnabled(stats.get("files", 0) > 0)
        except Exception:
            self.embedding_cache_label.setText("Cache indisponível")

    def _clear_embedding_cache(self) -> None:
        try:
            from core import embeddings
            removed = embeddings.clear_cache()
            self._refresh_embedding_cache_label()
            QMessageBox.information(
                self, "Cache de embeddings",
                f"{removed} arquivo(s) de cache removido(s).",
            )
        except Exception as exc:
            QMessageBox.warning(self, "Cache de embeddings", str(exc))

    def result_config(self) -> AnalysisConfig:
        cfg = AnalysisConfig()
        cfg.summary_method = self.combo_method.currentText()
        cfg.summary_ratio = self.spin_ratio.value()
        cfg.summary_size = self.combo_size.currentData()
        cfg.sentiment_domain = self.combo_sentiment.currentData()
        cfg.ner_mode = self.combo_ner.currentData()
        cfg.models_v1 = self.check_models.isChecked()
        cfg.models_ollama = self.check_models_ollama.isChecked()
        cfg.models_ollama_model = self.config.models_ollama_model
        try:
            if hasattr(self, 'combo_ui_lang'):
                lang_code = self.combo_ui_lang.currentData()
                userdata.update_settings({"ui_language": lang_code})
                i18n.set_locale(lang_code)
        except Exception:
            pass
        try:
            if hasattr(self, 'combo_embedding_model'):
                model_name = self.combo_embedding_model.currentText().strip()
                if model_name:
                    userdata.update_settings({"embedding_model": model_name})
        except Exception:
            pass
        try:
            if hasattr(self, 'combo_theme'):
                theme_code = self.combo_theme.currentData()
                userdata.update_settings({"theme": theme_code})
        except Exception:
            pass
        cfg.max_keywords = self.spin_keywords.value()
        cfg.top_words = self.spin_top.value()
        cfg.cooc_window = self.spin_window.value()
        cfg.cooc_min_freq = self.spin_minfreq.value()
        cfg.cooc_min_edge = self.spin_minedge.value()
        cfg.topics = self.spin_topics.value()
        cfg.clusters = self.spin_clusters.value()
        cfg.wordcloud_palette = self.combo_palette.currentText()
        background = self.combo_background.currentText()
        cfg.wordcloud_transparent = background == "Transparente"
        cfg.wordcloud_background = "black" if background == "Preto" else "white"
        cfg.wordcloud_mask = self.input_mask.text().strip()
        cfg.exclude_terms = [
            term.strip() for term in self.input_exclude.text().split(",")
            if term.strip()
        ]
        return cfg


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(
            i18n.t("app.window_title", "Semantorium · Analisador Textual")
        )
        self.resize(1280, 860)
        self.setMinimumSize(980, 640)
        self.setAcceptDrops(True)

        self.config = AnalysisConfig()
        self.current_text = ""
        self.current_meta: dict = {}
        self.current_path = ""
        self.result: dict = {}
        self.ai_reports: list = []
        self._analysis_worker = None
        self._load_worker = None
        self._load_settings()

        self._build_ui()
        self._build_menu()
        self._retranslate_ui()
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Pronto. Carregue um arquivo para começar.")
        self._apply_style()
        self._refresh_menus()
        self._sync_favorite_action()

    # ------------------------------------------------------------------
    def _load_settings(self) -> None:
        """Restaura a configuração salva sem impedir a abertura do app."""
        try:
            settings = userdata.load_settings()
            self.config = userdata.config_from_dict(
                settings.get("config"), AnalysisConfig
            )
        except Exception:
            self.config = AnalysisConfig()

    def _persist_config(self) -> None:
        try:
            settings = userdata.load_settings()
            settings["config"] = userdata.config_to_dict(self.config)
            userdata.save_settings(settings)
        except Exception:
            pass

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # Barra superior
        bar = QHBoxLayout()
        self.btn_generate = QPushButton(i18n.t(
            "button.generate", "⚡  Gerar relatório"
        ))
        self.btn_generate.setObjectName("Primary")
        self.btn_generate.setMinimumHeight(38)
        self.btn_generate.setEnabled(False)
        self.btn_generate.clicked.connect(self.run_analysis)
        bar.addWidget(self.btn_generate)

        self.btn_settings = QPushButton(i18n.t(
            "button.settings", "⚙  Configurações"
        ))
        self.btn_settings.clicked.connect(self.open_settings)
        bar.addWidget(self.btn_settings)

        self.btn_search = QPushButton(i18n.t("button.search", "🔎  Buscar"))
        self.btn_search.setToolTip("Busca global no relatório (Ctrl+F)")
        self.btn_search.clicked.connect(self.open_global_search)
        bar.addWidget(self.btn_search)

        bar.addStretch()
        self.progress = QProgressBar()
        self.progress.setFixedWidth(280)
        self.progress.setVisible(False)
        bar.addWidget(self.progress)
        layout.addLayout(bar)

        # Abas
        self.tabs = QTabWidget()

        self.view_load = LoadView()
        self.view_overview = OverviewView()
        self.view_words = WordsView()
        self.view_graphs = GraphsView()
        self.view_citations = CitationsView()
        self.view_advanced = AdvancedView()
        self.view_explore = ExploreView()
        self.view_compare = CompareView()
        self.view_corpus = CorpusView()
        self.view_ai_reports = AiReportsView()
        self.view_export = ExportView()

        self._tab_specs = [
            (self.view_load, "tab.load", "📄 Carregar"),
            (self.view_overview, "tab.overview", "📊 Visão geral"),
            (self.view_words, "tab.words", "🔤 Palavras"),
            (self.view_graphs, "tab.graphs", "🕸️ Redes"),
            (self.view_citations, "tab.citations", "📑 Citações & índices"),
            (self.view_advanced, "tab.advanced", "🔬 Análise avançada"),
            (self.view_explore, "tab.explore", "🧭 Explorar"),
            (self.view_compare, "tab.compare", "⚖️ Comparar"),
            (self.view_corpus, "tab.corpus", "🗂️ Corpus"),
            (self.view_ai_reports, "tab.ai_reports", "🤖 Relatórios de IA"),
            (self.view_export, "tab.export", "💾 Exportar"),
        ]
        # As sete análises especializadas saem de "Análise avançada" e passam
        # a ser abas de topo, logo depois dela, mantendo a ordem original.
        advanced_index = next(
            index for index, spec in enumerate(self._tab_specs)
            if spec[0] is self.view_advanced
        )
        self._tab_specs[advanced_index + 1:advanced_index + 1] = list(
            self.view_advanced.promoted_tabs
        )
        for widget, key, default in self._tab_specs:
            self.tabs.addTab(widget, i18n.t(key, default))
        self.tabs.setAccessibleName("Abas de análise do Semantorium")
        self.tabs.setAccessibleDescription(
            "Use Ctrl+Tab e Ctrl+Shift+Tab para percorrer as abas do grupo "
            "atual, Alt+N para abrir uma aba específica e Ctrl+1 a Ctrl+6 "
            "para trocar de grupo."
        )
        self.tabs.setUsesScrollButtons(True)
        self.tabs.tabBar().setElideMode(Qt.ElideRight)
        self.tabs.tabBar().setFocusPolicy(Qt.StrongFocus)
        self.tabs.tabBar().setExpanding(False)
        self.tabs.setFocusPolicy(Qt.StrongFocus)

        for index in range(1, self.tabs.count()):
            self.tabs.setTabEnabled(index, False)
        # O corpus é independente do documento carregado.
        self.tabs.setTabEnabled(self.tabs.indexOf(self.view_corpus), True)
        # A aba de relatórios de IA fica disponível para consulta/exportação,
        # mesmo antes de gerar um novo relatório.
        self.tabs.setTabEnabled(self.tabs.indexOf(self.view_ai_reports), True)

        # Seis grupos substituem a navegação por 18 abas soltas. O conjunto
        # plano de abas é preservado (mesmos índices, visões e atalhos Alt+N);
        # o grupo apenas alterna a visibilidade das abas que o compõem.
        self.tab_groups = [
            ("group.reading", "📖 Leitura", (
                self.view_load, self.view_overview, self.view_words,
                self.view_graphs,
            )),
            ("group.text", "🔤 Texto", (
                self.view_advanced.page_lexicometry,
                self.view_advanced.page_linguistics,
                self.view_advanced.page_style,
            )),
            ("group.research", "🎓 Pesquisa", (
                self.view_advanced, self.view_advanced.page_research,
                self.view_citations,
            )),
            ("group.discourse", "🗣️ Discurso", (
                self.view_advanced.page_discourse,
                self.view_advanced.page_knowledge,
                self.view_advanced.page_consistency,
            )),
            ("group.compare", "⚖️ Comparar", (
                self.view_explore, self.view_compare,
            )),
            ("group.output", "💾 Saída", (
                self.view_corpus, self.view_ai_reports, self.view_export,
            )),
        ]
        self._tab_keys = [key for _widget, key, _default in self._tab_specs]

        group_row = QHBoxLayout()
        group_row.setSpacing(4)
        self._tab_group_buttons = []
        self._tab_group = QButtonGroup(self)
        self._tab_group.setExclusive(True)
        for index, (key, label, _views) in enumerate(self.tab_groups):
            button = QPushButton(i18n.t(key, label))
            button.setObjectName("TabGroup")
            button.setCheckable(True)
            button.setFocusPolicy(Qt.StrongFocus)
            button.setAccessibleName(i18n.t(key, label))
            button.setToolTip(i18n.t(key, label))
            button.clicked.connect(
                lambda checked=False, group=index:
                self._select_tab_group(group)
            )
            self._tab_group.addButton(button, index)
            group_row.addWidget(button)
            self._tab_group_buttons.append(button)
        group_row.addStretch()
        layout.addLayout(group_row)

        layout.addWidget(self.tabs, 1)
        self._select_tab_group(0)
        self._restore_last_tab()

        self.view_load.file_selected.connect(self.load_file)
        self.view_export.status.connect(self.statusBar().showMessage)
        self.view_ai_reports.status.connect(self.statusBar().showMessage)
        self.view_ai_reports.reports_changed.connect(self._on_ai_reports_changed)
        self.view_explore.status.connect(self.statusBar().showMessage)
        self.view_explore.reveal_requested.connect(self._reveal_in_document)
        self.view_words.status.connect(self.statusBar().showMessage)
        self.view_graphs.status.connect(self.statusBar().showMessage)
        self.view_compare.status.connect(self.statusBar().showMessage)
        self.view_corpus.status.connect(self.statusBar().showMessage)
        self.view_words.stoplist_requested.connect(self.open_stoplist)
        self.view_words.config_changed.connect(self.update_config)
        self.view_graphs.config_changed.connect(self.update_config)
        self.view_words.apply_config(self.config)
        self.view_graphs.apply_config(self.config)
        self.view_export.set_config(self.config)
        self.view_export.config_loaded.connect(self.load_template_config)
        self.view_export.apply_default_format()

    def _build_menu(self) -> None:
        menubar = self.menuBar()

        self.menu_file = menubar.addMenu(i18n.t("menu.file", "Arquivo"))
        self.action_open = QAction(
            i18n.t("action.open", "Abrir arquivo…"), self
        )
        self.action_open.setShortcut(QKeySequence.Open)
        self.action_open.setStatusTip("Abrir um documento suportado")
        self.action_open.triggered.connect(lambda: self.view_load._pick())
        self.menu_file.addAction(self.action_open)

        self.action_session = QAction(
            i18n.t("action.open_session", "Abrir sessão…"), self
        )
        self.action_session.setShortcut("Ctrl+Shift+O")
        self.action_session.triggered.connect(self.open_session)
        self.menu_file.addAction(self.action_session)

        self.menu_recent = self.menu_file.addMenu(
            i18n.t("menu.recent", "Documentos recentes")
        )
        self.menu_favorites = self.menu_file.addMenu(
            i18n.t("menu.favorites", "Favoritos")
        )
        self.favorite_action = QAction(
            i18n.t("action.favorite_toggle", "Favoritar documento atual"),
            self,
        )
        self.favorite_action.setCheckable(True)
        self.favorite_action.setShortcut("Ctrl+D")
        self.favorite_action.setStatusTip(
            "Adicionar/remover o documento dos favoritos"
        )
        self.favorite_action.triggered.connect(self.toggle_favorite)
        self.menu_file.addAction(self.favorite_action)

        self.action_history = QAction(
            i18n.t("action.history", "Histórico de análises…"), self
        )
        self.action_history.setShortcut("Ctrl+H")
        self.action_history.triggered.connect(self.open_history)
        self.menu_file.addAction(self.action_history)

        self.menu_file.addSeparator()
        self.action_quit = QAction(i18n.t("action.quit", "Sair"), self)
        self.action_quit.setShortcut(QKeySequence.Quit)
        self.action_quit.triggered.connect(self.close)
        self.menu_file.addAction(self.action_quit)

        self.menu_analysis = menubar.addMenu(
            i18n.t("menu.analysis", "Análise")
        )
        self.action_run = QAction(
            i18n.t("action.run", "Gerar relatório"), self
        )
        self.action_run.setShortcut("F5")
        self.action_run.setStatusTip(
            "Executar todas as análises do documento"
        )
        self.action_run.triggered.connect(self.run_analysis)
        self.menu_analysis.addAction(self.action_run)

        self.action_settings = QAction(
            i18n.t("action.settings", "Configurações…"), self
        )
        self.action_settings.setShortcut("Ctrl+,")
        self.action_settings.triggered.connect(self.open_settings)
        self.menu_analysis.addAction(self.action_settings)

        self.action_stoplist = QAction(
            i18n.t("action.stoplist", "Editar stoplist…"), self
        )
        self.action_stoplist.setShortcut("Ctrl+K")
        self.action_stoplist.triggered.connect(self.open_stoplist)
        self.menu_analysis.addAction(self.action_stoplist)

        self.action_assistant = QAction(
            i18n.t("action.assistant", "Assistente local (Ollama)…"), self
        )
        self.action_assistant.setShortcut("Ctrl+Shift+A")
        self.action_assistant.setStatusTip(
            "Resumo/perguntas com um modelo local, opcional e offline"
        )
        self.action_assistant.triggered.connect(self.open_assistant)
        self.menu_analysis.addAction(self.action_assistant)

        self.menu_view = menubar.addMenu(i18n.t("menu.view", "Exibir"))
        self.tab_actions = []
        for number in range(1, self.tabs.count() + 1):
            action = QAction(
                i18n.t("action.tab", "Aba {number}").format(number=number),
                self,
            )
            action.setShortcut(QKeySequence(f"Alt+{number}"))
            action.triggered.connect(
                lambda checked=False, index=number - 1:
                self._focus_tab(index)
            )
            self.menu_view.addAction(action)
            self.tab_actions.append(action)
        self.menu_view.addSeparator()
        self.action_next_tab = QAction(
            i18n.t("action.next_tab", "Próxima aba do grupo"), self
        )
        self.action_next_tab.setShortcuts([
            QKeySequence("Ctrl+Tab"), QKeySequence("Ctrl+PgDown"),
        ])
        self.action_next_tab.triggered.connect(
            lambda: self._cycle_visible_tab(1)
        )
        self.menu_view.addAction(self.action_next_tab)
        self.action_previous_tab = QAction(
            i18n.t("action.previous_tab", "Aba anterior do grupo"), self
        )
        self.action_previous_tab.setShortcuts([
            QKeySequence("Ctrl+Shift+Tab"), QKeySequence("Ctrl+PgUp"),
        ])
        self.action_previous_tab.triggered.connect(
            lambda: self._cycle_visible_tab(-1)
        )
        self.menu_view.addAction(self.action_previous_tab)
        self.menu_view.addSeparator()
        self.group_actions = []
        for number, (key, label, _views) in enumerate(self.tab_groups, start=1):
            action = QAction(i18n.t(key, label), self)
            action.setShortcut(QKeySequence(f"Ctrl+{number}"))
            action.triggered.connect(
                lambda checked=False, group=number - 1:
                self._select_tab_group(group)
            )
            self.menu_view.addAction(action)
            self.group_actions.append(action)
        self.menu_view.addSeparator()
        self.action_export = QAction(
            i18n.t("action.export_tab", "Ir para Exportar"), self
        )
        self.action_export.setShortcut("Ctrl+E")
        self.action_export.triggered.connect(
            lambda: self._focus_tab(self.tabs.count() - 1)
        )
        self.menu_view.addAction(self.action_export)

        self.menu_view.addSeparator()
        self.action_search = QAction(
            i18n.t("action.search", "Busca global…"), self
        )
        self.action_search.setShortcut("Ctrl+F")
        self.action_search.triggered.connect(self.open_global_search)
        self.menu_view.addAction(self.action_search)

        self.menu_help = menubar.addMenu(i18n.t("menu.help", "Ajuda"))
        self.action_about = QAction(
            i18n.t("action.about", "Sobre o Semantorium"), self
        )
        self.action_about.setShortcut("F1")
        self.action_about.triggered.connect(self.show_about)
        self.menu_help.addAction(self.action_about)

    def _retranslate_ui(self) -> None:
        """Reaplica os textos da interface no idioma atual."""
        self.setWindowTitle(
            i18n.t("app.window_title", "Semantorium · Analisador Textual")
        )
        for menu, key, default in (
            (self.menu_file, "menu.file", "Arquivo"),
            (self.menu_analysis, "menu.analysis", "Análise"),
            (self.menu_view, "menu.view", "Exibir"),
            (self.menu_help, "menu.help", "Ajuda"),
            (self.menu_recent, "menu.recent", "Documentos recentes"),
            (self.menu_favorites, "menu.favorites", "Favoritos"),
        ):
            menu.setTitle(i18n.t(key, default))
        for action, key, default in (
            (self.action_open, "action.open", "Abrir arquivo…"),
            (self.action_session, "action.open_session", "Abrir sessão…"),
            (self.favorite_action, "action.favorite_toggle",
             "Favoritar documento atual"),
            (self.action_history, "action.history",
             "Histórico de análises…"),
            (self.action_quit, "action.quit", "Sair"),
            (self.action_run, "action.run", "Gerar relatório"),
            (self.action_settings, "action.settings", "Configurações…"),
            (self.action_stoplist, "action.stoplist", "Editar stoplist…"),
            (self.action_assistant, "action.assistant",
             "Assistente local (Ollama)…"),
            (self.action_export, "action.export_tab", "Ir para Exportar"),
            (self.action_search, "action.search", "Busca global…"),
            (self.action_next_tab, "action.next_tab",
             "Próxima aba do grupo"),
            (self.action_previous_tab, "action.previous_tab",
             "Aba anterior do grupo"),
            (self.action_about, "action.about", "Sobre o Semantorium"),
        ):
            action.setText(i18n.t(key, default))
        tab_template = i18n.t("action.tab", "Aba {number}")
        for number, action in enumerate(self.tab_actions, start=1):
            action.setText(tab_template.format(number=number))
        for index, (key, label, _views) in enumerate(self.tab_groups):
            text = i18n.t(key, label)
            button = self._tab_group_buttons[index]
            button.setText(text)
            button.setAccessibleName(text)
            button.setToolTip(text)
            self.group_actions[index].setText(text)
        for index, (_widget, key, default) in enumerate(self._tab_specs):
            self.tabs.setTabText(index, i18n.t(key, default))
        self._update_tab_tooltips()
        self.btn_generate.setText(
            i18n.t("button.generate", "⚡  Gerar relatório")
        )
        self.btn_settings.setText(
            i18n.t("button.settings", "⚙  Configurações")
        )
        self.btn_search.setText(i18n.t("button.search", "🔎  Buscar"))

    def _focus_tab(self, index: int) -> None:
        if 0 <= index < self.tabs.count() and self.tabs.isTabEnabled(index):
            group = self._group_for_view(self.tabs.widget(index))
            if group is not None:
                self._select_tab_group(group, focus=False)
            self.tabs.setCurrentIndex(index)

    def _cycle_visible_tab(self, step: int) -> None:
        """Percorre as abas visíveis do grupo atual, com retorno circular."""
        visible = [
            index for index in range(self.tabs.count())
            if self.tabs.tabBar().isTabVisible(index)
            and self.tabs.isTabEnabled(index)
        ]
        if not visible:
            return
        current = self.tabs.currentIndex()
        if current in visible:
            position = visible.index(current)
            target = visible[(position + step) % len(visible)]
        else:
            target = visible[0] if step >= 0 else visible[-1]
        self._focus_tab(target)

    def _update_tab_tooltips(self) -> None:
        """Tooltip de cada aba com o atalho Alt+N e o grupo a que pertence."""
        for index, (_widget, key, default) in enumerate(self._tab_specs):
            text = i18n.t(key, default)
            group = self._group_for_view(self.tabs.widget(index))
            suffix = ""
            if 0 <= group < len(self.tab_groups):
                group_key, group_label, _views = self.tab_groups[group]
                suffix = f" · {i18n.t(group_key, group_label)}"
            self.tabs.setTabToolTip(index, f"{text} (Alt+{index + 1}){suffix}")

    def _group_for_view(self, widget) -> int:
        """Índice do grupo que contém ``widget`` (ou -1)."""
        for index, (_key, _label, views) in enumerate(self.tab_groups):
            if widget in views:
                return index
        return -1

    def _select_tab_group(self, group: int, focus: bool = True) -> None:
        """Mostra apenas as abas do grupo e seleciona a primeira disponível."""
        if not (0 <= group < len(self.tab_groups)):
            return
        self._active_group = group
        members = set(self.tab_groups[group][2])
        for index in range(self.tabs.count()):
            self.tabs.tabBar().setTabVisible(
                index, self.tabs.widget(index) in members
            )
        button = self._tab_group_buttons[group]
        if not button.isChecked():
            button.setChecked(True)
        if not focus:
            return
        current = self.tabs.currentWidget()
        if current in members:
            return
        fallback = None
        for widget in self.tab_groups[group][2]:
            index = self.tabs.indexOf(widget)
            if index < 0:
                continue
            if fallback is None:
                fallback = index
            if self.tabs.isTabEnabled(index):
                self.tabs.setCurrentIndex(index)
                return
        if fallback is not None:
            self.tabs.setCurrentIndex(fallback)

    def _reveal_in_document(self, start: int, end: int) -> None:
        """Abre a aba de leitura e seleciona o trecho da evidência."""
        index = self.tabs.indexOf(self.view_load)
        if index < 0:
            return
        group = self._group_for_view(self.view_load)
        if group >= 0:
            self._select_tab_group(group, focus=False)
        self.tabs.setCurrentIndex(index)
        if self.view_load.reveal_range(start, end):
            self.statusBar().showMessage(
                f"Trecho {int(start)}–{int(end)} selecionado no documento."
            )

    def _save_last_tab(self) -> None:
        """Guarda a aba e o grupo atuais para a próxima sessão."""
        try:
            settings = userdata.load_settings()
            index = self.tabs.currentIndex()
            if 0 <= index < len(self._tab_keys):
                settings["last_tab"] = self._tab_keys[index]
                settings["last_tab_group"] = self._group_for_view(
                    self.tabs.currentWidget()
                )
            userdata.save_settings(settings)
        except Exception:
            pass

    def _restore_last_tab(self) -> None:
        """Reabre a aba salva; se ela ainda não estiver disponível, cai no grupo."""
        try:
            settings = userdata.load_settings()
        except Exception:
            settings = {}
        key = settings.get("last_tab")
        index = self._tab_keys.index(key) if key in self._tab_keys else -1
        if index >= 0 and self.tabs.isTabEnabled(index):
            self._focus_tab(index)
            return
        group = settings.get("last_tab_group")
        if not isinstance(group, int) or not 0 <= group < len(self.tab_groups):
            group = 0
        self._select_tab_group(group)

    def open_global_search(self) -> None:
        """Busca global (Ctrl+F) em todas as seções do relatório."""
        from ui.dialogs.global_search_dialog import GlobalSearchDialog

        if not self.result:
            self.statusBar().showMessage(
                "Gere um relatório para usar a busca global."
            )
            return

        dialog = GlobalSearchDialog(self.result, self.current_text or "", self)
        if dialog.exec() != QDialog.Accepted:
            return

        section = dialog.selected_section
        mapping = {
            "summary": (self.view_overview, None),
            "keywords": (self.view_words, None),
            "words": (self.view_words, None),
            "concepts": (self.view_citations, 4),
            "citations": (self.view_citations, 1),
            "quotes": (self.view_citations, 2),
            "references": (self.view_citations, 0),
            "onomastic": (self.view_citations, 3),
            "text": (self.view_citations, 5),
        }
        view, inner_tab = mapping.get(section, (None, None))
        if view is not None:
            index = self.tabs.indexOf(view)
            if index >= 0:
                self._focus_tab(index)
        if inner_tab is not None and hasattr(self.view_citations, "tabs"):
            try:
                self.view_citations.tabs.setCurrentIndex(inner_tab)
            except Exception:
                pass
        self.statusBar().showMessage(
            f"Busca global: seção “{section or '—'}” selecionada."
        )

    def _refresh_menus(self) -> None:
        """Reconstrói as listas de recentes e favoritos."""
        self.menu_recent.clear()
        recent = userdata.recent_files()
        if not recent:
            empty = QAction("(nenhum documento recente)", self)
            empty.setEnabled(False)
            self.menu_recent.addAction(empty)
        for item in recent:
            path = item.get("path", "")
            label = item.get("name") or Path(path).name
            action = QAction(label, self)
            action.setStatusTip(path)
            action.triggered.connect(
                lambda checked=False, target=path: self._open_document(target)
            )
            self.menu_recent.addAction(action)
        self.menu_recent.addSeparator()
        clear_recent = QAction("Limpar lista", self)
        clear_recent.triggered.connect(self._clear_recent)
        self.menu_recent.addAction(clear_recent)

        self.menu_favorites.clear()
        favorites = userdata.favorites()
        if not favorites:
            empty = QAction("(nenhum favorito)", self)
            empty.setEnabled(False)
            self.menu_favorites.addAction(empty)
        for item in favorites:
            path = item.get("path", "")
            label = item.get("name") or Path(path).name
            action = QAction(label, self)
            action.setStatusTip(path)
            action.triggered.connect(
                lambda checked=False, target=path: self._open_document(target)
            )
            self.menu_favorites.addAction(action)

    def _open_document(self, path: str) -> None:
        if not path:
            return
        if not Path(path).exists():
            QMessageBox.warning(
                self, "Arquivo não encontrado",
                f"O arquivo não está mais no caminho registrado:\n{path}",
            )
            return
        self.load_file(path)

    def _clear_recent(self) -> None:
        settings = userdata.load_settings()
        settings["recent"] = []
        userdata.save_settings(settings)
        self._refresh_menus()

    def _sync_favorite_action(self) -> None:
        active = bool(self.current_path) and userdata.is_favorite(
            self.current_path
        )
        self.favorite_action.blockSignals(True)
        self.favorite_action.setChecked(active)
        self.favorite_action.setEnabled(bool(self.current_path))
        self.favorite_action.blockSignals(False)

    def toggle_favorite(self) -> None:
        if not self.current_path:
            QMessageBox.information(
                self, "Favoritos",
                "Carregue um arquivo para poder favoritá-lo.",
            )
            self._sync_favorite_action()
            return
        active = userdata.toggle_favorite(self.current_path, self.current_meta)
        self._refresh_menus()
        self._sync_favorite_action()
        self.statusBar().showMessage(
            "Documento adicionado aos favoritos." if active
            else "Documento removido dos favoritos."
        )

    def open_history(self) -> None:
        dialog = HistoryDialog(self)
        dialog.exec()
        if dialog.selected_path:
            self._open_document(dialog.selected_path)
        self._refresh_menus()

    def _apply_style(self) -> None:
        base = """
        QMainWindow, QWidget { background:#f6f8fb; color:#1b1f24;
            font-family:"Segoe UI", sans-serif; font-size:12px; }
        QTabWidget::pane { border:1px solid #e2e8f0; border-radius:8px;
            background:#ffffff; top:-1px; }
        QTabBar::tab { background:transparent; padding:8px 14px;
            margin-right:2px; border:none; color:#5b6673; }
        QTabBar::tab:selected { color:#1c53b8; border-bottom:2px solid #2d7ff9;
            font-weight:600; }
        QTabBar::tab:disabled { color:#b6bfcc; }
        QPushButton { background:#ffffff; border:1px solid #d6dde8;
            border-radius:7px; padding:7px 14px; color:#1b1f24; }
        QPushButton:hover { border-color:#2d7ff9; color:#1c53b8; }
        QPushButton:disabled { color:#b6bfcc; border-color:#eef2f7; }
        QPushButton#Primary { background:#2d7ff9; border:none; color:#ffffff;
            font-weight:600; }
        QPushButton#Primary:hover { background:#1c6be8; color:#ffffff; }
        QPushButton#Primary:disabled { background:#c7d8f5; color:#ffffff; }
        QProgressBar { border:1px solid #d6dde8; border-radius:6px;
            background:#ffffff; text-align:center; height:18px; }
        QProgressBar::chunk { background:#2d7ff9; border-radius:5px; }
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { background:#ffffff;
            border:1px solid #d6dde8; border-radius:6px; padding:5px 8px; }
        QLineEdit:focus, QComboBox:focus { border-color:#2d7ff9; }
        QScrollArea { border:none; background:transparent; }
        QTextEdit, QTextBrowser { background:#ffffff; border:1px solid #e2e8f0;
            border-radius:8px; padding:8px; }
        QStatusBar { background:#ffffff; border-top:1px solid #e2e8f0;
            color:#5b6673; }
        QFrame#Card { background:#ffffff; border:1px solid #e2e8f0;
            border-radius:10px; }
        QFrame#Kpi { background:#eaf1ff; border-radius:9px;
            border:1px solid #d6e2f7; }
        QLabel#KpiValue { color:#1c53b8; }
        QLabel#KpiName { color:#5b6673; letter-spacing:1px; }
        QTableWidget#DataTable { background:#ffffff; border:1px solid #e2e8f0;
            border-radius:8px; gridline-color:#eef2f7; }
        QTableWidget#DataTable QHeaderView::section { background:#f6f8fb;
            border:none; border-bottom:1px solid #e2e8f0; padding:6px;
            font-weight:600; color:#5b6673; text-align:left; }
        QLabel#SectionHeader { color:#1b1f24; margin-top:6px; }
        QLabel#Chip { background:#eaf1ff; color:#1c53b8; border-radius:11px;
            padding:4px 10px; font-size:11px; }
        QFrame#HLine { color:#e2e8f0; }
        QPushButton#TabGroup { background:transparent; border:none;
            border-radius:6px; padding:6px 10px; color:#5b6673;
            font-weight:600; }
        QPushButton#TabGroup:hover { background:#eaf1ff; color:#1c53b8; }
        QPushButton#TabGroup:checked { background:#eaf1ff; color:#1c53b8;
            border-bottom:2px solid #2d7ff9; }
        QWidget#TablePager { background:transparent; }
        QLabel#TablePagerLabel { color:#5b6673; padding:0 8px; }
        QPushButton#TablePagerButton { background:#ffffff;
            border:1px solid #d6dde8; border-radius:6px; padding:2px 10px;
            min-width:22px; color:#1b1f24; }
        QPushButton#TablePagerButton:hover { border-color:#2d7ff9;
            color:#1c53b8; }
        QPushButton#TablePagerButton:disabled { color:#b6bfcc;
            border-color:#eef2f7; }
        """
        try:
            from ui import theme as theme_mod
            theme = userdata.load_settings().get("theme", "light")
            self._theme = theme_mod.normalize(theme)
            theme_mod.set_current(self._theme)
            base = theme_mod.stylesheet_for(self._theme, base)
        except Exception:
            self._theme = "light"
        self.setStyleSheet(base)

    # ------------------------------------------------------------------
    def load_file(self, filepath: str) -> None:
        self.current_path = str(Path(filepath).resolve())
        self.view_load.show_loading(Path(filepath).name)
        self.statusBar().showMessage(f"Carregando {Path(filepath).name}…")
        self.btn_generate.setEnabled(False)

        self._load_worker = LoadWorker(filepath)
        self._load_worker.finished_ok.connect(self._on_loaded)
        self._load_worker.failed.connect(self._on_load_failed)
        self._load_worker.start()

    def _on_loaded(self, result: dict) -> None:
        self.current_text = result.get("text", "")
        self.current_meta = result.get("meta", {})
        self.view_load.set_result(result)

        if not self.current_text.strip():
            QMessageBox.warning(
                self, "Sem texto",
                "Nenhum texto foi extraído do arquivo. "
                "Se for um PDF escaneado, instale o componente de OCR."
            )
            self.statusBar().showMessage("Falha: nenhum texto extraído.")
            return

        self.btn_generate.setEnabled(True)
        meta = self.current_meta
        try:
            userdata.record_recent(self.current_path, meta)
            self._refresh_menus()
            self._sync_favorite_action()
        except Exception:
            pass
        self.statusBar().showMessage(
            f"{meta.get('filename','arquivo')} carregado · "
            f"{meta.get('words', 0):,} palavras · método {meta.get('method','—')}"
            .replace(",", ".")
        )
        # Reseta resultados antigos
        self.result = {}
        self.ai_reports = []
        self.view_ai_reports.clear()
        for index in range(1, self.tabs.count()):
            self.tabs.setTabEnabled(index, False)
        self.tabs.setTabEnabled(self.tabs.indexOf(self.view_corpus), True)
        self.tabs.setTabEnabled(self.tabs.indexOf(self.view_ai_reports), True)
        for view in (self.view_overview, self.view_words, self.view_citations,
                     self.view_advanced, self.view_explore, self.view_export):
            if hasattr(view, "clear"):
                view.clear()
        self.view_graphs.clear()
        self.view_compare.clear()
        self.view_compare.set_primary_text(
            self.current_text,
            label=Path(meta.get("filename", "Texto A")).stem or "Texto A",
        )

    def _on_load_failed(self, message: str) -> None:
        self.statusBar().showMessage("Erro ao carregar arquivo.")
        QMessageBox.critical(self, "Erro ao carregar", message)

    # ------------------------------------------------------------------
    def run_analysis(self) -> None:
        if not self.current_text.strip():
            QMessageBox.warning(self, "Aviso", "Carregue um arquivo primeiro.")
            return
        if self._analysis_worker and self._analysis_worker.isRunning():
            return

        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.progress.setFormat("%p%")
        self.btn_generate.setEnabled(False)
        self.view_load.btn_open.setEnabled(False)
        self.statusBar().showMessage("Analisando…")

        self._analysis_worker = AnalysisWorker(
            self.current_text, self.current_meta, self.config
        )
        self._analysis_worker.progress.connect(self._on_progress)
        self._analysis_worker.finished_ok.connect(self._on_analysis_done)
        self._analysis_worker.failed.connect(self._on_analysis_failed)
        self._analysis_worker.start()

    def _on_progress(self, pct: int, message: str) -> None:
        self.progress.setValue(pct)
        self.statusBar().showMessage(message)

    def _on_analysis_done(self, result: dict) -> None:
        # Relatórios de IA gerados antes/depois da análise fazem parte do
        # relatório final. Ao abrir uma sessão, os textos vêm no próprio
        # resultado; ao reanalisar, preservamos os que já estavam na janela.
        incoming = result.get("ai_reports") or []
        if incoming:
            self.ai_reports = [
                dict(report) for report in incoming if isinstance(report, dict)
            ]
        if self.ai_reports:
            result["ai_reports"] = self.ai_reports
        self.result = result
        self.view_ai_reports.set_reports(self.ai_reports)
        self.progress.setVisible(False)
        self.btn_generate.setEnabled(True)
        self.view_load.btn_open.setEnabled(True)

        self.view_overview.update_results(result)
        self.view_words.update_results(result)
        self.view_graphs.update_results(result, self.current_text)
        self.view_citations.update_results(result, self.current_text)
        self.view_advanced.update_results(result, self.current_text)
        self.view_explore.update_results(result, self.current_text)
        self.view_compare.set_primary_text(
            self.current_text,
            label=Path(
                self.current_meta.get("filename", "Texto A")
            ).stem or "Texto A",
            lang=result.get("language"),
        )
        self.view_export.update_results(
            result, self.current_text, self.current_path or ""
        )
        self.view_words.apply_config(self.config)
        self.view_graphs.apply_config(self.config)
        if self.current_path:
            try:
                userdata.record_history(self.current_path, self.current_meta, result)
                self._refresh_menus()
                self._sync_favorite_action()
            except Exception:
                pass

        for index in range(1, self.tabs.count()):
            self.tabs.setTabEnabled(index, True)

        self._select_tab_group(0, focus=False)
        self.tabs.setCurrentIndex(1)
        warnings = result.get("warnings") or []
        message = (
            f"Análise concluída em {result.get('duration_seconds', 0)} s · "
            f"idioma {result.get('language_label', '—')} · "
            f"motor {result.get('engine', '—')}"
        )
        if warnings:
            message += f" · ⚠ {len(warnings)} aviso(s) — veja a Visão geral"
        self.statusBar().showMessage(message)

    def _on_analysis_failed(self, message: str) -> None:
        self.progress.setVisible(False)
        self.btn_generate.setEnabled(True)
        self.view_load.btn_open.setEnabled(True)
        self.statusBar().showMessage("Erro na análise.")
        QMessageBox.critical(self, "Erro na análise", message)

    # ------------------------------------------------------------------
    def open_settings(self) -> None:
        dialog = SettingsDialog(self.config, self)
        if dialog.exec() == QDialog.Accepted:
            self.config = dialog.result_config()
            self.view_words.apply_config(self.config)
            self.view_graphs.apply_config(self.config)
            self.view_export.set_config(self.config)
            self._persist_config()
            self._apply_style()
            self._retranslate_ui()
            self.statusBar().showMessage("Configurações atualizadas.")
            if self.result:
                self.statusBar().showMessage(
                    "Configurações atualizadas. Gere o relatório novamente para aplicar."
                )

    def load_template_config(self, data: dict) -> None:
        """Aplica um modelo de análise salvo pelo usuário."""
        try:
            self.config = userdata.config_from_dict(data, AnalysisConfig)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(
                self, "Modelo inválido",
                f"Não foi possível aplicar o modelo:\n{exc}",
            )
            return
        self.view_words.apply_config(self.config)
        self.view_graphs.apply_config(self.config)
        self.view_export.set_config(self.config)
        self._persist_config()
        self.statusBar().showMessage(
            "Modelo aplicado. Gere o relatório novamente para usar a nova "
            "configuração."
        )

    def update_config(self, patch: dict) -> None:
        """Atualiza preferências vindas das abas (nuvem, exclusões)."""
        if not isinstance(patch, dict):
            return
        for key, value in patch.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        self.view_export.set_config(self.config)
        self._persist_config()
        self.statusBar().showMessage(
            "Preferências atualizadas. Gere o relatório novamente para aplicar "
            "em todas as seções."
        )

    def open_assistant(self) -> None:
        """Abre o assistente local opcional (Ollama)."""
        if not self.current_text.strip():
            QMessageBox.information(
                self, "Assistente local",
                "Carregue um documento antes de usar o assistente local.",
            )
            return
        from ui.dialogs.assistant_dialog import AssistantDialog

        dialog = AssistantDialog(
            self.current_text, self.result or {}, self
        )
        dialog.report_generated.connect(self._on_ai_report_generated)
        try:
            dialog.exec()
        finally:
            dialog.deleteLater()

    def _on_ai_report_generated(self, report: dict) -> None:
        """Guarda a resposta do assistente na aba e no relatório final."""
        if not isinstance(report, dict):
            return
        self.ai_reports.append(dict(report))
        self.view_ai_reports.set_reports(self.ai_reports)
        if self.result is None:
            self.result = {}
        # ExportView mantém a mesma referência; mutar o resultado basta para
        # que o texto entre em todos os formatos de exportação.
        self.result["ai_reports"] = self.ai_reports
        index = self.tabs.indexOf(self.view_ai_reports)
        self.tabs.setTabEnabled(index, True)
        self._focus_tab(index)
        self.statusBar().showMessage(
            "Relatório de IA adicionado. Ele será incluído na exportação "
            "do relatório final."
        )

    def _on_ai_reports_changed(self, reports: list) -> None:
        """Sincroniza remoções/limpeza feitas na aba de relatórios de IA."""
        self.ai_reports = [
            dict(report) for report in (reports or [])
            if isinstance(report, dict)
        ]
        if self.result is None:
            self.result = {}
        self.result["ai_reports"] = self.ai_reports
        self.statusBar().showMessage(
            f"{len(self.ai_reports)} relatório(s) de IA no relatório final."
        )

    def open_stoplist(self) -> None:
        language = (self.result or {}).get("language") or "PT-BR"
        dialog = StoplistDialog(language, self)
        dialog.exec()
        if not dialog.changed:
            return
        self.statusBar().showMessage(
            "Stoplist atualizada. Gere o relatório novamente para aplicar."
        )
        if not self.current_text.strip():
            return
        answer = QMessageBox.question(
            self, "Stoplist alterada",
            "A stoplist mudou. Deseja gerar o relatório novamente agora?",
        )
        if answer == QMessageBox.Yes:
            self.run_analysis()

    def open_session(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "Abrir sessão", "", "Sessão Semantorium (*.lexima.json);;JSON (*.json)"
        )
        if not filename:
            return
        try:
            import json
            payload = json.loads(Path(filename).read_text(encoding="utf-8"))
            self.current_text = payload.get("text", "")
            result = payload.get("result", {})
            if not self.current_text or not result:
                raise ValueError("Sessão inválida ou incompleta.")
            self.current_meta = result.get("meta", {})
            self.current_path = self.current_meta.get("path", "") or ""
            # Evita herdar relatórios de IA do documento anterior; a sessão
            # restaura os seus próprios em _on_analysis_done.
            self.ai_reports = []
            self.view_ai_reports.clear()
            self.view_load.info.setText(
                f"Sessão carregada: {Path(filename).name} · "
                f"{len(self.current_text.split()):,} palavras".replace(",", ".")
            )
            preview = self.current_text[:8000]
            self.view_load.preview.setPlainText(preview)
            self.btn_generate.setEnabled(True)
            self._on_analysis_done(result)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Erro ao abrir sessão", str(exc))

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            "Sobre o Semantorium",
            f"<h2>Semantorium {APP_VERSION}</h2>"
            "<p><b>Analisador textual local para Windows.</b> Extração "
            "multi-formato com OCR, resumo automático com controle de tamanho, "
            "palavras-chave, nuvem personalizável, redes, mapa mental, citações "
            "e referências, índice onomástico editável com evidências, "
            "conceitos, concordância, legibilidade, tópicos, agrupamentos, "
            "sentimentos por domínio, argumentos, definições, linha do tempo "
            "com datas numéricas e séculos, grafo de citações, comparação entre "
            "textos e análise de corpus com matriz N×N, agrupamentos e "
            "duplicatas.</p>"
            "<p><b>Recursos de produtividade:</b> modelos de análise e "
            "exportação, preferências persistentes, documentos recentes, "
            "favoritos, histórico de análises e atalhos de teclado.</p>"
            "<p><b>Reconhecimento de nomes:</b> opcional, via spaCy e modelos "
            "locais na pasta <code>models/</code> ou em <code>LEXIMA_MODELS</code>; "
            "sem modelo, o aplicativo usa heurísticas internas.</p>"
            "<p><b>Desenvolvedor:</b> Mateus Filipe de Lima Pelanda "
            "(Umbalab)</p>"
            "<p><b>Linguagens:</b> Python (núcleo e interface), "
            "HTML/CSS/JavaScript (relatórios interativos), Mermaid (mapas "
            "mentais) e PowerShell (compilação).</p>"
            "<p><b>Bibliotecas principais:</b> PySide6/Qt, spaCy, "
            "scikit-learn, NumPy, NetworkX, matplotlib, wordcloud, Pillow, "
            "PyVis, ReportLab, openpyxl, PyMuPDF, python-docx, YAKE e "
            "sumy.</p>"
            "<p><b>Apoio ao desenvolvimento:</b> OpenCode e o modelo "
            "<i>Big Pickle</i> foram utilizados como ferramentas de auxílio "
            "na implementação, revisão e testes.</p>"
            "<p><b>Licença:</b> MIT — uso, distribuição e modificação "
            "permitidos, com manutenção do aviso de copyright.</p>"
            "<p><b>100% offline.</b></p>",
        )

    # ------------------------------------------------------------------
    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and Path(urls[0].toLocalFile()).suffix.lower() in {
                ".txt", ".md", ".markdown", ".pdf", ".docx", ".odt", ".rtf",
            }:
                event.acceptProposedAction()
                return
        event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802
        urls = event.mimeData().urls()
        if not urls:
            return
        filepath = urls[0].toLocalFile()
        if filepath:
            event.acceptProposedAction()
            self.load_file(filepath)

    # ------------------------------------------------------------------
    def closeEvent(self, event) -> None:  # noqa: N802
        self._save_last_tab()
        self._persist_config()
        for worker in (self._analysis_worker, self._load_worker):
            if worker and worker.isRunning():
                worker.terminate()
                worker.wait(1500)
        try:
            ollama_client.stop_server()
        except Exception:  # pragma: no cover - encerramento best effort
            pass
        super().closeEvent(event)
