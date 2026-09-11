# BizCard Studio

A **local-only** business card generator for Windows. No cloud, no accounts, no server —
everything runs on your PC and every file stays on your PC.

Design a two-sided card (front + back) in the browser, then export:

- **PNG** (front + back, 300 DPI, print-ready)
- **PDF** (2 pages with 0.125 in bleed)
- **.ai** (Adobe Illustrator builds the card natively via a script — 2 artboards)

It also does local AI background removal, local QR codes (vCard / link / email / phone,
with your logo embedded like on the sample noir card), and 10 two-sided templates.

---

## Setup (first time only — about 5 minutes)

1. **Install Python** 3.10–3.12 from <https://www.python.org/downloads/>
   - IMPORTANT: on the first installer screen, tick **"Add python.exe to PATH"**.
2. Double-click **`setup.bat`** and wait until it says *Setup complete*.
   (This installs everything into a local `.venv` folder — nothing is installed system-wide.)
3. Double-click **`start.bat`** from now on. That's it.

`start.bat` opens **http://127.0.0.1:8000** in your browser automatically.
Keep the black console window open while you work; close it to stop the app.

Prefer the terminal?

```bat
.venv\Scripts\activate
uvicorn app.main:app --reload
```

## One-time downloads (needs internet once, then works offline)

- The first time you click **Remove background**, a ~170 MB AI model (`u2net`) is
  downloaded to `C:\Users\<you>\.u2net`. After that, background removal is fully offline.
- If you skip `setup.bat`, `start.bat` installs everything automatically on first launch.

Everything else — templates, uploads, QR codes, previews, PNG/PDF, Illustrator
automation — never touches the internet.

## How to make a card

1. Pick a **template** (each has a front and a back — thumbnails show both).
2. Fill in **card details** and **contact** fields (empty fields are simply skipped).
3. Upload a **logo** (and a photo for the *Portrait Focus* template).
   Click **Remove background** if the logo isn't transparent yet.
4. Choose what the **QR code** contains — `vCard` packs the whole contact card
   into the QR. Tick *"Put the logo inside the QR"* to match the noir sample style.
5. The **preview** (front on top, back below) updates as you type — it is rendered by
   the same engine that produces the final files, so what you see is what prints.
6. Click **Generate PNG + PDF**. Files land in:
   - `generated/png/` – front + back at 300 DPI
   - `generated/pdf/` – 2-page print PDF with bleed
7. Click **Send to Illustrator** to have Adobe Illustrator build the same card as a
   real .ai file (2 artboards). The .ai is saved to `generated/ai/<job>/card.ai`.

### Folders

```
uploads/      your logos / photos / originals (never leaves the PC)
generated/    png | pdf | preview | ai outputs
templates/    template-01 … template-10 (template.json is plain editable JSON)
illustrator/  scripts/  the ExtendScript + job hand-off
              jobs/      per-render config, assets and card.ai
fonts/        (optional) drop any .ttf here to use it in templates
```

## Adobe Illustrator notes

- The app auto-detects Illustrator in `C:\Program Files\Adobe\...`.
  If it isn't found (the header shows *"Illustrator not found"*), create a file
  **`illustrator_path.txt`** next to `start.bat` containing the full path to
  `Illustrator.exe`, e.g.:
  `C:\Program Files\Adobe\Adobe Illustrator 2025\Support Files\Contents\Windows\Illustrator.exe`
- The .ai document is built in **RGB** so it matches your preview exactly.
  For print shops that want CMYK, use `File → Document Color Mode → CMYK` in
  Illustrator before saving/hand-off.
- The name font on the *Noir Classic* template uses an Old-English/blackletter face.
  Windows usually has **Old English Text MT** (with MS Office). If the header shows a
  different fallback font, drop any blackletter `.ttf` (e.g. UnifrakturMaguntia) into
  the **`fonts/`** folder and also install it in Windows (right-click → Install) so
  Illustrator can use it too.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `start.bat` says Python not found | Reinstall Python and tick "Add python.exe to PATH" |
| Port 8000 already in use | Close the other program, or change `port=8000` at the bottom of `main.py` |
| Remove background fails | Run `setup.bat` again; check internet for the one-time model download |
| Illustrator file never appears | Illustrator may show a first-run/license dialog — complete it once, then press "Send to Illustrator" again |
| Bangla/other scripts in card text | Latin fonts are used by default; complex scripts are best handled in the .ai step in Illustrator |

## Security

The app only listens on `127.0.0.1` — your own PC. There is no login by design
(nothing is reachable from the network).
