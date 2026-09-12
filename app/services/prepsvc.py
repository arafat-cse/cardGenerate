"""Image Remove & Prepare service.

Everything runs locally: rembg (u2net) for background removal, Pillow for
enhancement / trim / rotate / resize, vtracer (optional) for true
raster→vector tracing. Customer images never leave this PC.
"""

import base64
import json
import re
import shutil
import time
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

from . import bgremove
from ..config import PREP_DIR, UPLOADS_DIR

ALLOWED_TYPES = {"jpg", "jpeg", "png", "webp"}
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_SOURCE_PX = 6000     # longest side accepted from the user
MAX_OUTPUT_PX = 8000     # memory safety cap for the processed image
PREP_SESSION_DAYS = 7


class PrepError(Exception):
    pass


# ----------------------------------------------------------------- session

def session_dir(cid: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "", str(cid))[:40] or "session"
    d = PREP_DIR / safe
    d.mkdir(parents=True, exist_ok=True)
    return d


def _meta_path(d: Path) -> Path:
    return d / "meta.json"


def read_meta(d: Path) -> dict:
    try:
        return json.loads(_meta_path(d).read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_meta(d: Path, meta: dict) -> None:
    _meta_path(d).write_text(json.dumps(meta), encoding="utf-8")


def original_path(d: Path):
    p = d / "original.png"
    return p if p.is_file() else None


def nobg_path(d: Path):
    p = d / "nobg.png"
    return p if p.is_file() else None


def processed_path(d: Path):
    p = d / "processed.png"
    return p if p.is_file() else None


def rel_web(p: Path) -> str:
    return "/uploads/" + str(p.relative_to(UPLOADS_DIR)).replace("\\", "/")


# ------------------------------------------------------------------ upload

def new_session(cid: str, filename: str, raw: bytes) -> dict:
    if not raw:
        raise PrepError("Empty file")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise PrepError("File is larger than 20 MB — please use a smaller image")

    ext = (filename or "").rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_TYPES:
        raise PrepError("Only JPG, JPEG, PNG and WEBP files are supported")

    d = session_dir(cid)
    for old in d.glob("*"):
        if old.is_file():
            old.unlink()

    try:
        img = Image.open(BytesIO(raw))
        img.load()
    except Exception as e:
        raise PrepError(f"Could not read the image: {e}")
    img = ImageOps.exif_transpose(img)
    if max(img.size) > MAX_SOURCE_PX:
        img.thumbnail((MAX_SOURCE_PX, MAX_SOURCE_PX), Image.LANCZOS)
    img.save(d / "original.png", "PNG")

    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", (filename or "image").rsplit(".", 1)[0]).strip("_")[:48] or "image"
    write_meta(d, {
        "name": stem.lower(),
        "orig_name": filename or "image",
        "orig_type": ext.upper(),
        "orig_bytes": len(raw),
        "uploaded": time.time(),
    })
    return analyze(d)


# ---------------------------------------------------------------- analysis

def _img_info(img: Image.Image) -> dict:
    alpha_pct = 0.0
    if img.mode in ("RGBA", "LA", "PA"):
        a = img.getchannel("A")
        hist = a.histogram()
        transparent = sum(hist[:10])
        alpha_pct = round(100.0 * transparent / (img.width * img.height), 1)
    return {"width": img.width, "height": img.height, "transparency_pct": alpha_pct}


def analyze(d) -> dict:
    p = original_path(d)
    if not p:
        raise PrepError("No image uploaded yet")
    meta = read_meta(d)
    with Image.open(p) as img:
        info = _img_info(img.convert("RGBA"))
        mode = img.mode
    size_kb = round(p.stat().st_size / 1024)
    return {
        **info,
        "mode": mode,
        "type": meta.get("orig_type", "PNG"),
        "file_kb": size_kb,
        "orig_bytes": meta.get("orig_bytes"),
        "name": meta.get("name", "image"),
        "original_url": rel_web(p) + f"?v={int(p.stat().st_mtime)}",
        "has_nobg": nobg_path(d) is not None,
        "has_processed": processed_path(d) is not None,
        "processed_url": (rel_web(processed_path(d)) + f"?v={int(processed_path(d).stat().st_mtime)}") if processed_path(d) else None,
    }


def _verdict(src_w: int, src_h: int, tw: int, th: int) -> dict:
    """Compare the source resolution (before enhancement) with the requested
    output size — honest advice, not marketing."""
    if tw <= 0 or th <= 0:
        return {"level": "ok", "ratio": 1.0, "message": ""}
    ratio = min(src_w / tw, src_h / th)
    if ratio >= 0.98:
        return {"level": "good", "ratio": round(ratio, 2),
                "message": f"Good — the source ({src_w}×{src_h}) is large enough for {tw}×{th} px at this DPI."}
    if ratio >= 0.5:
        return {"level": "fair", "ratio": round(ratio, 2),
                "message": f"Fair — the source is about {1/ratio:.1f}× smaller than requested. 2× Enhance is recommended."}
    if ratio >= 0.25:
        return {"level": "low", "ratio": round(ratio, 2),
                "message": f"Low — the source is about {1/ratio:.1f}× smaller than requested. 4× Enhance recommended; fine details may still look soft."}
    return {"level": "verylow", "ratio": round(ratio, 2),
            "message": f"Very low — the source is {1/ratio:.0f}× smaller than requested. Even 4× Enhance cannot create the missing detail; consider a larger original."}


# ---------------------------------------------------------------- pipeline

def _enhance(img: Image.Image, factor: int) -> Image.Image:
    """Stepped Lanczos upscale + unsharp masking per step — a real, honest
    'smart upscale'. It can improve apparent sharpness, but it cannot invent
    detail that was never captured (the UI says so too)."""
    if factor <= 1 or img.width * img.height == 0:
        return img
    target_w = min(img.width * factor, MAX_OUTPUT_PX)
    cur = img
    while cur.width < target_w:
        step = min(2.0, target_w / cur.width)
        nw = min(target_w, max(cur.width + 1, round(cur.width * step)))
        nh = max(1, round(cur.height * nw / cur.width))
        cur = cur.resize((nw, nh), Image.Resampling.LANCZOS)
        cur = cur.filter(ImageFilter.UnsharpMask(radius=2, percent=90, threshold=2))
    return cur


def _trim(img: Image.Image) -> Image.Image:
    if img.mode != "RGBA":
        return img
    a = img.getchannel("A").point(lambda v: 255 if v > 8 else 0)
    bbox = a.getbbox()
    if not bbox:
        return img
    pad = max(2, round(0.01 * max(img.size)))
    x0, y0, x1, y1 = bbox
    return img.crop((max(0, x0 - pad), max(0, y0 - pad),
                     min(img.width, x1 + pad), min(img.height, y1 + pad)))


def _target_px(width, height, unit: str, dpi: int) -> tuple:
    def to_px(v):
        if v is None or v <= 0:
            return None
        if unit == "px":
            return int(round(v))
        if unit == "mm":
            return int(round(v / 25.4 * dpi))
        if unit == "cm":
            return int(round(v / 10 / 25.4 * dpi))
        if unit == "in":
            return int(round(v * dpi))
        return None
    return to_px(width), to_px(height)


def process(d, opts: dict) -> dict:
    """Full pipeline. The background-removed intermediate is cached in
    nobg.png, so changing sliders never re-runs the AI model."""
    src_kind = opts.get("bg_mode", "keep")
    src = nobg_path(d) if src_kind == "auto" else original_path(d)
    if src is None:
        if src_kind == "auto":
            # first automatic removal — runs rembg locally (u2net)
            src = original_path(d)
            if not src:
                raise PrepError("No image uploaded yet")
            try:
                bgremove.remove_background(src, d / "nobg.png")
            except bgremove.BgRemovalUnavailable as e:
                raise PrepError(str(e))
            except Exception as e:
                raise PrepError(f"Background removal failed: {e}")
            src = nobg_path(d)
        else:
            raise PrepError("No image uploaded yet")

    meta = read_meta(d)
    img = Image.open(src)
    img.load()
    img = ImageOps.exif_transpose(img).convert("RGBA")
    src_w, src_h = img.size

    factor = 1
    try:
        factor = {1: 1, 2: 2, 4: 4}.get(int(opts.get("enhance", 1)), 1)
    except Exception:
        factor = 1
    if factor > 1:
        img = _enhance(img, factor)

    rotate = float(opts.get("rotate") or 0)
    if abs(rotate) >= 0.5:
        img = img.rotate(rotate, expand=True, resample=Image.Resampling.BICUBIC)
    if opts.get("flip_h"):
        img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if opts.get("flip_v"):
        img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    if opts.get("trim"):
        img = _trim(img)

    dpi = int(opts.get("dpi") or 300)
    dpi = max(36, min(1200, dpi))
    tw, th = _target_px(opts.get("width"), opts.get("height"), opts.get("unit", "px"), dpi)
    tw = min(tw, MAX_OUTPUT_PX) if tw else tw
    th = min(th, MAX_OUTPUT_PX) if th else th

    if tw or th:
        if opts.get("keep_aspect", True):
            if tw and th:
                scale = min(tw / img.width, th / img.height)
            else:
                scale = (tw or th) / (img.width if tw else img.height)
            nw = max(1, round(img.width * scale))
            nh = max(1, round(img.height * scale))
        else:
            nw, nh = tw or img.width, th or img.height
        if (nw, nh) != img.size:
            img = img.resize((nw, nh), Image.Resampling.LANCZOS)

    img = img.convert("RGBA")
    out = d / "processed.png"
    img.save(out, "PNG", dpi=(dpi, dpi))
    write_meta(d, {**meta, "last_dpi": dpi})

    info = _img_info(img)
    verdict = _verdict(src_w, src_h, info["width"], info["height"])
    warnings = []
    if src_kind != "auto":
        warnings.append("Background removal is OFF — the image keeps its original background, so 'transparent PNG' guarantees do not apply.")
    if info["transparency_pct"] < 1.0 and src_kind == "auto":
        warnings.append("Almost no transparency was detected in the result — the subject may fill the whole frame, or removal did not find a clear background.")
    if factor > 1:
        warnings.append("Enhancement improves apparent sharpness but cannot recover detail the original never had.")

    stem = meta.get("name", "image")
    v = int(time.time())
    return {
        **info,
        "enhance": factor,
        "verdict": verdict,
        "warnings": warnings,
        "png_name": f"{stem}_enhanced.png" if factor > 1 else f"{stem}_removed.png",
        "processed_url": rel_web(out) + f"?v={v}",
        "original_url": rel_web(original_path(d)) + f"?v={int(original_path(d).stat().st_mtime)}",
        "has_nobg": nobg_path(d) is not None,
    }


# ----------------------------------------------------------------- refine

def refine(d, data_url: str) -> dict:
    """Replace processed.png with the brush-edited canvas from the browser."""
    m = re.match(r"^data:image/png;base64,(.+)$", data_url or "")
    if not m:
        raise PrepError("Expected a base64 PNG from the refine editor")
    from io import BytesIO
    try:
        img = Image.open(BytesIO(base64.b64decode(m.group(1))))
        img.load()
    except Exception as e:
        raise PrepError(f"Could not read edited image: {e}")
    if max(img.size) > MAX_OUTPUT_PX:
        img.thumbnail((MAX_OUTPUT_PX, MAX_OUTPUT_PX), Image.LANCZOS)
    img.convert("RGBA").save(d / "processed.png", "PNG")
    info = _img_info(img.convert("RGBA"))
    meta = read_meta(d)
    stem = meta.get("name", "image")
    v = int(time.time())
    return {
        **info,
        "processed_url": rel_web(d / "processed.png") + f"?v={v}",
        "original_url": rel_web(original_path(d)) + f"?v={int(original_path(d).stat().st_mtime)}",
        "png_name": f"{stem}_edited.png",
        "has_nobg": nobg_path(d) is not None,
    }


# --------------------------------------------------------------------- svg

def _svg_wrapper(png_bytes: bytes, w: int, h: int, note: str) -> str:
    b64 = base64.b64encode(png_bytes).decode("ascii")
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{w}" height="{h}" viewBox="0 0 {w} {h}">\n'
        f"  <!-- {note} -->\n"
        f'  <image width="{w}" height="{h}" xlink:href="data:image/png;base64,{b64}"/>\n'
        "</svg>\n"
    )


