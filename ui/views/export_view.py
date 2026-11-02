#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Aba: Exportação do relatório e da sessão."""

import json
import os
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QGridLayout, QHBoxLayout, QInputDialog, QLabel,
    QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from core import userdata
from reports import exporters
from ui.widgets.help_panel import HelpPanel


class ExportView(QWidget):
    status = Signal(str)
    config_loaded = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._result = None
        self._text = ""
        self._config = None
        self._path = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.help_panel = HelpPanel("export")
        layout.addWidget(self.help_panel)

        title = QLabel("<b>Exportar relatório</b>")
        layout.addWidget(title)

        hint = QLabel(
            "Escolha um formato. O relatório HTML é autocontido e inclui todas "
            "as seções (nuvem, grafo interativo, concordância, árvore de "
            "palavras, rede semântica, similaridade e relatórios gerados por "
            "IA); PDF e DOCX/ODT trazem as mesmas seções em versão "
            "editável/para impressão (com tabelas e imagens); JSON preserva "
            "todos os dados e traz as referências em todos os estilos; TXT é "
            "texto puro; CSV/XLSX facilitam a análise em planilha."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#5b6673;")
        layout.addWidget(hint)

        templates_row = QHBoxLayout()
        templates_row.addWidget(QLabel("Modelo:"))
        self.combo_templates = QComboBox()
        self.combo_templates.setMinimumWidth(220)
        templates_row.addWidget(self.combo_templates, 1)
        self.btn_apply_template = QPushButton("Aplicar")
        self.btn_apply_template.clicked.connect(self.apply_template)
        templates_row.addWidget(self.btn_apply_template)
        self.btn_save_template = QPushButton("Salvar modelo…")
        self.btn_save_template.clicked.connect(self.save_template)
        templates_row.addWidget(self.btn_save_template)
        self.btn_delete_template = QPushButton("Excluir")
        self.btn_delete_template.clicked.connect(self.delete_template)
        templates_row.addWidget(self.btn_delete_template)
        templates_row.addWidget(QLabel("Formato preferido:"))
        self.combo_format = QComboBox()
        for label, value in (
            ("HTML", "html"), ("PDF", "pdf"), ("DOCX", "docx"),
            ("ODT", "odt"), ("JSON", "json"), ("TXT", "txt"), ("CSV", "csv"),
            ("XLSX", "xlsx"),
        ):
            self.combo_format.addItem(label, value)
        self.combo_format.currentIndexChanged.connect(self._remember_format)
        templates_row.addWidget(self.combo_format)
        layout.addLayout(templates_row)

        self.templates_hint = QLabel(
            "Modelos guardam a configuração da análise e o formato preferido; "
            "ficam em %APPDATA%\\Semantorium."
        )
        self.templates_hint.setStyleSheet("color:#5b6673; font-size:11px;")
        layout.addWidget(self.templates_hint)

        grid = QGridLayout()
        grid.setSpacing(10)

        self.button_html = QPushButton("🌐  Relatório HTML")
        self.button_pdf = QPushButton("📄  Relatório PDF")
        self.button_docx = QPushButton("📝  Relatório DOCX")
        self.button_odt = QPushButton("📃  Relatório ODT")
        self.button_json = QPushButton("🧾  Dados JSON")
        self.button_txt = QPushButton("📄  Texto puro TXT")
        self.button_csv = QPushButton("📊  Planilha CSV")
        self.button_xlsx = QPushButton("📈  Planilha XLSX")
        self.button_session = QPushButton("💾  Salvar sessão (.lexima.json)")

        for index, button in enumerate([
            self.button_html, self.button_pdf, self.button_docx, self.button_odt,
            self.button_json, self.button_txt, self.button_csv, self.button_xlsx,
            self.button_session,
        ]):
            button.setMinimumHeight(44)
            grid.addWidget(button, index // 3, index % 3)

        layout.addLayout(grid)

        assets_row = QHBoxLayout()
        self.button_pdf_assets = QPushButton("🖼  Figuras e tabelas do PDF…")
        self.button_pdf_assets.setEnabled(False)
        self.button_pdf_assets.clicked.connect(self._open_pdf_assets)
        assets_row.addWidget(self.button_pdf_assets)
        self.pdf_assets_hint = QLabel(
            "Extrai imagens, tabelas e legendas do PDF aberto (exporta em "
            "HTML autocontido ou JSON)."
        )
        self.pdf_assets_hint.setWordWrap(True)
        self.pdf_assets_hint.setStyleSheet("color:#5b6673; font-size:11px;")
        assets_row.addWidget(self.pdf_assets_hint, 1)
        layout.addLayout(assets_row)
        layout.addStretch()

        self.button_html.clicked.connect(lambda: self._export("html"))
        self.button_pdf.clicked.connect(lambda: self._export("pdf"))
        self.button_docx.clicked.connect(lambda: self._export("docx"))
        self.button_odt.clicked.connect(lambda: self._export("odt"))
        self.button_json.clicked.connect(lambda: self._export("json"))
        self.button_txt.clicked.connect(lambda: self._export("txt"))
        self.button_csv.clicked.connect(lambda: self._export("csv"))
        self.button_xlsx.clicked.connect(lambda: self._export("xlsx"))
        self.button_session.clicked.connect(self._export_session)

        for button in (self.button_html, self.button_pdf, self.button_docx,
                       self.button_odt, self.button_json, self.button_txt,
                       self.button_csv, self.button_xlsx, self.button_session):
            button.setEnabled(False)

    def update_results(self, result: dict, text: str = "",
                       path: str = "") -> None:
        self._result = result
        self._text = text
        if path:
            self._path = path
        for button in (self.button_html, self.button_pdf, self.button_docx,
                       self.button_odt, self.button_json, self.button_txt,
                       self.button_csv, self.button_xlsx, self.button_session):
            button.setEnabled(True)
        is_pdf = self._path.lower().endswith(".pdf")
        self.button_pdf_assets.setEnabled(is_pdf)
        self.pdf_assets_hint.setVisible(not is_pdf)

    def clear(self) -> None:
        self._result = None
        self._text = ""
        self._path = ""
        self.button_pdf_assets.setEnabled(False)
        self.pdf_assets_hint.setVisible(True)

    def _open_pdf_assets(self) -> None:
        if not self._path.lower().endswith(".pdf"):
            return
        from ui.dialogs.pdf_assets_dialog import PdfAssetsDialog

        dialog = PdfAssetsDialog(self._path, parent=self)
        try:
            dialog.exec()
        finally:
            dialog.deleteLater()

    # ------------------------------------------------------------------
    # Modelos de análise/exportação e formato preferido
    # ------------------------------------------------------------------
    def set_config(self, config) -> None:
        """Guarda a configuração atual usada ao salvar um modelo."""
        self._config = config

    def apply_default_format(self) -> None:
        """Restaura o formato preferido e a lista de modelos salvos."""
        try:
            preferred = userdata.load_settings().get("preferred_format", "html")
        except Exception:
            preferred = "html"
        self._set_format(preferred, persist=False)
        self._refresh_templates()

    def _set_format(self, value: str, persist: bool = True) -> None:
        index = self.combo_format.findData(value)
        if index < 0:
            index = 0
        self.combo_format.blockSignals(True)
        self.combo_format.setCurrentIndex(index)
        self.combo_format.blockSignals(False)
        if persist:
            self._remember_format()

    def _remember_format(self) -> None:
        value = self.combo_format.currentData() or "html"
        try:
            settings = userdata.load_settings()
            settings["preferred_format"] = value
            userdata.save_settings(settings)
        except Exception:
            pass

    def _refresh_templates(self) -> None:
        current = self.combo_templates.currentData()
        try:
            templates = userdata.list_templates()
        except Exception:
            templates = {}
        self.combo_templates.blockSignals(True)
        self.combo_templates.clear()
        self.combo_templates.addItem("(nenhum modelo salvo)", "")
        for name in sorted(templates):
            item = templates.get(name) or {}
            fmt = (item.get("preferred_format") or "").lower()
            label = f"{name} · {fmt.upper()}" if fmt else name
            self.combo_templates.addItem(label, name)
        index = self.combo_templates.findData(current)
        self.combo_templates.setCurrentIndex(max(0, index))
        self.combo_templates.blockSignals(False)
        has_templates = self.combo_templates.count() > 1
        self.btn_apply_template.setEnabled(has_templates)
        self.btn_delete_template.setEnabled(has_templates)

    def apply_template(self) -> None:
        name = self.combo_templates.currentData()
        if not name:
            return
        entry = userdata.list_templates().get(name)
        if not entry:
            self._refresh_templates()
            self.status.emit("O modelo selecionado não existe mais.")
            return
        self._set_format(entry.get("preferred_format", "html"), persist=True)
        self.config_loaded.emit(dict(entry.get("config") or {}))
        self.status.emit(f"Modelo “{name}” aplicado à análise.")

    def save_template(self) -> None:
        if self._config is None:
            QMessageBox.warning(
                self, "Modelos",
                "Abra o aplicativo novamente para salvar um modelo.",
            )
            return
        name, accepted = QInputDialog.getText(
            self, "Salvar modelo",
            "Nome do modelo (configuração da análise + formato preferido):",
        )
        name = userdata.clean_template_name(name)
        if not accepted or not name:
            return
        if name in userdata.list_templates():
            answer = QMessageBox.question(
                self, "Substituir modelo",
                f"Já existe um modelo chamado “{name}”. Substituir?",
            )
            if answer != QMessageBox.Yes:
                return
        try:
            userdata.save_template(
                name,
                userdata.config_to_dict(self._config),
                self.combo_format.currentData() or "html",
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Erro ao salvar modelo", str(exc))
            return
        self._refresh_templates()
        index = self.combo_templates.findData(name)
        if index >= 0:
            self.combo_templates.setCurrentIndex(index)
        self.status.emit(f"Modelo “{name}” salvo.")
        self.templates_hint.setText(
            "Modelo salvo. Use “Aplicar” para restaurar a configuração."
        )

    def delete_template(self) -> None:
        name = self.combo_templates.currentData()
        if not name:
            return
        answer = QMessageBox.question(
            self, "Excluir modelo",
            f"Excluir o modelo “{name}”?",
        )
        if answer != QMessageBox.Yes:
            return
        try:
            userdata.delete_template(name)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Erro ao excluir modelo", str(exc))
            return
        self._refresh_templates()
        self.status.emit(f"Modelo “{name}” excluído.")

    # ------------------------------------------------------------------
    def _default_name(self, extension: str) -> str:
        filename = (self._result or {}).get("meta", {}).get("filename", "lexima")
        stem = Path(filename).stem if filename else "lexima"
        return f"{stem}_relatorio.{extension}"

    def _export(self, kind: str) -> None:
        if not self._result:
            QMessageBox.warning(self, "Aviso", "Gere o relatório antes de exportar.")
            return

        filters = {
            "html": "HTML (*.html)",
            "pdf": "PDF (*.pdf)",
            "docx": "Word (*.docx)",
            "odt": "LibreOffice Writer (*.odt)",
            "json": "JSON (*.json)",
            "txt": "Texto (*.txt)",
            "csv": "CSV (*.csv)",
            "xlsx": "Excel (*.xlsx)",
        }
        filename, _ = QFileDialog.getSaveFileName(
            self, "Salvar relatório", self._default_name(kind), filters[kind]
        )
        if not filename:
            return

        try:
            if kind == "html":
                exporters.export_html(self._result, filename)
                # copiar o grafo interativo ao lado do relatório
                graph = (self._result.get("graphs", {})
                         .get("cooccurrence", {}).get("html"))
                if graph and Path(graph).exists():
                    target = Path(filename).with_name("cooccurrence.html")
                    target.write_bytes(Path(graph).read_bytes())
            elif kind == "pdf":
                exporters.export_pdf(self._result, filename)
            elif kind == "docx":
                from reports import office_export
                office_export.export_docx(self._result, filename)
            elif kind == "odt":
                from reports import office_export
                office_export.export_odt(self._result, filename)
            elif kind == "json":
                exporters.export_json(self._result, filename)
            elif kind == "txt":
                exporters.export_txt(self._result, filename)
            elif kind == "csv":
                exporters.export_csv(self._result, filename)
            elif kind == "xlsx":
                exporters.export_xlsx(self._result, filename)

            self._set_format(kind, persist=True)
            self.status.emit(f"Relatório salvo em {filename}")
            QMessageBox.information(self, "Exportado",
                                   f"Relatório salvo com sucesso:\n{filename}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Erro ao exportar", str(exc))

    def _export_session(self) -> None:
        if not self._result:
            QMessageBox.warning(self, "Aviso", "Gere o relatório antes de salvar.")
            return
        filename, _ = QFileDialog.getSaveFileName(
            self, "Salvar sessão", self._default_name("json"),
            "Sessão Semantorium (*.lexima.json);;JSON (*.json)"
        )
        if not filename:
            return
        try:
            payload = {
                "version": 1,
                "text": self._text,
                "result": {k: v for k, v in self._result.items() if k != "wordcloud"},
            }
            Path(filename).write_text(
                json.dumps(payload, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
            self.status.emit(f"Sessão salva em {filename}")
            QMessageBox.information(self, "Sessão salva",
                                   f"Sessão salva com sucesso:\n{filename}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Erro ao salvar sessão", str(exc))
