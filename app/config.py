from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

UPLOADS_DIR = BASE_DIR / "uploads"
LOGOS_DIR = UPLOADS_DIR / "logos"
PHOTOS_DIR = UPLOADS_DIR / "photos"
QR_DIR = UPLOADS_DIR / "qr"
ORIGINALS_DIR = UPLOADS_DIR / "originals"
PREP_DIR = UPLOADS_DIR / "prep"

GENERATED_DIR = BASE_DIR / "generated"
PNG_DIR = GENERATED_DIR / "png"
PDF_DIR = GENERATED_DIR / "pdf"
PREVIEW_DIR = GENERATED_DIR / "preview"
AI_DIR = GENERATED_DIR / "ai"
MOCKUP_OUT_DIR = GENERATED_DIR / "mockups"

MOCKUPS_DIR = BASE_DIR / "mockups"
MOCKUP_BG_DIR = MOCKUPS_DIR / "backgrounds"

ASSETS_DIR = BASE_DIR / "assets"
DEFAULT_LOGO = ASSETS_DIR / "default_logo.png"
DEFAULT_QR = ASSETS_DIR / "qr.png"

TEMPLATES_DIR = BASE_DIR / "templates"
ILLUSTRATOR_DIR = BASE_DIR / "illustrator"
SCRIPTS_DIR = ILLUSTRATOR_DIR / "scripts"
JOBS_DIR = ILLUSTRATOR_DIR / "jobs"
FONTS_DIR = BASE_DIR / "fonts"

WEB_DIR = Path(__file__).resolve().parent / "web"

CARD_W_IN = 86 / 25.4   # 86 mm
CARD_H_IN = 54 / 25.4   # 54 mm
BLEED_IN = 0.125

MASTER_DPI = 600
OUTPUT_DPI = 300
PREVIEW_DPI = 150

_ALL_DIRS = [
    LOGOS_DIR, PHOTOS_DIR, QR_DIR, ORIGINALS_DIR, PREP_DIR,
    PNG_DIR, PDF_DIR, PREVIEW_DIR, AI_DIR, MOCKUP_OUT_DIR,
    MOCKUP_BG_DIR,
    TEMPLATES_DIR, SCRIPTS_DIR, JOBS_DIR, FONTS_DIR, ASSETS_DIR,
]


def ensure_dirs() -> None:
    for d in _ALL_DIRS:
        d.mkdir(parents=True, exist_ok=True)


def resolve_user_path(rel: str | None, base: Path) -> Path | None:
    """Resolve a client-supplied relative path safely inside the project."""
    if not rel:
        return None
    p = (base / rel).resolve()
    try:
        p.relative_to(BASE_DIR)
    except ValueError:
        return None
    return p if p.is_file() else None
