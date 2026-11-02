#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Diálogo do assistente local opcional (Ollama)."""

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QTextBrowser, QVBoxLayout,
)

from core import i18n, ollama, ollama_install
from ui.worker import OllamaWorker


class AssistantDialog(QDialog):
    """Leitura assistida por um modelo local, com opt-in explícito."""

    # Emitido a cada resposta concluída, para que a janela principal a guarde
    # na aba "Relatórios de IA" e a inclua no relatório exportado.
    report_generated = Signal(dict)

    def __init__(self, text: str, result: dict = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(
            i18n.t("assistant.title", "Assistente local (Ollama)")
        )
        self.resize(780, 640)
        self._text = text or ""
        self._result = result or {}
        self._worker = None
        self._pending_report = None
        self._config = ollama.load_config()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        self.check_enabled = QCheckBox(
            "Ativar o assistente local (Ollama)"
        )
        self.check_enabled.setChecked(bool(self._config["enabled"]))
        layout.addWidget(self.check_enabled)

        hint = QLabel(
            "Opcional e desativado por padrão. Quando ativado, o texto do "
            "documento é enviado apenas para o servidor local informado "
            "(nada sai para a internet). O Semantorium continua funcionando "
            "normalmente sem o Ollama."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#5b6673; font-size:11px;")
        layout.addWidget(hint)

        connection = QHBoxLayout()
        connection.addWidget(QLabel("Servidor:"))
        self.input_url = QLineEdit(self._config["url"])
        self.input_url.setPlaceholderText(ollama.DEFAULT_URL)
        connection.addWidget(self.input_url, 2)
        connection.addWidget(QLabel("Modelo:"))
        self.combo_model = QComboBox()
        self.combo_model.setEditable(True)
        self.combo_model.setMinimumWidth(200)
        self.combo_model.setCurrentText(self._config["model"])
        connection.addWidget(self.combo_model, 2)
        self.btn_verify = QPushButton("Verificar")
        self.btn_verify.setToolTip(
            "Consultar os modelos instalados no servidor local"
        )
        self.btn_verify.clicked.connect(self._verify)
        connection.addWidget(self.btn_verify)
        layout.addLayout(connection)

        actions = QHBoxLayout()
        self.btn_start = QPushButton("▶  Iniciar Ollama")
        self.btn_start.setToolTip(
            "Executa `ollama serve` em segundo plano (não instala nada)"
        )
        self.btn_start.clicked.connect(self._start_ollama)
        actions.addWidget(self.btn_start)
        self.btn_stop = QPushButton("■  Parar Ollama")
        self.btn_stop.setToolTip(
            "Encerra apenas o servidor que o Semantorium iniciou nesta sessão"
        )
        self.btn_stop.clicked.connect(self._stop_ollama)
        actions.addWidget(self.btn_stop)
        self.btn_install = QPushButton("⬇  Baixar e instalar")
        self.btn_install.setToolTip(
            "Baixa o instalador oficial e instala o Ollama nesta máquina"
        )
        self.btn_install.clicked.connect(self._install_ollama)
        actions.addWidget(self.btn_install)
        actions.addStretch()
        layout.addLayout(actions)

        task_row = QHBoxLayout()
        task_row.addWidget(QLabel("Tarefa:"))
        self.combo_task = QComboBox()
        for value, label in ollama.TASK_OPTIONS:
            self.combo_task.addItem(label, value)
        self.combo_task.currentIndexChanged.connect(self._sync_question)
        task_row.addWidget(self.combo_task, 1)
        layout.addLayout(task_row)

        self.input_question = QLineEdit()
        self.input_question.setPlaceholderText(
            "Pergunta livre sobre o documento"
        )
        self.input_question.returnPressed.connect(self._generate)
        layout.addWidget(self.input_question)

        self.output = QTextBrowser()
        self.output.setPlaceholderText(
            "A resposta do modelo aparecerá aqui."
        )
        self.output.setOpenExternalLinks(True)
        layout.addWidget(self.output, 1)

        self.status = QLabel(
            "Ative o assistente para gerar uma resposta."
        )
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color:#5b6673;")
        layout.addWidget(self.status)

        buttons = QHBoxLayout()
        self.btn_generate = QPushButton("✨  Gerar")
        self.btn_generate.clicked.connect(self._generate)
        buttons.addWidget(self.btn_generate)
        self.btn_copy = QPushButton("Copiar")
        self.btn_copy.clicked.connect(self._copy)
        buttons.addWidget(self.btn_copy)
        self.btn_save = QPushButton("Salvar…")
        self.btn_save.clicked.connect(self._save)
        buttons.addWidget(self.btn_save)
        buttons.addStretch()
        close = QPushButton("Fechar")
        close.clicked.connect(self.reject)
        buttons.addWidget(close)
        layout.addLayout(buttons)

        self.check_enabled.toggled.connect(self._on_toggle)
        self._on_toggle(self.check_enabled.isChecked(), persist=False)
        self._sync_question()

    # ------------------------------------------------------------------
    def _refresh_availability(self) -> dict:
        """Atualiza os botões de diagnóstico (consulta local, sem rede)."""
        state = ollama.quick_status(self.input_url.text().strip())
        self.btn_start.setEnabled(
            bool(state.get("installed")) and not state.get("running")
        )
        url = self.input_url.text().strip()
        owned = ollama.server_owned(url)
        self.btn_stop.setEnabled(owned)
        self.btn_stop.setVisible(bool(state.get("installed")))
        self.btn_stop.setToolTip(
            "Encerra o servidor que o Semantorium iniciou nesta sessão"
            if owned else
            "Nenhum servidor iniciado pelo Semantorium. Um Ollama já aberto "
            "pertence ao usuário e não é encerrado."
        )
        installed = bool(state.get("installed"))
        self.btn_install.setVisible(not installed)
        self.btn_install.setEnabled(not installed)
        return state

    def _on_toggle(self, checked: bool, persist: bool = True) -> None:
        for widget in (
            self.input_url, self.combo_model, self.btn_verify,
            self.combo_task, self.btn_generate,
        ):
            widget.setEnabled(bool(checked))
        self._sync_question()
        self.btn_copy.setEnabled(self.output.toPlainText().strip() != "")
        self.btn_save.setEnabled(self.output.toPlainText().strip() != "")
        if not checked:
            self.status.setText(
                "Assistente desativado. Nenhum texto é enviado ao servidor."
            )
        elif self.status.text().startswith("Assistente desativado"):
            self.status.setText("Pronto. Verifique a conexão e gere a resposta.")
        if persist:
            try:
                ollama.save_config(
                    enabled=bool(checked),
                    url=self.input_url.text(),
                    model=self.combo_model.currentText(),
                )
            except Exception as exc:  # pragma: no cover - best effort
                self.status.setText(f"Não foi possível salvar: {exc}")
        if checked:
            state = self._refresh_availability()
            if not state.get("running"):
                self.status.setText(str(state.get("message", "")))
        else:
            self._refresh_availability()

    def _start_ollama(self) -> None:
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            result = ollama.start_server(self.input_url.text().strip())
        finally:
            QApplication.restoreOverrideCursor()
        self.status.setText(str(result.get("message", "")))
        self._refresh_availability()
        if result.get("ok"):
            QTimer.singleShot(1200, self._verify)

    def _stop_ollama(self) -> None:
        result = ollama.stop_server(self.input_url.text().strip())
        self.status.setText(str(result.get("message", "")))
        self._refresh_availability()

    def _install_ollama(self) -> None:
        state = ollama.quick_status(self.input_url.text().strip())
        if state.get("installed"):
            self.status.setText(
                "O Ollama já está instalado neste computador."
            )
            self._refresh_availability()
            return
        answer = QMessageBox.question(
            self,
            "Baixar e instalar o Ollama",
            "O Semantorium vai baixar o instalador oficial do Ollama "
            f"({ollama_install.DOWNLOAD_SIZE_HINT}) em ollama.com e "
            "instalá-lo neste computador.\n\n"
            "A instalação é silenciosa e seus documentos não são enviados "
            "para a internet. Deseja continuar?",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if answer != QMessageBox.Yes:
            self.status.setText(
                "Instalação cancelada. Nenhum download foi feito."
            )
            return

        from ui.dialogs.ollama_install_dialog import OllamaInstallDialog

        self.status.setText("Baixando e instalando o Ollama…")
        dialog = OllamaInstallDialog(self)
        try:
            dialog.exec()
        finally:
            dialog.deleteLater()

        self._refresh_availability()
        if dialog.outcome == "installed":
            result = ollama.start_server(self.input_url.text().strip())
            self.status.setText(str(result.get("message", "")))
            QTimer.singleShot(1500, self._verify)
        elif dialog.outcome == "cancelled":
            self.status.setText(
                "Instalação cancelada. Nenhum arquivo foi instalado."
            )
        else:
            self.status.setText(
                "A instalação do Ollama não foi concluída. "
                f"{dialog.error_message}".strip()
            )

    def _sync_question(self, *_args) -> None:
        livre = self.combo_task.currentData() == "livre"
        self.input_question.setVisible(livre)
        self.input_question.setEnabled(
            livre and self.check_enabled.isChecked()
        )

    def _verify(self) -> None:
        url = self.input_url.text().strip()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            info = ollama.diagnose(url, timeout=ollama.SHORT_TIMEOUT)
        finally:
            QApplication.restoreOverrideCursor()
        models = info.get("models") or []
        current = self.combo_model.currentText().strip()
        if models:
            self.combo_model.blockSignals(True)
            self.combo_model.clear()
            self.combo_model.addItems(models)
            index = self.combo_model.findText(current)
            if index >= 0:
                self.combo_model.setCurrentIndex(index)
            else:
                self.combo_model.setCurrentText(current or models[0])
            self.combo_model.blockSignals(False)
        self._refresh_availability()
        message = str(info.get("message", ""))
        detail = str(info.get("error") or "").strip()
        if not info.get("available") and detail:
            message = f"{message}\n\nDetalhe técnico: {detail}"
        self.status.setText(message)
        try:
            ollama.save_config(
                enabled=self.check_enabled.isChecked(),
                url=url,
                model=self.combo_model.currentText(),
            )
        except Exception:  # pragma: no cover - best effort
            pass

    def _generate(self) -> None:
        if not self.check_enabled.isChecked():
            self.status.setText(
                "Ative o assistente local para gerar uma resposta."
            )
            return
        if not self._text.strip():
            QMessageBox.information(
                self, "Assistente local",
                "Carregue um documento antes de usar o assistente.",
            )
            return
        task = self.combo_task.currentData() or "resumo"
        question = self.input_question.text().strip()
        if task == "livre" and not question:
            self.status.setText("Escreva a pergunta que deseja fazer.")
            self.input_question.setFocus()
            return
        try:
            ollama.save_config(
                enabled=True,
                url=self.input_url.text(),
                model=self.combo_model.currentText(),
            )
        except Exception:  # pragma: no cover - best effort
            pass

        self.btn_generate.setEnabled(False)
        self.status.setText(
            "Consultando o modelo local… isso pode levar alguns segundos."
        )
        model = self.combo_model.currentText().strip()
        # Guarda os metadados da geração; o texto só é anexado ao relatório
        # final quando o modelo responder.
        self._pending_report = {
            "task": task,
            "task_label": self.combo_task.currentText(),
            "question": question,
            "model": model,
            "created": datetime.now().isoformat(timespec="seconds"),
        }
        self._worker = OllamaWorker(
            self._text,
            task=task,
            question=question,
            model=model,
            url=self.input_url.text().strip(),
            timeout=self._config.get("timeout", 0),
        )
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _on_finished(self, answer: str) -> None:
        try:
            self.output.setMarkdown(answer)
        except Exception:  # pragma: no cover - Qt antigo
            self.output.setPlainText(answer)
        self.btn_copy.setEnabled(True)
        self.btn_save.setEnabled(True)
        text = str(answer or "").strip()
        if text:
            report = dict(self._pending_report or {})
            report.setdefault("task", self.combo_task.currentData() or "livre")
            report.setdefault("task_label", self.combo_task.currentText())
            report.setdefault("model", self.combo_model.currentText().strip())
            report.setdefault(
                "created", datetime.now().isoformat(timespec="seconds")
            )
            report["text"] = text
            self.report_generated.emit(report)
            self.status.setText(
                "Resposta gerada por um modelo local. Ela foi adicionada à "
                "aba “Relatórios de IA” e será incluída no relatório final. "
                "Revise antes de usar."
            )
        else:
            self.status.setText(
                "O modelo não retornou texto. Nenhum relatório foi adicionado."
            )

    def _on_failed(self, message: str) -> None:
        self._pending_report = None
        state = self._refresh_availability()
        extra = ""
        if not state.get("running"):
            extra = f"\n\n{state.get('message', '')}"
        self.status.setText(f"Falha: {message}{extra}")

    def _on_worker_finished(self) -> None:
        self.btn_generate.setEnabled(self.check_enabled.isChecked())
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None

    # ------------------------------------------------------------------
    def _copy(self) -> None:
        text = self.output.toPlainText().strip()
        if not text:
            return
        QApplication.clipboard().setText(text)
        self.status.setText("Resposta copiada para a área de transferência.")

    def _save(self) -> None:
        text = self.output.toPlainText().strip()
        if not text:
            return
        filename, _ = QFileDialog.getSaveFileName(
            self, "Salvar resposta do assistente", "resposta_ollama.md",
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
        self.status.setText(f"Resposta salva em {Path(filename).name}.")

    # ------------------------------------------------------------------
    def done(self, result: int) -> None:
        if self._worker is not None and self._worker.isRunning():
            self.status.setText(
                "Aguarde a resposta do assistente antes de fechar."
            )
            return
        super().done(result)
