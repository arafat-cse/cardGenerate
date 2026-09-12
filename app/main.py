import hashlib
import json
import re
import subprocess
import time
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import templates_def
from .config import (
    AI_DIR, BASE_DIR, DEFAULT_LOGO, DEFAULT_QR, GENERATED_DIR, ILLUSTRATOR_DIR, MOCKUP_BG_DIR,
    MOCKUP_OUT_DIR, OUTPUT_DPI, PDF_DIR, PNG_DIR, PREVIEW_DIR, PREVIEW_DPI, TEMPLATES_DIR,
    UPLOADS_DIR, ensure_dirs, resolve_user_path,
)
from .fonts import resolve as resolve_font
from .services import ai_illust, mockupsvc, pdfsvc, prepsvc, qrsvc, render
from .services.bgremove import BgRemovalUnavailable, remove_background
from .services.images import process_upload
from .services.prepsvc import PrepError
from .services.layout import qr_invert

app = FastAPI(title="BizCard Studio", version="1.0")


@app.on_event("startup")
def _startup():
    ensure_dirs()
    templates_def.build_all()
    prepsvc.cleanup_old()


class CardData(BaseModel):
    company: str = ""
    name: str = ""
    title: str = ""
    tagline: str = ""
    phone: str = ""
    email: str = ""
    website: str = ""
    address: str = ""


class QrCfg(BaseModel):
    type: str = "vcard"
    value: str = ""
    logo_in_qr: bool = False


class RenderReq(BaseModel):
    cid: str
    template_id: str
    data: CardData
    logo: Optional[str] = None
    photo: Optional[str] = None
    qr_image: Optional[str] = None
    qr: QrCfg = QrCfg()


def _load_tpl(template_id: str) -> dict:
    tpl = templates_def.load(template_id)
    if not tpl:
        raise HTTPException(400, f"Unknown template: {template_id}")
    return tpl


def _assets_of(req: RenderReq) -> dict:
    logo = resolve_user_path(req.logo, UPLOADS_DIR)
    if not logo and DEFAULT_LOGO.is_file():
        logo = DEFAULT_LOGO
    return {
        "logo": logo,
        "photo": resolve_user_path(req.photo, UPLOADS_DIR),
    }


def _qr_of(req: RenderReq, tpl: dict):
    # an uploaded QR image (or assets/qr.png) is placed on the back as-is;
    # otherwise a QR is generated from the card data
    path = resolve_user_path(req.qr_image, UPLOADS_DIR)
    if not path and req.qr.type != "none" and DEFAULT_QR.is_file():
        path = DEFAULT_QR
    if path:
        from PIL import Image
        return Image.open(path)

    logo_img = None
    logo_path = _assets_of(req)["logo"]
    if logo_path and req.qr.logo_in_qr:
        from PIL import Image
        logo_img = Image.open(logo_path)
    return qrsvc.build(
        req.qr.model_dump(), req.data.model_dump(), logo_img,
        invert=qr_invert(tpl),
        logo_in_qr=req.qr.logo_in_qr,
    )


def _slug(req: RenderReq) -> str:
    base = req.data.name or req.data.company or "card"
    s = re.sub(r"[^A-Za-z0-9]+", "-", base).strip("-").lower()[:40]
    return s or "card"


# ------------------------------------------------------------------ api

@app.get("/api/health")
def health():
    exe = ai_illust.find_illustrator()
    return {
        "ok": True,
        "illustrator": str(exe) if exe else None,
        "blackletter_font": resolve_font("blackletter")["family"],
    }


@app.get("/api/templates")
def list_templates():
    return templates_def.list_templates()


@app.post("/api/upload/{kind}")
async def upload(kind: str, cid: str = Form(...), file: UploadFile = File(...)):
    if kind not in ("logos", "photos", "qr"):
        raise HTTPException(400, "kind must be logos, photos or qr")
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "Empty file")
    try:
        return process_upload(kind, cid, file.filename or "image.png", raw)
    except Exception as e:
        raise HTTPException(400, f"Could not read image: {e}")


