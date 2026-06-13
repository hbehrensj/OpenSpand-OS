# OpenSpand OS (OSOS)

Interactive program launcher for a **Sinclair ZX81** with an **OpenSpand** expansion
(ZXpand+-compatible). Browse the SD card, configure per-game joystick keys, show the RTC
clock, and serial-load `.p` files from a PC. License: GPLv3.

## The one rule: `build_menu.py` is the only source of truth

`menu.bas` and `menu.p` are **generated artifacts — never edit them by hand.** All Z80
machine code and all BASIC are emitted by [build_menu.py](build_menu.py). Change the
generator, then rebuild.

```sh
python3 build_menu.py          # writes menu.bas (zxtext2p text format)
python3 build_menu.py --build  # also tokenizes menu.bas -> menu.p
                               # (macOS, headless via the maziac.zx81-bastop VSCode ext)
```
Goal after any change: `warnings: 0`. Copy `menu.p` to the SD card to run (rename `MENU.P`
to auto-boot). Bump `VER="V…"` (top of build_menu.py) for a user-visible change.

**Releasing (for the ESP auto-update):** commit the rebuilt `menu.p`, then push a matching
tag — `git tag -a vNNNN && git push origin vNNNN` (e.g. `v1988` for `VER="V1988"`). The
`.github/workflows/release.yml` job attaches `menu.p` + a generated `version.json` (version
parsed from `VER`) to the GitHub Release. The [osos-esp32](https://github.com/hbehrensj/osos-esp32)
bridge mirrors that release; the ZX81 installs it via the **U** key (zxsvr `'U'` verb →
`@OSUPDATE` → `RXSER` → `SAVE >MENU.P` → `LOAD "MENU.P"`).

## How it's built

ZX81 BASIC is far too slow, so the hot paths are **Z80 machine code living in line 1's
`REM`** (content sits at fixed address `BASE=16514`). build_menu.py is two things:

1. **A hand assembler** — `emit(*bytes)`, `lbl("NAME")`, `ref("NAME")` (2-byte address),
   `jr(cc,"NAME")` / `djnz("NAME")` (relative). Two passes resolve label addresses.
   MC routines: `OPEN`/`GETSLOT` (catalog via low-level PRT3 ports), `DRAWALL` (render the
   list straight to the display file), `NAV`/`WAITKEY` (the whole nav loop — joystick + keys),
   `BLITDAT`/`BLITTIM` (clock blit), `RXSER`+`TXA` (serial), panel render. Data cells
   (`sptr`, `TCELL`, `RXPTR`, `cfgbuf`, …) live after the code; `addr("name")` exposes their
   addresses to the BASIC as `USR`/`PEEK`/`POKE` targets.
2. **A BASIC label preprocessor** — write statements with `B("…")` and mark jump targets with
   `LBL("NAME")`; reference them as `@NAME` inside the text. Python assigns ascending line
   numbers and resolves `GOTO`/`GOSUB @NAME`. So **never hard-code BASIC line numbers.**
   Key labels: `@MAINLOOP`, `@LISTDIR`, `@REDRAW`, `@ACTIVATE`, `@SERLOAD`, `@CFGEDIT`.

Tunables are the line above `VER` (e.g. `SW`=name width/list cols, `MAXE`=max entries,
`V`=visible rows, `PCOL`=config-panel column, `SERBAUD`).

## Non-negotiable ZX81 / OpenSpand gotchas

- **Never emit byte `0x76`** anywhere in REM machine code — it's the BASIC line terminator.
  (That's why name-scan loops compare `CP 0x40`, not 118.)
- **String variables are single-letter only** (`A$`, not `AK$`) — two letters crash (report C).
- `PRINT AT` rows are **0–21**; a statement printing to row 21 must end with `;`.
- **Token reuse:** `ZXPAND` = the `LPRINT` token, `CAT` = `COPY`, **`CONFIG` = the `LLIST`
  token** (not an LPRINT verb). So `LPRINT "OPE SER 38400"` = `ZXPAND "OPE SER 38400"`, and
  `LLIST "J=12345"` = `CONFIG "J=…"`. CONFIG applies **live** (no physical 'S' save needed).
- High-level `OPE CAT` infinitely recurses (`directory_stat`) and resets the machine — the
  catalog is read via the PRT3 ports in MC, **one entry per BASIC call** (batching races the
  firmware and hangs).
- MC faults are **opaque** (video stops, no report code). Disassemble-verify new MC: dump the
  bytes from `menu.p` (`.p` loads at 16393, so `addr` → file offset `addr-16393`) and check
  the opcodes and every `jr`/`djnz` offset.

## Deeper, verified hardware facts

Two memory notes are auto-loaded each session and hold the reverse-engineered detail
(catalog format, joystick decode, SD block I/O, the full serial `zxsvr` pull protocol, the
toolchain). Trust them but **re-verify file:line claims against current code** before acting.

## Serial program load (dev workflow)

OSOS is a **`zxsvr` client** (charlierobson ZXpand-Vitamins/serial-server). The PC server
waits; press `S` on the ZX81 to pull the file (38400 8N1, receive runs in `FAST` mode). It's
saved as `INBOX.P` for launching from the browser. PC side: `zxsvr.exe file.p COMx` or the
bundled `./zxserver.sh file.p` (macOS/Linux re-impl). See README for the protocol.
