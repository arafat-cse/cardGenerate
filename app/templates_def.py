"""Template definitions.

Each template is data: a palette plus a front side and a back side made of
background shapes and elements (positions are normalized 0..1 of the trim
size). build_all() writes templates/template-XX/template.json and renders a
preview.png thumbnail for each (using sample data) on first startup.
"""

import json
import re

from PIL import Image

from .config import DEFAULT_LOGO, TEMPLATES_DIR
from .services import qrsvc
from .services.layout import qr_invert
from .services.render import render_stacked

TEMPLATE_VERSION = 6

SAMPLE_DATA = {
    "company": "Northwind Studio",
    "name": "Jubaer Ahmed",
    "title": "Creative Director",
    "tagline": "Design · Print · Brand",
    "phone": "+880 1712 345678",
    "email": "hello@northwind.co",
    "website": "northwind.co",
    "address": "221 Farmgate, Dhaka 1205",
}

# ---------------------------------------------------------------- back sides

def back_qr(dark: bool, bg_key: str = "bg", line_key: str = "line") -> dict:
    """Dynamic back side — resolved at render time by layout._qr_back_side:
    QR + photo -> photo | divider | QR; photo only -> centered photo;
    QR only -> QR centered."""
    return {
        "background": [{"t": "rect", "x": 0, "y": 0, "w": 1, "h": 1, "fill": bg_key, "bleed": True}],
        "dynamic": "qr_back",
        "invert": dark,
        "line_key": line_key,
    }


# ---------------------------------------------------------------- shape kit
# Small reusable background motifs shared by the "smart card" (NFC / PVC /
# metal) templates below, and used to give the original 10 a subtle 4-edge
# frame so the whole set reads as one styled product line.

def _frame(color: str = "accent", inset: float = 0.032, sw: float = 0.42) -> dict:
    """Thin stroke-only rect just inside the trim — a border on all 4 sides."""
    return {"t": "rect", "x": inset, "y": inset, "w": 1 - 2 * inset, "h": 1 - 2 * inset,
            "stroke": color, "strokeW": sw}


def _corner_brackets(color: str, inset: float = 0.032, arm: float = 0.055, sw: float = 1.0) -> list[dict]:
    """4 L-shaped corner marks (camera-viewfinder style) as an alternative to a full frame."""
    out = []
    for cx, cy, sxn, syn in ((inset, inset, 1, 1), (1 - inset, inset, -1, 1),
                              (inset, 1 - inset, 1, -1), (1 - inset, 1 - inset, -1, -1)):
        out.append({"t": "line", "x1": cx, "y1": cy, "x2": cx + sxn * arm, "y2": cy, "stroke": color, "w": sw})
        out.append({"t": "line", "x1": cx, "y1": cy, "x2": cx, "y2": cy + syn * arm, "stroke": color, "w": sw})
    return out


def _chip(x: float, y: float, w: float, h: float, plate: str = "accent", grid: str = "bg") -> list[dict]:
    """Small metallic EMV-style chip decal — the "smart card" signature mark."""
    return [
        {"t": "rect", "x": x, "y": y, "w": w, "h": h, "fill": plate, "radius": 0.018},
        {"t": "line", "x1": x + w * 0.34, "y1": y + h * 0.08, "x2": x + w * 0.34, "y2": y + h * 0.92,
         "stroke": grid, "w": 0.35},
        {"t": "line", "x1": x + w * 0.66, "y1": y + h * 0.08, "x2": x + w * 0.66, "y2": y + h * 0.92,
         "stroke": grid, "w": 0.35},
        {"t": "line", "x1": x + w * 0.08, "y1": y + h * 0.5, "x2": x + w * 0.92, "y2": y + h * 0.5,
         "stroke": grid, "w": 0.35},
    ]


def _hairlines(n: int, color: str, y0: float = 0.10, y1: float = 0.90) -> list[dict]:
    """Faint evenly-spaced horizontal lines — a cheap brushed-metal band hint."""
    step = (y1 - y0) / max(1, n - 1)
    return [{"t": "line", "x1": 0, "y1": y0 + i * step, "x2": 1, "y2": y0 + i * step,
             "stroke": color, "w": 0.3} for i in range(n)]


def _smart_front(palette_bg: str = "bg", frame_color: str = "accent", frame_mode: str = "line",
                  chip_plate: str = "accent", chip_grid: str = "bg", nfc_color: str = "accent",
                  name_font: str = "sansBold", name_color: str = "ink", name_size: float = 12.5,
                  company_color: str = "sub", title_color: str = "sub", contact_color: str = "ink",
                  website_color: str = "accent", qr_invert: bool = True,
                  logo_xywh: tuple = (0.775, 0.075, 0.145, 0.115), extra_bg: list | None = None) -> dict:
    """Shared skeleton for the NFC/metal-card templates: logo+company top,
    name/title mid-left, contact block, a chip + "NFC" mark bottom-left,
    QR bottom-right, and a 4-side frame (or corner brackets)."""
    bg = [{"t": "rect", "x": 0, "y": 0, "w": 1, "h": 1, "fill": palette_bg, "bleed": True}]
    if extra_bg:
        bg += extra_bg
    if frame_mode == "line":
        bg.append(_frame(frame_color))
    elif frame_mode == "corners":
        bg += _corner_brackets(frame_color)
    bg += _chip(0.055, 0.855, 0.115, 0.078, chip_plate, chip_grid)

    lx, ly, lw, lh = logo_xywh
    return {
        "background": bg,
        "elements": [
            {"t": "image", "role": "logo", "x": lx, "y": ly, "w": lw, "h": lh, "fit": "contain"},
            {"t": "text", "field": "company", "x": 0.07, "y": 0.09, "w": 0.55, "h": 0.05,
             "size": 8, "font": "sans", "color": company_color, "align": "left",
             "caps": True, "track": 0.18},
            {"t": "text", "field": "name", "x": 0.07, "y": 0.40, "w": 0.62, "h": 0.10,
             "size": name_size, "font": name_font, "color": name_color, "align": "left"},
            {"t": "text", "field": "title", "x": 0.07, "y": 0.525, "w": 0.60, "h": 0.05,
             "size": 7.5, "font": "sans", "color": title_color, "align": "left",
             "caps": True, "track": 0.14},
            {"t": "line", "x1": 0.07, "y1": 0.615, "x2": 0.21, "y2": 0.615, "stroke": frame_color, "w": 0.5},
            {"t": "text", "field": ["phone", "email"], "x": 0.07, "y": 0.65, "w": 0.60, "h": 0.05,
             "size": 7.5, "font": "sans", "color": contact_color, "align": "left"},
            {"t": "text", "field": "website", "x": 0.07, "y": 0.715, "w": 0.60, "h": 0.05,
             "size": 7.5, "font": "sans", "color": website_color, "align": "left"},
            {"t": "text", "lit": "NFC", "x": 0.185, "y": 0.863, "w": 0.12, "h": 0.045,
             "size": 6.5, "font": "sansBold", "color": nfc_color, "align": "left",
             "caps": True, "track": 0.32},
            {"t": "qr", "x": 0.845, "y": 0.785, "w": 0.10, "h": 0.14, "invert": qr_invert},
        ],
    }


