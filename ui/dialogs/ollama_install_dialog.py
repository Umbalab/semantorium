#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Janela de progresso do download/instalação do Ollama."""

from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout,
)

from core import ollama_install
from ui.worker import OllamaInstallWorker


class OllamaInstallDialog(QDialog):
    """Mostra o progresso e permite cancelar antes de concluir."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Baixar e instalar o Ollama")
        self.setModal(True)
        self.resize(540, 230)
        self.result_info = {}
        self.outcome = ""
        self.error_message = ""
        self._finished = False
        self._worker = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self.label_intro = QLabel(
            "Baixando o instalador oficial do Ollama "
            f"({ollama_install.DOWNLOAD_SIZE_HINT}). "
            "Você pode cancelar o download a qualquer momento."
        )
        self.label_intro.setWordWrap(True)
        layout.addWidget(self.label_intro)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.label_detail = QLabel("Preparando o download…")
        self.label_detail.setWordWrap(True)
        self.label_detail.setStyleSheet("color:#5b6673;")
        layout.addWidget(self.label_detail)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.clicked.connect(self._cancel)
        buttons.addWidget(self.btn_cancel)
        layout.addLayout(buttons)

        self._start_worker()

    # ------------------------------------------------------------------
    def _start_worker(self) -> None:
        self._worker = OllamaInstallWorker()
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.cancelled.connect(self._on_cancelled)
        self._worker.finished.connect(self._on_thread_finished)
        self._worker.start()

    def _on_progress(self, stage: str, percent: int, message: str) -> None:
        if stage == "install":
            self.label_intro.setText(
                "Instalando o Ollama. Não feche esta janela."
            )
            self.btn_cancel.setEnabled(False)
            self.btn_cancel.setToolTip(
                "A instalação já começou e não pode ser interrompida com "
                "segurança."
            )
        self.progress.setValue(int(percent))
        self.label_detail.setText(message)

    def _on_finished(self, result: dict) -> None:
        self._finished = True
        self.outcome = "installed"
        self.result_info = dict(result or {})
        self.progress.setValue(100)
        self.label_intro.setText("Ollama instalado com sucesso.")
        self.label_detail.setText(
            "Você já pode iniciar o servidor e verificar os modelos "
            "instalados."
        )
        self.btn_cancel.setText("Fechar")
        self.btn_cancel.setEnabled(True)
        self.btn_cancel.setToolTip("")

    def _on_failed(self, message: str) -> None:
        self._finished = True
        self.outcome = "failed"
        self.error_message = message
        self.label_intro.setText("Não foi possível instalar o Ollama.")
        self.label_detail.setText(message)
        self.btn_cancel.setText("Fechar")
        self.btn_cancel.setEnabled(True)
        self.btn_cancel.setToolTip("")

    def _on_cancelled(self) -> None:
        self._finished = True
        self.outcome = "cancelled"
        self.label_intro.setText("Instalação cancelada.")
        self.label_detail.setText(
            "O download foi interrompido e o arquivo parcial foi removido. "
            "Nada foi instalado."
        )
        self.btn_cancel.setText("Fechar")
        self.btn_cancel.setEnabled(True)
        self.btn_cancel.setToolTip("")

    def _on_thread_finished(self) -> None:
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None

    # ------------------------------------------------------------------
    def _cancel(self) -> None:
        if self._finished or self._worker is None:
            self.accept()
            return
        self.btn_cancel.setEnabled(False)
        self.label_detail.setText("Cancelando…")
        self._worker.cancel()

    def reject(self) -> None:
        self._stop_worker()
        super().reject()

    def accept(self) -> None:
        self._stop_worker()
        super().accept()

    def _stop_worker(self) -> None:
        worker = self._worker
        if worker is not None and worker.isRunning():
            worker.cancel()
            worker.wait(5000)

    def closeEvent(self, event) -> None:  # noqa: N802 - API do Qt
        self._stop_worker()
        super().closeEvent(event)
