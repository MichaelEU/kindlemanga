#!/usr/bin/env python3
"""Convert manga .cbz chapters into e-reader books that follow the real panels.

Panels are detected with Kumiko (OpenCV), then, depending on the device:
  - Kindles ("zoom" mode): each panel becomes a tap target (Amazon "region
    magnification") that zooms to exactly that panel, in reading order,
    instead of KCC's fixed four-corner split.
  - Other readers ("panels" mode): each panel becomes its own full-screen page,
    in reading order, written as XTC (Xteink), PDF (Sony) or CBZ.

Usage:
  panelview.py <folder-or-cbz> -d DEVICE [-o outdir] [--ltr]    (see -h for device ids)
"""
import argparse, hashlib, json, os, shutil, struct, subprocess, sys, tempfile, uuid, zipfile
from html import escape
from pathlib import Path
from PIL import Image

HERE = Path(__file__).resolve().parent
KUMIKO = Path(os.environ.get("KUMIKO", HERE / "kumiko" / "kumiko"))
KINDLEGEN = os.environ.get(
    "KINDLEGEN",
    "/Applications/Kindle Previewer 4.app/Contents/Resources/KFXGen/bin/kindlegen")
# mode "zoom": Kindle guided view inside the page; "panels": one panel per page.
# Screen sizes follow Kindle Comic Converter's device profiles.
def _dev(label, w, h, mode, fmt, color=False):
    return dict(label=label, size=(w, h), mode=mode, fmt=fmt, color=color)

DEVICES = {
    # Kindles with panel view
    "basic":   _dev("Kindle (2022 and later)", 1072, 1448, "zoom", "epub"),
    "k600":    _dev("Kindle 5, 7, 8 or 10", 600, 800, "zoom", "epub"),
    "kpw":     _dev("Kindle Paperwhite 1 or 2", 758, 1024, "zoom", "epub"),
    "kpw34":   _dev("Kindle Paperwhite 3 or 4, Voyage, Oasis 1", 1072, 1448, "zoom", "epub"),
    "kpw5":    _dev("Kindle Paperwhite 5 or Signature", 1236, 1648, "zoom", "epub"),
    "kpw6":    _dev("Kindle Paperwhite 6 (2024)", 1272, 1696, "zoom", "epub"),
    "kcs":     _dev("Kindle Colorsoft", 1272, 1696, "zoom", "epub", color=True),
    "ko":      _dev("Kindle Oasis 2 or 3", 1264, 1680, "zoom", "epub"),
    "scribe":  _dev("Kindle Scribe 1 or 2", 1860, 2480, "zoom", "epub"),
    "ks3":     _dev("Kindle Scribe 3", 1986, 2648, "zoom", "epub"),
    "kscs":    _dev("Kindle Scribe Colorsoft", 1986, 2648, "zoom", "epub", color=True),
    # Older Kindles: no panel view, so one panel per page inside a Kindle book
    "k34":     _dev("Kindle Keyboard or Touch", 600, 800, "panels", "mobi"),
    "kdx":     _dev("Kindle DX", 824, 1000, "panels", "mobi"),
    "k12":     _dev("Kindle 1 or 2", 600, 670, "panels", "mobi"),
    # Kobo: reads CBZ natively
    "koc":     _dev("Kobo Clara", 1072, 1448, "panels", "cbz"),
    "kon":     _dev("Kobo Nia", 758, 1024, "panels", "cbz"),
    "kol":     _dev("Kobo Libra", 1264, 1680, "panels", "cbz"),
    "kos":     _dev("Kobo Sage or Forma", 1440, 1920, "panels", "cbz"),
    "koe":     _dev("Kobo Elipsa", 1404, 1872, "panels", "cbz"),
    # Sony Reader: every model reads PDF
    "prs500":  _dev("Sony PRS-500 or 505", 600, 800, "panels", "pdf"),
    "prs300":  _dev("Sony PRS-300 or 350 (Pocket)", 600, 800, "panels", "pdf"),
    "prs600":  _dev("Sony PRS-600, 650 or 700 (Touch)", 600, 800, "panels", "pdf"),
    "prs950":  _dev("Sony PRS-900 or 950 (Daily Edition)", 600, 1024, "panels", "pdf"),
    "prst":    _dev("Sony PRS-T1 or T2", 600, 800, "panels", "pdf"),
    "prst3":   _dev("Sony PRS-T3", 758, 1024, "panels", "pdf"),
    # Other readers
    "x4":      _dev("Xteink X4", 480, 800, "panels", "xtch"),
    "generic": _dev("Other reader (CBZ)", 1264, 1680, "panels", "cbz"),
}
FORMATS = {"zoom": {"epub", "mobi"}, "panels": {"xtch", "xtc", "pdf", "cbz", "epub", "mobi"}}
HQ = 1.5           # stored image resolution relative to screen
MIN_AREA = 0.012   # ignore detected boxes smaller than this fraction of the page
MAX_AREA = 0.80    # a panel this big gains nothing from zooming
MIN_COVERAGE = 0.45  # panels covering less of the page than this: show the whole page too


