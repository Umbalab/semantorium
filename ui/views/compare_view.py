#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Aba: Comparação entre o documento atual e outro texto."""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QSplitter,
    QTabWidget, QTextBrowser, QVBoxLayout, QWidget,
)

from core.compare import compare_texts
from reports import exporters
from ui.widgets.common import Card, DataTable
from ui.widgets.help_panel import HelpPanel
from ui.worker import LoadWorker


class CompareView(QWidget):
    status = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._text_a = ""
        self._text_b = ""
        self._label_a = "Texto A"
        self._label_b = "Texto B"
        self._lang = None
        self._result = None
        self._worker = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        self.help_panel = HelpPanel("compare")
        layout.addWidget(self.help_panel)

        intro = QLabel(
            "Compare o documento carregado com um segundo arquivo: volume, "
            "riqueza lexical, legibilidade, vocabulário compartilhado, "
            "palavras-chave e trechos equivalentes. Tudo offline."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color:#5b6673;")
        layout.addWidget(intro)

        controls = QHBoxLayout()
        self.button_compare = QPushButton("⚖️  Comparar textos")
        self.button_compare.setObjectName("Primary")
        self.button_compare.setEnabled(False)
        self.button_compare.clicked.connect(self._run_compare)
        controls.addWidget(self.button_compare)

        self.button_export = QPushButton("💾  Salvar relatório HTML")
        self.button_export.setEnabled(False)
        self.button_export.clicked.connect(self._save_report)
        controls.addWidget(self.button_export)
        controls.addStretch()
        self.verdict = QLabel("Carregue os dois textos para comparar.")
        self.verdict.setStyleSheet("color:#5b6673;")
        controls.addWidget(self.verdict)
        layout.addLayout(controls)

        splitter = QSplitter(Qt.Horizontal)

        card_a = Card("Texto A · documento atual")
        self.preview_a = QTextBrowser()
        card_a.add(self.preview_a)
        splitter.addWidget(card_a)

        card_b = Card("Texto B · segundo arquivo")
        bar_b = QHBoxLayout()
        self.button_b = QPushButton("📂  Escolher arquivo…")
        self.button_b.clicked.connect(self._pick_b)
        bar_b.addWidget(self.button_b)
        self.label_b = QLabel("Nenhum arquivo selecionado.")
        self.label_b.setStyleSheet("color:#5b6673;")
        bar_b.addWidget(self.label_b, 1)
        card_b.add_layout(bar_b)
        self.preview_b = QTextBrowser()
        card_b.add(self.preview_b)
        splitter.addWidget(card_b)

        splitter.setSizes([500, 500])
        layout.addWidget(splitter, 1)

        self.tabs = QTabWidget()
        summary_widget = QWidget()
        summary_layout = QVBoxLayout(summary_widget)
        summary_layout.setContentsMargins(6, 6, 6, 6)
        self.summary_help = HelpPanel("compare_summary", expanded=False)
        summary_layout.addWidget(self.summary_help)
        self.summary_browser = QTextBrowser()
        summary_layout.addWidget(self.summary_browser, 1)
        self.tabs.addTab(summary_widget, "📊 Resumo")

        metric_widget = QWidget()
        metric_layout = QVBoxLayout(metric_widget)
        metric_layout.setContentsMargins(6, 6, 6, 6)
        self.metric_help = HelpPanel("compare_metrics", expanded=False)
        metric_layout.addWidget(self.metric_help)
        self.metric_table = DataTable(["Métrica", "Texto A", "Texto B", "Δ", "Δ%"])
        metric_layout.addWidget(self.metric_table)
        self.tabs.addTab(metric_widget, "📏 Métricas")

        vocab_widget = QWidget()
        vocab_layout = QVBoxLayout(vocab_widget)
        vocab_layout.setContentsMargins(6, 6, 6, 6)
        self.vocab_help = HelpPanel("compare_vocabulary", expanded=False)
        vocab_layout.addWidget(self.vocab_help)
        self.vocab_table = DataTable(["Termo", "Texto A", "Texto B"])
        vocab_layout.addWidget(self.vocab_table)
        self.tabs.addTab(vocab_widget, "🧠 Vocabulário")

        sent_widget = QWidget()
        sent_layout = QVBoxLayout(sent_widget)
        sent_layout.setContentsMargins(6, 6, 6, 6)
        self.sentence_help = HelpPanel("compare_sentences", expanded=False)
        sent_layout.addWidget(self.sentence_help)
        self.sentence_table = DataTable(
            ["Similaridade", "Trecho no texto A", "Trecho no texto B"]
        )
        sent_layout.addWidget(self.sentence_table)
        self.tabs.addTab(sent_widget, "🔗 Correspondências")

        layout.addWidget(self.tabs, 1)

    # ------------------------------------------------------------------
    def clear(self) -> None:
        self._text_a = ""
        self._text_b = ""
        self._result = None
        self.preview_a.clear()
        self.preview_b.clear()
        self.label_b.setText("Nenhum arquivo selecionado.")
        self.verdict.setText("Carregue os dois textos para comparar.")
        self.button_compare.setEnabled(False)
        self.button_export.setEnabled(False)
        self.summary_browser.clear()
        self.metric_table.set_rows([])
        self.vocab_table.set_rows([])
        self.sentence_table.set_rows([])

    def set_primary_text(self, text: str, label: str = "Texto A",
                         lang: str = None) -> None:
        self._text_a = text or ""
        self._label_a = label or "Texto A"
        self._lang = lang
        self.preview_a.setPlainText(self._text_a[:6000])
        self._update_ready()

    def _update_ready(self) -> None:
        self.button_compare.setEnabled(
            bool(self._text_a.strip() and self._text_b.strip())
        )

    # ------------------------------------------------------------------
    def _pick_b(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "Escolher o segundo texto", "",
            "Documentos (*.txt *.md *.markdown *.pdf *.docx *.odt *.rtf);;"
            "Todos os arquivos (*.*)",
        )
        if not filename:
            return
        self.label_b.setText(f"Carregando {Path(filename).name}…")
        self.button_b.setEnabled(False)
        self._worker = LoadWorker(filename)
        self._worker.finished_ok.connect(self._on_b_loaded)
        self._worker.failed.connect(self._on_b_failed)
        self._worker.start()

    def _on_b_loaded(self, result: dict) -> None:
        self.button_b.setEnabled(True)
        text = result.get("text", "")
        if not text.strip():
            self.label_b.setText("Nenhum texto extraído do arquivo.")
            return
        self._text_b = text
        self._label_b = Path(
            result.get("meta", {}).get("filename", "Texto B")
        ).stem
        self.label_b.setText(
            f"{self._label_b} · {len(text.split()):,} palavras".replace(",", ".")
        )
        self.preview_b.setPlainText(text[:6000])
        self._update_ready()

    def _on_b_failed(self, message: str) -> None:
        self.button_b.setEnabled(True)
        self.label_b.setText("Falha ao carregar o segundo arquivo.")
        QMessageBox.critical(self, "Erro ao carregar", message)

    # ------------------------------------------------------------------
    def _run_compare(self) -> None:
        if not (self._text_a.strip() and self._text_b.strip()):
            return
        try:
            self._result = compare_texts(
                self._text_a, self._text_b,
                label_a=self._label_a, label_b=self._label_b,
                lang=self._lang,
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Erro na comparação", str(exc))
            return
        self._render(self._result)
        self.button_export.setEnabled(True)
        self.status.emit("Comparação concluída.")

    def _render(self, comparison: dict) -> None:
        verdict = comparison.get("verdict") or {}
        self.verdict.setText(
            f"{verdict.get('label', '—')} · similaridade "
            f"{verdict.get('score', 0)}"
        )
        self.summary_browser.setHtml(
            f"<h2>{verdict.get('label', 'Comparação')}</h2>"
            f"<p>{verdict.get('explanation', '')}</p>"
            "<h3>Volumes</h3>"
            + self._volume_html(comparison)
        )

        self.metric_table.set_rows([
            (
                item.get("metric", ""),
                item.get("a", ""),
                item.get("b", ""),
                item.get("delta", ""),
                f"{item.get('delta_pct', '')}%"
                if item.get("delta_pct") not in (None, "") else "",
            )
            for item in (comparison.get("metrics") or [])
        ])

        vocabulary = comparison.get("vocabulary") or {}
        rows = []
        for item in (vocabulary.get("shared") or [])[:60]:
            rows.append((item.get("term", ""), item.get("a", 0), item.get("b", 0)))
        for item in (vocabulary.get("only_a") or [])[:40]:
            if isinstance(item, dict):
                rows.append((item.get("term", ""), item.get("count", ""), "—"))
            else:
                rows.append((item, "", "—"))
        for item in (vocabulary.get("only_b") or [])[:40]:
            if isinstance(item, dict):
                rows.append((item.get("term", ""), "—", item.get("count", "")))
            else:
                rows.append((item, "—", ""))
        self.vocab_table.set_rows(rows)

        sentences = comparison.get("sentences") or {}
        self.sentence_table.set_rows([
            (
                pair.get("similarity", 0),
                pair.get("sentence_a", ""),
                pair.get("sentence_b", ""),
            )
            for pair in (sentences.get("pairs") or [])[:200]
        ])

    def _volume_html(self, comparison: dict) -> str:
        stats = comparison.get("stats") or {}
        a = stats.get("a") or {}
        b = stats.get("b") or {}
        labels = [
            ("Palavras", "words"), ("Sentenças", "sentences"),
            ("Parágrafos", "paragraphs"), ("Palavras únicas", "unique_words"),
        ]
        rows = "".join(
            f"<tr><td>{label}</td><td align='right'>{a.get(key, 0)}</td>"
            f"<td align='right'>{b.get(key, 0)}</td></tr>"
            for label, key in labels
        )
        return (
            "<table width='100%' cellpadding='5' "
            "style='border-collapse:collapse'>"
            "<tr style='background:#f6f8fb'><th align='left'>Métrica</th>"
            f"<th align='right'>{self._label_a}</th>"
            f"<th align='right'>{self._label_b}</th></tr>{rows}</table>"
        )

    def _save_report(self) -> None:
        if not self._result:
            return
        filename, _ = QFileDialog.getSaveFileName(
            self, "Salvar comparação", "comparacao_lexima.html",
            "HTML (*.html)",
        )
        if not filename:
            return
        if not Path(filename).suffix:
            filename += ".html"
        try:
            exporters.export_compare_html(
                self._result, filename,
                title=f"Comparação · {self._label_a} × {self._label_b}",
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Erro ao salvar", str(exc))
            return
        self.status.emit(f"Comparação salva em {filename}")
