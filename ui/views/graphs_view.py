#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Aba: Redes, grafos, árvore de palavras, mapa mental e similaridade."""

import re
import tempfile
from collections import Counter
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPushButton, QSpinBox, QTabWidget, QTextBrowser, QVBoxLayout, QWidget,
)

from core import coauthorship, semantic
from core.coocurrence import (
    build_cooccurrence_network, build_tree, export_pyvis_html, network_stats,
)
from core.stopwords import effective_stopwords, normalize
from core.textproc import TextProcessor
from ui.widgets.common import Card, DataTable
from ui.widgets.graph_view import GraphView
from ui.widgets.help_panel import HelpPanel


class GraphsView(QWidget):
    status = Signal(str)
    config_changed = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._result = None
        self._text = ""
        self._excluded = set()
        self._sim_use_embeddings = False
        self._coauthorship = None
        self._coauthor_html = ""
        self._mindmap_data = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        self.help_panel = HelpPanel("graphs")
        layout.addWidget(self.help_panel)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Janela de coocorrência:"))
        self.spin_window = QSpinBox()
        self.spin_window.setRange(2, 12)
        self.spin_window.setValue(5)
        controls.addWidget(self.spin_window)

        controls.addWidget(QLabel("Frequência mínima:"))
        self.spin_freq = QSpinBox()
        self.spin_freq.setRange(1, 50)
        self.spin_freq.setValue(2)
        controls.addWidget(self.spin_freq)

        controls.addWidget(QLabel("Peso mínimo:"))
        self.spin_edge = QSpinBox()
        self.spin_edge.setRange(1, 50)
        self.spin_edge.setValue(2)
        controls.addWidget(self.spin_edge)

        controls.addStretch()

        self.btn_apply = QPushButton("Aplicar")
        self.btn_apply.setEnabled(False)
        controls.addWidget(self.btn_apply)

        self.stats_label = QLabel("—")
        self.stats_label.setStyleSheet("color:#5b6673;")
        controls.addWidget(self.stats_label)
        layout.addLayout(controls)

        exclude_row = QHBoxLayout()
        exclude_row.addWidget(QLabel("Excluir das redes:"))
        self.input_exclude = QLineEdit()
        self.input_exclude.setPlaceholderText(
            "Termos separados por vírgula (ex.: ética, dados)"
        )
        exclude_row.addWidget(self.input_exclude, 1)
        self.btn_exclude = QPushButton("Excluir termos")
        self.btn_exclude.setEnabled(False)
        self.btn_exclude.clicked.connect(self._apply_exclusions)
        exclude_row.addWidget(self.btn_exclude)
        layout.addLayout(exclude_row)

        self.tabs = QTabWidget()

        # Coocorrência
        cooc_widget = QWidget()
        cooc_layout = QVBoxLayout(cooc_widget)
        cooc_layout.setContentsMargins(6, 6, 6, 6)
        self.cooc_help = HelpPanel("graphs_cooccurrence", expanded=False)
        cooc_layout.addWidget(self.cooc_help)
        self.cooc_view = GraphView()
        cooc_layout.addWidget(self.cooc_view, 1)
        self.tabs.addTab(cooc_widget, "🕸️ Coocorrência")

        # Árvore de palavras
        tree_widget = QWidget()
        tree_layout = QVBoxLayout(tree_widget)
        tree_layout.setContentsMargins(6, 6, 6, 6)
        self.tree_help = HelpPanel("graphs_tree", expanded=False)
        tree_layout.addWidget(self.tree_help)
        self.tree_label = QLabel("Selecione um termo após gerar o relatório.")
        self.tree_label.setStyleSheet("color:#5b6673;")
        self.tree_browser = QTextBrowser()
        tree_layout.addWidget(self.tree_label)
        tree_layout.addWidget(self.tree_browser, 1)
        self.tabs.addTab(tree_widget, "🌳 Árvore de palavras")

        # Rede semântica / conceitos relacionados
        semantic_widget = QWidget()
        semantic_layout = QVBoxLayout(semantic_widget)
        semantic_layout.setContentsMargins(6, 6, 6, 6)
        self.semantic_help = HelpPanel("graphs_semantic", expanded=False)
        semantic_layout.addWidget(self.semantic_help)
        self.semantic_browser = QTextBrowser()
        semantic_layout.addWidget(self.semantic_browser, 1)
        self.tabs.addTab(semantic_widget, "🧠 Rede semântica")

        # Similaridade
        sim_widget = QWidget()
        sim_layout = QVBoxLayout(sim_widget)
        sim_layout.setContentsMargins(6, 6, 6, 6)
        self.sim_help = HelpPanel("graphs_similarity", expanded=False)
        sim_layout.addWidget(self.sim_help)
        from core import embeddings as _emb
        sim_ctrl = QHBoxLayout()
        self.use_embeddings = QPushButton("🧠 Usar embeddings locais (sentence-transformers)")
        self.use_embeddings.setCheckable(True)
        if not _emb.is_available():
            self.use_embeddings.setEnabled(False)
            self.use_embeddings.setToolTip("sentence-transformers/torch não instalados")
        self.sim_method_label = QLabel("Método: TF-IDF")
        self.sim_method_label.setStyleSheet("color:#5b6673;")
        sim_ctrl.addWidget(self.use_embeddings)
        sim_ctrl.addWidget(self.sim_method_label)
        sim_ctrl.addStretch()
        sim_layout.addLayout(sim_ctrl)
        self.sim_table = DataTable(["Numeração do parágrafo", "Trecho", "Similaridade média"])
        sim_layout.addWidget(self.sim_table)
        self.tabs.addTab(sim_widget, "📐 Similaridade")
        self.use_embeddings.toggled.connect(self._on_similarity_toggle)

        # Mapa mental
        mind_widget = QWidget()
        mind_layout = QVBoxLayout(mind_widget)
        mind_layout.setContentsMargins(6, 6, 6, 6)
        self.mind_help = HelpPanel("graphs_mindmap", expanded=False)
        mind_layout.addWidget(self.mind_help)
        mind_bar = QHBoxLayout()
        self.mind_label = QLabel("Mapa mental ainda não gerado.")
        self.mind_label.setStyleSheet("color:#5b6673;")
        mind_bar.addWidget(self.mind_label, 1)
        for kind, label in (
            ("svg", "SVG"), ("html", "HTML"),
            ("mermaid", "Mermaid"), ("markdown", "Markdown"),
        ):
            button = QPushButton(f"💾 {label}")
            button.setEnabled(False)
            button.clicked.connect(
                lambda _=False, k=kind: self._save_mindmap(k)
            )
            mind_bar.addWidget(button)
            setattr(self, f"button_mind_{kind}", button)
        mind_layout.addLayout(mind_bar)
        self.mind_view = GraphView()
        mind_layout.addWidget(self.mind_view, 1)
        self.tabs.addTab(mind_widget, "🗺️ Mapa mental")

        # Grafo de citações
        graph_widget = QWidget()
        graph_layout = QVBoxLayout(graph_widget)
        graph_layout.setContentsMargins(6, 6, 6, 6)
        self.citation_help = HelpPanel("graphs_citations", expanded=False)
        graph_layout.addWidget(self.citation_help)
        graph_bar = QHBoxLayout()
        self.citation_label = QLabel("Grafo de citações ainda não gerado.")
        self.citation_label.setStyleSheet("color:#5b6673;")
        graph_bar.addWidget(self.citation_label, 1)
        self.button_save_citation = QPushButton("💾 Salvar HTML")
        self.button_save_citation.setEnabled(False)
        self.button_save_citation.clicked.connect(self._save_citation_graph)
        graph_bar.addWidget(self.button_save_citation)
        graph_layout.addLayout(graph_bar)
        self.citation_view = GraphView()
        graph_layout.addWidget(self.citation_view, 1)
        self.tabs.addTab(graph_widget, "🔗 Grafo de citações")

        coauthor_widget = QWidget()
        coauthor_layout = QVBoxLayout(coauthor_widget)
        coauthor_layout.setContentsMargins(6, 6, 6, 6)
        self.coauthor_help = HelpPanel("graphs_coauthorship", expanded=False)
        coauthor_layout.addWidget(self.coauthor_help)
        coauthor_bar = QHBoxLayout()
        self.coauthor_label = QLabel("Rede de coautoria ainda não gerada.")
        self.coauthor_label.setStyleSheet("color:#5b6673;")
        coauthor_bar.addWidget(self.coauthor_label, 1)
        self.button_save_coauthor = QPushButton("💾 Exportar HTML")
        self.button_save_coauthor.setEnabled(False)
        self.button_save_coauthor.clicked.connect(self._save_coauthorship)
        coauthor_bar.addWidget(self.button_save_coauthor)
        coauthor_layout.addLayout(coauthor_bar)
        self.coauthor_view = GraphView()
        coauthor_layout.addWidget(self.coauthor_view, 1)
        self.tabs.addTab(coauthor_widget, "👥 Coautoria")

        layout.addWidget(self.tabs, 1)

        self.btn_apply.clicked.connect(self._rebuild_graph)

    # ------------------------------------------------------------------
    def clear(self) -> None:
        self._result = None
        self._text = ""
        self._excluded = set()
        self._sim_use_embeddings = False
        self.btn_apply.setEnabled(False)
        self.btn_exclude.setEnabled(False)
        self.cooc_view.show_status("Gere o relatório para visualizar a rede.")
        self.tree_browser.clear()
        self.semantic_browser.clear()
        self.sim_table.set_rows([])
        self.stats_label.setText("—")
        self.mind_view.show_status("Gere o relatório para visualizar o mapa mental.")
        self.mind_label.setText("Mapa mental ainda não gerado.")
        self.citation_view.show_status("Gere o relatório para visualizar o grafo.")
        self.citation_label.setText("Grafo de citações ainda não gerado.")
        self.coauthor_view.show_status(
            "Gere o relatório para visualizar a rede de coautoria."
        )
        self.coauthor_label.setText("Rede de coautoria ainda não gerada.")
        self.button_save_coauthor.setEnabled(False)
        self._coauthorship = None
        for kind in ("svg", "html", "mermaid", "markdown"):
            getattr(self, f"button_mind_{kind}").setEnabled(False)
        self.button_save_citation.setEnabled(False)

    def apply_config(self, config) -> None:
        if not config:
            return
        terms = getattr(config, "exclude_terms", []) or []
        self.input_exclude.setText(", ".join(terms))
        self._excluded = {normalize(t) for t in terms if t}

    def update_results(self, result: dict, text: str = "") -> None:
        self._result = result
        self._text = text
        self.btn_apply.setEnabled(bool(text))
        self.btn_exclude.setEnabled(bool(text))
        if not self.input_exclude.text():
            self._excluded = {
                normalize(t) for t in (result.get("stoplist", {}) or {}).get(
                    "excluded", []
                ) if t
            }

        graphs = result.get("graphs", {})
        cooc = graphs.get("cooccurrence") or {}
        stats = cooc.get("stats", {})
        self.stats_label.setText(
            f"{stats.get('nodes', 0)} nós · {stats.get('edges', 0)} conexões · "
            f"densidade {stats.get('density', 0)}"
        )

        if cooc.get("html"):
            self.cooc_view.load_html_file(cooc["html"])
            if not getattr(self.cooc_view, "browser", None):
                self.cooc_view.show_network_fallback(
                    stats, cooc.get("edges_sample", [])
                )
        else:
            self.cooc_view.show_status(
                "Rede de coocorrência não gerada (texto curto ou bibliotecas ausentes)."
            )

        self._render_tree(graphs.get("tree"))
        self._render_semantic(graphs.get("semantic"), result.get("concepts", []))
        sim = result.get("similarity", {}) or {}
        if isinstance(sim, dict):
            sim = dict(sim)
            sim["method"] = sim.get("method") or ("embeddings" if getattr(self, '_sim_use_embeddings', False) else "tfidf")
        self._render_similarity(sim)
        self._render_mindmap(result.get("mindmap") or {})
        self._render_citation_graph(result.get("citation_graph") or {})
        self._render_coauthorship(result.get("references") or {})

    # ------------------------------------------------------------------
    def _parse_exclusions(self) -> set:
        raw = self.input_exclude.text()
        parts = [
            normalize(part) for part in raw.replace(";", ",").split(",")
        ]
        return {part for part in parts if part}

    def _apply_exclusions(self) -> None:
        self._excluded = self._parse_exclusions()
        self.config_changed.emit({"exclude_terms": sorted(self._excluded)})
        self._rebuild_graph()

    def _rebuild_graph(self) -> None:
        """Reconstrói a rede de coocorrência com os parâmetros atuais da tela."""
        if not self._text:
            return
        try:
            lang = (self._result or {}).get("language", "PT-BR")
            stops = effective_stopwords(lang)
            processor = TextProcessor(lang, stop_words=stops)
            processed = processor.process(self._text)
            tokens = [
                token for token in processed.content_tokens()
                if normalize(token) not in self._excluded
            ]

            graph = build_cooccurrence_network(
                tokens,
                window_size=self.spin_window.value(),
                min_freq=self.spin_freq.value(),
                min_edge_weight=self.spin_edge.value(),
            )
            stats = network_stats(graph)
            self.stats_label.setText(
                f"{stats.get('nodes', 0)} nós · {stats.get('edges', 0)} conexões · "
                f"densidade {stats.get('density', 0)}"
            )

            out = Path(tempfile.mkdtemp(prefix="lexima_graph_")) / "cooccurrence.html"
            export_pyvis_html(graph, str(out))
            self.cooc_view.load_html_file(str(out))

            if tokens:
                root = Counter(tokens).most_common(1)[0][0]
                self._render_tree(build_tree(tokens, root))

            semantic_data = semantic.semantic_network(
                (self._result or {}).get("concepts", []),
                stop_words=stops,
                exclude=self._excluded,
            )
            if self._result is not None:
                self._result.setdefault("graphs", {})["semantic"] = semantic_data
            self._render_semantic(
                semantic_data, (self._result or {}).get("concepts", [])
            )
            self.status.emit(
                "Redes reconstruídas com os termos excluídos."
            )
        except Exception as exc:  # noqa: BLE001
            self.cooc_view.show_status(f"Erro ao gerar a rede: {exc}")

    # ------------------------------------------------------------------
    def _render_tree(self, tree) -> None:
        self.tree_browser.clear()
        if not tree:
            self.tree_label.setText("Árvore não disponível.")
            return
        self.tree_label.setText(
            f"Árvore a partir de “{tree.get('name','')}” "
            f"({tree.get('count',0)} ocorrências)"
        )

        lines = [f"🌳 <b>{tree['name']}</b> ({tree['count']}×)"]

        def walk(node, prefix):
            children = node.get("children", [])
            for index, child in enumerate(children):
                last = index == len(children) - 1
                branch = "└── " if last else "├── "
                lines.append(
                    f"{prefix}{branch}<b>{child['name']}</b> ({child['count']}×)"
                )
                walk(child, prefix + ("    " if last else "│   "))

        walk(tree, "")
        self.tree_browser.setHtml(
            "<pre style='font-family:Consolas,monospace; font-size:12px;'>"
            + "<br>".join(lines) + "</pre>"
        )

    def _render_semantic(self, semantic_data, concepts) -> None:
        if not concepts:
            self.semantic_browser.setPlainText("Sem conceitos suficientes.")
            return
        rows = []
        for item in concepts[:30]:
            if normalize(item.get("term", "")) in self._excluded:
                continue
            related = [
                rel for rel in (item.get("related") or [])
                if normalize(rel) not in self._excluded
            ]
            related_text = ", ".join(related) or "—"
            rows.append(
                f"<tr><td><b>{item['term']}</b></td><td>{item['count']}</td>"
                f"<td style='color:#5b6673'>{related_text}</td></tr>"
            )
        self.semantic_browser.setHtml(
            "<h3>Conceitos e relações</h3>"
            "<p style='color:#5b6673;font-size:12px'>Termos excluídos: "
            f"{', '.join(sorted(self._excluded)) or 'nenhum'}.</p>"
            "<table width='100%' cellspacing='0' cellpadding='4' "
            "style='font-size:12px;border-collapse:collapse'>"
            "<tr style='background:#f6f8fb'><th align='left'>Conceito</th>"
            "<th align='left'>Ocorr.</th><th align='left'>Relacionados</th></tr>"
            + "".join(rows) + "</table>"
        )

    def _on_similarity_toggle(self, checked):
        self._sim_use_embeddings = bool(checked)
        if hasattr(self, 'sim_method_label'):
            self.sim_method_label.setText("Método: Embeddings" if checked else "Método: TF-IDF")

    def _render_similarity(self, similarity: dict) -> None:
        matrix = similarity.get("matrix") or []
        labels = similarity.get("labels") or []
        # ``semantic.similarity_matrix`` devolve os textos em ``docs``. Versões
        # anteriores liam ``paragraphs`` (inexistente), então a coluna Trecho
        # acabava mostrando apenas o número do parágrafo.
        paragraphs = (
            similarity.get("paragraphs")
            or similarity.get("docs")
            or similarity.get("texts")
            or []
        )
        method = similarity.get("method") or ("embeddings" if self._sim_use_embeddings else "tfidf")
        if hasattr(self, 'sim_method_label'):
            if method == "embeddings":
                self.sim_method_label.setText("Método: Embeddings")
            elif method == "embeddings_unavailable":
                self.sim_method_label.setText("Método: Embeddings (indisponível) -> TF-IDF")
            else:
                self.sim_method_label.setText("Método: TF-IDF")
        if not matrix:
            self.sim_table.set_rows([])
            return
        rows = []
        for index, label in enumerate(labels):
            values = [v for j, v in enumerate(matrix[index]) if j != index]
            avg = sum(values) / len(values) if values else 0
            para = paragraphs[index] if index < len(paragraphs) else ""
            snippet = " ".join(str(para or label or "").split())
            match = re.match(r"§\s*(\d+)", str(label or ""))
            num = int(match.group(1)) if match else index + 1
            rows.append((num, snippet or label, round(avg, 3)))
        rows.sort(key=lambda r: -r[2])
        self.sim_table.set_rows(rows)
        # O texto completo do parágrafo fica no tooltip e pode ser copiado;
        # a coluna é limitada para não alargar demais a tabela. Como a tabela
        # é reordenada ao ser preenchida, localizamos cada linha pelo número.
        for num, snippet, _ in rows:
            for row_index in range(self.sim_table.rowCount()):
                number_item = self.sim_table.item(row_index, 0)
                if number_item is None or number_item.text() != str(num):
                    continue
                item = self.sim_table.item(row_index, 1)
                if item is not None:
                    item.setToolTip(snippet)
                break
        try:
            header = self.sim_table.horizontalHeader()
            header.setSectionResizeMode(1, QHeaderView.Interactive)
            self.sim_table.setColumnWidth(1, 520)
        except Exception:
            pass

    # ------------------------------------------------------------------
    def _render_mindmap(self, mindmap: dict) -> None:
        mindmap = mindmap or {}
        self._mindmap_data = dict(mindmap)
        branch_count = len(self._mindmap_data.get("branches") or [])
        loaded = False

        # ``build_and_render`` devolve o conteúdo em ``html`` e os caminhos em
        # ``paths``. Versões anteriores tratavam o conteúdo como caminho de
        # arquivo e exibiam "Grafo não disponível".
        paths = self._mindmap_data.get("paths") or {}
        html_value = self._mindmap_data.get("html")
        html_file = None
        if isinstance(paths, dict) and paths.get("html"):
            html_file = str(paths["html"])
        elif isinstance(html_value, str) and html_value.lstrip()[:1] != "<":
            html_file = html_value

        if html_file and Path(html_file).is_file():
            try:
                self.mind_view.load_html_file(html_file)
                loaded = True
            except Exception:
                loaded = False

        if not loaded:
            content = (
                self._mindmap_data.get("html_string")
                or self._mindmap_data.get("html_content")
            )
            if not content and isinstance(html_value, str) and "<" in html_value:
                content = html_value
            if content:
                try:
                    self.mind_view.load_html_string(str(content))
                    loaded = True
                except Exception:
                    loaded = False

        if not loaded and self._mindmap_data.get("svg"):
            try:
                self.mind_view.load_html_string(
                    str(self._mindmap_data["svg"])
                )
                loaded = True
            except Exception:
                loaded = False

        if loaded:
            self.mind_label.setText(
                f"{branch_count} ramos principais · visualize, navegue e "
                "exporte nos formatos ao lado."
            )
        else:
            self.mind_view.show_status(
                "Mapa mental não disponível para este documento."
            )
            self.mind_label.setText("Mapa mental não gerado.")
        for kind in ("svg", "html", "mermaid", "markdown", "png", "pdf"):
            try:
                getattr(self, f"button_mind_{kind}").setEnabled(bool(self._mindmap_data.get(kind) or kind in ("png", "pdf")))
            except Exception:
                pass
        try:
            self.button_mind_edit.setEnabled(bool(self._mindmap_data.get("branches")))
        except Exception:
            pass

    def _render_citation_graph(self, graph: dict) -> None:
        summary = graph.get("summary") or {}
        if graph.get("html"):
            self.citation_view.load_html_file(graph["html"])
            self.button_save_citation.setEnabled(True)
            self.citation_label.setText(
                f"{summary.get('references', 0)} referências · "
                f"{summary.get('citations', 0)} citações · "
                f"cobertura {summary.get('coverage', 0)} · "
                f"{summary.get('missing', 0)} sem referência"
            )
        else:
            self.citation_view.show_status(
                "Sem referências ou citações suficientes para montar o grafo."
            )
            self.citation_label.setText(
                "Grafo de citações não gerado (referências/citações ausentes)."
            )
            self.button_save_citation.setEnabled(False)

    def _render_coauthorship(self, references: dict) -> None:
        data = coauthorship.build_coauthorship(references)
        self._coauthorship = data
        stats = data.get("stats") or {}
        self.coauthor_label.setText(
            f"{stats.get('authors', 0)} autores · "
            f"{stats.get('collaborations', 0)} colaborações · "
            f"densidade {stats.get('density', 0)} · "
            f"{stats.get('isolated', 0)} sem parceria"
        )
        if not data.get("nodes"):
            self.coauthor_view.show_status(
                "Sem autores reconhecíveis nas referências para montar a rede."
            )
            self.button_save_coauthor.setEnabled(False)
            return
        self._coauthor_html = coauthorship.render_html(data)
        output = Path(tempfile.mkdtemp(prefix="lexima_coauthor_")) / \
            "coauthorship.html"
        output.write_text(self._coauthor_html, encoding="utf-8")
        self.coauthor_view.load_html_file(str(output))
        self.button_save_coauthor.setEnabled(True)

    def _save_coauthorship(self) -> None:
        data = getattr(self, "_coauthorship", None)
        if not data:
            return
        filename, _ = QFileDialog.getSaveFileName(
            self, "Exportar rede de coautoria",
            "rede_coautoria.html", "HTML (*.html)",
        )
        if not filename:
            return
        if not filename.lower().endswith(".html"):
            filename += ".html"
        try:
            Path(filename).write_text(
                coauthorship.render_html(data), encoding="utf-8"
            )
        except Exception as exc:  # noqa: BLE001
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Erro ao exportar", str(exc))
            return
        self.status.emit(f"Rede de coautoria exportada: {Path(filename).name}")

    def _save_mindmap(self, kind: str) -> None:
        mindmap = (self._result or {}).get("mindmap") or {}
        content = mindmap.get(kind)
        if not content:
            return
        suffixes = {
            "svg": (".svg", "SVG (*.svg)"),
            "html": (".html", "HTML (*.html)"),
            "mermaid": (".mmd", "Mermaid (*.mmd)"),
            "markdown": (".md", "Markdown (*.md)"),
        }
        suffix, filter_text = suffixes[kind]
        filename, _ = QFileDialog.getSaveFileName(
            self, "Salvar mapa mental", f"mapa_mental{suffix}", filter_text
        )
        if not filename:
            return
        if not Path(filename).suffix:
            filename += suffix
        try:
            Path(filename).write_text(content, encoding="utf-8")
        except OSError as exc:
            self.status.emit(f"Erro ao salvar: {exc}")
            return
        self.status.emit(f"Mapa mental salvo em {filename}")

    def _save_citation_graph(self) -> None:
        graph = (self._result or {}).get("citation_graph") or {}
        html_text = graph.get("html")
        if not html_text or not Path(html_text).exists():
            return
        filename, _ = QFileDialog.getSaveFileName(
            self, "Salvar grafo de citações", "grafo_citacoes.html",
            "HTML (*.html)",
        )
        if not filename:
            return
        if not Path(filename).suffix:
            filename += ".html"
        try:
            Path(filename).write_bytes(Path(html_text).read_bytes())
        except OSError as exc:
            self.status.emit(f"Erro ao salvar: {exc}")
            return
        self.status.emit(f"Grafo salvo em {filename}")


    def _export_mindmap_png(self):
        try:
            from PySide6.QtWidgets import QFileDialog, QMessageBox
            from core import export_mindmap
            if not getattr(self, '_mindmap_data', None):
                return
            filename, _ = QFileDialog.getSaveFileName(self, 'Exportar mapa mental PNG', '', 'PNG (*.png)')
            if filename:
                res = export_mindmap.export_mindmap_png(self._mindmap_data, filename)
                if res:
                    QMessageBox.information(self, 'Exportado', 'Mapa mental exportado em PNG.')
                else:
                    QMessageBox.warning(self, 'Erro', 'Nao foi possivel exportar PNG.')
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, 'Erro', str(e))

    def _export_mindmap_pdf(self):
        try:
            from PySide6.QtWidgets import QFileDialog, QMessageBox
            from core import export_mindmap
            if not getattr(self, '_mindmap_data', None):
                return
            filename, _ = QFileDialog.getSaveFileName(self, 'Exportar mapa mental PDF', '', 'PDF (*.pdf)')
            if filename:
                res = export_mindmap.export_mindmap_pdf(self._mindmap_data, filename)
                if res:
                    QMessageBox.information(self, 'Exportado', 'Mapa mental exportado em PDF.')
                else:
                    QMessageBox.warning(self, 'Erro', 'Nao foi possivel exportar PDF.')
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, 'Erro', str(e))

    def _edit_mindmap(self):
        try:
            from PySide6.QtWidgets import QDialog, QVBoxLayout, QDialogButtonBox, QMessageBox
            from ui.views.mindmap_editor import MindmapEditorView
            if not getattr(self, '_mindmap_data', None):
                return
            dlg = QDialog(self)
            dlg.setWindowTitle('Editor visual do mapa mental')
            dlg.resize(800, 500)
            layout = QVBoxLayout(dlg)
            editor = MindmapEditorView(dlg)
            editor.load_mindmap(self._mindmap_data)
            layout.addWidget(editor)
            buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            buttons.accepted.connect(dlg.accept)
            buttons.rejected.connect(dlg.reject)
            layout.addWidget(buttons)
            if dlg.exec():
                new_data = editor.get_mindmap()
                # O editor altera apenas os ramos; os formatos exportáveis
                # precisam ser regenerados para refletir a edição.
                try:
                    from core import mindmap as mindmap_core
                    new_data["svg"] = mindmap_core.to_svg(new_data)
                    new_data["html"] = mindmap_core.to_html(new_data)
                    new_data["mermaid"] = mindmap_core.to_mermaid(new_data)
                    new_data["markdown"] = mindmap_core.to_markdown(new_data)
                except Exception:
                    pass
                new_data.pop("paths", None)
                self._mindmap_data = new_data
                if hasattr(self, '_result') and isinstance(self._result, dict):
                    self._result['mindmap'] = new_data
                    if isinstance(self._result.get('graphs'), dict):
                        self._result['graphs']['mindmap'] = new_data
                self._render_mindmap(self._mindmap_data)
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, 'Erro', str(e))
