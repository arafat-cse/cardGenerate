import re
import subprocess
import time
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import templates_def
from .config import (
    AI_DIR, BASE_DIR, DEFAULT_LOGO, DEFAULT_QR, GENERATED_DIR, ILLUSTRATOR_DIR, OUTPUT_DPI,
    PDF_DIR, PNG_DIR, PREVIEW_DIR, PREVIEW_DPI, TEMPLATES_DIR,
    UPLOADS_DIR, ensure_dirs, resolve_user_path,
)
from .fonts import resolve as resolve_font
from .services import ai_illust, pdfsvc, qrsvc, render
from .services.bgremove import BgRemovalUnavailable, remove_background
from .services.images import process_upload
from .services.layout import qr_invert

app = FastAPI(title="BizCard Studio", version="1.0")


@app.on_event("startup")
def _startup():
    ensure_dirs()
    templates_def.build_all()


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


# ------------------------------------------------------------------ static

ensure_dirs()  # StaticFiles requires the directories to exist at import time

app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")
app.mount("/generated", StaticFiles(directory=GENERATED_DIR), name="generated")
app.mount("/templates", StaticFiles(directory=TEMPLATES_DIR), name="templates")
app.mount("/illustrator", StaticFiles(directory=ILLUSTRATOR_DIR), name="illustrator")
app.mount("/", StaticFiles(directory=BASE_DIR / "app" / "web", html=True), name="web")
