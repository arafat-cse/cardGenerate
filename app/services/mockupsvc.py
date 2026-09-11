"""Mockup renderer.

Turns uploaded/generated front/back card PNGs into a realistic product
mockup: true 3D perspective, rounded corners, soft drop shadow, subtle
sheen highlight, on a scene background — pure Pillow, fully offline.
The SAME engine renders the live preview and the high-resolution export,
so the customer preview is exactly what downloads.
"""

import math

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .. import fonts

# scene → default background + vignette strength
SCENES = {
    "clean":   {"bg": "gradient", "vignette": 0.08},
    "minimal": {"bg": "white",    "vignette": 0.0},
    "dark":    {"bg": "dark",     "vignette": 0.34},
    "desk":    {"bg": "desk",     "vignette": 0.30},
}

_BG_FLAT = {
    "white": "#FFFFFF",
    "black": "#131417",
    "light": "#F1F2F4",
    "dark":  "#1B1D22",
}
_GRADIENTS = {
    "gradient": ("#F8F9FB", "#DBDFE6"),
    "dark":     ("#212329", "#0D0E11"),
    "desk":     ("#EFE8DD", "#D7CDBC"),
}


def _hex_rgb(s: str, fallback=(241, 242, 244)) -> tuple:
    s = (s or "").strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        return fallback
    try:
        return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return fallback


def _lum(rgb: tuple) -> float:
    return (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]) / 255.0


# ---------------------------------------------------------------- background

def _v_gradient(W: int, H: int, c1: tuple, c2: tuple) -> Image.Image:
    mask = Image.linear_gradient("L").resize((W, H))
    top = Image.new("RGB", (W, H), c1)
    bot = Image.new("RGB", (W, H), c2)
    return Image.composite(bot, top, mask)


def _paint_bg(W: int, H: int, scene: str, bg: str,
              custom_color: str, bg_image: Image.Image | None) -> tuple[Image.Image, tuple]:
    """Returns (background RGB image, representative base color)."""
    if bg == "auto":
        bg = SCENES.get(scene, SCENES["clean"])["bg"]

    if bg == "image" and bg_image is not None:
        img = bg_image.convert("RGB")
        scale = max(W / img.width, H / img.height)
        img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
        x = (img.width - W) // 2
        y = (img.height - H) // 2
        return img.crop((x, y, x + W, y + H)), (128, 128, 128)

    if bg == "custom":
        c = _hex_rgb(custom_color, (241, 242, 244))
        return Image.new("RGB", (W, H), c), c

    if bg in _GRADIENTS:
        c1 = _hex_rgb(_GRADIENTS[bg][0])
        c2 = _hex_rgb(_GRADIENTS[bg][1])
        return _v_gradient(W, H, c1, c2), c2

    c = _hex_rgb(_BG_FLAT.get(bg, "#F1F2F4"))
    return Image.new("RGB", (W, H), c), c


def _vignette(img: Image.Image, strength: float) -> None:
    """Darkened edges drawn as shrinking ellipses — smooth, no saturation ring."""
    if strength <= 0.001:
        return
    W, H = img.size
    mask = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(mask)
    N = 40
    for k in range(N, 0, -1):
        frac = k / N
        t = max(0.0, (frac - 0.45) / 0.55)
        v = int(255 * strength * (t ** 1.6))
        rx, ry = W * 0.75 * frac, H * 0.72 * frac
        d.ellipse([W / 2 - rx, H / 2 - ry, W / 2 + rx, H / 2 + ry], fill=v)
    black = Image.new("RGBA", (W, H), (7, 8, 10, 0))
    black.putalpha(mask)
    img.alpha_composite(black)


# ------------------------------------------------------------------ geometry

def _solve8(rows: list[list[float]]) -> list[float] | None:
    n = 8
    m = [list(r) for r in rows]
    for i in range(n):
        piv = max(range(i, n), key=lambda r: abs(m[r][i]))
        if abs(m[piv][i]) < 1e-10:
            return None
        m[i], m[piv] = m[piv], m[i]
        for r in range(n):
            if r == i:
                continue
            f = m[r][i] / m[i][i]
            for c in range(i, n + 1):
                m[r][c] -= f * m[i][c]
    return [m[i][n] / m[i][i] for i in range(n)]


def _homography(quad: list[tuple], rect: list[tuple]) -> list[float] | None:
    """PIL PERSPECTIVE coeffs mapping output-canvas quad → input-image rect."""
    rows = []
    for (x, y), (u, v) in zip(quad, rect):
        rows.append([x, y, 1, 0, 0, 0, -u * x, -u * y, u])
        rows.append([0, 0, 0, x, y, 1, -v * x, -v * y, v])
    return _solve8(rows)


