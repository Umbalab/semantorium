#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Visualizador de HTML embutido (PyVis) com fallback para QTextBrowser.
"""

import os
from pathlib import Path

from PySide6.QtWidgets import QTextBrowser, QVBoxLayout, QWidget

# Em ambientes sem GPU/ambiente gráfico (ou para contornar problemas de driver)
# o navegador embutido pode ser desativado; a visualização estática assume.
_DISABLED = os.environ.get("LEXIMA_DISABLE_WEBENGINE", "").strip().lower() in (
    "1", "true", "yes", "on",
)

try:  # QtWebEngine é opcional (pacote PySide6 completo inclui)
    if _DISABLED:
        raise ImportError("QtWebEngine desativado por LEXIMA_DISABLE_WEBENGINE")
    from PySide6.QtWebEngineWidgets import QWebEngineView
    HAS_WEBENGINE = True
except Exception:  # pragma: no cover
    QWebEngineView = None
    HAS_WEBENGINE = False


class GraphView(QWidget):
    """Mostra um arquivo HTML interativo ou um status em texto."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.browser = None
        self.text = QTextBrowser()

        if HAS_WEBENGINE:
            try:
                self.browser = QWebEngineView()
                self.layout.addWidget(self.browser)
            except Exception:
                self.browser = None

        if self.browser is None:
            self.text.setOpenExternalLinks(True)
            self.layout.addWidget(self.text)

    def show_status(self, message: str) -> None:
        if self.browser is not None:
            self.browser.setHtml(
                "<body style='font-family:Segoe UI,sans-serif;padding:2rem;"
                "color:#5b6673'><p>" + message + "</p></body>"
            )
        else:
            self.text.setPlainText(message)

    def load_html_file(self, path: str) -> None:
        if not path or not Path(path).exists():
            self.show_status("Grafo não disponível.")
            return
        if self.browser is not None:
            from PySide6.QtCore import QUrl
            self.browser.setUrl(QUrl.fromLocalFile(str(Path(path).resolve())))
        else:
            self.text.setHtml(
                Path(path).read_text(encoding="utf-8", errors="replace")
            )

    def show_network_fallback(self, stats: dict, edges: list) -> None:
        """Sem WebEngine: mostra a rede em tabela estática."""
        if self.browser is not None:
            return
        rows = "".join(
            f"<tr><td>{e.get('source','')}</td><td>↔</td>"
            f"<td>{e.get('target','')}</td><td align='right'>{e.get('weight','')}</td></tr>"
            for e in edges[:300]
        )
        self.text.setHtml(
            "<h3>Rede de coocorrência</h3>"
            f"<p>{stats.get('nodes',0)} nós · {stats.get('edges',0)} conexões · "
            f"densidade {stats.get('density',0)}</p>"
            "<p style='color:#5b6673'>Visualização interativa indisponível "
            "neste ambiente (QtWebEngine ausente). Segue a lista de conexões:</p>"
            f"<table width='100%' cellpadding='4' style='font-size:12px'>{rows}</table>"
        )

    def load_html_string(self, html: str) -> None:
        if self.browser is not None:
            self.browser.setHtml(html)
        else:
            self.text.setHtml(html)
