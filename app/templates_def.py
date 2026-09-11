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

TEMPLATE_VERSION = 5

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
                "background": [{"t": "rect", "x": 0, "y": 0, "w": 1, "h": 1, "fill": "bg", "bleed": True}],
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
                "background": [{"t": "rect", "x": 0, "y": 0, "w": 1, "h": 1, "fill": "bg", "bleed": True}],
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
