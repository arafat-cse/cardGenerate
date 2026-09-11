"""Shared layout engine.

Templates are data (templates/template-XX/template.json). resolve_side()
turns a card side + user data into a flat list of primitive items with
absolute coordinates in points (origin: trim top-left, y grows downward).
The Pillow renderer and the Illustrator JSX script both consume the same
items, so the PNG/PDF/preview and the .ai file match each other.
"""

from .. import fonts
from ..config import BLEED_IN, CARD_H_IN, CARD_W_IN

CARD_W_PT = CARD_W_IN * 72.0
CARD_H_PT = CARD_H_IN * 72.0
BLEED_PT = BLEED_IN * 72.0
GAP_PT = 12.0  # gap between front/back artboards in the .ai file

_MEAS_DPI = 300


def _pt(v_norm: float, card_pt: float) -> float:
    return v_norm * card_pt


def resolve_text_field(el: dict, data: dict) -> str:
    f = el.get("field")
    if isinstance(f, list):
        parts = [str(data.get(k) or "").strip() for k in f]
        return "  ·  ".join(p for p in parts if p)
    return str(data.get(f or "") or "").strip()


def _text_item(el: dict, s: str, pal: dict) -> dict:
    x = _pt(el["x"], CARD_W_PT)
    y = _pt(el["y"], CARD_H_PT)
    w = _pt(el["w"], CARD_W_PT)
    h = _pt(el["h"], CARD_H_PT)
    base = float(el["size"])
    track = float(el.get("track", 0) or 0)
    info = fonts.resolve(el["font"])

    px = base * _MEAS_DPI / 72.0
    maxw = max(1.0, w * _MEAS_DPI / 72.0)

    def width_at(p: float) -> float:
        f = fonts.load_path(info["path"], max(4, int(round(p))))
        return f.getlength(s) + track * p * max(0, len(s) - 1)

    wd = width_at(px)
    if wd > maxw and wd > 0:
        px = max(px * maxw / wd, px * 0.5)

    pxi = max(4, int(round(px)))
    f = fonts.load_path(info["path"], pxi)
    asc, desc = f.getmetrics()
    cy = y + h / 2.0
    y_top = cy - (asc + desc) / 2.0 * 72.0 / _MEAS_DPI

    return {
        "t": "text", "s": s, "x": x, "y": y, "w": w, "h": h,
        "size": pxi * 72.0 / _MEAS_DPI, "yTop": y_top,
        "font": info["ps"], "family": info["family"], "style": info["style"],
        "ttf": info["path"], "color": pal.get(el["color"], "#000000"),
        "align": el.get("align", "left"), "track": track,
    }


def _image_box(el: dict) -> dict:
    return {
        "t": "image", "src": el["role"],
        "x": _pt(el["x"], CARD_W_PT), "y": _pt(el["y"], CARD_H_PT),
        "w": _pt(el["w"], CARD_W_PT), "h": _pt(el["h"], CARD_H_PT),
        "fit": el.get("fit", "contain"),
        "circle": el.get("shape") == "circle",
    }


def _photo_fallback_items(el: dict, pal: dict, has_logo: bool, data: dict) -> list[dict]:
    x = _pt(el["x"], CARD_W_PT)
    y = _pt(el["y"], CARD_H_PT)
    w = _pt(el["w"], CARD_W_PT)
    h = _pt(el["h"], CARD_H_PT)
    d = min(w, h)
    bx = x + (w - d) / 2.0
    by = y + (h - d) / 2.0
    fill = pal.get(el.get("fb_fill", "panel"), "#EEEEEE")
    items: list[dict] = [{"t": "ellipse", "x": bx, "y": by, "w": d, "h": d, "fill": fill}]
    if has_logo:
        ins = d * 0.20
        items.append({
            "t": "image", "src": "logo", "x": bx + ins, "y": by + ins,
            "w": d - 2 * ins, "h": d - 2 * ins, "fit": "contain", "circle": False,
        })
    else:
        # center the text in the circle's inner square
        inner = d * 0.68
        cx = bx + d / 2.0
        cy = by + d / 2.0
        fb = {
            "x": (cx - inner / 2.0) / CARD_W_PT,
            "y": (cy - inner / 2.0) / CARD_H_PT,
            "w": inner / CARD_W_PT,
            "h": inner / CARD_H_PT,
            "size": el.get("fb_size", 10), "font": el.get("fb_font", "sansBold"),
            "color": el.get("fb_color", "ink"), "align": "center",
            "track": el.get("fb_track", 0.1), "caps": True, "field": "company",
        }
        s = resolve_text_field(fb, data)
        if s:
            items.append(_text_item(fb, s.upper(), pal))
    return items


