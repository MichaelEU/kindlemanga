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
def _dev(label, w, h, mode, fmt, color=False, ppi=300):
    return dict(label=label, size=(w, h), mode=mode, fmt=fmt, color=color, ppi=ppi)

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
    "k34":     _dev("Kindle Keyboard or Touch", 600, 800, "panels", "mobi", ppi=167),
    "kdx":     _dev("Kindle DX", 824, 1000, "panels", "mobi", ppi=150),
    "k12":     _dev("Kindle 1 or 2", 600, 670, "panels", "mobi", ppi=167),
    # Kobo: reads CBZ natively
    "koc":     _dev("Kobo Clara", 1072, 1448, "panels", "cbz"),
    "kon":     _dev("Kobo Nia", 758, 1024, "panels", "cbz", ppi=212),
    "kol":     _dev("Kobo Libra", 1264, 1680, "panels", "cbz"),
    "kos":     _dev("Kobo Sage or Forma", 1440, 1920, "panels", "cbz"),
    "koe":     _dev("Kobo Elipsa", 1404, 1872, "panels", "cbz", ppi=227),
    # Sony Reader: every model reads PDF
    "prs500":  _dev("Sony PRS-500 or 505", 600, 800, "panels", "pdf", ppi=167),
    "prs300":  _dev("Sony PRS-300 or 350 (Pocket)", 600, 800, "panels", "pdf", ppi=200),
    "prs600":  _dev("Sony PRS-600, 650 or 700 (Touch)", 600, 800, "panels", "pdf", ppi=167),
    "prs950":  _dev("Sony PRS-900 or 950 (Daily Edition)", 600, 1024, "panels", "pdf", ppi=170),
    "prst":    _dev("Sony PRS-T1 or T2", 600, 800, "panels", "pdf", ppi=167),
    "prst3":   _dev("Sony PRS-T3", 758, 1024, "panels", "pdf", ppi=212),
    # Other readers
    "x4":      _dev("Xteink X4", 480, 800, "panels", "xtch", ppi=220),
    "generic": _dev("Other reader (CBZ)", 1264, 1680, "panels", "cbz"),
}
FORMATS = {"zoom": {"epub", "mobi"}, "panels": {"xtch", "xtc", "pdf", "cbz", "epub", "mobi"}}
HQ = 1.5           # stored image resolution relative to screen
MIN_AREA = 0.012   # ignore detected boxes smaller than this fraction of the page
MAX_AREA = 0.80    # a panel this big gains nothing from zooming
MIN_COVERAGE = 0.45  # panels covering less of the page than this: show the whole page too
COLOUR_PAGE = 0.01   # more colourful pixels than this: a cover or credits page, not a black-and-white story page
BUBBLE_TEXT_MM = {"small": 2.8, "medium": 3.6, "large": 4.6}   # bubble zoom: height of a line of text on screen
TEXTBOXES = Path(os.environ.get("TEXTBOXES", HERE / "textboxes"))  # Vision text finder (Tools/textboxes.swift)


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}


def is_page(p):
    return p.is_file() and p.suffix.lower() in IMAGE_EXTS and not p.name.startswith(".")


def is_image_folder(p):
    """A folder that directly holds page images is one chapter, like a .cbz."""
    return p.is_dir() and any(is_page(c) for c in p.iterdir())


def chapter_name(p):
    return p.name if p.is_dir() else p.stem          # keep "Vol.1 Ch.4.5" whole for folders


def find_chapters(root):
    """Every .cbz and every folder of images under root (not root itself), in name order."""
    def hidden(p):
        return any(part.startswith(".") or part == "__MACOSX" for part in p.relative_to(root).parts)
    found = [p for p in root.rglob("*") if not hidden(p) and
             ((p.is_file() and p.suffix.lower() == ".cbz") or is_image_folder(p))]
    return sorted(found, key=lambda p: str(p).lower())


def natural_images(d, recursive=True):
    files = [p for p in (Path(d).rglob("*") if recursive else Path(d).iterdir()) if is_page(p)]
    return sorted(files, key=lambda p: [int(t) if t.isdigit() else t for t in
                                        __import__("re").split(r"(\d+)", str(p.relative_to(d)).lower())])


def detect_panels(jpg_dir, rtl):
    cmd = [sys.executable, str(KUMIKO), "-i", str(jpg_dir)] + (["--rtl"] if rtl else [])
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    return {Path(p["filename"]).name: p for p in json.loads(out)}


def open_page(src, color):
    return Image.open(src).convert("RGB" if color else "L")


