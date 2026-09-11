import os
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

from .config import FONTS_DIR

_WINDIR = Path(os.environ.get("WINDIR", r"C:\Windows"))
SEARCH_DIRS = [
    FONTS_DIR,  # project fonts folder - drop any .ttf here to use it
    _WINDIR / "Fonts",
    Path.home() / "AppData" / "Local" / "Microsoft" / "Windows" / "Fonts",
]

# (filename, illustrator postscript name, family, style)
_FAMILIES = {
    "sans": [
        ("segoeui.ttf", "SegoeUI", "Segoe UI", "Regular"),
        ("arial.ttf", "ArialMT", "Arial", "Regular"),
        ("tahoma.ttf", "Tahoma", "Tahoma", "Regular"),
    ],
    "sansBold": [
        ("segoeuib.ttf", "SegoeUI-Bold", "Segoe UI", "Bold"),
        ("arialbd.ttf", "Arial-BoldMT", "Arial", "Bold"),
        ("tahomabd.ttf", "Tahoma-Bold", "Tahoma", "Bold"),
    ],
    "serif": [
        ("georgia.ttf", "Georgia", "Georgia", "Regular"),
        ("times.ttf", "TimesNewRomanPSMT", "Times New Roman", "Regular"),
    ],
    "serifBold": [
        ("georgiab.ttf", "Georgia-Bold", "Georgia", "Bold"),
        ("timesbd.ttf", "TimesNewRomanPS-BoldMT", "Times New Roman", "Bold"),
    ],
    "serifItal": [
        ("georgiai.ttf", "Georgia-Italic", "Georgia", "Italic"),
        ("timesi.ttf", "TimesNewRomanPS-ItalicMT", "Times New Roman", "Italic"),
    ],
    "mono": [
        ("consola.ttf", "Consolas", "Consolas", "Regular"),
        ("cour.ttf", "CourierNewPSMT", "Courier New", "Regular"),
    ],
}

# Old English / blackletter faces (used by the Noir template). Windows has
# "Old English Text MT" when MS Office is installed; otherwise drop any
# blackletter .ttf into the project fonts/ folder.
_BLACKLETTER_PATTERNS = [
    "blackletter.ttf", "Blackletter*.ttf",
    "*oldenglish*.ttf", "*oldeng*.ttf", "OLDENGL*.TTF",
    "*unifraktur*.ttf", "*cloister*.ttf", "*fraktur*.ttf",
]
_BLACKLETTER_PS = ["OldEnglishTextMT", "UnifrakturMaguntia", "UnifrakturCook"]


def _find(patterns: list[str]) -> Path | None:
    for d in SEARCH_DIRS:
        if not d.is_dir():
            continue
        for pat in patterns:
            hits = sorted(
                p for p in d.glob(pat)
                if p.is_file() and p.suffix.lower() in (".ttf", ".otf")
            )
            if hits:
                return hits[0]
    return None


def _info(path: Path, ps_names: list[str], family: str | None, style: str | None) -> dict:
    fam, sty = family, style
    try:
        got = ImageFont.truetype(str(path), 20).getname()
        if not fam:
            fam, sty = got[0], got[1]
    except Exception:
        fam = fam or ""
        sty = sty or "Regular"
    return {
        "path": str(path),
        "ps": list(ps_names),
        "family": fam or "",
        "style": sty or "Regular",
    }


@lru_cache(maxsize=None)
def resolve(family_key: str) -> dict:
    key = family_key
    if key == "blackletter":
        p = _find(_BLACKLETTER_PATTERNS)
        if p:
            return _info(p, _BLACKLETTER_PS, None, None)
        key = "serifBold"
    for fname, ps, fam, sty in _FAMILIES.get(key, _FAMILIES["sans"]):
        p = _find([fname])
        if p:
            return _info(p, [ps], fam, sty)
    p = _find(["arial.ttf"]) or _FAMILIES["sans"][0][0]
    return _info(Path(p), ["ArialMT"], "Arial", "Regular")


@lru_cache(maxsize=128)
def load_path(path: str, size_px: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size_px)


def available_blackletter() -> bool:
    return _find(_BLACKLETTER_PATTERNS) is not None
