import glob
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

from ..config import (
    AI_DIR, BASE_DIR, JOBS_DIR, SCRIPTS_DIR,
)
from . import layout

_GLOBS = [
    r"C:\Program Files\Adobe\*Adobe Illustrator*\Support Files\Contents\Windows\Illustrator.exe",
    r"C:\Program Files\Adobe\*\Support Files\Contents\Windows\Illustrator.exe",
    r"C:\Program Files (x86)\Adobe\*\Support Files\Contents\Windows\Illustrator.exe",
]

JSX_PATH = SCRIPTS_DIR / "generate_bizcard.jsx"


def find_illustrator() -> Path | None:
    override = BASE_DIR / "illustrator_path.txt"
    if override.exists():
        p = Path(override.read_text(encoding="utf-8").strip().strip('"'))
        if p.is_file():
            return p
    for pat in _GLOBS:
        for hit in sorted(glob.glob(pat)):
            return Path(hit)
    return None


def build_job(cid: str, tpl: dict, data: dict, assets: dict, qr_img) -> str:
    """Write the job folder (config + assets) and point the JSX script at it."""
    job_name = time.strftime("%Y%m%d-%H%M%S") + "_" + re.sub(r"[^a-zA-Z0-9]", "", cid)[:8]
    job_dir = JOBS_DIR / job_name
    (job_dir / "assets").mkdir(parents=True, exist_ok=True)

    for role in ("logo", "photo"):
        src = assets.get(role)
        if src:
            shutil.copy2(src, job_dir / "assets" / f"{role}.png")
    if qr_img is not None:
        qr_img.save(job_dir / "assets" / "qr.png")

    has = {k: assets.get(k) is not None for k in ("logo", "photo")}
    has["qr"] = qr_img is not None

    dy_back = layout.CARD_H_PT + layout.GAP_PT
    items: list[dict] = []
    for idx, side_key in enumerate(("front", "back")):
        dy = 0.0 if idx == 0 else dy_back
        for it in layout.resolve_side(tpl, tpl["sides"][side_key], data, has):
            it = dict(it)
            it["dy"] = dy
            items.append(it)

    config = {
        "doc": {
            "w": layout.CARD_W_PT, "h": layout.CARD_H_PT,
            "bleed": layout.BLEED_PT, "gap": layout.GAP_PT,
        },
        "items": items,
        "out": {"ai": "card.ai"},
    }
    # ensure_ascii=True keeps config.jsx pure ASCII (\uXXXX escapes), which
    # ExtendScript's evalFile reads reliably regardless of its default encoding.
    (job_dir / "config.jsx").write_text(
        "var JOB = " + json.dumps(config, ensure_ascii=True) + ";", encoding="utf-8"
    )
    (job_dir / "job.json").write_text(
        json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    (SCRIPTS_DIR / "current_job.txt").write_text(str(job_dir), encoding="utf-8")
    return job_name


def launch(job_name: str) -> bool:
    exe = find_illustrator()
    if not exe:
        return False
    subprocess.Popen([str(exe), str(JSX_PATH)], cwd=str(SCRIPTS_DIR))
    return True


def job_status(job_name: str) -> dict:
    if not re.fullmatch(r"[0-9]{8}-[0-9]{6}_[a-zA-Z0-9]{1,8}", job_name):
        return {"status": "error", "message": "bad job id"}
    done = JOBS_DIR / job_name / "done.json"
    if not done.exists():
        return {"status": "running"}
    try:
        res = json.loads(done.read_text(encoding="utf-8"))
    except Exception:
        return {"status": "running"}
    if not res.get("ok"):
        return {"status": "error", "message": res.get("error") or "Illustrator script failed"}
    ai_path = AI_DIR / job_name
    ai_path.mkdir(parents=True, exist_ok=True)
    final = ai_path / "card.ai"
    if not final.exists():
        shutil.copy2(JOBS_DIR / job_name / "card.ai", final)
        if (JOBS_DIR / job_name / "assets").is_dir():
            shutil.copytree(JOBS_DIR / job_name / "assets", ai_path / "assets", dirs_exist_ok=True)
    return {"status": "done", "url": f"/generated/ai/{job_name}/card.ai"}