# ------------------------------------------------------------------- fronts

def templates() -> list[dict]:
    out = []

    # 01 - Noir Classic (dark, blackletter name, logo top-right / logo+QR back)
    out.append({
        "id": "template-01", "name": "Noir Classic",
        "desc": "Black card, Old-English name — front logo + back QR",
        "v": TEMPLATE_VERSION,
        "palette": {"bg": "#0B0B0D", "ink": "#FFFFFF", "sub": "#B9BDC4",
                    "accent": "#C9A227", "line": "#E8E8E8", "panel": "#1A1A1F"},
        "sides": {
            "front": {
                "background": [
                    {"t": "rect", "x": 0, "y": 0, "w": 1, "h": 1, "fill": "bg", "bleed": True},
                    _frame("accent"),
                ],
                "elements": [
                    {"t": "image", "role": "logo", "x": 0.80, "y": 0.055, "w": 0.145, "h": 0.115, "fit": "contain"},
                    {"t": "text", "field": "company", "x": 0.055, "y": 0.065, "w": 0.45, "h": 0.05,
                     "size": 7.5, "font": "sans", "color": "sub", "align": "left",
                     "caps": True, "track": 0.20},
                    {"t": "text", "field": "name", "x": 0.055, "y": 0.695, "w": 0.89, "h": 0.135,
                     "size": 14.5, "font": "blackletter", "color": "ink", "align": "left"},
                    {"t": "text", "field": "title", "x": 0.058, "y": 0.85, "w": 0.85, "h": 0.05,
                     "size": 7, "font": "sans", "color": "sub", "align": "left",
                     "caps": True, "track": 0.18},
                ],
            },
            "back": back_qr(dark=True),
        },
    })

    # 02 - Classic Ivory (double gold frame, centered serif)
    out.append({
        "id": "template-02", "name": "Classic Ivory",
        "desc": "Ivory paper, gold double frame, centered serif",
        "v": TEMPLATE_VERSION,
        "palette": {"bg": "#FBF8F1", "ink": "#1E2A3A", "sub": "#6E7A88",
                    "accent": "#B08D3E", "line": "#D9CBA8", "panel": "#FFFFFF"},
        "sides": {
            "front": {
                "background": [
                    {"t": "rect", "x": 0, "y": 0, "w": 1, "h": 1, "fill": "bg", "bleed": True},
                    {"t": "rect", "x": 0.045, "y": 0.06, "w": 0.91, "h": 0.88, "stroke": "accent", "strokeW": 0.6},
                    {"t": "rect", "x": 0.055, "y": 0.072, "w": 0.89, "h": 0.856, "stroke": "accent", "strokeW": 0.25},
                ],
                "elements": [
                    {"t": "image", "role": "logo", "x": 0.775, "y": 0.09, "w": 0.14, "h": 0.105, "fit": "contain"},
                    {"t": "text", "field": "company", "x": 0.10, "y": 0.265, "w": 0.80, "h": 0.06,
                     "size": 9, "font": "serifBold", "color": "accent", "align": "center",
                     "caps": True, "track": 0.18},
                    {"t": "line", "x1": 0.43, "y1": 0.345, "x2": 0.57, "y2": 0.345, "stroke": "accent", "w": 0.6},
                    {"t": "text", "field": "name", "x": 0.10, "y": 0.385, "w": 0.80, "h": 0.105,
                     "size": 13, "font": "serifBold", "color": "ink", "align": "center",
                     "caps": True, "track": 0.06},
                    {"t": "text", "field": "title", "x": 0.10, "y": 0.505, "w": 0.80, "h": 0.055,
                     "size": 7.5, "font": "sans", "color": "sub", "align": "center",
                     "caps": True, "track": 0.16},
                    {"t": "text", "field": ["phone", "email"], "x": 0.10, "y": 0.68, "w": 0.80, "h": 0.055,
                     "size": 7.5, "font": "sans", "color": "ink", "align": "center"},
                    {"t": "text", "field": ["website", "address"], "x": 0.10, "y": 0.755, "w": 0.80, "h": 0.055,
                     "size": 7, "font": "sans", "color": "sub", "align": "center"},
                    {"t": "qr", "x": 0.845, "y": 0.795, "w": 0.09, "h": 0.125, "invert": False},
                ],
            },
            "back": back_qr(dark=False),
        },
    })

    # 03 - Midnight Lux (near-black, gold serif, thin gold frame)
    out.append({
        "id": "template-03", "name": "Midnight Lux",
        "desc": "Charcoal black, gold serif name, right-aligned company",
        "v": TEMPLATE_VERSION,
        "palette": {"bg": "#101318", "ink": "#F2F3F5", "sub": "#9AA3AD",
                    "accent": "#C9A227", "line": "#C9A227", "panel": "#FFFFFF"},
        "sides": {
            "front": {
                "background": [
                    {"t": "rect", "x": 0, "y": 0, "w": 1, "h": 1, "fill": "bg", "bleed": True},
                    {"t": "rect", "x": 0.035, "y": 0.055, "w": 0.93, "h": 0.89, "stroke": "accent", "strokeW": 0.45},
                ],
                "elements": [
                    {"t": "image", "role": "logo", "x": 0.775, "y": 0.10, "w": 0.135, "h": 0.105, "fit": "contain"},
                    {"t": "text", "field": "company", "x": 0.07, "y": 0.105, "w": 0.60, "h": 0.05,
                     "size": 8, "font": "sans", "color": "ink", "align": "left",
                     "caps": True, "track": 0.18},
                    {"t": "text", "field": "name", "x": 0.07, "y": 0.45, "w": 0.55, "h": 0.105,
                     "size": 12.5, "font": "serifBold", "color": "accent", "align": "left"},
                    {"t": "text", "field": "title", "x": 0.07, "y": 0.575, "w": 0.55, "h": 0.05,
                     "size": 7.5, "font": "sans", "color": "sub", "align": "left",
                     "caps": True, "track": 0.14},
                    {"t": "line", "x1": 0.07, "y1": 0.665, "x2": 0.21, "y2": 0.665, "stroke": "accent", "w": 0.5},
                    {"t": "text", "field": ["phone", "email"], "x": 0.07, "y": 0.70, "w": 0.60, "h": 0.05,
                     "size": 7.5, "font": "sans", "color": "ink", "align": "left"},
                    {"t": "text", "field": "website", "x": 0.07, "y": 0.765, "w": 0.60, "h": 0.05,
                     "size": 7.5, "font": "sans", "color": "accent", "align": "left"},
                    {"t": "text", "field": "address", "x": 0.07, "y": 0.83, "w": 0.60, "h": 0.05,
                     "size": 7, "font": "sans", "color": "sub", "align": "left"},
                    {"t": "qr", "x": 0.845, "y": 0.785, "w": 0.10, "h": 0.14, "invert": True},
                ],
            },
            "back": back_qr(dark=True),
        },
    })

    # 04 - Corporate Band (navy header band)
    out.append({
        "id": "template-04", "name": "Corporate Band",
        "desc": "Navy header band with logo + company, clean white body",
        "v": TEMPLATE_VERSION,
        "palette": {"bg": "#FFFFFF", "band": "#1B3A5F", "ink": "#1F2937", "sub": "#5B6B7C",
                    "accent": "#1B3A5F", "onband": "#FFFFFF", "onbandSub": "#C7D4E4",
                    "line": "#B9C6D4", "panel": "#EEF2F7"},
        "sides": {
            "front": {
                "background": [
                    {"t": "rect", "x": 0, "y": 0, "w": 1, "h": 1, "fill": "bg", "bleed": True},
                    {"t": "rect", "x": 0, "y": 0, "w": 1, "h": 0.345, "fill": "band", "bleed": True},
                    _frame("accent"),
                ],
                "elements": [
                    {"t": "image", "role": "logo", "x": 0.79, "y": 0.075, "w": 0.15, "h": 0.195, "fit": "contain"},
                    {"t": "text", "field": "company", "x": 0.06, "y": 0.10, "w": 0.65, "h": 0.075,
                     "size": 11, "font": "sansBold", "color": "onband", "align": "left"},
                    {"t": "text", "field": "tagline", "x": 0.062, "y": 0.195, "w": 0.65, "h": 0.045,
                     "size": 6.5, "font": "sans", "color": "onbandSub", "align": "left",
                     "caps": True, "track": 0.12},
                    {"t": "text", "field": "name", "x": 0.06, "y": 0.44, "w": 0.60, "h": 0.085,
                     "size": 11.5, "font": "sansBold", "color": "ink", "align": "left"},
                    {"t": "text", "field": "title", "x": 0.06, "y": 0.545, "w": 0.60, "h": 0.05,
                     "size": 8, "font": "sans", "color": "sub", "align": "left"},
                    {"t": "text", "field": ["phone", "email"], "x": 0.06, "y": 0.655, "w": 0.66, "h": 0.05,
                     "size": 7.5, "font": "sans", "color": "ink", "align": "left"},
                    {"t": "text", "field": "website", "x": 0.06, "y": 0.72, "w": 0.66, "h": 0.05,
                     "size": 7.5, "font": "sans", "color": "accent", "align": "left"},
                    {"t": "text", "field": "address", "x": 0.06, "y": 0.785, "w": 0.66, "h": 0.05,
                     "size": 7, "font": "sans", "color": "sub", "align": "left"},
                    {"t": "rect_qr_panel", "x": 0.755, "y": 0.40, "w": 0.19, "h": 0.385,
                     "fill": "panel", "radius": 0.045},
                    {"t": "qr", "x": 0.775, "y": 0.425, "w": 0.15, "h": 0.335, "invert": False},
                ],
            },
            "back": back_qr(dark=False),
        },
    })

    # 05 - Teal Cut (diagonal teal wedge)
    out.append({
        "id": "template-05", "name": "Teal Cut",
        "desc": "White card with a diagonal teal wedge",
        "v": TEMPLATE_VERSION,
        "palette": {"bg": "#FFFFFF", "ink": "#0F172A", "sub": "#64748B",
                    "accent": "#0F766E", "line": "#94A3B8", "panel": "#FFFFFF"},
        "sides": {
            "front": {
                "background": [
                    {"t": "rect", "x": 0, "y": 0, "w": 1, "h": 1, "fill": "bg", "bleed": True},
                    {"t": "poly", "pts": [[0.60, 1.04], [1.04, 1.04], [1.04, 0.34]], "fill": "accent"},
                    _frame("accent"),
                ],
                "elements": [
                    {"t": "image", "role": "logo", "x": 0.795, "y": 0.075, "w": 0.135, "h": 0.115, "fit": "contain"},
                    {"t": "rect", "x": 0.07, "y": 0.33, "w": 0.085, "h": 0.012, "fill": "accent"},
                    {"t": "text", "field": "name", "x": 0.07, "y": 0.365, "w": 0.55, "h": 0.09,
                     "size": 12, "font": "sansBold", "color": "ink", "align": "left"},
                    {"t": "text", "field": "title", "x": 0.07, "y": 0.475, "w": 0.55, "h": 0.05,
                     "size": 7.5, "font": "sans", "color": "accent", "align": "left",
                     "caps": True, "track": 0.14},
                    {"t": "text", "field": ["phone", "email"], "x": 0.07, "y": 0.625, "w": 0.55, "h": 0.05,
                     "size": 7.5, "font": "sans", "color": "ink", "align": "left"},
                    {"t": "text", "field": "website", "x": 0.07, "y": 0.69, "w": 0.55, "h": 0.05,
                     "size": 7.5, "font": "sans", "color": "accent", "align": "left"},
                    {"t": "text", "field": "address", "x": 0.07, "y": 0.755, "w": 0.55, "h": 0.05,
                     "size": 7, "font": "sans", "color": "sub", "align": "left"},
                    {"t": "qr", "x": 0.795, "y": 0.775, "w": 0.13, "h": 0.165, "panel": True,
                     "panel_color": "bg", "invert": False},
                ],
            },
            "back": back_qr(dark=False),
        },
    })

    # 06 - Heritage Cream (serif, italic title, bronze)
    out.append({
        "id": "template-06", "name": "Heritage Cream",
        "desc": "Cream paper, bronze rules, serif + italic",
        "v": TEMPLATE_VERSION,
        "palette": {"bg": "#F6F0E4", "ink": "#43392B", "sub": "#8A7A5F",
                    "accent": "#8A6D3B", "line": "#C9B98F", "panel": "#FFFFFF"},
        "sides": {
            "front": {
                "background": [
                    {"t": "rect", "x": 0, "y": 0, "w": 1, "h": 1, "fill": "bg", "bleed": True},
                    {"t": "rect", "x": 0.04, "y": 0.055, "w": 0.92, "h": 0.89, "stroke": "line", "strokeW": 0.5},
                ],
                "elements": [
                    {"t": "image", "role": "logo", "x": 0.775, "y": 0.085, "w": 0.135, "h": 0.105, "fit": "contain"},
                    {"t": "text", "field": "company", "x": 0.10, "y": 0.24, "w": 0.80, "h": 0.055,
                     "size": 8.5, "font": "serifBold", "color": "accent", "align": "center",
                     "caps": True, "track": 0.22},
                    {"t": "line", "x1": 0.44, "y1": 0.325, "x2": 0.56, "y2": 0.325, "stroke": "line", "w": 0.6},
                    {"t": "text", "field": "name", "x": 0.08, "y": 0.36, "w": 0.84, "h": 0.10,
                     "size": 12.5, "font": "serifBold", "color": "ink", "align": "center",
                     "caps": True, "track": 0.08},
                    {"t": "text", "field": "title", "x": 0.10, "y": 0.485, "w": 0.80, "h": 0.05,
                     "size": 8, "font": "serifItal", "color": "sub", "align": "center"},
                    {"t": "text", "field": ["phone", "email"], "x": 0.10, "y": 0.675, "w": 0.80, "h": 0.05,
                     "size": 7.5, "font": "sans", "color": "ink", "align": "center"},
                    {"t": "text", "field": ["website", "address"], "x": 0.10, "y": 0.745, "w": 0.80, "h": 0.05,
                     "size": 7, "font": "sans", "color": "sub", "align": "center"},
                    {"t": "qr", "x": 0.855, "y": 0.80, "w": 0.09, "h": 0.12, "invert": False},
                ],
            },
            "back": back_qr(dark=False),
        },
    })

    # 07 - Azure Bold (deep blue, cyan accents)
    out.append({
        "id": "template-07", "name": "Azure Bold",
        "desc": "Deep blue with a cyan edge stripe",
        "v": TEMPLATE_VERSION,
        "palette": {"bg": "#0A3D91", "ink": "#FFFFFF", "sub": "#BBD0F0",
                    "accent": "#38BDF8", "line": "#38BDF8", "panel": "#FFFFFF"},
        "sides": {
            "front": {
                "background": [
                    {"t": "rect", "x": 0, "y": 0, "w": 1, "h": 1, "fill": "bg", "bleed": True},
                    {"t": "rect", "x": 0, "y": 0, "w": 0.02, "h": 1, "fill": "accent", "bleed": True},
                    _frame("accent"),
                ],
                "elements": [
                    {"t": "text", "field": "company", "x": 0.07, "y": 0.115, "w": 0.50, "h": 0.065,
                     "size": 10.5, "font": "sansBold", "color": "ink", "align": "left",
                     "caps": True, "track": 0.16},
                    {"t": "image", "role": "logo", "x": 0.72, "y": 0.075, "w": 0.21, "h": 0.165, "fit": "contain"},
                    {"t": "text", "field": "name", "x": 0.07, "y": 0.43, "w": 0.60, "h": 0.095,
                     "size": 12, "font": "sansBold", "color": "ink", "align": "left"},
                    {"t": "text", "field": "title", "x": 0.07, "y": 0.555, "w": 0.60, "h": 0.05,
                     "size": 7.5, "font": "sans", "color": "accent", "align": "left",
                     "caps": True, "track": 0.12},
                    {"t": "line", "x1": 0.07, "y1": 0.675, "x2": 0.205, "y2": 0.675, "stroke": "accent", "w": 0.6},
                    {"t": "text", "field": ["phone", "email"], "x": 0.07, "y": 0.715, "w": 0.60, "h": 0.05,
                     "size": 7.5, "font": "sans", "color": "ink", "align": "left"},
                    {"t": "text", "field": "website", "x": 0.07, "y": 0.78, "w": 0.60, "h": 0.05,
                     "size": 7.5, "font": "sans", "color": "accent", "align": "left"},
                    {"t": "text", "field": "address", "x": 0.07, "y": 0.845, "w": 0.60, "h": 0.05,
                     "size": 7, "font": "sans", "color": "sub", "align": "left"},
                    {"t": "qr", "x": 0.84, "y": 0.78, "w": 0.105, "h": 0.145, "panel": True, "invert": False},
                ],
            },
            "back": back_qr(dark=True),
        },
    })

    # 08 - Split Brand (deep green left panel)
    out.append({
        "id": "template-08", "name": "Split Brand",
        "desc": "Solid brand panel on the left, contact block on the right",
        "v": TEMPLATE_VERSION,
        "palette": {"bg": "#FFFFFF", "panel": "#14532D", "ink": "#1F2937", "sub": "#6B7280",
                    "accent": "#14532D", "line": "#14532D", "onpanel": "#FFFFFF",
                    "onpanelSub": "#A7C4B5"},
        "sides": {
            "front": {
                "background": [
                    {"t": "rect", "x": 0, "y": 0, "w": 1, "h": 1, "fill": "bg", "bleed": True},
                    {"t": "rect", "x": 0, "y": 0, "w": 0.375, "h": 1, "fill": "panel", "bleed": True},
                    _frame("accent"),
                ],
                "elements": [
                    {"t": "image", "role": "logo", "x": 0.775, "y": 0.085, "w": 0.15, "h": 0.12, "fit": "contain"},
                    {"t": "text", "field": "company", "x": 0.055, "y": 0.635, "w": 0.265, "h": 0.05,
                     "size": 7.5, "font": "sansBold", "color": "onpanel", "align": "center",
                     "caps": True, "track": 0.14},
                    {"t": "text", "field": "name", "x": 0.47, "y": 0.325, "w": 0.46, "h": 0.09,
                     "size": 12, "font": "sansBold", "color": "ink", "align": "left"},
                    {"t": "text", "field": "title", "x": 0.47, "y": 0.445, "w": 0.46, "h": 0.05,
                     "size": 7.5, "font": "sans", "color": "accent", "align": "left",
                     "caps": True, "track": 0.10},
                    {"t": "line", "x1": 0.47, "y1": 0.535, "x2": 0.56, "y2": 0.535, "stroke": "accent", "w": 0.6},
                    {"t": "text", "field": ["phone", "email"], "x": 0.47, "y": 0.585, "w": 0.46, "h": 0.05,
                     "size": 7.5, "font": "sans", "color": "ink", "align": "left"},
                    {"t": "text", "field": "website", "x": 0.47, "y": 0.65, "w": 0.46, "h": 0.05,
                     "size": 7.5, "font": "sans", "color": "accent", "align": "left"},
                    {"t": "text", "field": "address", "x": 0.47, "y": 0.715, "w": 0.46, "h": 0.05,
                     "size": 7, "font": "sans", "color": "sub", "align": "left"},
                    {"t": "qr", "x": 0.855, "y": 0.80, "w": 0.10, "h": 0.13, "invert": False},
                ],
            },
            "back": back_qr(dark=True, bg_key="panel", line_key="onpanel"),
        },
    })

    # 09 - Mono Minimal (pure white, single rule)
    out.append({
        "id": "template-09", "name": "Mono Minimal",
        "desc": "Ultra-clean black on white with one rule",
        "v": TEMPLATE_VERSION,
        "palette": {"bg": "#FFFFFF", "ink": "#111111", "sub": "#555555",
                    "accent": "#111111", "line": "#111111", "panel": "#FFFFFF"},
        "sides": {
            "front": {
                "background": [
                    {"t": "rect", "x": 0, "y": 0, "w": 1, "h": 1, "fill": "bg", "bleed": True},
                    _frame("accent"),
                ],
                "elements": [
                    {"t": "image", "role": "logo", "x": 0.80, "y": 0.075, "w": 0.12, "h": 0.10, "fit": "contain"},
                    {"t": "text", "field": "company", "x": 0.08, "y": 0.10, "w": 0.60, "h": 0.05,
                     "size": 7.5, "font": "sans", "color": "ink", "align": "left",
                     "caps": True, "track": 0.20},
                    {"t": "text", "field": "name", "x": 0.08, "y": 0.375, "w": 0.62, "h": 0.085,
                     "size": 11, "font": "sansBold", "color": "ink", "align": "left"},
                    {"t": "text", "field": "title", "x": 0.08, "y": 0.475, "w": 0.62, "h": 0.045,
                     "size": 7.5, "font": "sans", "color": "sub", "align": "left"},
                    {"t": "line", "x1": 0.08, "y1": 0.565, "x2": 0.24, "y2": 0.565, "stroke": "line", "w": 1.1},
                    {"t": "text", "field": ["phone", "email"], "x": 0.08, "y": 0.62, "w": 0.62, "h": 0.05,
                     "size": 7.5, "font": "sans", "color": "ink", "align": "left"},
                    {"t": "text", "field": "website", "x": 0.08, "y": 0.685, "w": 0.62, "h": 0.05,
                     "size": 7, "font": "sans", "color": "sub", "align": "left"},
                    {"t": "text", "field": "address", "x": 0.08, "y": 0.75, "w": 0.62, "h": 0.05,
                     "size": 7, "font": "sans", "color": "sub", "align": "left"},
                    {"t": "qr", "x": 0.865, "y": 0.80, "w": 0.085, "h": 0.115, "invert": False},
                ],
            },
            "back": back_qr(dark=False),
        },
    })

    # 10 - Portrait Focus (circular photo right)
    out.append({
        "id": "template-10", "name": "Portrait Focus",
        "desc": "Big circular photo on the right, contacts on the left",
        "v": TEMPLATE_VERSION,
        "palette": {"bg": "#FFFFFF", "ink": "#2D2A26", "sub": "#8A8378",
                    "accent": "#C05621", "line": "#C05621", "panel": "#F5EDE4"},
        "sides": {
            "front": {
                "background": [
                    {"t": "rect", "x": 0, "y": 0, "w": 1, "h": 1, "fill": "bg", "bleed": True},
                    {"t": "ellipse", "x": 0.565, "y": 0.145, "w": 0.37, "h": 0.71,
                     "stroke": "accent", "strokeW": 1.0, "circle": True},
                    _frame("accent"),
                ],
                "elements": [
                    {"t": "image", "role": "photo", "x": 0.585, "y": 0.175, "w": 0.33, "h": 0.64,
                     "fit": "cover", "shape": "circle", "fallback_logo": True,
                     "fb_fill": "panel", "fb_size": 8, "fb_font": "sansBold",
                     "fb_color": "accent"},
                    {"t": "text", "field": "company", "x": 0.07, "y": 0.125, "w": 0.46, "h": 0.06,
                     "size": 9.5, "font": "sansBold", "color": "accent", "align": "left",
                     "caps": True, "track": 0.14},
                    {"t": "text", "field": "name", "x": 0.07, "y": 0.40, "w": 0.46, "h": 0.09,
                     "size": 11.5, "font": "sansBold", "color": "ink", "align": "left"},
                    {"t": "text", "field": "title", "x": 0.07, "y": 0.51, "w": 0.46, "h": 0.05,
                     "size": 7.5, "font": "sans", "color": "sub", "align": "left",
                     "caps": True, "track": 0.10},
                    {"t": "line", "x1": 0.07, "y1": 0.60, "x2": 0.17, "y2": 0.60, "stroke": "accent", "w": 0.7},
                    {"t": "text", "field": ["phone", "email"], "x": 0.07, "y": 0.645, "w": 0.46, "h": 0.05,
                     "size": 7.5, "font": "sans", "color": "ink", "align": "left"},
                    {"t": "text", "field": "website", "x": 0.07, "y": 0.71, "w": 0.46, "h": 0.05,
                     "size": 7.5, "font": "sans", "color": "accent", "align": "left"},
                    {"t": "text", "field": "address", "x": 0.07, "y": 0.775, "w": 0.46, "h": 0.05,
                     "size": 7, "font": "sans", "color": "sub", "align": "left"},
                    {"t": "qr", "x": 0.07, "y": 0.835, "w": 0.085, "h": 0.11, "invert": False},
                ],
            },
            "back": back_qr(dark=False),
        },
    })

    # ---------------------------------------------------------- smart cards
    # 11–20: styled for NFC / PVC / metal card printing — 4-side frame (or
    # corner brackets), a metallic chip decal + "NFC" mark, brushed-metal
    # hairline banding. Built on the shared _smart_front() skeleton except
    # where the layout itself needed to differ (13, 14, 18).

    # 11 - Gunmetal Chip (brushed steel, silver chip)
    out.append({
        "id": "template-11", "name": "Gunmetal Chip",
        "desc": "Brushed gunmetal steel, silver frame + chip — NFC / metal card",
        "v": TEMPLATE_VERSION,
        "palette": {"bg": "#2A2D31", "ink": "#F2F3F4", "sub": "#9AA0A7",
                    "accent": "#C9CDD2", "line": "#C9CDD2", "panel": "#34383D"},
        "sides": {
            "front": _smart_front(
                extra_bg=_hairlines(7, "panel"),
                chip_plate="accent", chip_grid="bg", nfc_color="accent",
                name_font="sansBold", website_color="accent", qr_invert=True,
            ),
            "back": back_qr(dark=True),
        },
    })

    # 12 - Rose Gold Steel (matte black, rose-gold chip + frame)
    out.append({
        "id": "template-12", "name": "Rose Gold Steel",
        "desc": "Matte black metal card, rose-gold frame + chip",
        "v": TEMPLATE_VERSION,
        "palette": {"bg": "#141013", "ink": "#FFFFFF", "sub": "#BBA9AC",
                    "accent": "#B76E79", "line": "#B76E79", "panel": "#241A1D"},
        "sides": {
            "front": _smart_front(
                chip_plate="accent", chip_grid="bg", nfc_color="accent",
                name_font="serifBold", website_color="accent", qr_invert=True,
            ),
            "back": back_qr(dark=True),
        },
    })

    # 13 - Carbon Weave (diagonal weave corner, amber tech accent)
    out.append({
        "id": "template-13", "name": "Carbon Weave",
        "desc": "Carbon-fibre corner weave, amber tech accent — NFC metal card",
        "v": TEMPLATE_VERSION,
        "palette": {"bg": "#17181A", "ink": "#FFFFFF", "sub": "#9CA3A8",
                    "accent": "#FF6A3D", "line": "#FF6A3D", "panel": "#1F2124"},
        "sides": {
            "front": {
                "background": [
                    {"t": "rect", "x": 0, "y": 0, "w": 1, "h": 1, "fill": "bg", "bleed": True},
                    {"t": "poly", "pts": [[0.58, -0.04], [1.04, -0.04], [1.04, 0.46]], "fill": "panel"},
                    {"t": "line", "x1": 0.66, "y1": -0.02, "x2": 0.80, "y2": 0.42, "stroke": "accent", "w": 0.35},
                    {"t": "line", "x1": 0.78, "y1": -0.02, "x2": 0.92, "y2": 0.42, "stroke": "accent", "w": 0.35},
                    {"t": "line", "x1": 0.90, "y1": -0.02, "x2": 1.02, "y2": 0.34, "stroke": "accent", "w": 0.35},
                    _frame("accent"),
                    *_chip(0.055, 0.855, 0.115, 0.078, "accent", "bg"),
                ],
                "elements": [
                    {"t": "image", "role": "logo", "x": 0.795, "y": 0.09, "w": 0.125, "h": 0.10, "fit": "contain"},
                    {"t": "text", "field": "company", "x": 0.07, "y": 0.09, "w": 0.55, "h": 0.05,
                     "size": 8, "font": "sans", "color": "sub", "align": "left", "caps": True, "track": 0.18},
                    {"t": "text", "field": "name", "x": 0.07, "y": 0.40, "w": 0.60, "h": 0.10,
                     "size": 12.5, "font": "sansBold", "color": "ink", "align": "left"},
                    {"t": "text", "field": "title", "x": 0.07, "y": 0.525, "w": 0.60, "h": 0.05,
                     "size": 7.5, "font": "sans", "color": "accent", "align": "left",
                     "caps": True, "track": 0.14},
                    {"t": "line", "x1": 0.07, "y1": 0.615, "x2": 0.21, "y2": 0.615, "stroke": "accent", "w": 0.5},
                    {"t": "text", "field": ["phone", "email"], "x": 0.07, "y": 0.65, "w": 0.60, "h": 0.05,
                     "size": 7.5, "font": "sans", "color": "ink", "align": "left"},
                    {"t": "text", "field": "website", "x": 0.07, "y": 0.715, "w": 0.60, "h": 0.05,
                     "size": 7.5, "font": "sans", "color": "accent", "align": "left"},
                    {"t": "text", "lit": "NFC", "x": 0.185, "y": 0.863, "w": 0.12, "h": 0.045,
                     "size": 6.5, "font": "sansBold", "color": "accent", "align": "left",
                     "caps": True, "track": 0.32},
                    {"t": "qr", "x": 0.845, "y": 0.785, "w": 0.10, "h": 0.14, "invert": True},
                ],
            },
            "back": back_qr(dark=True),
        },
    })

    # 14 - Gold Foil Onyx (centered luxury double frame, black + gold)
    out.append({
        "id": "template-14", "name": "Gold Foil Onyx",
        "desc": "Onyx black, double gold foil frame, centered serif — metal card",
        "v": TEMPLATE_VERSION,
        "palette": {"bg": "#000000", "ink": "#FFFFFF", "sub": "#C9C9C9",
                    "accent": "#D4AF37", "line": "#D4AF37", "panel": "#141414"},
        "sides": {
            "front": {
                "background": [
                    {"t": "rect", "x": 0, "y": 0, "w": 1, "h": 1, "fill": "bg", "bleed": True},
                    _frame("accent", inset=0.045, sw=0.55),
                    _frame("accent", inset=0.06, sw=0.22),
                    *_chip(0.055, 0.855, 0.115, 0.078, "accent", "bg"),
                ],
                "elements": [
                    {"t": "image", "role": "logo", "x": 0.775, "y": 0.09, "w": 0.14, "h": 0.105, "fit": "contain"},
                    {"t": "text", "field": "company", "x": 0.10, "y": 0.20, "w": 0.80, "h": 0.06,
                     "size": 9, "font": "serifBold", "color": "accent", "align": "center",
                     "caps": True, "track": 0.18},
                    {"t": "line", "x1": 0.43, "y1": 0.285, "x2": 0.57, "y2": 0.285, "stroke": "accent", "w": 0.6},
                    {"t": "text", "field": "name", "x": 0.10, "y": 0.325, "w": 0.80, "h": 0.105,
                     "size": 13, "font": "serifBold", "color": "ink", "align": "center",
                     "caps": True, "track": 0.06},
                    {"t": "text", "field": "title", "x": 0.10, "y": 0.445, "w": 0.80, "h": 0.055,
                     "size": 7.5, "font": "sans", "color": "sub", "align": "center",
                     "caps": True, "track": 0.16},
                    {"t": "text", "field": ["phone", "email"], "x": 0.10, "y": 0.605, "w": 0.80, "h": 0.055,
                     "size": 7.5, "font": "sans", "color": "ink", "align": "center"},
                    {"t": "text", "field": "website", "x": 0.10, "y": 0.675, "w": 0.80, "h": 0.05,
                     "size": 7.5, "font": "sans", "color": "accent", "align": "center"},
                    {"t": "text", "lit": "NFC", "x": 0.185, "y": 0.863, "w": 0.12, "h": 0.045,
                     "size": 6.5, "font": "sansBold", "color": "accent", "align": "left",
                     "caps": True, "track": 0.32},
                    {"t": "qr", "x": 0.845, "y": 0.785, "w": 0.10, "h": 0.14, "invert": True},
                ],
            },
            "back": back_qr(dark=True),
        },
    })

    # 15 - Chrome Line (light brushed aluminium, tech blue accent)
    out.append({
        "id": "template-15", "name": "Chrome Line",
        "desc": "Brushed aluminium light metal, tech-blue accent — PVC smart card",
        "v": TEMPLATE_VERSION,
        "palette": {"bg": "#EDEEF0", "ink": "#1F2933", "sub": "#5B6570",
                    "accent": "#1D4ED8", "line": "#1D4ED8", "panel": "#E1E3E6"},
        "sides": {
            "front": _smart_front(
                extra_bg=_hairlines(7, "panel"),
                chip_plate="accent", chip_grid="ink", nfc_color="accent",
                name_font="sansBold", website_color="accent", qr_invert=False,
            ),
            "back": back_qr(dark=False),
        },
    })

    # 16 - Signal Navy (dark navy/cyan tech)
    out.append({
        "id": "template-16", "name": "Signal Navy",
        "desc": "Deep navy tech surface, cyan frame + chip — NFC smart card",
        "v": TEMPLATE_VERSION,
        "palette": {"bg": "#071A2E", "ink": "#FFFFFF", "sub": "#8FA6BD",
                    "accent": "#22D3EE", "line": "#22D3EE", "panel": "#0D2740"},
        "sides": {
            "front": _smart_front(
                extra_bg=_hairlines(7, "panel"),
                chip_plate="accent", chip_grid="bg", nfc_color="accent",
                name_font="sansBold", website_color="accent", qr_invert=True,
            ),
            "back": back_qr(dark=True),
        },
    })

    # 17 - Matte Black Frame (minimal matte black + silver frame/chip)
    out.append({
        "id": "template-17", "name": "Matte Black Frame",
        "desc": "Matte black minimal, silver frame + chip — metal card",
        "v": TEMPLATE_VERSION,
        "palette": {"bg": "#0A0A0A", "ink": "#FFFFFF", "sub": "#8C8C8C",
                    "accent": "#D9D9D9", "line": "#D9D9D9", "panel": "#141414"},
        "sides": {
            "front": _smart_front(
                chip_plate="accent", chip_grid="bg", nfc_color="accent",
                name_font="sansBold", website_color="accent", qr_invert=True,
            ),
            "back": back_qr(dark=True),
        },
    })

    # 18 - Titanium Split (gunmetal panel + orange, chip on panel)
    out.append({
        "id": "template-18", "name": "Titanium Split",
        "desc": "Gunmetal side panel, orange tech accent — NFC PVC card",
        "v": TEMPLATE_VERSION,
        "palette": {"bg": "#FFFFFF", "panel": "#2E3238", "ink": "#1F2937", "sub": "#6B7280",
                    "accent": "#FF7A00", "line": "#FF7A00", "onpanel": "#FFFFFF",
                    "onpanelSub": "#C7CBCE"},
        "sides": {
            "front": {
                "background": [
                    {"t": "rect", "x": 0, "y": 0, "w": 1, "h": 1, "fill": "bg", "bleed": True},
                    {"t": "rect", "x": 0, "y": 0, "w": 0.375, "h": 1, "fill": "panel", "bleed": True},
                    _frame("accent"),
                    *_chip(0.055, 0.805, 0.10, 0.072, "accent", "onpanel"),
                ],
                "elements": [
                    {"t": "image", "role": "logo", "x": 0.775, "y": 0.085, "w": 0.15, "h": 0.12, "fit": "contain"},
                    {"t": "text", "field": "company", "x": 0.045, "y": 0.635, "w": 0.285, "h": 0.05,
                     "size": 7.5, "font": "sansBold", "color": "onpanel", "align": "center",
                     "caps": True, "track": 0.12},
                    {"t": "text", "field": "name", "x": 0.47, "y": 0.325, "w": 0.46, "h": 0.09,
                     "size": 12, "font": "sansBold", "color": "ink", "align": "left"},
                    {"t": "text", "field": "title", "x": 0.47, "y": 0.445, "w": 0.46, "h": 0.05,
                     "size": 7.5, "font": "sans", "color": "accent", "align": "left",
                     "caps": True, "track": 0.10},
                    {"t": "line", "x1": 0.47, "y1": 0.535, "x2": 0.56, "y2": 0.535, "stroke": "accent", "w": 0.6},
                    {"t": "text", "field": ["phone", "email"], "x": 0.47, "y": 0.585, "w": 0.46, "h": 0.05,
                     "size": 7.5, "font": "sans", "color": "ink", "align": "left"},
                    {"t": "text", "field": "website", "x": 0.47, "y": 0.65, "w": 0.46, "h": 0.05,
                     "size": 7.5, "font": "sans", "color": "accent", "align": "left"},
                    {"t": "text", "lit": "NFC", "x": 0.045, "y": 0.885, "w": 0.24, "h": 0.04,
                     "size": 6.5, "font": "sansBold", "color": "onpanelSub", "align": "center",
                     "caps": True, "track": 0.3},
                    {"t": "qr", "x": 0.855, "y": 0.775, "w": 0.10, "h": 0.13, "invert": False},
                ],
            },
            "back": back_qr(dark=True, bg_key="panel", line_key="onpanel"),
        },
    })

    # 19 - Onyx Double Gold (asymmetric, serif gold, double frame)
    out.append({
        "id": "template-19", "name": "Onyx Double Gold",
        "desc": "Onyx black, double gold frame, serif name — metal card",
        "v": TEMPLATE_VERSION,
        "palette": {"bg": "#0D0D0D", "ink": "#FFFFFF", "sub": "#ADB0B6",
                    "accent": "#C9A227", "line": "#C9A227", "panel": "#1A1A1A"},
        "sides": {
            "front": _smart_front(
                extra_bg=[_frame("accent", inset=0.06, sw=0.24)],
                chip_plate="accent", chip_grid="bg", nfc_color="accent",
                name_font="serifBold", website_color="accent", qr_invert=True,
            ),
            "back": back_qr(dark=True),
        },
    })

    # 20 - Graphite Copper (corner brackets instead of a full frame)
    out.append({
        "id": "template-20", "name": "Graphite Copper",
        "desc": "Graphite metal, copper corner brackets + chip — NFC card",
        "v": TEMPLATE_VERSION,
        "palette": {"bg": "#1C1C1E", "ink": "#FFFFFF", "sub": "#9C9C9E",
                    "accent": "#C77B4D", "line": "#C77B4D", "panel": "#262628"},
        "sides": {
            "front": _smart_front(
                frame_mode="corners",
                chip_plate="accent", chip_grid="bg", nfc_color="accent",
                name_font="sansBold", website_color="accent", qr_invert=True,
            ),
            "back": back_qr(dark=True),
        },
    })

    return out