@app.post("/api/bg-remove")
async def bg_remove(cid: str = Form(...), kind: str = Form(...), path: str = Form(...)):
    src = resolve_user_path(path, UPLOADS_DIR)
    if not src:
        raise HTTPException(404, "File not found")
    dst = src.with_name(src.stem + "_nobg.png")
    try:
        remove_background(src, dst)
    except BgRemovalUnavailable as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Background removal failed: {e}")
    rel = str(dst.relative_to(UPLOADS_DIR)).replace("\\", "/")
    return {"path": rel, "url": f"/uploads/{rel}"}


@app.post("/api/preview")
def preview(req: RenderReq):
    tpl = _load_tpl(req.template_id)
    assets = _assets_of(req)
    qr_img = _qr_of(req, tpl)
    data = req.data.model_dump()
    img = render.render_stacked(tpl, data, assets, qr_img, PREVIEW_DPI)
    out = PREVIEW_DIR / f"{re.sub(r'[^a-zA-Z0-9_-]', '', req.cid)[:32] or 'preview'}_preview.png"
    img.save(out, "PNG", optimize=True)
    return {"url": f"/generated/preview/{out.name}?v={int(time.time())}"}


@app.post("/api/generate")
def generate(req: RenderReq):
    tpl = _load_tpl(req.template_id)
    assets = _assets_of(req)
    qr_img = _qr_of(req, tpl)
    data = req.data.model_dump()
    cid8 = re.sub(r"[^a-zA-Z0-9]", "", req.cid)[:8] or "card"
    base = f"{cid8}_{_slug(req)}_{time.strftime('%Y%m%d-%H%M%S')}"

    png_paths = []
    urls = {}
    for side_key in ("front", "back"):
        img = render.render_side(tpl, side_key, data, {**assets, "qr": qr_img}, 600)
        img = img.resize((round(img.width * OUTPUT_DPI / 600), round(img.height * OUTPUT_DPI / 600)))
        p = PNG_DIR / f"{base}_{side_key}.png"
        img.save(p, "PNG", dpi=(OUTPUT_DPI, OUTPUT_DPI))
        png_paths.append(p)
        urls[f"png_{side_key}"] = f"/generated/png/{p.name}"

    pdf_path = PDF_DIR / f"{base}.pdf"
    title = req.data.name or req.data.company or "Business Card"
    pdfsvc.save_pdf(pdf_path, png_paths, title)
    urls["pdf"] = f"/generated/pdf/{pdf_path.name}"

    def entry(url, label):
        return {"url": url, "name": url.rsplit("/", 1)[-1], "label": label}

    return {
        "ok": True,
        "outputs": [
            entry(urls["png_front"], "PNG · front"),
            entry(urls["png_back"], "PNG · back"),
            entry(urls["pdf"], "PDF · print-ready (2 pages, with bleed)"),
        ],
    }


@app.post("/api/illustrator")
def illustrator(req: RenderReq):
    if not ai_illust.find_illustrator():
        raise HTTPException(
            400,
            "Adobe Illustrator was not found. Create a file 'illustrator_path.txt' next to "
            "start.bat containing the full path to Illustrator.exe and try again.",
        )
    tpl = _load_tpl(req.template_id)
    assets = _assets_of(req)
    qr_img = _qr_of(req, tpl)
    job = ai_illust.build_job(req.cid, tpl, req.data.model_dump(), assets, qr_img)
    ai_illust.launch(job)
    return {"job": job, "status": "launched"}


@app.get("/api/illustrator/status/{job}")
def illustrator_status(job: str):
    return ai_illust.job_status(job)


