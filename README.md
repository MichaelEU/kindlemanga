# Manga Panel View

A Mac app that turns manga `.cbz` chapters into e-reader books that follow the **real panels**
on each page:

- **Kindles, Paperwhites, Oasis and Scribe:** panel-by-panel guided view. You tap through a page
  one panel at a time, the way Amazon's own comics work.
- **Older Kindles, Kobos, Sony Readers, the Xteink X4 and other readers:** each panel becomes its
  own full-screen page, in reading order, so small screens show one readable panel at a time.

Tools like Kindle Comic Converter split every page into the same four quarters. That cuts
panels in half and makes spreads unreadable. Manga Panel View finds the actual panels on each
page, including slanted and irregular layouts, and shows each one in reading order.

Tested on a Kindle (basic) and a Kindle Scribe. The Xteink X4 and Sony files were checked by
decoding them on a Mac, the same way CrossPoint reads them, but haven't been tried on a device yet.

---

## Contents

- [How it works](#how-it-works)
- [Requirements](#requirements)
- [Setup](#setup)
- [Using the app](#using-the-app)
- [Getting books onto your device](#getting-books-onto-your-device)
- [Settings explained](#settings-explained)
- [Command line](#command-line)
- [Troubleshooting](#troubleshooting)
- [Project layout](#project-layout)
- [Acknowledgements](#acknowledgements)

---

## How it works

1. Each chapter's pages are extracted from the `.cbz` file.
2. [Kumiko](https://github.com/njean42/kumiko) finds where the panels are on every page and
   puts them in reading order (right-to-left for manga).
3. Then it depends on the device:
   - **Kindles:** the pages are resized for the screen, and each panel becomes a tap target
     using Amazon's *region magnification* markup, the same mechanism Kindle's own comics use.
     The result is an EPUB (or MOBI) book.
   - **Other readers:** each panel is cropped out and enlarged to fill the screen, one panel per
     page. The result is an XTCH/XTC file (Xteink), a PDF (Sony) or a CBZ (other readers).
4. You get one book per chapter.

Very small detections are ignored. Panels that already fill most of the page aren't zoomed or
split, because it would gain nothing. On one-panel-per-page devices, a page whose panels cover
less than about half of it is also shown whole first, so art outside the panels isn't lost.

### Bubble zoom (small screens)

On tiny screens like the Xteink X4, a whole panel can still leave the lettering too small to
read. With **Bubble zoom** on, the app finds the lettering with macOS's built-in text recognition
(Apple Vision, on your Mac, nothing is uploaded), groups the lines into speech bubbles in reading
order, and adds close-up screens after any panel whose text would show smaller than the size you
picked. Neighbouring bubbles share a screen when they fit.

It only uses *where* the text is, not what it says, so the original lettering is shown exactly as
the scanlators drew it: enlarged, cleaned up to crisp black on white, and lightly sharpened.
Low-resolution scans are enlarged before the text search so small lettering is still found. Sound
effects and big titles are skipped.

### Whole pages (no panel detection)

The **Whole pages** layout skips panel detection. Each page's plain white or black margins are
trimmed and the page is sized to fill the screen. It's faster and works well on big screens like
the Kindle Scribe; on small screens it still works with page rotation and bubble zoom.

### Supported devices

Screen sizes follow [Kindle Comic Converter](https://github.com/ciromattia/kcc)'s device profiles.

**Kindles with panel zoom** (EPUB or MOBI):

| Device | Screen |
|---|---|
| Kindle (2022 and later) | 1072×1448 |
| Kindle 5, 7, 8 or 10 | 600×800 |
| Kindle Paperwhite 1 or 2 | 758×1024 |
| Kindle Paperwhite 3 or 4, Voyage, Oasis 1 | 1072×1448 |
| Kindle Paperwhite 5 or Signature | 1236×1648 |
| Kindle Paperwhite 6 (2024) | 1272×1696 |
| Kindle Colorsoft | 1272×1696, colour |
| Kindle Oasis 2 or 3 | 1264×1680 |
| Kindle Scribe 1 or 2 | 1860×2480 |
| Kindle Scribe 3 | 1986×2648 |
| Kindle Scribe Colorsoft | 1986×2648, colour |

**One panel per page:**

| Device | Format | Screen |
|---|---|---|
| Kindle Keyboard or Touch | MOBI or EPUB | 600×800 |
| Kindle DX | MOBI or EPUB | 824×1000 |
| Kindle 1 or 2 | MOBI or EPUB | 600×670 |
| Kobo Clara | CBZ | 1072×1448 |
| Kobo Nia | CBZ | 758×1024 |
| Kobo Libra | CBZ | 1264×1680 |
| Kobo Sage or Forma | CBZ | 1440×1920 |
| Kobo Elipsa | CBZ | 1404×1872 |
| Sony PRS-500 or 505 | PDF | 600×800 |
| Sony PRS-300 or 350 (Pocket) | PDF | 600×800 |
| Sony PRS-600, 650 or 700 (Touch) | PDF | 600×800 |
| Sony PRS-900 or 950 (Daily Edition) | PDF | 600×1024 |
| Sony PRS-T1 or T2 | PDF | 600×800 |
| Sony PRS-T3 | PDF | 758×1024 |
| Xteink X4 | XTCH (4 shades) or XTC (black & white) | 480×800 |
| Other reader | CBZ | 1264×1680 |

The oldest Kindles (1, 2, Keyboard, Touch and DX) can't do panel zoom, so they get one panel per
page inside a normal Kindle book. The Colorsoft models keep colour; everything else is
converted to grayscale.

---|---|---|---|
| Kindle | Panel zoom inside the page | EPUB or MOBI | 1072×1448 |
| Kindle Scribe | Panel zoom inside the page | EPUB or MOBI | 1860×2480 |
| Xteink X4 | One panel per page | XTCH (4 shades) or XTC (black & white) | 480×800 |
| Sony PRS-950 | One panel per page | PDF | 600×1024 |
| Other reader | One panel per page | CBZ | 1264×1680 |

---

## Requirements

| What | Why | How to get it |
|---|---|---|
| macOS 14 (Sonoma) or newer | The app is built with SwiftUI | |
| Xcode Command Line Tools | To build the app | `xcode-select --install` (full Xcode not needed) |
| Python 3 | Runs the panel detector | Usually already installed; otherwise [python.org](https://www.python.org/downloads/macos/) |
| Internet (first launch only) | Downloads the detector's libraries, about 100 MB | |
| Kindle Previewer 4 *(optional)* | Only needed for MOBI output | [Amazon](https://www.amazon.com/Kindle-Previewer/b?node=21381691011) |

---

## Setup

### 1. Get the code

```bash
git clone https://github.com/MichaelEU/kindlemanga.git
cd kindlemanga
```

### 2. Build the app

```bash
cd MangaPanelView
./build.sh
```

This creates `MangaPanelView/build/Manga Panel View.app`. The icon step needs a
`python3` with [Pillow](https://pypi.org/project/pillow/) installed. If yours doesn't have it,
either install it or point the build at a Python that does:

```bash
python3 -m pip install pillow
```

```bash
PYTHON=/path/to/python-with-pillow ./build.sh
```

### 3. Install it

```bash
cp -R "build/Manga Panel View.app" ~/Applications/
```

### 4. First launch

Open **Manga Panel View** and click **Set Up**. This is a one-time step. It creates a
private Python environment in `~/Library/Application Support/Manga Panel View` and installs
OpenCV, NumPy, Pillow and Requests into it. Nothing is installed system-wide.

If macOS asks whether the app may access a folder or drive (Documents, an external
drive, a network share), allow it. Otherwise the app can't read your manga or save books.

---

## Using the app

The window has two sides: **settings** on the left and the **queue** on the right.

1. **Add titles.** Drag manga folders or `.cbz` files onto the queue. You can drop as many
   as you like at once. Other ways to add them:
   - Click **Add…** and hold ⌘ to pick several.
   - Drop them on the app's Dock icon.
2. **Pick your device** from the menu under *Make books for*. The three devices you used most
   recently are listed at the top under *Recently used*, and the app remembers your last choice.
3. Click **Convert N Titles**.

Titles are converted **one at a time, top to bottom**. The bottom bar shows overall progress
("Title 3 of 120"), and each row shows its own progress.

**While it's running:**

- **Adding titles:** titles you drop in join the end of the queue and are picked up in the
  same run.
- **Stopping:** **Stop** is safe. Chapters that already finished are kept, and the stopped
  title resumes where it left off next time.

**Quitting** is safe too. Unfinished titles stay in the queue for the next launch.

**Converting again** skips chapters that already have a book. New chapters from your
downloader get converted and the rest are left alone, so it's cheap to re-add a whole series.

**In the queue:**

- A **"N failed"** link lists which chapters couldn't be converted, and why.
- The **folder** button opens a finished title's books in Finder.
- **✕** removes a title from the queue. It doesn't delete anything from disk.
- **Clear Finished** empties the completed titles.

### What to drop in

A chapter can be a `.cbz` file **or a folder of page images** (JPG, PNG, WebP, GIF or BMP). Pages
are read in name order, so `2.jpg` comes before `10.jpg`. Any of these work:

| You drop | You get |
|---|---|
| A series folder full of chapters (`.cbz` files, image folders, or a mix) | One book per chapter, in a folder named after the series |
| A folder of series folders (a whole library) | The same, for every series inside |
| A single `.cbz` file | One book, filed under the folder it came from |
| A single folder of page images | One book, filed under the folder it sits in |

Hidden folders and macOS `__MACOSX` leftovers are ignored.

Books are named `Series - Chapter` so they're easy to tell apart in your Kindle library.
By default they are saved to `~/Documents/Kindle Manga/<Device>/<Series>/`.

---

## Getting books onto your device

### Kindle: EPUB (default, recommended)

Send the `.epub` files with Amazon's **[Send to Kindle](https://www.amazon.com/sendtokindle)**
app for Mac, or through the website. Amazon converts them for your Kindle and **keeps the
panel zoom**.

### Kindle: MOBI

Choose **MOBI** under *Kindle format* if you prefer copying files over USB. Copy the `.mobi`
files into the Kindle's `documents` folder. On a Mac, Amazon's USB File Transfer app or
[OpenMTP](https://openmtp.ganeshrvel.com/) are the most reliable ways to do this.
Newer Kindles can be picky about MOBI, so if yours won't open them, use EPUB.

### Kindle: reading panel by panel

Open a converted chapter and tap into a panel. The Kindle zooms to it, and each tap or swipe
moves to the next panel in reading order. On some models and firmware versions, panel view
has to be switched on first in the **Aa** menu.

### Older Kindles (1, 2, Keyboard, Touch, DX)

Set *Kindle format* to **MOBI**, plug the Kindle in over USB (it shows up as a drive), and copy
the books into its `documents` folder. Each page turn shows the next panel.

### Kobo

Plug the Kobo in over USB and copy the CBZ files onto it. Kobo opens CBZ comics natively, and
each page is one panel.

### Xteink X4 (CrossPoint)

Copy the `.xtch` (or `.xtc`) files onto the X4's microSD card and open them from the library in
[CrossPoint Reader](https://github.com/crosspoint-reader/crosspoint-reader). These are Xteink's
native pre-rendered formats, so pages turn fast. Each page turn shows the next panel.

**4 shades (XTCH)** keeps manga screentones and gray shading. **Black & white (XTC)** files are
half the size and use dithering for grays. The X4 has no auto-rotate, so *Turn wide panels
sideways* (on by default) rotates wide panels and spreads to fill its narrow screen; turn the reader
a quarter turn to the left to read them.

### Sony Reader

Connect the Reader over USB and copy the PDFs onto it. Every Sony Reader model opens PDFs, and
each PDF page is one panel, shaped to that model's screen.

### Other readers

The CBZ files open in most comic apps and readers, for example KOReader, Kobo with KOReader,
and phone or tablet comic apps. Each page is one panel.

---

## Settings explained

| Setting | What it does |
|---|---|
| **Make books for** | The device to build for; see [Supported devices](#supported-devices). Your three most recent devices are at the top of the menu. |
| **Layout** | *Panel by panel* (default) follows the detected panels. *Whole pages* skips panel detection and shows each page with its margins trimmed. |
| **Reading direction** | *Right to left* for manga, *Left to right* for Western comics. Controls panel order and page turns. |
| **Show as a complete page: Cover** | Keeps a chapter's first page as a plain full page, not zoomed or split, **when it looks like a cover**: in colour, or without a panel layout. If the first page is a black-and-white story page, it's split as normal. |
| **Show as a complete page: Credits** | The same for the last page, when it looks like scanlator credits. |
| **Xteink shades** | *4 shades (XTCH)* or *Black & white (XTC)*. Shown when the X4 is chosen. |
| **Show whole page before its panels** | One-panel-per-page devices: show each full page first as an overview, then its panels. |
| **Bubble zoom** | Small screens: *Off*, or *Small / Medium / Large text*. Adds close-ups of speech bubbles whose lettering would be too small, enlarged to that size (about 2.8, 3.6 or 4.6 mm per line on the device). |
| **Turn wide panels sideways** | One-panel-per-page devices, on by default: any panel (or two-page spread) that is wider than it is tall is rotated a quarter turn clockwise so it fills the screen. Turn the reader a quarter turn to the left to read it. |
| **Kindle format** | EPUB for Send to Kindle, MOBI for USB (needs Kindle Previewer 4). Shown for Kindles; older Kindles should use MOBI. |
| **Save to** | Where the books go, in a subfolder named after the device. Switching devices never mixes their books. |
| **Chapters at once** | How many chapters of the current title are converted in parallel. 2 is a good default; raise it on a fast Mac. |
| **Rebuild books that already exist** | Normally chapters that already have a book are skipped. Turn this on after changing settings to remake them. |

---

## Command line

The converter also works without the app, once the app has set up its engine:

```bash
PY=~/Library/Application\ Support/Manga\ Panel\ View/venv/bin/python
```

```bash
"$PY" MangaPanelView/Resources/panelview.py "/path/to/manga" -d scribe -o ~/Desktop/kindle-out
```

| Option | Meaning |
|---|---|
| `-d ID` | Device. Kindles with panel zoom: `basic`, `k600`, `kpw`, `kpw34`, `kpw5`, `kpw6`, `kcs`, `ko`, `scribe`, `ks3`, `kscs`. Older Kindles: `k34`, `kdx`, `k12`. Kobo: `koc`, `kon`, `kol`, `kos`, `koe`. Sony: `prs500`, `prs300`, `prs600`, `prs950`, `prst`, `prst3`. Others: `x4`, `generic`. Run with `-h` for the full list. |
| `-o DIR` | Output folder |
| `-f FORMAT` | Kindles: `epub` or `mobi` (default `epub`; `mobi` for older Kindles). Other devices: `xtch`, `xtc`, `pdf` or `cbz` (defaults: X4 `xtch`, Sony `pdf`, Kobo and other `cbz`) |
| `--page-first` | One-panel-per-page devices: show each whole page before its panels |
| `--layout panels` / `pages` | Follow the detected panels (default), or show whole pages with trimmed margins |
| `--bubble-zoom off` / `small` / `medium` / `large` | One-panel-per-page devices: add close-ups of speech bubbles with small lettering (needs the `textboxes` helper that the app installs next to the converter) |
| `--rotate-wide` | One-panel-per-page devices: rotate panels and spreads that are wider than tall |
| `--ltr` | Left-to-right comics instead of manga |
| `--skip-first N` / `--skip-last N` | Keep the first/last N pages of each chapter whole when they look like a cover or credits (in colour, or no panel layout) |
| `--nozoom 1,17,18` | Single file only: specific pages to leave without zoom |
| `-j N` | Chapters converted in parallel |
| `--redo` | Rebuild books that already exist |
| `--keep-epub` | With `-f mobi`, also keep the intermediate EPUB |

Output lines look like `[3/40] ok  Series/Chapter 3.cbz` or
`[4/40] FAIL Series/Chapter 4.cbz  -> reason`, so they're easy to script around.

---

## Troubleshooting

**The Kindle won't open the MOBI files.**
Switch *Book format* to **EPUB** and use Send to Kindle.

**Two panels are zoomed together, or a panel is missed.**
The panel detector looks for panel borders. It sometimes merges small inset panels into a
neighbouring big panel, and panels without borders may be skipped. On Kindles the full page
is always still readable, so these pages just get fewer zoom stops. On one-panel-per-page
devices, merged panels show up together on one screen. Turn on *Show whole page before its
panels* if you want the full page as a fallback everywhere.

**Wide panels are tiny on the Xteink X4.**
Make sure *Turn wide panels sideways* is on (it is by default), and turn the reader a quarter turn to the left when one of those panels comes up.

**A credits page gets panel zoom, or a story page doesn't.**
The *Cover* and *Credits* switches check one page at each end. They keep it whole only if it
looks like a cover or credits: in colour (story pages are black and white), or without a panel
layout. So chapters without a cover or credits page are split normally. A black-and-white
credits page laid out in boxes can still be split. Some groups add two or more credit pages; for
those, use `--skip-first` / `--skip-last` on the command line.

**Setup fails.**
The error and the last lines of the install log are shown on screen. The usual causes are no
internet connection, or `python3` not being installed.

**The app can't see my external or network drive.**
Allow access when macOS asks. If you denied it earlier, go to System Settings → Privacy &
Security → Files and Folders and turn it on for Manga Panel View.

**I changed a setting but the books look the same.**
Chapters that already have a book are skipped. Turn on *Rebuild books that already exist*
(or delete the old books) and convert again.

**Bubble zoom shows a sound effect, or misses a bubble.**
Stylised lettering written in Latin letters can be taken for dialogue, and faint or tiny lettering
on very low-resolution scans can be missed. Those bubbles are still readable on the panel's own
screen, just smaller.

**Start over completely.**
Quit the app, delete `~/Library/Application Support/Manga Panel View`, and open it again.
Setup will run again.

---

## Project layout

```
MangaPanelView/
├── Sources/App.swift          SwiftUI app: queue, settings, progress, engine setup
├── Resources/
│   ├── panelview.py           Converter: panel detection → EPUB/MOBI, XTCH/XTC, PDF, CBZ
│   └── kumiko/                Bundled Kumiko panel detector (AGPL-3.0, unmodified)
├── Tools/textboxes.swift      Finds lettering with Apple Vision, for bubble zoom
├── make_icon.py               Draws the app icon
└── build.sh                   Builds the .app with the Command Line Tools
```

The app copies `panelview.py`, `kumiko/` and the `textboxes` helper into its Application Support folder on every
launch, so a rebuilt app always runs the latest converter.

To support another device, add a profile to `DEVICES` in `panelview.py` (screen size, `zoom`
or `panels` mode, default format) and a matching case to the `Device` enum in `App.swift`.

---

## Acknowledgements

This project stands on other people's work. Full credits and license notices are in
**[ACKNOWLEDGEMENTS.md](ACKNOWLEDGEMENTS.md)**, and in the app under
**Manga Panel View → About Manga Panel View** (or **Help → Acknowledgements**). In short:

- **[Kumiko](https://github.com/njean42/kumiko)** by njean42 does the panel detection
  (AGPL-3.0, bundled unmodified).
- **[Kindle Comic Converter (KCC)](https://github.com/ciromattia/kcc)** showed how to write
  Kindle panel-view markup and fixed-layout comic metadata (ISC).
- **[xtcjs](https://github.com/varo6/xtcjs)** and **[CrossPoint Reader](https://github.com/crosspoint-reader/crosspoint-reader)**
  showed exactly how Xteink XTC/XTCH files are laid out and read (both MIT).
- **OpenCV, NumPy, Pillow and Requests** power the image processing.
- **Amazon's** Kindle Previewer / kindlegen build the MOBI files.
- **Claude** (Anthropic) co-wrote this project with me in Claude Code.

## License

Kumiko keeps its own AGPL-3.0 license (`MangaPanelView/Resources/kumiko/LICENSE`).
No license has been chosen yet for the rest of this project's code.

This tool is for converting manga you own or have the right to read. It doesn't download
anything and contains no manga.
