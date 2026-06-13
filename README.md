# OpenSpand OS

An interactive program launcher for the **Sinclair ZX81** fitted with an
[**OpenSpand**](https://codeberg.org/NollKollTroll/OpenSpand) expansion.

Browse the SD card, walk into subfolders, and launch `.p` programs with a joystick
**or** the keyboard — with a live date/time from the OpenSpand real‑time clock and a
**per‑game joystick configuration** that's applied automatically when you launch.

```
OPENSPAND OS  2026-05-30  14:23:55
DIR:/GAMES
--------------------------------
 ..             CONFIG
>CIV.P          C=SET KEYS
 CHESS.P        S=SERIAL IN
 INVADERS.P
--------------------------------
7UP 6DN 5,8PG 0RUN C=KEY Q=X
```

## Features

- Scrollable list of files **and** folders — more than one screen, up to 100 entries per directory.
- Page up / down for fast travel through long directories.
- Subfolder navigation: enter a folder, select the `..` entry to go up.
- Live date & time from the OpenSpand RTC.
- Atari‑style joystick (game port) **and** keyboard control, polled together.
- **Per‑game joystick key mapping**, saved on the SD card and applied (via the OpenSpand
  `CONFIG` command) right before the game loads.
- **Serial program transfer** — send a `.p` straight from a PC over the serial port; it's
  saved to the SD card as `INBOX.P`, then launched like any other file.
- Catalog reading, list rendering, **and the entire navigation loop** run in **Z80 machine
  code** — browsing is near‑instant despite BASIC being far too slow on a 3.25 MHz ZX81.

## Controls

| Action | Key / Joystick |
|--------|----------------|
| Move up / down | `7` / `6` (or stick up / down) |
| Page up / down | `5` / `8` (or stick left / right) |
| Run program / enter folder | `0` (or fire) |
| Up one level | select the `..` entry |
| Configure the selected game's keys | `C` |
| Receive a `.p` over serial | `S` |
| Quit launcher | `Q` |

Works with an Atari‑compatible joystick on the OpenSpand game port, or with the
keyboard. (When the joystick is in `CONFIG‑J` keyboard‑injection mode it can interfere
with real keyboard reads; the launcher reads the joystick *raw*, so the controller works
regardless.)

## Per‑game joystick configuration

Different games expect different keys. Highlight a `.p` game and press **`C`** — the right
panel prompts you to **press a key** for each direction in turn (Up, Down, Left, Right,
Fire). Whatever key you press is recorded for that direction, and when all five are set the
mapping is saved as a hidden **`GAME.C`** file next to the game.

When you later launch that game, the launcher issues `CONFIG "J=…"` so the OpenSpand injects
your chosen keys for the joystick — no need to reconfigure the interface by hand. Games
without a `.c` file launch with whatever joystick config is already set. The `.c` files are
hidden from the listing.

## Serial program transfer (dev workflow)

Pull a `.p` straight from your PC over the OpenSpand's serial port — handy for testing a
program you just built without shuffling the SD card. OSOS is a **`zxsvr` client**
([ZXpand‑Vitamins/serial‑server](https://github.com/charlierobson/ZXpand-Vitamins/tree/master/serial-server)),
so the PC server just waits and the ZX81 starts the transfer.

1. On the PC, start the server pointed at your file (leave it running):
   - Windows: `zxsvr.exe yourprog.p COM3`
   - macOS/Linux: `./zxserver.sh yourprog.p` (a tiny Python re‑implementation of the same
     protocol; edit the device path at the top — `ls /dev/cu.*` on macOS)
2. On the ZX81, press **`S`**. The screen blanks for ~2 s while it pulls the file in `FAST`
   mode.
3. The bytes land in spare RAM, are saved to the SD card as **`INBOX.P`**, and the launcher
   returns to the browser. Select `INBOX.P` and launch it like any other program. Press `S`
   again any time — the server keeps running for the next transfer.

Max program size is ~15 KB (the receive buffer lives in the unused RAM above `RAMTOP`).

**Protocol (`zxsvr`, ZX81‑initiated pull, 38400 8N1):** the ZX81 sends `'I'` and the server
replies with the 2‑byte little‑endian file length; then for each 256‑byte block the ZX81 sends
`'T', blockNum, blockLen` (`blockLen` 0 = 256) and the server returns that many data bytes plus
a 2‑byte checksum; finally the ZX81 sends `'X'`. Because the data arrives back‑to‑back with no
per‑byte handshake, the receive runs in `FAST` mode so the full‑speed CPU keeps the OpenSpand's
32‑byte serial FIFO drained. (Transmitting from the ZX81 works by writing the serial data port
`0x00E3` once status `0x00EB` bit 2 signals the TX buffer has room.)

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

The BASIC is written with **labels** rather than hard line numbers — `build_menu.py` runs a
small two‑pass pass that assigns line numbers and resolves `GOTO`/`GOSUB` targets (the same
trick the Z80 assembler in the file uses for jumps), so code can be reordered freely.

Tunables live at the top of `build_menu.py`: `SW` (max name length / list width), `MAXE`
(max entries per directory), `V` (visible rows), `RPTN` (hold‑to‑scroll repeat speed),
`HKDIV` (idle clock/refresh cadence), `PCOL` (config‑panel column).

## How it works (notes for the curious)

The interesting parts were all dictated by ZX81/OpenSpand quirks:

- **Catalog read via the low‑level `PRT3` ports.** The high‑level `ZXPAND "OPE CAT"`
  recurses forever (`directory_stat`) and hard‑resets the machine, so the launcher drives
  the directory ports directly from a small Z80 routine in line 1's `REM`, one entry at a time.
- **List drawn straight to the display file (DFILE) in machine code.** `PRINT AT` costs
  ~60 ms per row (≈1 s for a full redraw); writing characters directly to screen memory is
  near‑instant.
- **The navigation loop lives in machine code.** A `NAV` routine polls the raw joystick *and*
  the keyboard matrix, moves the selection, scrolls, redraws, and handles auto‑repeat — all
  in Z80. BASIC's loop is a thin shell that only reacts to *actions* (launch / configure /
  quit), so interpreted‑BASIC overhead is kept off the hot path entirely.
- **Per‑game config uses plain `SAVE`/`LOAD` + `CONFIG`.** Config files are written/read as raw
  memory blocks (`SAVE ">NAME.C;addr,len"` / `LOAD "NAME.C;addr"`), and applied with the
  `CONFIG` command — which on OpenSpand is the **`LLIST` token**, not a `ZXPAND`/`LPRINT`
  verb. No machine code needed for any of it.
- Everything — Z80 *and* BASIC — is produced by `build_menu.py`.

## Vibe‑coded

This project was **vibe‑coded**: built end‑to‑end through an iterative, conversational
collaboration with an AI assistant (Anthropic's **Claude**), driven by real hardware
testing and a lot of back‑and‑forth debugging. The OpenSpand command interface and
directory format were reverse‑engineered from the firmware sources and confirmed with
on‑hardware probes, and the ZX81 gotchas (the `PRINT AT` row limit, the `directory_stat`
crash, Z80 register‑opcode traps, single‑letter string‑variable names, the floating‑point
cost) were each discovered and worked around along the way.

## Credits & thanks

Huge thanks to **Adam Klotblixt** (*NollKollTroll*), creator of **OpenSpand** — the
open‑source, all‑in‑one ZX80/ZX81 expansion this launcher is built for and could not
exist without. Project home: <https://codeberg.org/NollKollTroll/OpenSpand>

The `CONFIG`/`ZXPAND` command conventions follow **ZXpand** (Charlie Robson); the snappy
machine‑code navigation took inspiration from **zxpand‑commander**.

BASIC tokenizing courtesy of the **ZX81 BASIC to P‑File Converter**
(`maziac.zx81-bastop`).

## Files

| File | Purpose |
|------|---------|
| `build_menu.py` | Generator — source of truth (Z80 assembler + BASIC emitter) |
| `menu.bas` | Generated ZX81 BASIC (zxtext2p text format) |
| `menu.p` | The runnable ZX81 program — copy this to the SD card |
| `zxserver.sh` | macOS/Linux `zxsvr`‑protocol server for serial transfer (`./zxserver.sh file.p`) |
| `.vscode/tasks.json` | VSCode build task (`Build menu.p`) |
| `LICENSE` | GNU GPL v3.0 |

## License

Released under the **GNU General Public License v3.0** — the same license as the
OpenSpand firmware — see [`LICENSE`](LICENSE).

```
Copyright (C) 2026  Henrik Jensen

This program is free software: you can redistribute it and/or modify it under the
terms of the GNU General Public License as published by the Free Software Foundation,
either version 3 of the License, or (at your option) any later version.  It is
distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; see the
GNU General Public License for more details.
```
