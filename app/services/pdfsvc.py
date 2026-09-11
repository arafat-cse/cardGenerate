from pathlib import Path

from reportlab.pdfgen.canvas import Canvas

from ..config import BLEED_IN, CARD_H_IN, CARD_W_IN

PAGE_W = (CARD_W_IN + 2 * BLEED_IN) * 72
PAGE_H = (CARD_H_IN + 2 * BLEED_IN) * 72


def save_pdf(out: Path, side_png_paths: list[Path], title: str) -> None:
    c = Canvas(str(out), pagesize=(PAGE_W, PAGE_H))
    c.setTitle(title)
    for p in side_png_paths:
        c.drawImage(str(p), 0, 0, width=PAGE_W, height=PAGE_H)
        c.showPage()
    c.save()
