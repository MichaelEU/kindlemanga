# Manga Panel View

A Mac app that turns manga `.cbz` chapters into Kindle books with **real panel-by-panel
guided view**. You tap through a page one panel at a time, the way Amazon's own comics work.

Tools like Kindle Comic Converter split every page into the same four quarters. That cuts
panels in half and makes spreads unreadable. Manga Panel View finds the actual panels on each
page, including slanted and irregular layouts, and zooms to each one in reading order.

Tested on a Kindle (basic) and a Kindle Scribe.

---

## Contents

- [How it works](#how-it-works)
- [Requirements](#requirements)
- [Setup](#setup)
- [Using the app](#using-the-app)
- [Getting books onto your Kindle](#getting-books-onto-your-kindle)
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
3. The pages are resized for your Kindle's screen, and each panel becomes a tap target
   using Amazon's *region magnification* markup, the same mechanism Kindle's own comics use.
4. The result is packaged as an EPUB (or MOBI) book, one book per chapter.

Very small detections are ignored, and so are panels that already fill most of the page,
because zooming in would gain nothing.

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
2. **Pick your Kindle(s)** under *Make books for*. Each Kindle gets its own set of books,
   sized for its screen.
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

Any of these work:

| You drop | You get |
|---|---|
| A series folder full of `.cbz` chapters | One book per chapter, in a folder named after the series |
| A folder of series folders (a whole library) | The same, for every series inside |
| A single `.cbz` file | One book, filed under the folder it came from |

Books are named `Series - Chapter` so they're easy to tell apart in your Kindle library.
By default they are saved to `~/Documents/Kindle Manga/<Kindle model>/<Series>/`.

---

## Getting books onto your Kindle

### EPUB (default, recommended)

Send the `.epub` files with Amazon's **[Send to Kindle](https://www.amazon.com/sendtokindle)**
app for Mac, or through the website. Amazon converts them for your Kindle and **keeps the
panel zoom**.

### MOBI

Choose **MOBI** under *Book format* if you prefer copying files over USB. Copy the `.mobi`
files into the Kindle's `documents` folder. On a Mac, Amazon's USB File Transfer app or
[OpenMTP](https://openmtp.ganeshrvel.com/) are the most reliable ways to do this.
Newer Kindles can be picky about MOBI, so if yours won't open them, use EPUB.

### Reading panel by panel

Open a converted chapter and tap into a panel. The Kindle zooms to it, and each tap or swipe
moves to the next panel in reading order. On some models and firmware versions, panel view
has to be switched on first in the **Aa** menu.

---

## Settings explained

| Setting | What it does |
|---|---|
| **Make books for** | Which Kindles to build for: **Kindle** (1072×1448) and/or **Kindle Scribe** (1860×2480). |
| **Reading direction** | *Right to left* for manga, *Left to right* for Western comics. Controls panel order and page turns. |
| **Show complete view first** | Leaves each chapter's first page (usually the cover) as a plain full page with no panel zoom. |
| **Show complete view after** | The same for the last page (usually scanlator credits). |
| **Book format** | EPUB for Send to Kindle, MOBI for USB (needs Kindle Previewer 4). |
| **Save to** | Where the books go. Each Kindle model gets a subfolder. |
| **Chapters at once** | How many chapters of the current title are converted in parallel. 2 is a good default; raise it on a fast Mac. |

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
| `-d basic` / `-d scribe` | Kindle model |
| `-o DIR` | Output folder |
| `-f epub` / `-f mobi` | Book format (default `epub`) |
| `--ltr` | Left-to-right comics instead of manga |
| `--skip-first N` / `--skip-last N` | Leave the first/last N pages of each chapter without panel zoom |
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
neighbouring big panel, and panels without borders may be skipped. The full page is always
still readable, so these pages just get fewer zoom stops.

**A credits page gets panel zoom.**
Some scanlation groups add two or more credit pages. The *Show complete view* switches cover
one page at each end. For more, use `--skip-first` / `--skip-last` on the command line.

**Setup fails.**
The error and the last lines of the install log are shown on screen. The usual causes are no
internet connection, or `python3` not being installed.

**The app can't see my external or network drive.**
Allow access when macOS asks. If you denied it earlier, go to System Settings → Privacy &
Security → Files and Folders and turn it on for Manga Panel View.

**Start over completely.**
Quit the app, delete `~/Library/Application Support/Manga Panel View`, and open it again.
Setup will run again.

---

## Project layout

```
MangaPanelView/
├── Sources/App.swift          SwiftUI app: queue, settings, progress, engine setup
├── Resources/
│   ├── panelview.py           Converter: panel detection → Kindle EPUB/MOBI
│   └── kumiko/                Bundled Kumiko panel detector (AGPL-3.0, unmodified)
├── make_icon.py               Draws the app icon
└── build.sh                   Builds the .app with the Command Line Tools
```

The app copies `panelview.py` and `kumiko/` into its Application Support folder on every
launch, so a rebuilt app always runs the latest converter.

To support another Kindle model, add its screen size to `DEVICES` in `panelview.py` and to
the `Device` enum in `App.swift`.

---

## Acknowledgements

This project stands on other people's work. Full credits and license notices are in
**[ACKNOWLEDGEMENTS.md](ACKNOWLEDGEMENTS.md)**, and in the app under
**Manga Panel View → About Manga Panel View** (or **Help → Acknowledgements**). In short:

- **[Kumiko](https://github.com/njean42/kumiko)** by njean42 does the panel detection
  (AGPL-3.0, bundled unmodified).
- **[Kindle Comic Converter (KCC)](https://github.com/ciromattia/kcc)** showed how to write
  Kindle panel-view markup and fixed-layout comic metadata (ISC).
- **OpenCV, NumPy, Pillow and Requests** power the image processing.
- **Amazon's** Kindle Previewer / kindlegen build the MOBI files.
- **Claude** (Anthropic) co-wrote this project with me in Claude Code.

## License

Kumiko keeps its own AGPL-3.0 license (`MangaPanelView/Resources/kumiko/LICENSE`).
No license has been chosen yet for the rest of this project's code.

This tool is for converting manga you own or have the right to read. It doesn't download
anything and contains no manga.
