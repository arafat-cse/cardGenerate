import time
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

MAX_DIM = {"logos": 1400, "photos": 1600}


def trim_alpha(img: Image.Image) -> Image.Image:
    if img.mode != "RGBA":
        return img
    bbox = img.split()[-1].getbbox()
    return img.crop(bbox) if bbox else img


def _safe_ext(name: str) -> str:
    ext = Path(name or "").suffix.lower()
    return ext if ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff") else ".png"


def process_upload(kind: str, cid: str, filename: str, raw: bytes) -> dict:
    """Save the original, then a cleaned/resized working PNG. Returns URLs."""
    from ..config import LOGOS_DIR, ORIGINALS_DIR, PHOTOS_DIR, UPLOADS_DIR

    stamp = time.strftime("%Y%m%d-%H%M%S")
    stem = "".join(c for c in Path(filename).stem if c.isalnum() or c in "-_")[:40] or "image"

    orig_dir = ORIGINALS_DIR / cid
    orig_dir.mkdir(parents=True, exist_ok=True)
    orig_path = orig_dir / f"{stamp}_{stem}{_safe_ext(filename)}"
    orig_path.write_bytes(raw)

    img = Image.open(BytesIO(raw))
    img.load()
    img = ImageOps.exif_transpose(img).convert("RGBA")

    if kind == "logos":
        img = trim_alpha(img)
    max_dim = MAX_DIM[kind]
    if max(img.size) > max_dim:
        img.thumbnail((max_dim, max_dim), Image.LANCZOS)

    out_dir = LOGOS_DIR / cid if kind == "logos" else PHOTOS_DIR / cid
    out_dir.mkdir(parents=True, exist_ok=True)
    out_name = f"{stamp}_{stem}.png"
    out_path = out_dir / out_name
    img.save(out_path, "PNG", optimize=True)

    rel = f"{kind}/{cid}/{out_name}"
    return {
        "path": rel,
        "url": f"/uploads/{rel}",
        "width": img.width,
        "height": img.height,
    }