def _projected_quad(iw: float, ih: float, persp: float, tilt_sign: float,
                    rot_deg: float) -> list[tuple]:
    """3D-rotate a card centered at the origin, project it, rotate in 2D.
    Returns 4 canvas-space corners centered on (0,0), order TL,TR,BR,BL."""
    hw, hh = iw / 2.0, ih / 2.0
    focal = 3.5 * max(hw, hh)
    ang_y = tilt_sign * persp * 0.85   # turn around vertical axis
    ang_x = persp * 0.22               # slight tilt back
    cy_, sy_ = math.cos(ang_y), math.sin(ang_y)
    cx_, sx_ = math.cos(ang_x), math.sin(ang_x)

    pts = []
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        x, y, z = sx * hw, sy * hh, 0.0
        x, z = x * cy_ + z * sy_, -x * sy_ + z * cy_
        y, z = y * cx_ - z * sx_, y * sx_ + z * cx_
        s = focal / (focal + z)
        pts.append((x * s, y * s))

    rot = math.radians(rot_deg)
    cr, sr = math.cos(rot), math.sin(rot)
    pts = [(x * cr - y * sr, x * sr + y * cr) for x, y in pts]
    return pts


# ------------------------------------------------------------------ card prep

def _rounded(card: Image.Image, radius_frac: float) -> None:
    iw, ih = card.size
    rr = max(1, int(radius_frac * ih))
    mask = Image.new("L", card.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, iw - 1, ih - 1], radius=rr, fill=255)
    card.putalpha(ImageChops.multiply(card.getchannel("A"), mask))


def _sheen(card: Image.Image, strength: float = 0.10) -> None:
    """Soft glossy light falling from the top edge (applied before the warp,
    so it follows the perspective automatically)."""
    iw, ih = card.size
    g = Image.linear_gradient("L").resize((iw, ih))  # 0 at top → 255 at bottom
    a = g.point(lambda v: int(255 * strength * max(0.0, 1.0 - (v / 255.0) / 0.42)))
    white = Image.new("RGBA", (iw, ih), (255, 255, 255, 0))
    white.putalpha(a)
    card.alpha_composite(white)


def _load_card(path, tw_px: int, radius_frac: float) -> Image.Image:
    from PIL import ImageOps
    img = Image.open(path)
    img.load()
    img = ImageOps.exif_transpose(img).convert("RGBA")
    target = min(max(int(tw_px * 1.6), 640), 3000)
    if img.width > target:
        img = img.resize((target, round(img.height * target / img.width)), Image.LANCZOS)
    _sheen(img)
    _rounded(img, radius_frac)
    return img


# -------------------------------------------------------------------- layout

def _positions(n: int, layout: str, W: float, H: float, size_pct: float,
               aspects: list[float]) -> list[tuple]:
    """Per-card (cx, cy, target_w). Order matches the cards given."""
    s = size_pct / 100.0
    if n == 1:
        a = aspects[0]
        return [(W / 2.0, H * 0.485, min(s * W, 0.78 * H * a))]

    if layout == "vertical":
        th = 0.40 * H * (0.55 + s * 0.75)
        ws = [min(a * th, 0.60 * W) for a in aspects]
        gap = 0.045 * H
        total = sum(w / a for w, a in zip(ws, aspects)) + gap
        starty = (H - total) / 2.0
        out = []
        y = starty
        for w, a in zip(ws, aspects):
            h = w / a
            out.append((W / 2.0, y + h / 2.0, w))
            y += h + gap
        return out

    if layout == "large":
        w1 = min(s * 0.62 * W, 0.44 * W)
        w2 = 0.60 * w1
        gap = 0.045 * W
        total = w1 + w2 + gap
        startx = (W - total) / 2.0
        return [
            (startx + w1 / 2.0, H * 0.47, w1),
            (startx + w1 + gap + w2 / 2.0, H * 0.525, w2),
        ]

    # side by side (default)
    ws = [min(s * 0.52 * W, 0.40 * W) for _ in range(n)]
    gap = 0.05 * W
    total = sum(ws) + gap
    startx = (W - total) / 2.0
    out = []
    x = startx
    for w in ws:
        out.append((x + w / 2.0, H * 0.47, w))
        x += w + gap
    return out


# -------------------------------------------------------------------- render