def build_svg(d, mode: str = "preserve", detail: int = 6, smoothing: bool = True,
              colors: int = 6) -> dict:
    src = processed_path(d) or original_path(d)
    if not src:
        raise PrepError("No image uploaded yet")
    meta = read_meta(d)
    stem = meta.get("name", "image")

    img = Image.open(src)
    img.load()
    img = ImageOps.exif_transpose(img).convert("RGBA")
    w, h = img.size

    if mode in ("preserve", "optimize"):
        if mode == "optimize":
            try:
                q = img.quantize(colors=256, method=Image.Quantize.FASTOCTREE)
                buf = BytesIO()
                q.save(buf, "PNG", optimize=True)
            except Exception:
                buf = BytesIO()
                img.save(buf, "PNG", optimize=True)
            note = ("Raster image — SVG wrapper (optimized). The PNG is embedded inside an SVG; "
                    "this is NOT a true vector file.")
            label = "Raster image — SVG wrapper (optimized)"
        else:
            buf = BytesIO()
            img.save(buf, "PNG", optimize=True)
            note = ("Raster image — SVG wrapper. The original PNG is embedded unchanged inside an SVG; "
                    "this is NOT a true vector file.")
            label = "Raster image — SVG wrapper"
        svg_text = _svg_wrapper(buf.getvalue(), w, h, note)
        kind = "wrapper"
    elif mode == "vectorize":
        try:
            import tempfile
            import vtracer
        except ImportError:
            buf = _dumps_png(img)
            svg_text = _svg_wrapper(
                buf.getvalue(), w, h,
                "Raster image — SVG wrapper (vectorizer not installed — run: pip install vtracer)")
            return {"kind": "wrapper", "label": "Raster image — SVG wrapper (vectorizer not installed)",
                    "name": f"{stem}.svg", "svg": svg_text,
                    "note": "True vectorizing needs the optional 'vtracer' package. Run: .venv\\Scripts\\pip install vtracer"}
        # trace on a manageable copy for speed
        timg = img
        if max(img.size) > 1000:
            timg = img.copy()
            timg.thumbnail((1000, 1000), Image.LANCZOS)
        with tempfile.TemporaryDirectory() as td:
            t_in = d / "_trace_in.png"
            timg.save(t_in, "PNG")
            t_out = str(Path(td) / "out.svg")
            try:
                vtracer.convert_image_to_svg_py(
                    str(t_in), t_out,
                    colormode="color",
                    hierarchical="stacked",
                    mode="spline" if smoothing else "polygon",
                    filter_speckle=max(0, 12 - int(detail)),
                    color_precision=max(2, min(10, int(colors))),
                    layer_difference=16,
                    corner_threshold=60,
                    length_threshold=4.0,
                    splice_threshold=45,
                    path_precision=3,
                )
            finally:
                try:
                    t_in.unlink()
                except OSError:
                    pass
            svg_text = Path(t_out).read_text(encoding="utf-8", errors="replace")
        label = f"True vector (traced locally · {'smoothed' if smoothing else 'polygon'} paths)"
        kind = "vector"
    else:
        raise PrepError("Unknown SVG mode")

    return {"kind": kind, "label": label, "name": f"{stem}.svg", "svg": svg_text}


