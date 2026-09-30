# Acknowledgements

Manga Panel View exists thanks to the people and projects below.

---

## Kumiko: panel detection

**https://github.com/njean42/kumiko**
Copyright (C) 2018 njean42. Licensed under the **GNU Affero General Public License v3.0 or later**.

Kumiko finds where the panels are on a comic page, and in what order to read them.
It is the core of this project. Without it, every page would get the same fixed grid.

Kumiko is bundled **unmodified** in `MangaPanelView/Resources/kumiko/`, with its original
license in `MangaPanelView/Resources/kumiko/LICENSE`. It runs as a separate program:
Manga Panel View calls its command line and reads the JSON it prints. Kumiko's full source
is included here and is available from the link above.

Thanks also to Hurluberlue for the Kumiko mascot artwork, which is not included here.

---

## Kindle Comic Converter (KCC): Kindle panel-view know-how

**https://github.com/ciromattia/kcc**

KCC is the standard tool for turning comics into Kindle books. This project doesn't use KCC's
code directly. I studied it to learn how Kindle books do panel view, and followed its approach:

- the `app-amzn-magnify` tap targets and the hidden zoom layers they point to,
- the fixed-layout comic metadata in the book's package file (`region-mag`, `book-type`,
  `original-resolution`, and so on),
- its Kindle device screen sizes.

Manga Panel View's difference is where the tap targets go. KCC always uses four fixed page
quarters; this project puts one on each detected panel.

KCC is released under the ISC license:

```
ISC LICENSE

Copyright (c) 2012-2025 Ciro Mattia Gonano <ciromattia@gmail.com>
Copyright (c) 2013-2019 Paweł Jastrzębski <pawelj@iosphe.re>
Copyright (c) 2021-2023 Darodi (https://github.com/darodi)
Copyright (c) 2023-2025 Alex Xu (https://github.com/axu2)

Permission to use, copy, modify, and/or distribute this software for
any purpose with or without fee is hereby granted, provided that the
above copyright notice and this permission notice appear in all
copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL
WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE
AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL
DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA
OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER
TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
PERFORMANCE OF THIS SOFTWARE.
```

---

## xtcjs and CrossPoint Reader: Xteink file formats

The Xteink X4 output (`.xtch` / `.xtc`) is written by this project's own code, but getting the
details right came from studying two open-source projects:

- **[xtcjs](https://github.com/varo6/xtcjs)** by varo6 and contributors (MIT). A browser-based
  CBZ-to-XTC converter. Its encoder confirmed how the container is laid out and that a set bit
  in a black-and-white page means white.
- **[CrossPoint Reader](https://github.com/crosspoint-reader/crosspoint-reader)** by the
  CrossPoint Reader organization (MIT). The open-source X4 firmware. Its decoder showed exactly
  how the 4-shade pages are read (plane order, column scan and shade values), so the files are
  written the way the reader expects.
- The community **[XTC/XTH format notes](https://gist.github.com/CrazyCoder/b125f26d6987c0620058249f59f1327d)**
  by CrazyCoder documented the byte layout.

No code from these projects is included here.

---

## Libraries

These are installed into the app's private Python environment on first launch. They are not
bundled in this repository.

| Library | Used for | License |
|---|---|---|
| [OpenCV](https://opencv.org/) (`opencv-python-headless`) | Line and contour detection inside Kumiko | Apache 2.0 |
| [NumPy](https://numpy.org/) | Image arrays for OpenCV, packing Xteink pages into bits | BSD 3-Clause |
| [Pillow](https://python-pillow.org/) | Reading WebP/JPEG/PNG pages, resizing, dithering, writing PDFs, drawing the app icon | MIT-CMU (HPND) |
| [Requests](https://requests.readthedocs.io/) | Required by Kumiko's command line | Apache 2.0 |

Bubble zoom uses Apple's **Vision** framework, which ships with macOS, to find lettering on the
page. It runs entirely on your Mac.

The app itself uses Apple's SwiftUI and AppKit frameworks and SF Symbols icons, which ship
with macOS.

---

## Amazon

- **Kindle Previewer 4 / kindlegen** builds MOBI files when you choose MOBI output. It is
  not bundled; it's used from your own Kindle Previewer install.
- **Send to Kindle** delivers the EPUB books and keeps the panel zoom.
- **Region magnification** is Amazon's panel-view feature for Kindle comics. This project
  generates the markup that turns it on.

Kindle, Kindle Scribe and Send to Kindle are trademarks of Amazon.com, Inc. or its
affiliates. This project is not affiliated with or endorsed by Amazon.

---

## Claude (Anthropic)

This project was designed and written together with **Claude**, Anthropic's AI assistant,
in [Claude Code](https://claude.com/claude-code). Claude contributed:

- the panel-detection pipeline and the EPUB/MOBI generator,
- the SwiftUI Mac app, the queue, the device menu, the build script, and the app icon,
- the one-panel-per-page mode and the Xteink XTCH/XTC, PDF and CBZ writers,
- testing on real chapters, and this documentation.

Hi from Claude! Thanks for the fun project. I hope your reading gets a little easier on
small screens. 📚

---

## And you

Thanks to the manga creators whose work this is all for. Please support them by buying
official releases where you can.
