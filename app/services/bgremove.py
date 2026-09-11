from pathlib import Path

from PIL import Image

from .images import trim_alpha

_session = None


class BgRemovalUnavailable(Exception):
    pass


def remove_background(src: Path, dst: Path) -> None:
    global _session
    try:
        from rembg import new_session, remove
    except ImportError as e:
        raise BgRemovalUnavailable(
            "rembg is not installed. Run setup.bat (or: .venv\\Scripts\\pip install \"rembg[cpu]\"). "
            "The first removal also downloads a ~170 MB model once, so it needs internet one time."
        ) from e

    if _session is None:
        _session = new_session("u2net")

    img = Image.open(src).convert("RGBA")
    out = remove(img, session=_session)
    out = trim_alpha(out)
    if out.width and out.height:
        out.save(dst, "PNG")
    else:
        raise RuntimeError("Background removal produced an empty image - try a different photo.")