def natural_images(d):
    exts = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
    files = [p for p in Path(d).rglob("*") if p.suffix.lower() in exts and not p.name.startswith(".")]
    return sorted(files, key=lambda p: [int(t) if t.isdigit() else t for t in
                                        __import__("re").split(r"(\d+)", str(p.relative_to(d)).lower())])


def detect_panels(jpg_dir, rtl):
    cmd = [sys.executable, str(KUMIKO), "-i", str(jpg_dir)] + (["--rtl"] if rtl else [])
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    return {Path(p["filename"]).name: p for p in json.loads(out)}


def open_page(src, color):
    return Image.open(src).convert("RGB" if color else "L")


def fit_page(src, W, H, color=False):
    """Fit page into an (HQ*W)x(HQ*H) white canvas, return image + placement in that canvas."""
    im = open_page(src, color)
    CW, CH = int(W * HQ), int(H * HQ)
    s = min(CW / im.width, CH / im.height)
    nw, nh = round(im.width * s), round(im.height * s)
    im = im.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new(im.mode, (CW, CH), "white")
    ox, oy = (CW - nw) // 2, (CH - nh) // 2
    canvas.paste(im, (ox, oy))
    return canvas, s, ox, oy


def fit_screen(im, W, H, rotate_wide=False):
    """Scale an image as large as it fits on a WxH screen, centred on white."""
    if rotate_wide and W < H and im.width > im.height:
        # Turn wide panels sideways when that makes them noticeably bigger.
        if min(W / im.height, H / im.width) > 1.2 * min(W / im.width, H / im.height):
            im = im.rotate(-90, expand=True)
    s = min(W / im.width, H / im.height)
    im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
    screen = Image.new(im.mode, (W, H), "white")
    screen.paste(im, ((W - im.width) // 2, (H - im.height) // 2))
    return screen


def panel_screens(src, boxes, W, H, whole, page_first, rotate_wide, color=False):
    """Screens for one source page: the whole page and/or each panel, in reading order."""
    im = open_page(src, color)
    if whole or not boxes:
        return [fit_screen(im, W, H, rotate_wide)]
    screens = [fit_screen(im, W, H, rotate_wide)] if page_first else []
    for (x, y, w, h) in boxes:
        pad = round(0.015 * max(w, h))                 # a little breathing room
        box = (max(0, x - pad), max(0, y - pad), min(im.width, x + w + pad), min(im.height, y + h + pad))
        screens.append(fit_screen(im.crop(box), W, H, rotate_wide))
    return screens


def xtc_page(screen, gray):
    """One XTG (1-bit) or XTH (4-shade) page, laid out the way CrossPoint and the Xteink firmware read them."""
    import numpy as np
    w, h = screen.size
    if gray:
        # Dither to 4 shades, then map to XTH values: 0 white, 1 dark grey, 2 light grey, 3 black.
        palette = Image.new("P", (1, 1))
        palette.putpalette([v for g in (255, 170, 85, 0) for v in (g, g, g)] + [0] * 756)
        shade = np.asarray(screen.convert("RGB").quantize(palette=palette, dither=Image.Dither.FLOYDSTEINBERG))
        value = np.array([0, 2, 1, 3], dtype=np.uint8)[shade]
        # Two bit planes (high bit first), each scanned column by column from the right edge,
        # 8 vertical pixels per byte, topmost pixel in the most significant bit.
        cols = value[:, ::-1].T
        planes = [np.packbits((cols >> bit) & 1, axis=1) for bit in (1, 0)]
        data = b"".join(plane.tobytes() for plane in planes)
        magic = b"XTH\0"
    else:
        # Rows packed MSB-first and padded to whole bytes; a set bit is a white pixel.
        data = np.packbits(np.asarray(screen.convert("1"), dtype=bool), axis=1).tobytes()  # Floyd-Steinberg
        magic = b"XTG\0"
    head = struct.pack("<4sHHBBI8s", magic, w, h, 0, 0, len(data), hashlib.md5(data).digest()[:8])
    return head + data, w, h


def write_xtc(screens, dest, gray=False):
    """Xteink's native container: XTC (1-bit pages) or XTCH (4-shade pages), no metadata or chapters."""
    pages = [xtc_page(screen, gray) for screen in screens]
    index_offset = 56
    offset = data_offset = index_offset + 16 * len(pages)
    out = [struct.pack("<4sHH8xQQQQQ", b"XTCH" if gray else b"XTC\0", 1, len(pages),
                       0, index_offset, data_offset, 0, 0)]
    for blob, w, h in pages:
        out.append(struct.pack("<QIHH", offset, len(blob), w, h))
        offset += len(blob)
    out += [blob for blob, _, _ in pages]
    Path(dest).write_bytes(b"".join(out))


def write_pdf(screens, dest):
    screens[0].save(dest, "PDF", save_all=True, append_images=screens[1:], resolution=170)


def write_cbz(screens, dest):
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_STORED) as z:
        for i, screen in enumerate(screens, 1):
            path = Path(dest).with_name(f"{i:04d}.jpg")
            screen.save(path, quality=85)
            z.write(path, path.name)
            path.unlink()


WRITERS = {"xtc": write_xtc, "xtch": lambda screens, dest: write_xtc(screens, dest, gray=True),
           "pdf": write_pdf, "cbz": write_cbz}


def kindlegen(epub):
    """Build a .mobi next to the .epub with Amazon's kindlegen (from Kindle Previewer)."""
    res = subprocess.run([KINDLEGEN, "-dont_append_source", "-locale", "en", str(epub)],
                         capture_output=True, text=True)
    mobi = Path(epub).with_suffix(".mobi")
    if not mobi.exists():
        print(res.stdout[-3000:])
        sys.exit("kindlegen failed")
    return mobi


def write_screen_book(screens, dest, title, W, H, rtl, fmt):
    """Fixed-layout Kindle book with one screen per page (for Kindles without panel view)."""
    book = Path(dest).parent / "screen_book"
    (book / "OEBPS" / "Images").mkdir(parents=True)
    (book / "OEBPS" / "Text").mkdir()
    (book / "OEBPS" / "Text" / "style.css").write_text(CSS)
    names = []
    for i, screen in enumerate(screens, 1):
        name = f"{i:04d}"
        screen.save(book / "OEBPS" / "Images" / f"{name}.jpg", quality=88, optimize=True)
        if i == 1:
            screen.save(book / "OEBPS" / "Images" / "cover.jpg", quality=88)
        (book / "OEBPS" / "Text" / f"{name}.xhtml").write_text(page_xhtml(name, W, H, [], i))
        names.append(name)
    build_epub(book, title, names, W, H, rtl)
    epub = Path(dest).with_suffix(".epub")
    zip_epub(book, epub)
    result = epub if fmt == "epub" else kindlegen(epub)
    if result != Path(dest):
        shutil.move(result, dest)


def page_xhtml(name, W, H, panels, n):
    """panels: list of (x,y,w,h) in screen (WxH) coordinates, already in reading order."""
    img = f'<img width="{W}" height="{H}" src="../Images/{name}.jpg"/>'
    body = ['<div style="text-align:center;">', '<div style="display:none;">.</div>', img, "</div>"]
    if panels:
        body.append('<div id="PV">')
        for i, (x, y, w, h) in enumerate(panels, 1):
            body.append(
                f'<div id="PV-{i}" style="position:absolute;left:{x / W * 100:.3f}%;top:{y / H * 100:.3f}%;'
                f'width:{w / W * 100:.3f}%;height:{h / H * 100:.3f}%;">'
                f'<a style="display:inline-block;width:100%;height:100%;" class="app-amzn-magnify" '
                f"data-app-amzn-magnify='{{\"targetId\":\"PV-{i}-P\", \"ordinal\":{i}}}'></a></div>")
        body.append("</div>")
        for i, (x, y, w, h) in enumerate(panels, 1):
            pad = 0.015 * max(w, h)                       # a little breathing room
            x0, y0 = max(0, x - pad), max(0, y - pad)
            x1, y1 = min(W, x + w + pad), min(H, y + h + pad)
            pw, ph = x1 - x0, y1 - y0
            s = min(W / pw, H / ph)                        # zoom so the panel fills the screen
            vw, vh = pw * s, ph * s                        # visible window size (px)
            vx, vy = (W - vw) / 2, (H - vh) / 2            # centred on screen
            body.append(
                f'<div class="PV-P" id="PV-{i}-P">'
                f'<div style="position:absolute;left:{vx:.1f}px;top:{vy:.1f}px;width:{vw:.1f}px;height:{vh:.1f}px;overflow:hidden;">'
                f'<img style="position:absolute;left:{-x0 * s:.1f}px;top:{-y0 * s:.1f}px;" '
                f'width="{W * s:.1f}" height="{H * s:.1f}" src="../Images/{name}.jpg"/>'
                f"</div></div>")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head>
<title>{escape(name)}</title>
<link href="style.css" type="text/css" rel="stylesheet"/>
<meta name="viewport" content="width={W}, height={H}"/>
</head>
<body style="">
{chr(10).join(body)}
</body>
</html>
"""


CSS = """@page { margin: 0; }
body { display: block; margin: 0; padding: 0; }
img { display: block; }
#PV { position: absolute; width: 100%; height: 100%; top: 0; left: 0; }
.PV-P { width: 100%; height: 100%; top: 0; left: 0; position: absolute; display: none; background-color: #ffffff; }
"""


def build_epub(root, title, names, W, H, rtl):
    uid = str(uuid.uuid4())
    o = root / "OEBPS"
    (root / "META-INF").mkdir(exist_ok=True)
    (root / "mimetype").write_text("application/epub+zip")
    (root / "META-INF" / "container.xml").write_text(
        '<?xml version="1.0"?>\n<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
        '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
        "</rootfiles></container>")
    first = names[0]
    (o / "toc.ncx").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<ncx version="2005-1" xml:lang="en" xmlns="http://www.daisy.org/z3986/2005/ncx/">'
        f'<head><meta name="dtb:uid" content="urn:uuid:{uid}"/><meta name="dtb:depth" content="1"/>'
        '<meta name="dtb:totalPageCount" content="0"/><meta name="dtb:maxPageNumber" content="0"/></head>'
        f"<docTitle><text>{escape(title)}</text></docTitle><navMap>"
        f'<navPoint id="p1"><navLabel><text>{escape(title)}</text></navLabel><content src="Text/{first}.xhtml"/></navPoint>'
        "</navMap></ncx>")
    (o / "nav.xhtml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n<html xmlns="http://www.w3.org/1999/xhtml" '
        'xmlns:epub="http://www.idpf.org/2007/ops"><head><title>' + escape(title) + '</title><meta charset="utf-8"/></head><body>'
        '<nav epub:type="toc" id="toc"><ol>' f'<li><a href="Text/{first}.xhtml">{escape(title)}</a></li>' "</ol></nav></body></html>")
    manifest = ['<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
                '<item id="nav" href="nav.xhtml" properties="nav" media-type="application/xhtml+xml"/>',
                '<item id="cover" href="Images/cover.jpg" media-type="image/jpeg" properties="cover-image"/>',
                '<item id="css" href="Text/style.css" media-type="text/css"/>']
    spine, side = [], ("right" if rtl else "left")
    for n in names:
        manifest.append(f'<item id="page_{n}" href="Text/{n}.xhtml" media-type="application/xhtml+xml"/>')
        manifest.append(f'<item id="img_{n}" href="Images/{n}.jpg" media-type="image/jpeg"/>')
        spine.append(f'<itemref idref="page_{n}" linear="yes" properties="page-spread-{side}"/>')
        side = "left" if side == "right" else "right"
    wm = "horizontal-rl" if rtl else "horizontal-lr"
    (o / "content.opf").write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<package version="3.0" unique-identifier="BookID" xmlns="http://www.idpf.org/2007/opf">
<metadata xmlns:opf="http://www.idpf.org/2007/opf" xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:title>{escape(title)}</dc:title>
<dc:language>en-US</dc:language>
<dc:identifier id="BookID">urn:uuid:{uid}</dc:identifier>
<meta property="dcterms:modified">2026-01-01T00:00:00Z</meta>
<meta name="cover" content="cover"/>
<meta name="fixed-layout" content="true"/>
<meta name="original-resolution" content="{W}x{H}"/>
<meta name="book-type" content="comic"/>
<meta name="primary-writing-mode" content="{wm}"/>
<meta name="zero-gutter" content="true"/>
<meta name="zero-margin" content="true"/>
<meta name="ke-border-color" content="#FFFFFF"/>
<meta name="ke-border-width" content="0"/>
<meta name="orientation-lock" content="none"/>
<meta name="region-mag" content="true"/>
<meta property="rendition:spread">landscape</meta>
<meta property="rendition:layout">pre-paginated</meta>
</metadata>
<manifest>
{chr(10).join(manifest)}
</manifest>
<spine page-progression-direction="{'rtl' if rtl else 'ltr'}" toc="ncx">
{chr(10).join(spine)}
</spine>
</package>
""")


def zip_epub(root, dest):
    with zipfile.ZipFile(dest, "w") as z:
        z.write(root / "mimetype", "mimetype", compress_type=zipfile.ZIP_STORED)
        for p in sorted(root.rglob("*")):
            if p.is_file() and p.name != "mimetype":
                z.write(p, p.relative_to(root), compress_type=zipfile.ZIP_DEFLATED)


def convert(cbz, device, rtl, nozoom, outdir, keep_epub, debug, title=None, skip_first=0, skip_last=0,
            fmt=None, page_first=False, rotate_wide=False):
    profile = DEVICES[device]
    W, H = profile["size"]
    fmt = fmt or profile["fmt"]
    cbz = Path(cbz)
    title = title or cbz.stem
    outdir = Path(outdir); outdir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        src, jpg, book = tmp / "src", tmp / "jpg", tmp / "book"
        with zipfile.ZipFile(cbz) as z:
            z.extractall(src)
        pages = natural_images(src)
        jpg.mkdir()
        for i, p in enumerate(pages, 1):
            Image.open(p).convert("RGB").save(jpg / f"{i:04d}.jpg", quality=95)
        info = detect_panels(jpg, rtl)
        safe = title.replace("/", "-")
        if profile["mode"] == "panels":
            screens = []
            for i, p in enumerate(pages, 1):
                k = info[f"{i:04d}.jpg"]
                area = k["size"][0] * k["size"][1]
                boxes = [b for b in k["panels"] if b[2] * b[3] >= MIN_AREA * area]
                if len(boxes) == 1 and boxes[0][2] * boxes[0][3] > MAX_AREA * area:
                    boxes = []                          # one full-page panel: just show the page
                coverage = sum(b[2] * b[3] for b in boxes) / area
                whole = i in nozoom or i <= skip_first or i > len(pages) - skip_last
                screens += panel_screens(p, boxes, W, H, whole, page_first or coverage < MIN_COVERAGE,
                                         rotate_wide, profile["color"])
            result = tmp / f"book.{fmt}"
            if fmt in ("epub", "mobi"):
                write_screen_book(screens, result, title, W, H, rtl, fmt)
            else:
                WRITERS[fmt](screens, result)
            part = outdir / f".{safe}.{fmt}.part"
            shutil.copy(result, part)
            os.replace(part, outdir / f"{safe}.{fmt}")
            return f"{title}: {len(pages)} pages -> {len(screens)} screens"
        (book / "OEBPS" / "Images").mkdir(parents=True)
        (book / "OEBPS" / "Text").mkdir()
        (book / "OEBPS" / "Text" / "style.css").write_text(CSS)
        names, dbg = [], []
        for i, p in enumerate(pages, 1):
            name = f"{i:04d}"
            canvas, s, ox, oy = fit_page(p, W, H, profile["color"])
            canvas.save(book / "OEBPS" / "Images" / f"{name}.jpg", quality=88, optimize=True)
            if i == 1:
                canvas.convert("RGB").save(book / "OEBPS" / "Images" / "cover.jpg", quality=88)
            panels = []
            k = info[f"{name}.jpg"]
            iw, ih = k["size"]
            if i not in nozoom and i > skip_first and i <= len(pages) - skip_last:
                for (x, y, w, h) in k["panels"]:
                    if MIN_AREA <= (w * h) / (iw * ih) <= MAX_AREA:
                        # source px -> screen (W x H) px
                        panels.append(((x * s + ox) / HQ, (y * s + oy) / HQ, w * s / HQ, h * s / HQ))
            names.append(name)
            (book / "OEBPS" / "Text" / f"{name}.xhtml").write_text(page_xhtml(name, W, H, panels, i))
            dbg.append((i, len(panels)))
        build_epub(book, title, names, W, H, rtl)
        epub = tmp / f"{title}.epub"
        zip_epub(book, epub)
        if fmt == "epub":
            result = epub
        else:
            result = kindlegen(epub)
            if keep_epub:
                shutil.copy(epub, outdir / f"{safe}.epub")
        part = outdir / f".{safe}.{fmt}.part"          # never leave a half-written book behind
        shutil.copy(result, part)
        os.replace(part, outdir / f"{safe}.{fmt}")
        if debug:
            shutil.copytree(book, outdir / f"{title}_book", dirs_exist_ok=True)
    return f"{title}: {len(pages)} pages, panels/page = {[n for _, n in dbg]}"


def _job(args):
    cbz, dest_dir, title, opts = args
    try:
        return True, cbz, convert(
            cbz, opts["device"], opts["rtl"], opts["nozoom"], dest_dir, opts["keep_epub"], False,
            title=title, skip_first=opts["skip_first"], skip_last=opts["skip_last"], fmt=opts["fmt"],
            page_first=opts["page_first"], rotate_wide=opts["rotate_wide"])
    except BaseException as e:  # keep going on a bad file
        return False, cbz, f"{type(e).__name__}: {e}"


def main():
    ap = argparse.ArgumentParser(description="Convert manga .cbz files into Kindle books with per-panel guided view.")
    ap.add_argument("input", help="a .cbz file, or a folder (searched recursively for .cbz)")
    ap.add_argument("-d", "--device", choices=DEVICES, default="basic")
    ap.add_argument("--ltr", action="store_true", help="left-to-right (western) instead of manga right-to-left")
    ap.add_argument("--nozoom", default="", help="single file only: 1-based pages to leave without panel zoom")
    ap.add_argument("--skip-first", type=int, default=0, help="leave the first N pages of each chapter without zoom")
    ap.add_argument("--skip-last", type=int, default=0, help="leave the last N pages of each chapter without zoom")
    ap.add_argument("-o", "--out", default="out")
    ap.add_argument("-j", "--jobs", type=int, default=2, help="chapters converted in parallel (folder mode)")
    ap.add_argument("-f", "--format", choices=["epub", "mobi", "xtch", "xtc", "pdf", "cbz"],
                    help="Kindles: epub (default, Send to Kindle) or mobi (USB, needs Kindle Previewer); "
                         "other readers: xtch (Xteink, 4 shades), xtc (Xteink, black and white), pdf or cbz "
                         "(default depends on the device)")
    ap.add_argument("--page-first", action="store_true",
                    help="one-panel-per-page devices: show each whole page before its panels")
    ap.add_argument("--rotate-wide", action="store_true",
                    help="one-panel-per-page devices: turn wide panels sideways to make them bigger")
    ap.add_argument("--keep-epub", action="store_true", help="with --format mobi, also keep the epub")
    ap.add_argument("--redo", action="store_true", help="re-convert even if the book already exists")
    a = ap.parse_args()
    try:
        os.setpgrp()  # own process group, so a GUI "Stop" can end every worker at once
    except OSError:
        pass
    profile = DEVICES[a.device]
    fmt = a.format or profile["fmt"]
    if fmt not in FORMATS[profile["mode"]]:
        ap.error(f"{profile['label']} can use: {', '.join(sorted(FORMATS[profile['mode']]))}")
    opts = dict(device=a.device, rtl=not a.ltr, nozoom={int(x) for x in a.nozoom.split(",") if x},
                keep_epub=a.keep_epub, skip_first=a.skip_first, skip_last=a.skip_last, fmt=fmt,
                page_first=a.page_first, rotate_wide=a.rotate_wide)
    src, out = Path(a.input), Path(a.out)
    if src.is_file():
        candidates, src = [src], src.parent
    else:
        candidates = sorted(src.rglob("*.cbz"), key=lambda p: str(p).lower())
    jobs, skipped = [], 0
    for cbz in candidates:
        if cbz.name.startswith("."):
            continue
        rel = cbz.relative_to(src)
        # chapters straight inside the dropped folder belong to a series named after that folder
        series = rel.parent if rel.parent.parts else Path(src.name)
        dest = out / series
        title = f"{series.name} - {cbz.stem}"
        if (dest / f'{title.replace("/", "-")}.{fmt}').exists() and not a.redo:
            skipped += 1
            continue
        jobs.append((cbz, dest, title, opts))
    print(f"{len(jobs)} to convert, {skipped} already done", flush=True)
    from concurrent.futures import ProcessPoolExecutor
    failed = []
    with ProcessPoolExecutor(max_workers=max(1, a.jobs)) as ex:
        for n, (ok, cbz, msg) in enumerate(ex.map(_job, jobs), 1):
            print(f"[{n}/{len(jobs)}] {'ok  ' if ok else 'FAIL'} {cbz.relative_to(src)}" + ("" if ok else f"  -> {msg}"), flush=True)
            if not ok:
                failed.append(cbz)
    print(f"done: {len(jobs) - len(failed)} converted, {len(failed)} failed")
    for f in failed:
        print("  failed:", f)


if __name__ == "__main__":
    main()
