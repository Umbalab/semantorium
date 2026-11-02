#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Conversão do diagrama PRISMA (SVG) para PNG usando Qt — sem navegador."""

from PySide6.QtCore import QByteArray, QSize
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


def svg_to_png(svg: str, output_path: str, scale: float = 2.0) -> str:
    """Renderiza o SVG em PNG com fundo branco e devolve o caminho salvo."""
    renderer = QSvgRenderer(QByteArray((svg or "").encode("utf-8")))
    if not renderer.isValid():
        raise ValueError("SVG inválido para renderização.")
    size = renderer.defaultSize()
    if size.isEmpty():
        size = QSize(840, 690)
    scale = max(1.0, float(scale or 1.0))
    image = QImage(
        int(size.width() * scale), int(size.height() * scale),
        QImage.Format.Format_ARGB32,
    )
    image.fill(0xFFFFFFFF)
    painter = QPainter(image)
    try:
        renderer.render(painter)
    finally:
        painter.end()
    if not image.save(output_path, "PNG"):
        raise RuntimeError(f"Não foi possível gravar o PNG em {output_path}.")
    return output_path