def trim_box(im):
    """The page's content box, without plain white or black margins (for the whole-pages layout)."""
    import numpy as np
    gray = np.asarray(im.convert("L"), dtype=np.int16)
    h, w = gray.shape
    background = np.median(np.concatenate([gray[0], gray[-1], gray[:, 0], gray[:, -1]]))
    ink = np.abs(gray - background) > 48
    rows = np.where(ink.sum(axis=1) > 0.004 * w)[0]      # ignore dust and scanner specks
    cols = np.where(ink.sum(axis=0) > 0.004 * h)[0]
    if not len(rows) or not len(cols):
        return (0, 0, w, h)
    pad = round(0.01 * max(w, h))
    box = (max(0, cols[0] - pad), max(0, rows[0] - pad), min(w, cols[-1] + 1 + pad), min(h, rows[-1] + 1 + pad))
    if (box[2] - box[0]) * (box[3] - box[1]) < 0.5 * w * h:
        return (0, 0, w, h)                              # mostly blank page: don't crop it away
    return box


def fit_page(src, W, H, color=False, box=None):
    """Fit page (or its box) into an (HQ*W)x(HQ*H) white canvas, return image + placement in that canvas."""
    im = open_page(src, color)
    if box:
        im = im.crop(box)
    CW, CH = int(W * HQ), int(H * HQ)
    s = min(CW / im.width, CH / im.height)
    nw, nh = round(im.width * s), round(im.height * s)
    im = im.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new(im.mode, (CW, CH), "white")
    ox, oy = (CW - nw) // 2, (CH - nh) // 2
    canvas.paste(im, (ox, oy))
    return canvas, s, ox, oy


def screen_fit(w, h, W, H, rotate_wide):
    """How a w x h image lands on a W x H screen: (rotated, scale)."""
    rotate = rotate_wide and W < H and w > h
    if rotate:
        w, h = h, w
    return rotate, min(W / w, H / h)