@app.get("/api/outputs")
def outputs(cid: str):
    cid8 = re.sub(r"[^a-zA-Z0-9]", "", cid)[:8]
    rows = []
    for folder, kind in ((PNG_DIR, "png"), (PDF_DIR, "pdf"), (AI_DIR, "ai")):
        if not folder.is_dir():
            continue
        for p in folder.rglob("*"):
            if p.is_file() and p.name.startswith(cid8):
                rows.append({
                    "name": p.name,
                    "url": f"/generated/{folder.name}/" + str(p.relative_to(folder)).replace("\\", "/"),
                    "kind": kind,
                    "mtime": p.stat().st_mtime,
                })
    rows.sort(key=lambda r: -r["mtime"])
    return rows[:15]


@app.post("/api/open-folder")
def open_folder():
    subprocess.Popen(["explorer", str(GENERATED_DIR)])
    return {"ok": True}


# ------------------------------------------------------------------ mockup

class MockupReq(BaseModel):
    front: Optional[str] = None
    back: Optional[str] = None
    scene: str = "clean"          # clean | minimal | dark | desk
    bg: str = "auto"              # auto | white | black | light | dark | gradient | custom | image
    custom_color: str = "#f1f2f4"
    bg_image: Optional[str] = None
    layout: str = "side"          # side | large | vertical
    size: int = 60
    rotation: int = 0
    perspective: int = 32
    shadow: int = 55
    radius: int = 30
    labels: bool = False
    width: int = 1280
    height: int = 800


def _mockup_src(rel: Optional[str]):
    """Accept web paths (/uploads/…, /generated/…, /mockup-backgrounds/…)
    or project-relative paths for mockup source images."""
    if not rel:
        return None
    rel2 = rel.replace("\\", "/").lstrip("/").split("?", 1)[0]
    prefix_map = {
        "uploads/": UPLOADS_DIR,
        "generated/": GENERATED_DIR,
        "mockups/": BASE_DIR / "mockups",
    }
    for prefix, root in prefix_map.items():
        if rel2.startswith(prefix):
            p = (BASE_DIR / rel2).resolve()
            try:
                p.relative_to(BASE_DIR)
            except ValueError:
                return None
            return p if p.is_file() else None
    return resolve_user_path(rel, UPLOADS_DIR) or resolve_user_path(rel, GENERATED_DIR)


@app.post("/api/mockup/upload/{side}")
async def mockup_upload(side: str, cid: str = Form(...), file: UploadFile = File(...)):
    if side not in ("front", "back"):
        raise HTTPException(400, "side must be front or back")
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "Empty file")
    from io import BytesIO
    from PIL import Image, ImageOps
    try:
        img = Image.open(BytesIO(raw))
        img.load()
        img = ImageOps.exif_transpose(img).convert("RGBA")
    except Exception as e:
        raise HTTPException(400, f"Could not read image: {e}")
    if max(img.size) > 2400:
        img.thumbnail((2400, 2400), Image.LANCZOS)

    safe_cid = re.sub(r"[^a-zA-Z0-9_-]", "", cid)[:40] or "cid"
    out_dir = UPLOADS_DIR / "mockup" / safe_cid
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"{time.strftime('%Y%m%d-%H%M%S')}_{side}.png"
    img.save(out_dir / name, "PNG", optimize=True)
    rel = f"uploads/mockup/{safe_cid}/{name}"
    return {"path": rel, "url": f"/{rel}", "width": img.width, "height": img.height}


@app.get("/api/mockup/backgrounds")
def mockup_backgrounds():
    out = []
    if MOCKUP_BG_DIR.is_dir():
        for p in sorted(MOCKUP_BG_DIR.iterdir()):
            if p.is_file() and p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                out.append({
                    "name": p.stem,
                    "path": f"mockups/backgrounds/{p.name}",
                    "url": f"/mockup-backgrounds/{p.name}",
                })
    return out


