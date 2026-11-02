#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Aba: relatórios gerados pelo assistente local (Ollama)."""

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QTextBrowser, QVBoxLayout, QWidget,
)

from ui.widgets.help_panel import HelpPanel


def _clean(value) -> str:
    return " ".join(str(value or "").split())


def _report_title(report: dict) -> str:
    """Rótulo curto exibido na lista de relatórios."""
    created = str(report.get("created") or "").replace("T", " ")[:16]
    task = _clean(report.get("task_label") or report.get("task") or "Relatório")
    model = _clean(report.get("model"))
    parts = [part for part in (created, task, model) if part]
    return " · ".join(parts) or "Relatório de IA"


class AiReportsView(QWidget):
    """Lista os textos produzidos pelo assistente local e permite exportá-los."""

    reports_changed = Signal(list)
    status = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._reports = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        self.help_panel = HelpPanel("ai_reports")
        layout.addWidget(self.help_panel)

        title = QLabel("<b>Relatórios gerados por modelo de IA</b>")
        layout.addWidget(title)

        hint = QLabel(
            "Textos produzidos pelo assistente local (Ollama). Eles são "
            "incluídos automaticamente no relatório final exportado. Revise "
            "o conteúdo antes de usar: a resposta é gerada por um modelo e "
            "pode conter imprecisões."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#5b6673; font-size:11px;")
        layout.addWidget(hint)

        picker = QHBoxLayout()
        picker.addWidget(QLabel("Relatório:"))
        self.combo_reports = QComboBox()
        self.combo_reports.setMinimumWidth(320)
        self.combo_reports.currentIndexChanged.connect(self._show_current)
        picker.addWidget(self.combo_reports, 1)
        layout.addLayout(picker)

        self.meta_label = QLabel("Nenhum relatório gerado ainda.")
        self.meta_label.setWordWrap(True)
        self.meta_label.setStyleSheet("color:#5b6673;")
        layout.addWidget(self.meta_label)

        self.preview = QTextBrowser()
        self.preview.setOpenExternalLinks(True)
        self.preview.setPlaceholderText(
            "Use o Assistente local (menu Análise) para gerar um relatório. "
            "O texto aparecerá aqui e será incluído na exportação."
        )
        layout.addWidget(self.preview, 1)

        buttons = QHBoxLayout()
        self.btn_copy = QPushButton("Copiar")
        self.btn_copy.clicked.connect(self._copy)
        buttons.addWidget(self.btn_copy)
        self.btn_save = QPushButton("Salvar…")
        self.btn_save.clicked.connect(self._save)
        buttons.addWidget(self.btn_save)
        self.btn_remove = QPushButton("Remover")
        self.btn_remove.clicked.connect(self._remove)
        buttons.addWidget(self.btn_remove)
        self.btn_clear = QPushButton("Limpar tudo")
        self.btn_clear.clicked.connect(self._clear_all)
        buttons.addWidget(self.btn_clear)
        buttons.addStretch()
        layout.addLayout(buttons)

        self._refresh()

    # ------------------------------------------------------------------
    def reports(self) -> list:
        return [dict(report) for report in self._reports]

    def set_reports(self, reports) -> None:
        self._reports = [
            dict(report) for report in (reports or [])
            if isinstance(report, dict) and str(report.get("text") or "").strip()
        ]
        self._refresh()

    def add_report(self, report: dict, emit: bool = True) -> None:
        if not isinstance(report, dict):
            return
        if not str(report.get("text") or "").strip():
            return
        self._reports.append(dict(report))
        self._refresh(select=len(self._reports) - 1)
        if emit:
            self.reports_changed.emit(self.reports())

    def clear(self, emit: bool = False) -> None:
        self._reports = []
        self._refresh()
        if emit:
            self.reports_changed.emit([])

    # ------------------------------------------------------------------
    def _refresh(self, select: int = None) -> None:
        current = select
        if current is None:
            current = self.combo_reports.currentIndex()
        self.combo_reports.blockSignals(True)
        self.combo_reports.clear()
        for report in self._reports:
            self.combo_reports.addItem(_report_title(report))
        if self._reports:
            self.combo_reports.setCurrentIndex(
                max(0, min(int(current), len(self._reports) - 1))
            )
        self.combo_reports.blockSignals(False)
        self.combo_reports.setEnabled(bool(self._reports))
        self._show_current()

    def _current_report(self) -> dict:
        index = self.combo_reports.currentIndex()
        if 0 <= index < len(self._reports):
            return self._reports[index]
        return {}

    def _show_current(self, *_args) -> None:
        report = self._current_report()
        text = str(report.get("text") or "").strip()
        has_report = bool(text)
        for button in (self.btn_copy, self.btn_save, self.btn_remove):
            button.setEnabled(has_report)
        self.btn_clear.setEnabled(bool(self._reports))
        if not has_report:
            self.meta_label.setText("Nenhum relatório gerado ainda.")
            self.preview.clear()
            return
        parts = []
        task = _clean(report.get("task_label") or report.get("task"))
        if task:
            parts.append(f"Tarefa: {task}")
        model = _clean(report.get("model"))
        if model:
            parts.append(f"Modelo: {model}")
        created = str(report.get("created") or "").replace("T", " ")[:19]
        if created:
            parts.append(f"Gerado em: {created}")
        question = _clean(report.get("question"))
        if question:
            parts.append(f"Pergunta: {question}")
        self.meta_label.setText(" · ".join(parts) or "Relatório de IA")
        try:
            self.preview.setMarkdown(text)
        except Exception:  # pragma: no cover - Qt antigo
            self.preview.setPlainText(text)

    # ------------------------------------------------------------------
    def _copy(self) -> None:
        text = str(self._current_report().get("text") or "").strip()
        if not text:
            return
        QApplication.clipboard().setText(text)
        self.status.emit("Relatório de IA copiado para a área de transferência.")

    def _save(self) -> None:
        report = self._current_report()
        text = str(report.get("text") or "").strip()
        if not text:
            return
        default = f"relatorio_ia_{_clean(report.get('task') or 'assistente')}.md"
        filename, _ = QFileDialog.getSaveFileName(
            self, "Salvar relatório de IA", default,
            "Markdown (*.md);;Texto (*.txt)",
        )
        if not filename:
            return
        suffix = Path(filename).suffix.lower()
        if suffix not in {".md", ".markdown", ".txt"}:
            filename = str(Path(filename).with_suffix(".md"))
        try:
            Path(filename).write_text(text + "\n", encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "Erro ao salvar", str(exc))
            return
        self.status.emit(f"Relatório de IA salvo em {filename}")

    def _remove(self) -> None:
        index = self.combo_reports.currentIndex()
        if not (0 <= index < len(self._reports)):
            return
        report = self._reports[index]
        answer = QMessageBox.question(
            self, "Remover relatório",
            f"Remover o relatório “{_report_title(report)}”? "
            "Ele deixará de ser incluído na exportação.",
        )
        if answer != QMessageBox.Yes:
            return
        del self._reports[index]
        self._refresh(select=min(index, len(self._reports) - 1))
        self.reports_changed.emit(self.reports())

    def _clear_all(self) -> None:
        if not self._reports:
            return
        answer = QMessageBox.question(
            self, "Limpar relatórios de IA",
            "Remover todos os relatórios gerados por IA? Eles deixarão de ser "
            "incluídos na exportação.",
        )
        if answer != QMessageBox.Yes:
            return
        self.clear(emit=True)
        self.status.emit("Relatórios de IA removidos.")