def render(opts: dict, front_path, back_path) -> Image.Image:
    W = max(320, min(int(opts.get("width", 1280)), 3840))
    H = max(240, min(int(opts.get("height", 800)), 3840))
    scene = opts.get("scene", "clean")
    bg = opts.get("bg", "auto")
    custom = opts.get("custom_color", "#f1f2f4")
    layout_mode = opts.get("layout", "side")
    size = float(opts.get("size", 60))
    rotation = float(opts.get("rotation", 0))
    persp = min(max(float(opts.get("perspective", 32)), 0.0), 100.0) / 100.0
    shadow = min(max(float(opts.get("shadow", 55)), 0.0), 100.0) / 100.0
    radius = min(max(float(opts.get("radius", 30)), 0.0), 100.0) / 100.0
    labels = bool(opts.get("labels", False))

    ss = 2 if max(W, H) <= 1920 else 1.5
    WS, HS = int(W * ss), int(H * ss)

    bg_image = None
    if bg == "image" and opts.get("bg_image"):
        try:
            bg_image = Image.open(opts["bg_image"])
            bg_image.load()
        except Exception:
            bg_image = None

    base_img, base_color = _paint_bg(WS, HS, scene, bg, custom, bg_image)
    canvas = base_img.convert("RGBA")
    vign = SCENES.get(scene, SCENES["clean"])["vignette"]

    cards = []
    if front_path:
        cards.append(("FRONT", front_path, +1.0))
    if back_path:
        cards.append(("BACK", back_path, -1.0))

    pos_guess = _positions(len(cards), layout_mode, WS, HS, size, [86.0 / 56.25] * len(cards))
    imgs = [_load_card(c[1], pos_guess[i][2], radius * 0.13) for i, c in enumerate(cards)]
    aspects = [im.width / im.height for im in imgs]
    pos = _positions(len(cards), layout_mode, WS, HS, size, aspects)

    shadow_layer = Image.new("RGBA", (WS, HS), (0, 0, 0, 0))
    card_layers = []
    label_slots = []

    for idx, (label, path, tilt) in enumerate(cards):
        cx, cy, tw = pos[idx]
        img = imgs[idx]

        rot = rotation + (3.0 if (label == "BACK" and len(cards) > 1) else (-2.0 if len(cards) > 1 else 0.0))
        quad = _projected_quad(img.width, img.height, persp, tilt, rot)

        xs = [p[0] for p in quad]
        ys = [p[1] for p in quad]
        k = (tw) / max(1e-6, (max(xs) - min(xs)))
        quad = [(cx + x * k, cy + y * k) for x, y in quad]

        card_h = tw / max(1e-6, aspects[idx])
        if shadow > 0.001:
            cenx = sum(p[0] for p in quad) / 4.0
            ceny = sum(p[1] for p in quad) / 4.0
            grow = 1.03
            poly = [(cenx + (x - cenx) * grow + tw * 0.012,
                     ceny + (y - ceny) * grow + card_h * (0.03 + 0.05 * shadow)) for x, y in quad]
            alpha = int(175 * (shadow ** 0.8))
            d = ImageDraw.Draw(shadow_layer)
            d.polygon(poly, fill=(10, 12, 16, alpha))

        rect = [(0, 0), (img.width, 0), (img.width, img.height), (0, img.height)]
        coeffs = _homography(quad, rect)
        if coeffs:
            layer = img.transform((WS, HS), Image.Transform.PERSPECTIVE, coeffs,
                                  resample=Image.Resampling.BICUBIC, fillcolor=(0, 0, 0, 0))
        else:
            layer = img
        card_layers.append(layer)

        bottom = max(p[1] for p in quad)
        label_slots.append((cx / ss, (bottom / ss) + max(14, W * 0.018), label))

    if shadow > 0.001:
        blur = max(2.0, 0.045 * (HS * 0.25) * (0.45 + shadow))
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(blur))
        canvas.alpha_composite(shadow_layer)
    for layer in card_layers:
        canvas.alpha_composite(layer)

    _vignette(canvas, vign)

    out = canvas.convert("RGB").resize((W, H), Image.Resampling.LANCZOS)

    if labels:
        d = ImageDraw.Draw(out)
        fpx = max(13, int(W * 0.016))
        font = fonts.load_path(fonts.resolve("sansBold")["path"], fpx)
        track = fpx * 0.38
        fill = (120, 124, 132) if _lum(base_color) > 0.5 else (150, 155, 165)
        for (lx, ly, text) in label_slots:
            widths = [d.textlength(ch, font=font) for ch in text]
            total = sum(widths) + track * (len(text) - 1)
            x = lx - total / 2.0
            for ch, w in zip(text, widths):
                d.text((x, ly), ch, font=font, fill=fill)
                x += w + track
    return out
