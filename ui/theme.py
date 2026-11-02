#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Temas visuais do Semantorium.

Hoje há dois temas: ``light`` (base definida em ``ui/main_window.py``) e
``dark`` (este módulo fornece o QSS complementar, em ``assets/styles_dark.qss``).

O tema escolhido fica em ``settings.json`` (chave ``theme``) e é aplicado na
inicialização e ao salvar as preferências.
"""

import re
from pathlib import Path
from typing import List, Tuple

ASSETS = Path(__file__).resolve().parent.parent / "assets"
DARK_QSS = ASSETS / "styles_dark.qss"

DEFAULT_THEME = "light"

#: Tema efetivamente aplicado na janela principal. Os gráficos consultam este
#: valor para adaptar apenas a exibição (o conteúdo exportado não muda).
CURRENT_THEME = DEFAULT_THEME

#: Cores claras fixas dos gráficos SVG e seus equivalentes no tema escuro.
#: A troca é textual e só ocorre ao exibir; exportações usam o SVG original.
_DARK_SVG_COLORS: Tuple[Tuple[str, str], ...] = (
    ("#ffffff", "#1c222a"),
    ("#1b1f24", "#e6eaf0"),
    ("#5b6673", "#9aa6b4"),
    ("#8a94a6", "#7c8794"),
    ("#1c53b8", "#7fb2ff"),
    ("#2d7ff9", "#5b9bff"),
    ("#b45309", "#f0a35e"),
    ("#c98a1c", "#e0a93f"),
    ("#2f8f4e", "#5fbf7c"),
    ("#eef7ee", "#16281c"),
    ("#eaf1ff", "#182336"),
    ("#f3eefb", "#241a33"),
    ("#fff6e6", "#2a2116"),
    ("#fff7e8", "#2a2116"),
    ("#e6ecf5", "#222a35"),
    ("#fff5f5", "#2a1a1a"),
    ("#b8c7e0", "#3a4a63"),
    ("#e2e8f0", "#2a313b"),
)

THEMES: List[Tuple[str, str]] = [
    ("light", "Claro"),
    ("dark", "Escuro"),
]


def normalize(theme: str) -> str:
    value = (theme or "").strip().lower()
    return value if value in dict(THEMES) else DEFAULT_THEME


def dark_stylesheet() -> str:
    """Conteúdo do QSS escuro (string vazia se o arquivo não existir)."""
    try:
        return DARK_QSS.read_text(encoding="utf-8")
    except Exception:
        return ""


def set_current(theme: str) -> str:
    """Registra o tema aplicado para que os gráficos adaptem a exibição."""
    global CURRENT_THEME
    CURRENT_THEME = normalize(theme)
    return CURRENT_THEME


def current_theme() -> str:
    return CURRENT_THEME


def adapt_svg(svg: str, theme: str | None = None) -> str:
    """Devolve o SVG com paleta escura, apenas para exibição.

    O SVG original permanece intacto: quem exporta continua usando a string
    gerada pelo gráfico. A substituição é limitada às cores claras fixas dos
    gráficos internos (fundo, texto e eixos), de modo que o tema escuro não
    exiba uma página branca. No tema claro a função devolve o texto original.
    """
    if not svg:
        return svg
    if normalize(theme or CURRENT_THEME) != "dark":
        return svg
    result = str(svg)
    for source, target in _DARK_SVG_COLORS:
        result = re.sub(
            re.escape(source) + r"\b", target, result, flags=re.IGNORECASE
        )
    return result


def stylesheet_for(theme: str, base: str = "") -> str:
    """Combina a base clara com o complemento escuro quando necessário."""
    if normalize(theme) == "dark":
        extra = dark_stylesheet()
        if extra:
            return f"{base}\n{extra}" if base else extra
    return base