def resolve_side(tpl: dict, side: dict, data: dict, has: dict) -> list[dict]:
    pal = tpl["palette"]
    items: list[dict] = []

    def col(key_or_hex):
        return pal.get(key_or_hex, key_or_hex)

    for b in side.get("background", []):
        if b["t"] == "line":
            items.append({
                "t": "line",
                "x1": _pt(b["x1"], CARD_W_PT), "y1": _pt(b["y1"], CARD_H_PT),
                "x2": _pt(b["x2"], CARD_W_PT), "y2": _pt(b["y2"], CARD_H_PT),
                "stroke": col(b["stroke"]), "w": b.get("w", 0.5),
            })
            continue
        if b["t"] == "poly":
            items.append({
                "t": "poly",
                "pts": [[_pt(px, CARD_W_PT), _pt(py, CARD_H_PT)] for px, py in b["pts"]],
                "fill": col(b["fill"]) if b.get("fill") else None,
            })
            continue

        x = _pt(b["x"], CARD_W_PT)
        y = _pt(b["y"], CARD_H_PT)
        w = _pt(b["w"], CARD_W_PT)
        h = _pt(b["h"], CARD_H_PT)
        if b.get("bleed"):
            if b["x"] <= 1e-6:
                x -= BLEED_PT
                w += BLEED_PT
            if b["x"] + b["w"] >= 1 - 1e-6:
                w += BLEED_PT
            if b["y"] <= 1e-6:
                y -= BLEED_PT
                h += BLEED_PT
            if b["y"] + b["h"] >= 1 - 1e-6:
                h += BLEED_PT
        if b["t"] == "rect":
            items.append({
                "t": "rect", "x": x, "y": y, "w": w, "h": h,
                "fill": col(b["fill"]) if b.get("fill") else None,
                "stroke": col(b["stroke"]) if b.get("stroke") else None,
                "strokeW": b.get("strokeW"),
                "radius": b.get("radius", 0) * CARD_H_PT,
            })
        elif b["t"] == "ellipse":
            items.append({
                "t": "ellipse", "x": x, "y": y, "w": w, "h": h,
                "fill": col(b["fill"]) if b.get("fill") else None,
                "stroke": col(b["stroke"]) if b.get("stroke") else None,
                "strokeW": b.get("strokeW"),
                "circle": b.get("circle", False),
            })

    for el in side.get("elements", []):
        t = el["t"]
        if t == "image":
            role = el["role"]
            if has.get(role):
                items.append(_image_box(el))
            elif role == "photo" and (el.get("fallback_logo") or el.get("fb_fill")):
                items += _photo_fallback_items(el, pal, bool(has.get("logo")), data)
            elif el.get("fallback_text"):
                fb = {
                    "x": el["x"], "y": el["y"], "w": el["w"], "h": el["h"],
                    "size": el.get("fb_size", 10), "font": el.get("fb_font", "sansBold"),
                    "color": el.get("fb_color", "ink"), "align": el.get("fb_align", "center"),
                    "track": el.get("fb_track", 0.1), "caps": True, "field": "company",
                }
                s = resolve_text_field(fb, data)
                if s:
                    items.append(_text_item(fb, s.upper(), pal))
        elif t == "qr":
            if not has.get("qr"):
                continue
            if el.get("panel"):
                pad = 4.0
                items.append({
                    "t": "rect",
                    "x": _pt(el["x"], CARD_W_PT) - pad,
                    "y": _pt(el["y"], CARD_H_PT) - pad,
                    "w": _pt(el["w"], CARD_W_PT) + 2 * pad,
                    "h": _pt(el["h"], CARD_H_PT) + 2 * pad,
                    "fill": col(el.get("panel_color", "bg")),
                    "radius": 0.045 * CARD_H_PT,
                })
            items.append({
                "t": "image", "src": "qr",
                "x": _pt(el["x"], CARD_W_PT), "y": _pt(el["y"], CARD_H_PT),
                "w": _pt(el["w"], CARD_W_PT), "h": _pt(el["h"], CARD_H_PT),
                "fit": "contain", "circle": False,
            })
        elif t == "line":
            items.append({
                "t": "line",
                "x1": _pt(el["x1"], CARD_W_PT), "y1": _pt(el["y1"], CARD_H_PT),
                "x2": _pt(el["x2"], CARD_W_PT), "y2": _pt(el["y2"], CARD_H_PT),
                "stroke": col(el["stroke"]), "w": el.get("w", 0.5),
            })
        elif t == "text":
            s = resolve_text_field(el, data)
            if not s:
                continue
            if el.get("caps"):
                s = s.upper()
            items.append(_text_item(el, s, pal))

    return items


def qr_invert(tpl: dict) -> bool:
    for side in tpl["sides"].values():
        for el in side.get("elements", []):
            if el.get("t") == "qr" and el.get("invert"):
                return True
    return False