def fit_screen(im, W, H, rotate_wide=False):
    """Scale an image as large as it fits on a WxH screen, centred on white."""
    rotate, s = screen_fit(im.width, im.height, W, H, rotate_wide)
    if rotate:
        # Wider than tall on a portrait screen: turn it a quarter turn clockwise so it fills
        # the screen; the reader turns the device a quarter turn to the left to read it.
        im = im.rotate(-90, expand=True)
    im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
    screen = Image.new(im.mode, (W, H), "white")
    screen.paste(im, ((W - im.width) // 2, (H - im.height) // 2))
    return screen


def is_colourful(src):
    """Scanlator covers and credits are usually in colour; story pages are black and white."""
    import numpy as np
    im = Image.open(src).convert("RGB")
    im.thumbnail((200, 200))
    rgb = np.asarray(im, dtype=np.int16)
    return ((rgb.max(axis=2) - rgb.min(axis=2)) > 40).mean() > COLOUR_PAGE


def is_edge_extra(src, k):
    """Does a first/last page look like a cover or credits page rather than a story page?

    Story pages have a multi-panel layout and are black and white. Scanlator covers and
    credits are usually one image or in colour, even when their boxes look like panels.
    """
    area = k["size"][0] * k["size"][1]
    if sum(1 for b in k["panels"] if b[2] * b[3] >= MIN_AREA * area) < 2:
        return True
    return is_colourful(src)


def find_text(paths, workdir):
    """Lines of text on each page, from the Vision helper: {path: [[x, y, w, h, confidence, text], ...]}.

    Low-resolution pages are enlarged 2x first, which helps it read small lettering.
    """
    if not TEXTBOXES.exists():
        raise FileNotFoundError(f"bubble zoom needs the text finder at {TEXTBOXES} (built by build.sh)")
    inputs, scale = {}, {}
    for i, p in enumerate(paths):
        im = Image.open(p)
        if im.width < 1100:
            big = Path(workdir) / f"text-{i:04d}.png"
            im.convert("L").resize((im.width * 2, im.height * 2), Image.LANCZOS).save(big)
            inputs[str(big)], scale[str(big)] = str(p), 2
        else:
            inputs[str(p)], scale[str(p)] = str(p), 1
    out = subprocess.run([str(TEXTBOXES), *inputs], capture_output=True, text=True, check=True).stdout
    found = json.loads(out)
    return {inputs[k]: [[x / scale[k], y / scale[k], w / scale[k], h / scale[k], c, t] for x, y, w, h, c, t in v]
            for k, v in found.items()}


def text_bubbles(lines):
    """Group lines of text into speech bubbles: [x0, y0, x1, y1, line_height]."""
    lines = [l for l in lines if l[4] >= 0.2 and any(ch.isalpha() for ch in l[5])]
    sure = [l for l in lines if l[4] >= 0.5 and sum(ch.isalpha() for ch in l[5]) >= 2]
    if not sure:
        return []
    typical = sorted(l[3] for l in sure)[len(sure) // 2]
    # [x0, y0, x1, y1, line height, confidently read?]; unsure lines only join bubbles
    groups = [[[l[0], l[1], l[0] + l[2], l[1] + l[3], l[3], l in sure]] for l in lines
              if l[3] <= 2.5 * typical]                   # huge lettering is sound effects or titles

    def bounds(g):
        return (min(b[0] for b in g), min(b[1] for b in g), max(b[2] for b in g), max(b[3] for b in g),
                sorted(b[4] for b in g)[len(g) // 2], any(b[5] for b in g))

    def close(a, b):
        lh = min(a[4], b[4])
        gap = max(a[1], b[1]) - min(a[3], b[3])               # vertical gap between them
        side = min(a[2], b[2]) - max(a[0], b[0])              # horizontal overlap (negative: apart)
        return gap < 0.9 * lh and side > -0.3 * lh

    merged = True
    while merged:
        merged = False
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                if close(bounds(groups[i]), bounds(groups[j])):
                    groups[i] += groups.pop(j)
                    merged = True
                    break
            if merged:
                break
    return [list(bounds(g))[:5] for g in groups if bounds(g)[5]]


def reading_order(bubbles, rtl):
    """Top to bottom; bubbles side by side are read right to left for manga."""
    order = sorted(bubbles, key=lambda b: b[1])
    for _ in range(len(order) ** 2):
        swapped = False
        for i in range(len(order) - 1):
            a, b = order[i], order[i + 1]
            overlap = min(a[3], b[3]) - max(a[1], b[1])
            if overlap > 0.3 * min(a[3] - a[1], b[3] - b[1]) and ((b[0] > a[0]) if rtl else (b[0] < a[0])):
                order[i], order[i + 1] = b, a
                swapped = True
        if not swapped:
            break
    return order


def grow_to_lettering(gray, b):
    """Extend a bubble up and down over lines of lettering the text finder missed.

    Keeps going while the next rows hold dark strokes on a mostly light background (lettering),
    and stops at a gap taller than a line spacing or at artwork (mostly dark rows).
    """
    h, w = gray.shape
    x0, y0, x1, y1, lh = b
    lx0, lx1 = int(max(0, x0 - lh)), int(min(w, x1 + lh))
    step = max(1, int(lh / 4))

    def lettering(ya, yb):
        strip = gray[max(0, ya):min(h, yb), lx0:lx1]
        if not strip.size:
            return False
        dark = (strip < 110).mean()
        return 0.01 < dark < 0.35

    def grow(y, direction):
        edge, blank, limit = y, 0, 6 * lh                  # at most about four more lines
        while abs(y - edge) < limit and 0 < y < h:
            ya, yb = (y - step, y) if direction < 0 else (y, y + step)
            if lettering(ya, yb):
                edge, blank = (ya if direction < 0 else yb), 0
            else:
                blank += step
                if blank > 0.9 * lh:
                    break
            y += direction * step
        return edge

    return [x0, grow(int(y0), -1), x1, grow(int(y1), +1), lh]


def clean_lettering(im):
    """Levels for enlarged bubbles: near-white to white, near-black to black, so scan noise and grey
    fringes don't turn into dither speckle on e-ink."""
    return im.point(lambda v: 0 if v < 50 else 255 if v > 205 else (v - 50) * 255 // 155)


def bubble_screens(im, region, bubbles, W, H, region_scale, target, rtl):
    """Extra screens enlarged onto the speech bubbles in one region whose text shows too small."""
    from PIL import ImageFilter
    x0, y0, x1, y1 = region
    small = [b for b in bubbles if x0 <= (b[0] + b[2]) / 2 <= x1 and y0 <= (b[1] + b[3]) / 2 <= y1
             and b[4] * region_scale < 0.85 * target]     # bubbles already readable on the panel's screen are left
    import numpy as np
    gray = np.asarray(im.convert("L"))
    small = [grow_to_lettering(gray, b) for b in small]
    screens, group = [], []

    def layout(g):
        """Crop box around a group of balloons, and the scale that brings its lettering to the target size."""
        lh = sorted(b[4] for b in g)[len(g) // 2]
        pad = 0.4 * lh
        box = (max(0, min(b[0] for b in g) - pad), max(0, min(b[1] for b in g) - pad),
               min(im.width, max(b[2] for b in g) + pad), min(im.height, max(b[3] for b in g) + pad))
        return box, target / lh

    def flush():
        box, k = layout(group)
        crop = clean_lettering(im.crop(tuple(round(v) for v in box)))
        s = min(k, W / crop.width, H / crop.height)
        crop = crop.resize((max(1, round(crop.width * s)), max(1, round(crop.height * s))), Image.LANCZOS)
        if s > 1.15:
            crop = crop.filter(ImageFilter.UnsharpMask(radius=1.0, percent=60, threshold=3))  # crisp lettering
        screen = Image.new(im.mode, (W, H), "white")
        screen.paste(crop, ((W - crop.width) // 2, (H - crop.height) // 2))
        screens.append(screen)

    for b in reading_order(small, rtl):
        box, k = layout(group + [b])
        if group and ((box[2] - box[0]) * k > W or (box[3] - box[1]) * k > H):
            flush()                                       # the next bubble doesn't fit: new screen
            group = [b]
        else:
            group.append(b)
    if group:
        flush()
    return screens


def panel_screens(src, boxes, W, H, whole, page_first, rotate_wide, color=False,
                  bubbles=None, target=0, rtl=True, page_box=None, zoom_whole=True):
    """Screens for one source page: the whole page and/or each panel in reading order, each
    followed by enlarged speech bubbles when bubble zoom is on and its text would be too small."""
    im = open_page(src, color)

    def show(box, zoom=True):
        crop = im.crop(box)
        screens = [fit_screen(crop, W, H, rotate_wide)]
        if zoom and bubbles and target:
            _, s = screen_fit(crop.width, crop.height, W, H, rotate_wide)
            screens += bubble_screens(im, box, bubbles, W, H, s, target, rtl)
        return screens

    page = page_box or (0, 0, im.width, im.height)
    if whole or not boxes:
        return show(page, zoom_whole)
    screens = show(page, zoom=False) if page_first else []    # an overview; its panels follow
    for (x, y, w, h) in boxes:
        pad = round(0.015 * max(w, h))                 # a little breathing room
        screens += show((max(0, x - pad), max(0, y - pad), min(im.width, x + w + pad), min(im.height, y + h + pad)))
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
            fmt=None, page_first=False, rotate_wide=False, layout="panels", bubble_zoom="off"):
    profile = DEVICES[device]
    W, H = profile["size"]
    fmt = fmt or profile["fmt"]
    cbz = Path(cbz)
    title = title or chapter_name(cbz)
    outdir = Path(outdir); outdir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        src, jpg, book = tmp / "src", tmp / "jpg", tmp / "book"
        if cbz.is_dir():                              # a folder of images: read the pages in place
            pages = natural_images(cbz, recursive=False)
        else:
            with zipfile.ZipFile(cbz) as z:
                z.extractall(src)
            pages = natural_images(src)
        if not pages:
            raise ValueError("no page images found")
        whole_pages = layout == "pages"
        if not whole_pages:                           # the panel detector reads JPEG copies
            jpg.mkdir()
            for i, p in enumerate(pages, 1):
                Image.open(p).convert("RGB").save(jpg / f"{i:04d}.jpg", quality=95)
            info = detect_panels(jpg, rtl)
        safe = title.replace("/", "-")
        if profile["mode"] == "panels":
            target = BUBBLE_TEXT_MM.get(bubble_zoom, 0) * profile["ppi"] / 25.4
            text = find_text(pages, tmp) if target else {}
            screens = []
            for i, p in enumerate(pages, 1):
                edge = i <= skip_first or i > len(pages) - skip_last
                bubbles = text_bubbles(text.get(str(p), [])) if target else None
                if whole_pages:
                    page = open_page(p, False)
                    extra = edge and is_colourful(p)    # cover or credits: no bubble zoom
                    screens += panel_screens(p, [], W, H, True, False, rotate_wide, profile["color"],
                                             bubbles, target, rtl, trim_box(page), zoom_whole=not extra)
                    continue
                k = info[f"{i:04d}.jpg"]
                area = k["size"][0] * k["size"][1]
                boxes = [b for b in k["panels"] if b[2] * b[3] >= MIN_AREA * area]
                if len(boxes) == 1 and boxes[0][2] * boxes[0][3] > MAX_AREA * area:
                    boxes = []                          # one full-page panel: just show the page
                coverage = sum(b[2] * b[3] for b in boxes) / area
                extra = edge and is_edge_extra(p, k)
                whole = i in nozoom or extra
                screens += panel_screens(p, boxes, W, H, whole, page_first or coverage < MIN_COVERAGE,
                                         rotate_wide, profile["color"], bubbles, target, rtl,
                                         zoom_whole=not extra)
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
            box = trim_box(open_page(p, False)) if whole_pages else None
            canvas, s, ox, oy = fit_page(p, W, H, profile["color"], box)
            canvas.save(book / "OEBPS" / "Images" / f"{name}.jpg", quality=88, optimize=True)
            if i == 1:
                canvas.convert("RGB").save(book / "OEBPS" / "Images" / "cover.jpg", quality=88)
            panels = []
            if whole_pages:                           # no panel zoom: just the trimmed page
                names.append(name)
                (book / "OEBPS" / "Text" / f"{name}.xhtml").write_text(page_xhtml(name, W, H, [], i))
                dbg.append((i, 0))
                continue
            k = info[f"{name}.jpg"]
            iw, ih = k["size"]
            edge = i <= skip_first or i > len(pages) - skip_last
            if i not in nozoom and not (edge and is_edge_extra(p, k)):
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
            page_first=opts["page_first"], rotate_wide=opts["rotate_wide"],
            layout=opts["layout"], bubble_zoom=opts["bubble_zoom"])
    except BaseException as e:  # keep going on a bad file
        return False, cbz, f"{type(e).__name__}: {e}"


def main():
    ap = argparse.ArgumentParser(description="Convert manga .cbz files into Kindle books with per-panel guided view.")
    ap.add_argument("input", help="a .cbz file, a folder of page images, or a folder searched for both")
    ap.add_argument("-d", "--device", choices=DEVICES, default="basic")
    ap.add_argument("--ltr", action="store_true", help="left-to-right (western) instead of manga right-to-left")
    ap.add_argument("--nozoom", default="", help="single file only: 1-based pages to leave without panel zoom")
    ap.add_argument("--skip-first", type=int, default=0,
                    help="keep the first N pages of each chapter whole when they look like a cover (no panel layout, or in colour)")
    ap.add_argument("--skip-last", type=int, default=0,
                    help="keep the last N pages of each chapter whole when they look like credits (no panel layout, or in colour)")
    ap.add_argument("-o", "--out", default="out")
    ap.add_argument("-j", "--jobs", type=int, default=2, help="chapters converted in parallel (folder mode)")
    ap.add_argument("-f", "--format", choices=["epub", "mobi", "xtch", "xtc", "pdf", "cbz"],
                    help="Kindles: epub (default, Send to Kindle) or mobi (USB, needs Kindle Previewer); "
                         "other readers: xtch (Xteink, 4 shades), xtc (Xteink, black and white), pdf or cbz "
                         "(default depends on the device)")
    ap.add_argument("--layout", choices=["panels", "pages"], default="panels",
                    help="panels: follow the detected panels (default); pages: skip panel detection and show "
                         "each page whole, with its margins trimmed so it fills the screen")
    ap.add_argument("--bubble-zoom", choices=["off", *BUBBLE_TEXT_MM], default="off",
                    help="one-panel-per-page devices: after a panel whose text is too small, add screens "
                         "enlarged onto its speech bubbles, with text this size")
    ap.add_argument("--page-first", action="store_true",
                    help="one-panel-per-page devices: show each whole page before its panels")
    ap.add_argument("--rotate-wide", action="store_true",
                    help="one-panel-per-page devices: rotate panels (and spreads) that are wider than tall")
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
                page_first=a.page_first, rotate_wide=a.rotate_wide,
                layout=a.layout, bubble_zoom=a.bubble_zoom)
    src, out = Path(a.input), Path(a.out)
    if src.is_file():
        candidates, src = [src], src.parent
    elif is_image_folder(src):                         # a single chapter folder of images
        candidates, src = [src], src.parent
    else:
        candidates = find_chapters(src)
    jobs, skipped = [], 0
    for cbz in candidates:
        if cbz.name.startswith("."):
            continue
        rel = cbz.relative_to(src)
        # chapters straight inside the dropped folder belong to a series named after that folder
        series = rel.parent if rel.parent.parts else Path(src.name)
        dest = out / series
        title = f"{series.name} - {chapter_name(cbz)}"
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