@app.post("/api/mockup/render")
def mockup_render(req: MockupReq):
    front = _mockup_src(req.front)
    back = _mockup_src(req.back)
    bg_image = _mockup_src(req.bg_image)
    if not front and not back:
        raise HTTPException(400, "Upload a front or back image first")

    opts = {
        "scene": req.scene, "bg": req.bg, "custom_color": req.custom_color,
        "bg_image": str(bg_image) if bg_image else None,
        "layout": req.layout, "size": req.size, "rotation": req.rotation,
        "perspective": req.perspective, "shadow": req.shadow, "radius": req.radius,
        "labels": req.labels, "width": req.width, "height": req.height,
    }
    key = hashlib.md5(json.dumps(
        {**opts, "front": str(front), "back": str(back)}, sort_keys=True
    ).encode()).hexdigest()[:16]
    out = MOCKUP_OUT_DIR / f"mockup_{key}.png"
    if not out.exists():
        img = mockupsvc.render(opts, front, back)
        img.save(out, "PNG")
        w, h = img.size
    else:
        from PIL import Image
        with Image.open(out) as im:
            w, h = im.size
    return {"url": f"/generated/mockups/{out.name}", "width": w, "height": h}


# ------------------------------------------------------------------ image prep

class PrepProcessReq(BaseModel):
    cid: str
    bg_mode: str = "keep"          # auto | keep
    enhance: int = 1               # 1 | 2 | 4
    rotate: float = 0.0
    flip_h: bool = False
    flip_v: bool = False
    trim: bool = False
    width: Optional[float] = None
    height: Optional[float] = None
    unit: str = "px"               # px | mm | cm | in
    dpi: int = 300
    keep_aspect: bool = True


class PrepSvgReq(BaseModel):
    cid: str
    mode: str = "preserve"         # preserve | optimize | vectorize
    detail: int = 6                # 1..10
    smoothing: bool = True
    colors: int = 6                # color precision 2..10


class PrepUseReq(BaseModel):
    cid: str
    kind: str                      # logo | photo


@app.post("/api/prep/upload")
async def prep_upload(cid: str = Form(...), file: UploadFile = File(...)):
    raw = await file.read()
    try:
        return prepsvc.new_session(cid, file.filename or "image.png", raw)
    except PrepError as e:
        raise HTTPException(400, str(e))


@app.post("/api/prep/process")
def prep_process(req: PrepProcessReq):
    try:
        return prepsvc.process(prepsvc.session_dir(req.cid), req.model_dump())
    except PrepError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Processing failed: {e}")


@app.post("/api/prep/refine")
def prep_refine(cid: str = Form(...), image: str = Form(...)):
    try:
        return prepsvc.refine(prepsvc.session_dir(cid), image)
    except PrepError as e:
        raise HTTPException(400, str(e))


@app.post("/api/prep/svg")
def prep_svg(req: PrepSvgReq):
    try:
        out = prepsvc.build_svg(prepsvc.session_dir(req.cid), req.mode,
                                req.detail, req.smoothing, req.colors)
        out["size_kb"] = round(len(out["svg"].encode("utf-8")) / 1024, 1)
        return out
    except PrepError as e:
        raise HTTPException(400, str(e))


@app.post("/api/prep/use")
def prep_use(req: PrepUseReq):
    try:
        return prepsvc.use_in_generator(req.cid, req.kind)
    except PrepError as e:
        raise HTTPException(400, str(e))


# ------------------------------------------------------------------ static

ensure_dirs()  # StaticFiles requires the directories to exist at import time

app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")
app.mount("/generated", StaticFiles(directory=GENERATED_DIR), name="generated")
app.mount("/templates", StaticFiles(directory=TEMPLATES_DIR), name="templates")
app.mount("/illustrator", StaticFiles(directory=ILLUSTRATOR_DIR), name="illustrator")
app.mount("/mockup-backgrounds", StaticFiles(directory=MOCKUP_BG_DIR), name="mockup-backgrounds")
app.mount("/", StaticFiles(directory=BASE_DIR / "app" / "web", html=True), name="web")