def _fix_rect_qr_panel(tpl: dict) -> None:
    """Convert marker 'rect_qr_panel' into a real rect element placed before the qr."""
    for side in tpl["sides"].values():
        els = side.get("elements") or []
        for i, el in enumerate(els):
            if el.get("t") == "rect_qr_panel":
                els[i] = {
                    "t": "rect", "x": el["x"], "y": el["y"], "w": el["w"], "h": el["h"],
                    "fill": el["fill"], "radius": el["radius"],
                }


def build_all(force: bool = False) -> None:
    for tpl in templates():
        _fix_rect_qr_panel(tpl)
        tdir = TEMPLATES_DIR / tpl["id"]
        tdir.mkdir(parents=True, exist_ok=True)
        jpath = tdir / "template.json"
        need = force or not jpath.exists()
        if not need:
            try:
                need = json.loads(jpath.read_text(encoding="utf-8")).get("v") != TEMPLATE_VERSION
            except Exception:
                need = True
        if need:
            jpath.write_text(json.dumps(tpl, indent=2, ensure_ascii=False), encoding="utf-8")
        thumb = tdir / "preview.png"
        # rebuild when missing, when template.json was just rewritten,
        # or when the default logo file changed
        stale = not thumb.exists() or thumb.stat().st_mtime < jpath.stat().st_mtime or (
            DEFAULT_LOGO.is_file() and DEFAULT_LOGO.stat().st_mtime > thumb.stat().st_mtime
        )
        if stale:
            logo = DEFAULT_LOGO if DEFAULT_LOGO.is_file() else None
            qr_img = qrsvc.build({"type": "vcard", "value": "", "logo_in_qr": False},
                                 SAMPLE_DATA, None,
                                 invert=qr_invert(tpl), logo_in_qr=False)
            img = render_stacked(tpl, SAMPLE_DATA, {"logo": logo, "photo": None}, qr_img, 150)
            img.thumbnail((520, 4000), Image.LANCZOS)
            img.save(thumb)


def load(template_id: str) -> dict | None:
    if not re.fullmatch(r"template-\d{1,3}", template_id):
        return None
    p = TEMPLATES_DIR / template_id / "template.json"
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def list_templates() -> list[dict]:
    out = []
    if TEMPLATES_DIR.is_dir():
        for d in sorted(TEMPLATES_DIR.iterdir()):
            j = d / "template.json"
            if d.is_dir() and j.exists():
                t = json.loads(j.read_text(encoding="utf-8"))
                out.append({
                    "id": t["id"], "name": t.get("name", t["id"]),
                    "desc": t.get("desc", ""),
                    "preview": f"/templates/{t['id']}/preview.png",
                })
    return out
