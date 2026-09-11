import qrcode
from PIL import Image, ImageDraw

from ..config import CARD_W_IN


def vcard_text(data: dict) -> str:
    lines = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"FN:{data.get('name', '')}",
        f"N:{data.get('name', '')};;;;",
    ]
    if data.get("company"):
        lines.append(f"ORG:{data['company']}")
    if data.get("title"):
        lines.append(f"TITLE:{data['title']}")
    if data.get("phone"):
        lines.append(f"TEL;TYPE=WORK,VOICE:{data['phone']}")
    if data.get("email"):
        lines.append(f"EMAIL:{data['email']}")
    if data.get("website"):
        lines.append(f"URL:{data['website']}")
    if data.get("address"):
        lines.append(f"ADR;TYPE=WORK:;;{data['address']};;;;")
    lines.append("END:VCARD")
    return "\n".join(lines)


def build(qr_cfg: dict, data: dict, logo_img: Image.Image | None,
          invert: bool, logo_in_qr: bool) -> Image.Image | None:
    qtype = (qr_cfg.get("type") or "none").lower()
    if qtype == "none":
        return None

    if qtype == "vcard":
        content = vcard_text(data)
        if not data.get("name") and not data.get("phone") and not data.get("email"):
            return None
    elif qtype == "url":
        content = (qr_cfg.get("value") or "").strip()
        if content and "://" not in content:
            content = "https://" + content
    elif qtype == "email":
        v = (qr_cfg.get("value") or "").strip()
        content = f"mailto:{v}" if v else ""
    elif qtype == "phone":
        v = (qr_cfg.get("value") or "").strip()
        content = f"tel:{v}" if v else ""
    else:
        return None

    if not content:
        return None

    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=16, border=2)
    qr.add_data(content)
    qr.make(fit=True)
    fill = "white" if invert else "black"
    back = "black" if invert else "white"
    img = qr.make_image(fill_color=fill, back_color=back).convert("RGB")

    if logo_in_qr and logo_img is not None:
        side = img.width
        box_side = max(24, int(side * 0.28))
        pad = max(4, box_side // 12)
        back_rgb = (0, 0, 0) if invert else (255, 255, 255)
        logo_side = box_side - 2 * pad
        logo = logo_img.convert("RGBA")
        logo.thumbnail((logo_side, logo_side), Image.LANCZOS)
        flat = Image.new("RGBA", (box_side, box_side), back_rgb + (255,))
        d = ImageDraw.Draw(flat)
        d.rounded_rectangle([0, 0, box_side - 1, box_side - 1], radius=box_side // 5, fill=back_rgb + (255,))
        flat.alpha_composite(logo, ((box_side - logo.width) // 2, (box_side - logo.height) // 2))
        img.paste(flat.convert("RGB"), ((side - box_side) // 2, (side - box_side) // 2))

    # render at a resolution proportional to the master card (600 dpi card,
    # qr box is roughly a third of the card width -> ~700 px is a good target)
    target = int(CARD_W_IN * 600 * 0.35)
    if img.width < target:
        img = img.resize((target, target), Image.NEAREST)
    return img
