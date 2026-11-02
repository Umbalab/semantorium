#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Aba: Palavras frequentes e nuvem de palavras."""

import shutil
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPushButton, QScrollArea, QSplitter, QVBoxLayout, QWidget,
)

from core.wordcloud_gen import available_palettes, generate_wordcloud
from ui.widgets.common import Card, DataTable, row
from ui.widgets.help_panel import HelpPanel


_BACKGROUNDS = [
    ("Branco", "white", False),
    ("Preto", "black", False),
    ("Transparente", "white", True),
]


class WordsView(QWidget):
    status = Signal(str)
    stoplist_requested = Signal()
    config_changed = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._result = None
        self._pixmap_original = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        self.help_panel = HelpPanel("words")
        layout.addWidget(self.help_panel)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Mostrar:"))
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["Mais frequentes", "Menos frequentes"])
        controls.addWidget(self.combo_mode)
        controls.addWidget(QLabel("Quantidade:"))
        self.combo_limit = QComboBox()
        self.combo_limit.addItems(["20", "40", "80", "200"])
        self.combo_limit.setCurrentText("40")
        controls.addWidget(self.combo_limit)
        controls.addStretch()
        self.summary = QLabel("—")
        self.summary.setStyleSheet("color:#5b6673;")
        controls.addWidget(self.summary)

        self.button_stoplist = QPushButton("🚫  Stoplist…")
        self.button_stoplist.setToolTip(
            "Gerenciar as palavras ignoradas em todas as análises"
        )
        self.button_stoplist.clicked.connect(self.stoplist_requested.emit)
        controls.addWidget(self.button_stoplist)
        layout.addLayout(controls)

        splitter = QSplitter(Qt.Horizontal)

        table_card = Card("Frequência de palavras")
        from core import explanations as _expl
        self.words_info = QLabel(_expl.ANALYSIS_EXPLANATIONS.get('palavras', ''))
        self.words_info.setWordWrap(True)
        self.words_info.setStyleSheet("color:#5b6673;")
        table_card.add(self.words_info)
        self.table = DataTable(
            ["Palavra", "Ocorrências", "Formas"], search=True
        )
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        table_card.add(self.table)
        splitter.addWidget(table_card)

        cloud_card = Card("Nuvem de palavras")
        self.cloud_help = HelpPanel("wordcloud", expanded=False, max_height=150)
        cloud_card.add(self.cloud_help)

        palette_row = QHBoxLayout()
        palette_row.addWidget(QLabel("Paleta:"))
        self.combo_palette = QComboBox()
        self.combo_palette.addItems(available_palettes())
        self.combo_palette.setCurrentText("Viridis")
        palette_row.addWidget(self.combo_palette, 1)
        palette_row.addWidget(QLabel("Fundo:"))
        self.combo_background = QComboBox()
        for label, _, _ in _BACKGROUNDS:
            self.combo_background.addItem(label)
        palette_row.addWidget(self.combo_background)
        cloud_card.add_layout(palette_row)

        mask_row = QHBoxLayout()
        mask_row.addWidget(QLabel("Máscara:"))
        self.input_mask = QLineEdit()
        self.input_mask.setPlaceholderText("Padrão (retângulo). Aceita PNG, JPG ou SVG.")
        mask_row.addWidget(self.input_mask, 1)
        self.button_mask = QPushButton("Escolher…")
        self.button_mask.clicked.connect(self._pick_mask)
        mask_row.addWidget(self.button_mask)
        self.button_clear_mask = QPushButton("Limpar")
        self.button_clear_mask.clicked.connect(lambda: self.input_mask.clear())
        mask_row.addWidget(self.button_clear_mask)
        cloud_card.add_layout(mask_row)

        generate_row = QHBoxLayout()
        self.button_generate = QPushButton("🎨  Gerar/re-desenhar nuvem")
        self.button_generate.setEnabled(False)
        self.button_generate.clicked.connect(self._generate_cloud)
        generate_row.addWidget(self.button_generate)
        self.button_save_cloud = QPushButton("💾  Salvar (PNG)")
        self.button_save_cloud.setEnabled(False)
        self.button_save_cloud.clicked.connect(self._save_cloud)
        generate_row.addWidget(self.button_save_cloud)
        generate_row.addStretch()
        cloud_card.add_layout(generate_row)

        cloud_scroll = QScrollArea()
        cloud_scroll.setWidgetResizable(True)
        cloud_scroll.setFrameShape(QScrollArea.NoFrame)
        self.cloud_label = QLabel("Gere o relatório para visualizar a nuvem.")
        self.cloud_label.setAlignment(Qt.AlignCenter)
        self.cloud_label.setStyleSheet("color:#5b6673;")
        cloud_scroll.setWidget(self.cloud_label)
        cloud_card.add(cloud_scroll)

        splitter.addWidget(cloud_card)
        splitter.setSizes([460, 540])
        layout.addWidget(splitter, 1)

        self.combo_mode.currentIndexChanged.connect(self._refresh_table)
        self.combo_limit.currentIndexChanged.connect(self._refresh_table)
        for widget in (self.combo_palette, self.combo_background):
            widget.currentIndexChanged.connect(self._emit_config)

    # ------------------------------------------------------------------
    def clear(self) -> None:
        self._result = None
        self.table.set_rows([])
        self.summary.setText("—")
        self._pixmap_original = None
        self.cloud_label.setPixmap(QPixmap())
        self.cloud_label.setText("Gere o relatório para visualizar a nuvem.")
        self.button_save_cloud.setEnabled(False)
        self.button_generate.setEnabled(False)

    def apply_config(self, config) -> None:
        """Reflete na tela as preferências atuais de nuvem."""
        if not config:
            return
        palette = getattr(config, "wordcloud_palette", "Viridis")
        if self.combo_palette.findText(palette) >= 0:
            self.combo_palette.setCurrentText(palette)
        background = getattr(config, "wordcloud_background", "white")
        transparent = getattr(config, "wordcloud_transparent", False)
        for index, (_, color, is_transparent) in enumerate(_BACKGROUNDS):
            if is_transparent == transparent and color == background:
                self.combo_background.setCurrentIndex(index)
                break
        mask = getattr(config, "wordcloud_mask", "")
        self.input_mask.setText(mask or "")

    def update_results(self, result: dict) -> None:
        self._result = result
        self._refresh_table()
        self.button_generate.setEnabled(bool(result.get("words", {}).get("all")))

        words = result.get("words", {})
        self.summary.setText(
            f"{words.get('total_tokens', 0):,} tokens · "
            f"{words.get('total_unique', 0):,} palavras únicas".replace(",", ".")
        )

        path = result.get("wordcloud")
        if path and Path(path).exists():
            self._show_cloud(path)
            return

        self._pixmap_original = None
        self.button_save_cloud.setEnabled(False)
        detail = ""
        for warning in result.get("warnings") or []:
            if str(warning).startswith("nuvem"):
                detail = f"\n\n{str(warning)[:400]}"
                break
        self.cloud_label.setPixmap(QPixmap())
        self.cloud_label.setText(
            "Nuvem não disponível (biblioteca wordcloud/matplotlib ausente "
            "ou texto insuficiente)." + detail
        )

    # ------------------------------------------------------------------
    def _show_cloud(self, path: str) -> None:
        pixmap = QPixmap(path)
        if pixmap.isNull():
            return
        self._pixmap_original = pixmap
        self.cloud_label.setText("")
        self._fit_cloud()
        self.button_save_cloud.setEnabled(True)

    def _emit_config(self) -> None:
        _, color, transparent = _BACKGROUNDS[self.combo_background.currentIndex()]
        self.config_changed.emit({
            "wordcloud_palette": self.combo_palette.currentText(),
            "wordcloud_background": color,
            "wordcloud_transparent": transparent,
            "wordcloud_mask": self.input_mask.text().strip(),
        })

    def _pick_mask(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "Escolher máscara da nuvem", "",
            "Imagens (*.png *.jpg *.jpeg *.svg);;Todos os arquivos (*.*)",
        )
        if not filename:
            return
        self.input_mask.setText(filename)
        self._emit_config()

    def _generate_cloud(self) -> None:
        result = self._result or {}
        words = result.get("words", {}).get("all", [])
        if not words:
            QMessageBox.information(
                self, "Sem palavras", "Gere o relatório primeiro."
            )
            return
        frequencies = {w["word"]: int(w["count"]) for w in words[:150]}
        _, color, transparent = _BACKGROUNDS[self.combo_background.currentIndex()]
        palette = self.combo_palette.currentText()
        mask_path = self.input_mask.text().strip()
        target = Path(tempfile.mkdtemp(prefix="lexima_cloud_")) / "wordcloud.png"
        kwargs = dict(
            background_color=color,
            palette=palette,
            transparent=transparent,
            mask_path=mask_path or None,
        )
        try:
            generate_wordcloud(frequencies, str(target), **kwargs)
        except Exception as exc:  # noqa: BLE001
            if mask_path:
                kwargs["mask_path"] = None
                try:
                    generate_wordcloud(frequencies, str(target), **kwargs)
                except Exception as exc2:  # noqa: BLE001
                    QMessageBox.critical(
                        self, "Erro na nuvem",
                        f"{exc2}\n\nMáscara: {mask_path}",
                    )
                    return
                self.status.emit(
                    "Nuvem gerada sem a máscara (arquivo inválido ou "
                    "bibliotecas de imagem ausentes)."
                )
            else:
                QMessageBox.critical(self, "Erro na nuvem", str(exc))
                return
        result["wordcloud"] = str(target)
        self._emit_config()
        self._show_cloud(str(target))
        self.status.emit("Nuvem de palavras atualizada.")

    def _save_cloud(self) -> None:
        result = self._result or {}
        source = result.get("wordcloud")
        if not source or not Path(source).exists():
            QMessageBox.warning(
                self, "Nuvem indisponível",
                "Gere o relatório com a nuvem de palavras habilitada.",
            )
            return

        filename = result.get("meta", {}).get("filename", "lexima") or "lexima"
        stem = Path(filename).stem
        target, _ = QFileDialog.getSaveFileName(
            self, "Salvar nuvem de palavras", f"{stem}_nuvem.png",
            "Imagem PNG (*.png)",
        )
        if not target:
            return
        if not target.lower().endswith(".png"):
            target += ".png"
        try:
            shutil.copyfile(source, target)
        except OSError as exc:
            QMessageBox.critical(self, "Erro ao salvar a nuvem", str(exc))
            return
        self.status.emit(f"Nuvem salva em {target}")

    def _fit_cloud(self) -> None:
        if not self._pixmap_original:
            return
        area = self.cloud_label.parentWidget().size()
        target = self._pixmap_original.scaled(
            max(200, area.width() - 30), max(200, area.height() - 30),
            Qt.KeepAspectRatio, Qt.SmoothTransformation,
        )
        self.cloud_label.setPixmap(target)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._fit_cloud()

    def _refresh_table(self) -> None:
        if not self._result:
            return
        words = self._result.get("words", {})
        limit = int(self.combo_limit.currentText())
        source = (
            words.get("top", [])
            if self.combo_mode.currentIndex() == 0
            else words.get("bottom", [])
        )
        rows = []
        for item in source[:limit]:
            forms = ", ".join(
                f"{form['form']} ({form['count']})"
                for form in (item.get("forms") or [])[:3]
            )
            rows.append((item["word"], item["count"], forms or "—"))
        self.table.set_rows(rows)