def _dumps_png(img: Image.Image):
    from io import BytesIO
    b = BytesIO()
    img.save(b, "PNG", optimize=True)
    return b


# -------------------------------------------------------- use in generator

def use_in_generator(cid: str, kind: str) -> dict:
    src = processed_path(session_dir(cid))
    if not src:
        raise PrepError("Process an image first")
    if kind not in ("logo", "photo"):
        raise PrepError("kind must be logo or photo")
    meta = read_meta(session_dir(cid))
    stem = meta.get("name", "image")
    dest_dir = UPLOADS_DIR / ("logos" if kind == "logo" else "photos") / re.sub(r"[^a-zA-Z0-9_-]", "", cid)[:40]
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{int(time.time())}_{stem}_prepared.png"
    shutil.copyfile(src, dest)
    rel = str(dest.relative_to(UPLOADS_DIR)).replace("\\", "/")
    return {"path": rel, "url": f"/uploads/{rel}", "kind": kind}


# ----------------------------------------------------------------- cleanup

def cleanup_old(days: int = PREP_SESSION_DAYS) -> None:
    """Delete prep sessions untouched for more than `days` days."""
    if not PREP_DIR.is_dir():
        return
    cutoff = time.time() - days * 86400
    for d in PREP_DIR.iterdir():
        try:
            if d.is_dir() and d.stat().st_mtime < cutoff:
                shutil.rmtree(d, ignore_errors=True)
        except OSError:
            pass
