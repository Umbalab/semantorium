"""Gera um PDF sem camada de texto para testar o OCR do Semantorium.

Uso:
    .\\.venv\\Scripts\\python.exe tools\\make_scan_sample.py
"""

from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw, ImageFont


TEXT_LINES = [
    "Relatorio de teste do OCR",
    "A educacao digital exige transparencia algoritmica.",
    "Silva (2020) defende auditoria dos sistemas escolares.",
    "Este arquivo e uma imagem, sem texto selecionavel.",
    "Semantorium deve reconhecer estas linhas automaticamente.",
]


def main() -> int:
    width, height = 1240, 1754  # A4 a 150 dpi
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)

    font = None
    for candidate in (
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path(r"C:\Windows\Fonts\segoeui.ttf"),
    ):
        if candidate.exists():
            font = ImageFont.truetype(str(candidate), 40)
            break
    if font is None:
        font = ImageFont.load_default()

    y = 160
    for line in TEXT_LINES:
        draw.text((120, y), line, fill="black", font=font)
        y += 80

    out_dir = Path(__file__).resolve().parent.parent / "samples"
    out_dir.mkdir(parents=True, exist_ok=True)
    jpg_path = out_dir / "_scan_demo.jpg"
    image.save(jpg_path, quality=82, optimize=True)

    pdf_path = out_dir / "scan_demo.pdf"
    document = pymupdf.open()
    page = document.new_page(width=595, height=842)  # A4 em pontos
    page.insert_image(page.rect, filename=str(jpg_path))
    document.save(pdf_path, deflate=True)
    document.close()
    jpg_path.unlink(missing_ok=True)

    print(f"Gerado: {pdf_path} ({pdf_path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
