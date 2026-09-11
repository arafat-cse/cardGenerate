from PIL import Image, ImageDraw

from .. import fonts
from ..config import BLEED_IN, CARD_H_IN, CARD_W_IN
from . import layout


def _rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _load_asset(src, assets):
    a = assets.get(src)
    if a is None:
        return None
    if isinstance(a, Image.Image):
        return a.convert("RGBA")
    return Image.open(a).convert("RGBA")


def _paste_image(canvas: Image.Image, item: dict, assets, ox: int, oy: int, s: float):
    img = _load_asset(item["src"], assets)
    if img is None:
        return
    bw, bh = item["w"] * s, item["h"] * s
    iw, ih = img.size
    if item.get("fit") == "cover":
        sc = max(bw / iw, bh / ih)
        nw, nh = int(iw * sc), int(ih * sc)
        img = img.resize((max(1, nw), max(1, nh)), Image.LANCZOS)
        left = (img.width - bw) / 2
        top = (img.height - bh) / 2
        img = img.crop((int(left), int(top), int(left + bw), int(top + bh)))
    else:
        sc = min(bw / iw, bh / ih)
        img = img.resize((max(1, int(iw * sc)), max(1, int(ih * sc))), Image.LANCZOS)

    if item.get("circle"):
        d = int(min(bw, bh))
        side = min(img.size)
        img = img.crop((
            (img.width - side) // 2, (img.height - side) // 2,
            (img.width - side) // 2 + side, (img.height - side) // 2 + side,
        )).resize((d, d), Image.LANCZOS)
        mask = Image.new("L", (d * 4, d * 4), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, d * 4 - 1, d * 4 - 1), fill=255)
        mask = mask.resize((d, d), Image.LANCZOS)
        px = int(ox + item["x"] * s + (bw - d) / 2)
        py = int(oy + item["y"] * s + (bh - d) / 2)
        canvas.alpha_composite(img, (px, py), mask=mask)
    else:
        px = int(ox + item["x"] * s + (bw - img.width) / 2)
        py = int(oy + item["y"] * s + (bh - img.height) / 2)
        canvas.alpha_composite(img, (px, py))


def _draw_text(draw: ImageDraw.ImageDraw, item: dict, ox: int, oy: int, s: float):
    px = max(4, int(round(item["size"] * s)))
    f = fonts.load_path(item["ttf"], px)
    color = _rgb(item["color"]) + (255,)
    text = item["s"]
    track_em = item.get("track", 0) or 0
    align = item.get("align", "left")
    cy = oy + (item["y"] + item["h"] / 2.0) * s

    if track_em > 0:
        track_px = track_em * px
        asc, desc = f.getmetrics()
        baseline = cy + (asc - desc) / 2.0
        total = f.getlength(text) + track_px * max(0, len(text) - 1)
        if align == "center":
            x = ox + (item["x"] + item["w"] / 2.0) * s - total / 2.0
        elif align == "right":
            x = ox + (item["x"] + item["w"]) * s - total
        else:
            x = ox + item["x"] * s
        for ch in text:
            draw.text((x, baseline), ch, font=f, fill=color, anchor="ls")
            x += f.getlength(ch) + track_px
    else:
        if align == "center":
            x, anchor = ox + (item["x"] + item["w"] / 2.0) * s, "mm"
        elif align == "right":
            x, anchor = ox + (item["x"] + item["w"]) * s, "rm"
        else:
            x, anchor = ox + item["x"] * s, "lm"
        draw.text((x, cy), text, font=f, fill=color, anchor=anchor)


def render_side(tpl: dict, side_key: str, data: dict, assets: dict, dpi: int) -> Image.Image:
    side = tpl["sides"][side_key]
    has = {k: assets.get(k) is not None for k in ("logo", "photo", "qr")}
    items = layout.resolve_side(tpl, side, data, has)

    bleed = round(BLEED_IN * dpi)
    w = round(CARD_W_IN * dpi)
    h = round(CARD_H_IN * dpi)
    canvas = Image.new("RGBA", (w + 2 * bleed, h + 2 * bleed), (255, 255, 255, 255))
    ox, oy = bleed, bleed
    s = dpi / 72.0
    draw = ImageDraw.Draw(canvas)

    for it in items:
        t = it["t"]
        if t == "rect":
            box = [ox + it["x"] * s, oy + it["y"] * s,
                   ox + (it["x"] + it["w"]) * s, oy + (it["y"] + it["h"]) * s]
            fill = _rgb(it["fill"]) + (255,) if it.get("fill") else None
            stroke = _rgb(it["stroke"]) + (255,) if it.get("stroke") else None
            sw = max(1, round((it.get("strokeW") or 0.5) * s))
            radius = (it.get("radius") or 0) * s
            if radius > 0.5:
                draw.rounded_rectangle(box, radius=radius, fill=fill, outline=stroke, width=sw if stroke else 0)
            else:
                draw.rectangle(box, fill=fill, outline=stroke, width=sw if stroke else 0)
        elif t == "ellipse":
            x, y, w2, h2 = it["x"], it["y"], it["w"], it["h"]
            if it.get("circle"):
                d = min(w2, h2)
                x += (w2 - d) / 2.0
                y += (h2 - d) / 2.0
                w2 = h2 = d
            box = [ox + x * s, oy + y * s, ox + (x + w2) * s, oy + (y + h2) * s]
            fill = _rgb(it["fill"]) + (255,) if it.get("fill") else None
            stroke = _rgb(it["stroke"]) + (255,) if it.get("stroke") else None
            draw.ellipse(box, fill=fill, outline=stroke,
                         width=max(1, round((it.get("strokeW") or 1) * s)) if stroke else 0)
        elif t == "poly":
            pts = [(ox + px * s, oy + py * s) for px, py in it["pts"]]
            draw.polygon(pts, fill=_rgb(it["fill"]) + (255,) if it.get("fill") else None)
        elif t == "line":
            draw.line(
                [(ox + it["x1"] * s, oy + it["y1"] * s), (ox + it["x2"] * s, oy + it["y2"] * s)],
                fill=_rgb(it["stroke"]) + (255,), width=max(1, round(it.get("w", 0.5) * s)),
            )
        elif t == "image":
            _paste_image(canvas, it, assets, ox, oy, s)
        elif t == "text":
            _draw_text(draw, it, ox, oy, s)

    return canvas.convert("RGB")


def render_stacked(tpl: dict, data: dict, assets: dict, qr_img, dpi: int, border: bool = True) -> Image.Image:
    """Front above back with a small gap - used for the on-screen preview."""
    all_assets = dict(assets)
    all_assets["qr"] = qr_img
    front = render_side(tpl, "front", data, all_assets, dpi)
    back = render_side(tpl, "back", data, all_assets, dpi)
    gap = round(0.10 * dpi)
    out = Image.new("RGB", (front.width, front.height + gap + back.height), (234, 234, 240))
    out.paste(front, (0, 0))
    out.paste(back, (0, front.height + gap))
    if border:
        d = ImageDraw.Draw(out)
        d.rectangle([0, 0, front.width - 1, front.height - 1], outline=(200, 200, 210))
        d.rectangle([0, front.height + gap, front.width - 1, out.height - 1], outline=(200, 200, 210))
    return out
