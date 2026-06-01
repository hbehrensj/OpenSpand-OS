# OpenSpand OS

An interactive program launcher for the **Sinclair ZX81** fitted with an
[**OpenSpand**](https://codeberg.org/NollKollTroll/OpenSpand) expansion.

Browse the SD card, walk into subfolders, and launch `.p` programs with a joystick
**or** the keyboard — with a live date/time from the OpenSpand real‑time clock.

```
OPENSPAND OS  2026-05-30  14:23:55
DIR:/GAMES
------------------------------
 ..
>CIV.P
 CHESS.P
 INVADERS.P
------------------------------
7UP 6DN 5,8PG 0RUN QQUIT
```

## Features

- Scrollable list of files **and** folders — more than one screen, up to 100 entries per directory.
- Page up / down for fast travel through long directories.
- Subfolder navigation: enter a folder, select the `..` entry to go up.
- Live date & time from the OpenSpand RTC.
- Atari‑style joystick (game port) **and** keyboard control, polled together.
- Catalog reading, list rendering, **and the whole input poll** done in **Z80 machine code**
  for speed (BASIC alone is far too slow for snappy scrolling / input on a 3.25 MHz ZX81).

## Controls

| Action | Key / Joystick |
|--------|----------------|
| Move up / down | `7` / `6` (or stick up / down) |
| Page up / down | `5` / `8` (or stick left / right) |
| Run program / enter folder | `0` (or fire) |
| Up one level | select the `..` entry |
| Quit launcher | `Q` |

Works with an Atari‑compatible joystick on the OpenSpand game port, or with the
keyboard. (When the joystick is in CONFIG‑J keyboard‑injection mode it can interfere
with real keyboard reads; the launcher reads the joystick *raw*, so the controller
works regardless.)

## Install

Copy **`menu.p`** to the root of your SD card. Rename it to **`MENU.P`** to have
OpenSpand auto‑boot it on power‑up.

## Build

`menu.p` is **generated** by `build_menu.py`, which hand‑assembles the embedded Z80
machine code, resolves all addresses, and emits the complete ZX81 BASIC:

```sh
python3 build_menu.py          # writes menu.bas
python3 build_menu.py --build  # also converts menu.bas -> menu.p
                               # (macOS, via the VSCode zx81-bastop extension)
```

Or convert `menu.bas` → `menu.p` yourself with the
[**maziac.zx81-bastop**](https://marketplace.visualstudio.com/items?itemName=maziac.zx81-bastop)
VSCode extension (right‑click the file, or run the build task in `.vscode/tasks.json`).

Tunables live at the top of `build_menu.py` (`SW` = max name length, `MAXE` = max
entries per directory, `V` = visible rows).

## How it works (notes for the curious)

The interesting parts were all dictated by ZX81/OpenSpand quirks:

- **Catalog read via the low‑level `PRT3` ports.** The high‑level `ZXPAND "OPE CAT"`
  recurses forever (`directory_stat`) and hard‑resets the machine, so the launcher
  drives the directory ports directly from a small Z80 routine in line 1's `REM`.
- **List drawn straight to the display file (DFILE) in machine code.** `PRINT AT`
  costs ~60 ms per row (≈1 s for a full redraw); writing characters directly to
  screen memory is near‑instant.
- **Input poll done in machine code.** A single `WAITKEY` routine reads the raw joystick
  *and* the keyboard matrix in one non‑blocking poll and returns a single direction code,
  so the BASIC loop does almost no work per iteration — the ZX81 floating‑point calculator
  never touches the hot path. Presses register instantly.
- Everything — Z80 *and* BASIC — is produced by `build_menu.py`.

## Vibe‑coded

This project was **vibe‑coded**: built end‑to‑end through an iterative, conversational
collaboration with an AI assistant (Anthropic's **Claude**), driven by real hardware
testing and a lot of back‑and‑forth debugging. The OpenSpand command interface and
directory format were reverse‑engineered from the firmware sources, and the ZX81
gotchas (the `PRINT AT` row limit, the `directory_stat` crash, Z80 register‑opcode
traps, the floating‑point cost) were each discovered and worked around along the way.

## Credits & thanks

Huge thanks to **Adam Klotblixt** (*NollKollTroll*), creator of **OpenSpand** — the
open‑source, all‑in‑one ZX80/ZX81 expansion this launcher is built for and could not
exist without. Project home: <https://codeberg.org/NollKollTroll/OpenSpand>

BASIC tokenizing courtesy of the **ZX81 BASIC to P‑File Converter**
(`maziac.zx81-bastop`).

## Files

| File | Purpose |
|------|---------|
| `build_menu.py` | Generator — source of truth (Z80 assembler + BASIC emitter) |
| `menu.bas` | Generated ZX81 BASIC (zxtext2p text format) |
| `menu.p` | The runnable ZX81 program — copy this to the SD card |
| `.vscode/tasks.json` | VSCode build task (`Build menu.p`) |
| `LICENSE` | GNU GPL v3.0 |

## License

Released under the **GNU General Public License v3.0** — the same license as the
OpenSpand firmware — see [`LICENSE`](LICENSE).

```
Copyright (C) 2026  <your name>

This program is free software: you can redistribute it and/or modify it under the
terms of the GNU General Public License as published by the Free Software Foundation,
either version 3 of the License, or (at your option) any later version.  It is
distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; see the
GNU General Public License for more details.
```
