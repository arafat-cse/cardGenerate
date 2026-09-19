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
    # Linux
    Path("/usr/share/fonts"),
    Path("/usr/local/share/fonts"),
    Path.home() / ".fonts",
    Path.home() / ".local" / "share" / "fonts",
    # macOS
    Path("/Library/Fonts"),
    Path("/System/Library/Fonts"),
    Path.home() / "Library" / "Fonts",
]

# (filename, illustrator postscript name, family, style) - Windows/Office
# names first, then the DejaVu / Liberation / Noto faces Linux and Mac
# actually ship, so the app renders without any manual font install.
_FAMILIES = {
    "sans": [
        ("segoeui.ttf", "SegoeUI", "Segoe UI", "Regular"),
        ("arial.ttf", "ArialMT", "Arial", "Regular"),
        ("tahoma.ttf", "Tahoma", "Tahoma", "Regular"),
        ("DejaVuSans.ttf", "DejaVuSans", "DejaVu Sans", "Regular"),
        ("LiberationSans-Regular.ttf", "LiberationSans", "Liberation Sans", "Regular"),
        ("NotoSans-Regular.ttf", "NotoSans", "Noto Sans", "Regular"),
    ],
    "sansBold": [
        ("segoeuib.ttf", "SegoeUI-Bold", "Segoe UI", "Bold"),
        ("arialbd.ttf", "Arial-BoldMT", "Arial", "Bold"),
        ("tahomabd.ttf", "Tahoma-Bold", "Tahoma", "Bold"),
        ("DejaVuSans-Bold.ttf", "DejaVuSans-Bold", "DejaVu Sans", "Bold"),
        ("LiberationSans-Bold.ttf", "LiberationSans-Bold", "Liberation Sans", "Bold"),
        ("NotoSans-Bold.ttf", "NotoSans-Bold", "Noto Sans", "Bold"),
    ],
    "serif": [
        ("georgia.ttf", "Georgia", "Georgia", "Regular"),
        ("times.ttf", "TimesNewRomanPSMT", "Times New Roman", "Regular"),
        ("DejaVuSerif.ttf", "DejaVuSerif", "DejaVu Serif", "Regular"),
        ("LiberationSerif-Regular.ttf", "LiberationSerif", "Liberation Serif", "Regular"),
        ("NotoSerif-Regular.ttf", "NotoSerif", "Noto Serif", "Regular"),
    ],
    "serifBold": [
        ("georgiab.ttf", "Georgia-Bold", "Georgia", "Bold"),
        ("timesbd.ttf", "TimesNewRomanPS-BoldMT", "Times New Roman", "Bold"),
        ("DejaVuSerif-Bold.ttf", "DejaVuSerif-Bold", "DejaVu Serif", "Bold"),
        ("LiberationSerif-Bold.ttf", "LiberationSerif-Bold", "Liberation Serif", "Bold"),
        ("NotoSerif-Bold.ttf", "NotoSerif-Bold", "Noto Serif", "Bold"),
    ],
    "serifItal": [
        ("georgiai.ttf", "Georgia-Italic", "Georgia", "Italic"),
        ("timesi.ttf", "TimesNewRomanPS-ItalicMT", "Times New Roman", "Italic"),
        ("DejaVuSerif-Italic.ttf", "DejaVuSerif-Italic", "DejaVu Serif", "Italic"),
        ("LiberationSerif-Italic.ttf", "LiberationSerif-Italic", "Liberation Serif", "Italic"),
        ("NotoSerif-Italic.ttf", "NotoSerif-Italic", "Noto Serif", "Italic"),
    ],
    "mono": [
        ("consola.ttf", "Consolas", "Consolas", "Regular"),
        ("cour.ttf", "CourierNewPSMT", "Courier New", "Regular"),
        ("DejaVuSansMono.ttf", "DejaVuSansMono", "DejaVu Sans Mono", "Regular"),
        ("LiberationMono-Regular.ttf", "LiberationMono", "Liberation Mono", "Regular"),
        ("NotoSansMono-Regular.ttf", "NotoSansMono", "Noto Sans Mono", "Regular"),
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
            # rglob: system font dirs (e.g. /usr/share/fonts) nest files
            # under per-family subdirectories, not flat.
            hits = sorted(
                p for p in d.rglob(pat)
                if p.is_file() and p.suffix.lower() in (".ttf", ".otf")
            )
            if hits:
                return hits[0]
    return None


def _any_font() -> Path | None:
    """Absolute last resort: the first .ttf/.otf found anywhere searched."""
    for d in SEARCH_DIRS:
        if not d.is_dir():
            continue
        hits = sorted(p for p in list(d.rglob("*.ttf")) + list(d.rglob("*.otf")) if p.is_file())
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
    p = _any_font()
    if p is None:
        raise RuntimeError(
            "No usable fonts found on this system. Drop any .ttf files into "
            f"the project's {FONTS_DIR} folder, or install some "
            "(e.g. `sudo apt install fonts-dejavu-core fonts-liberation`)."
        )
    return _info(p, ["ArialMT"], "Arial", "Regular")


@lru_cache(maxsize=128)
def load_path(path: str, size_px: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size_px)


def available_blackletter() -> bool:
    return _find(_BLACKLETTER_PATTERNS) is not None
