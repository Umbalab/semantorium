#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Worker em thread separada para não travar a interface.
"""

from PySide6.QtCore import QThread, Signal

from core.analysis import AnalysisConfig, AnalysisRunner


class AnalysisWorker(QThread):
    progress = Signal(int, str)
    finished_ok = Signal(dict)
    failed = Signal(str)

    def __init__(self, text: str, meta: dict, config: AnalysisConfig):
        super().__init__()
        self.text = text
        self.meta = meta
        self.config = config

    def run(self) -> None:
        try:
            runner = AnalysisRunner(self.config, self._emit)
            result = runner.run(self.text, self.meta)
            self.finished_ok.emit(result)
        except Exception as exc:  # noqa: BLE001
            import traceback
            self.failed.emit(f"{exc}\n\n{traceback.format_exc()}")

    def _emit(self, pct: int, msg: str) -> None:
        self.progress.emit(int(pct), msg)


class LoadWorker(QThread):
    """Carrega e extrai o arquivo fora da thread da UI."""
    finished_ok = Signal(dict)
    failed = Signal(str)

    def __init__(self, filepath: str):
        super().__init__()
        self.filepath = filepath

    def run(self) -> None:
        try:
            from core.extractor import extract_text
            self.finished_ok.emit(extract_text(self.filepath))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class OllamaWorker(QThread):
    """Executa uma tarefa do assistente local sem travar a interface."""

    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, text: str, task: str = "resumo",
                 question: str = "", model: str = "", url: str = "",
                 timeout: int = 0):
        super().__init__()
        self.text = text
        self.task = task
        self.question = question
        self.model = model
        self.url = url
        self.timeout = timeout

    def run(self) -> None:
        try:
            from core import ollama

            answer = ollama.summarize(
                self.text,
                task=self.task,
                question=self.question,
                model=self.model or None,
                url=self.url or None,
                timeout=self.timeout or None,
            )
            self.finished_ok.emit(answer)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class OllamaInstallWorker(QThread):
    """Baixa e instala o Ollama em segundo plano, com cancelamento."""

    progress = Signal(str, int, str)
    finished_ok = Signal(dict)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, directory=None):
        super().__init__()
        import threading

        self._cancel = threading.Event()
        self.directory = directory

    def cancel(self) -> None:
        self._cancel.set()

    def run(self) -> None:
        try:
            from core import ollama_install

            result = ollama_install.install_ollama(
                cancelled=self._cancel,
                progress=lambda stage, pct, msg: self.progress.emit(
                    str(stage), int(pct), str(msg)
                ),
                directory=self.directory,
            )
            self.finished_ok.emit(result)
        except Exception as exc:  # noqa: BLE001
            from core.ollama_install import InstallCancelled

            if isinstance(exc, InstallCancelled):
                self.cancelled.emit()
            else:
                self.failed.emit(str(exc))


class CorpusWorker(QThread):
    """Extrai e analisa vários documentos fora da thread da UI."""
    progress = Signal(int, str)
    finished_ok = Signal(dict)
    failed = Signal(str)

    def __init__(self, paths, clusters: int = 4,
                 language: str = "Auto-detectar"):
        super().__init__()
        self.paths = list(paths or [])
        self.clusters = clusters
        self.language = language

    def run(self) -> None:
        try:
            from pathlib import Path

            from core.corpus import analyze_corpus
            from core.extractor import extract_text

            documents = []
            total = max(1, len(self.paths))
            for index, path in enumerate(self.paths):
                name = Path(path).name
                self.progress.emit(
                    int(index / total * 45), f"Extraindo {name}…"
                )
                try:
                    data = extract_text(path)
                except Exception as exc:  # noqa: BLE001
                    documents.append({
                        "name": name, "path": path, "text": "",
                        "error": f"{type(exc).__name__}: {exc}",
                    })
                    continue
                documents.append({
                    "name": name,
                    "path": path,
                    "text": data.get("text", ""),
                })
            self.progress.emit(50, "Calculando similaridade e agrupamentos…")
            result = analyze_corpus(
                documents, clusters=self.clusters, language=self.language
            )
            self.progress.emit(100, "Concluído.")
            self.finished_ok.emit(result)
        except Exception as exc:  # noqa: BLE001
            import traceback
            self.failed.emit(f"{exc}\n\n{traceback.format_exc()}")
