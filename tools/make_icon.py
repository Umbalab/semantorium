#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera assets/icon.ico simples (letra L estilizada) usando Pillow."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def main() -> None:
    size = 256
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # Fundo arredondado azul
    draw.rounded_rectangle([8, 8, size - 8, size - 8], radius=48,
                           fill=(45, 127, 249, 255))
    # Linhas de "texto"
    for index, width in enumerate((120, 150, 90)):
        y = 96 + index * 34
        draw.rounded_rectangle([64, y, 64 + width, y + 14], radius=7,
                               fill=(255, 255, 255, 220))
    # Letra L
    draw.rounded_rectangle([64, 150, 84, 206], radius=8, fill=(255, 255, 255, 255))
    draw.rounded_rectangle([64, 190, 128, 208], radius=8, fill=(255, 255, 255, 255))

    out = Path(__file__).resolve().parent.parent / "assets" / "icon.ico"
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out, sizes=[(16, 16), (32, 32), (48, 48), (64, 64),
                           (128, 128), (256, 256)])
    png = out.with_suffix(".png")
    image.save(png)
    print(f"Ícone gerado: {out}")


if __name__ == "__main__":
    main()
