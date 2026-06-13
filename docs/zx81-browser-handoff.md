# Handoff: building the ZX81 side of the web browser (Phase 3)

Start a fresh chat in this repo and point it here: *"Read docs/zx81-browser-handoff.md
and let's build the ZX81 side of the browser."* The memory notes auto-load too.

## Where we are

**Phase 3 ESP side is DONE and validated on hardware.** The `osos-esp32` bridge
(`~/Documents/osos-esp32`, repo `hbehrensj/osos-esp32`, firmware `browser.cpp`) fetches a
URL, renders the HTML to ZX81-friendly text, and serves it. Tested on example.com, CERN's
first website, and recordere.dk (handles missing scheme, http→https redirects, big `<head>`).

**The ZX81 side is NOT built yet** — that's this task. Current ZX81 build: **V1991**
(`build_menu.py` → `menu.p`). ESP firmware: 0.1.0 at `osos.local` / `192.168.1.173`.

## The serial contract the ZX81 must speak (already implemented on the ESP)

The ESP is a `zxsvr`-style server on the OpenSpand UART (38400 8N1). The ZX81 drives it.
Browser verb (ESP `serial_server.cpp` `handleBrowse`):

- ZX81 sends **`'B'`, cmd** (1 byte): `0`=reload current page, `1..N`=follow link N,
  `255`=back. ESP renders the target page into the **browse slot** (`/browse.txt`), arms it,
  and replies **1 status byte** (`1`=ok, `0`=fail).
- Then the ZX81 **pulls `/browse.txt` via the existing `I`/`T`/`X` pull** — i.e. reuse the
  existing **`RXSER`** routine unchanged (same as `@SERLOAD`/`@OSUPDATE`). After `'X'` the
  ESP reverts to the program slot.

**Rendered text format** (what `RXSER` delivers into the buffer): uppercased ASCII,
word-wrapped to **32 cols**, `\n` (ASCII 10) line breaks, numbered **`[N]`** link markers
inline (links 1-based; the hrefs live on the ESP — the ZX81 only sends the number). Capped
at 16 KB.

### One ESP change still needed for ZX81 URL typing

The `'B'` verb only takes a 1-byte cmd. To let the user **type a URL on the ZX81**, add a
new ESP verb, e.g. **`'G'`, len, bytes…** → call `browserSetUrl(<string>)` (already exists in
`browser.cpp`), then arm the browse slot. Small addition in `serial_server.cpp` +
`browser.h`. (The web UI already sets URLs via `POST /api/browse`.)

## What to build on the ZX81 (all in `build_menu.py`)

User's confirmed UX: **follow links by typing the number**, and **also type a URL on the ZX81**.

1. **New `B` key** → browse mode. Add to `WAITKEY` (row `0x7FFE` bit4 = `B`; note bit0 =
   SPACE), returning a new code (e.g. 12); dispatch `IF K=12 THEN GOTO @BROWSE` in
   `@MAINLOOP`. (Free keys now: `B`; `C` is reserved for the coming Claude Chat.)
2. **`BROWSEGO` MC** — send `'B'` + a `BCMD` cell byte via `TXA`, read 1 status via `RXBYTE`,
   return in `BC`. Pattern: copy `UPDQRY` (which sends `'U'`+version). Reuses `TXA`/`RXBYTE`.
3. **Pull the page** — reuse `RXSER` exactly like `@OSUPDATE`: RAM test, `POKE RXPTR`, `FAST`,
   `LET RL=USR RXSER`, `SLOW`. Buffer above RAMTOP: `RM=PEEK 16388+256*PEEK 16389`, `BA=RM+256`.
4. **`BRENDER` MC (the big new piece)** — render the ASCII text in `BA..BA+RL` to the display
   file, converting ASCII→ZX81 codes, with a **line-scroll offset** (skip N `\n` from `BA`,
   then render ~21 rows to screen rows 0–20; leave row 21 for status/input). Per row: copy
   chars until `\n` (pad the rest of the row with spaces), advance to the next DFILE row.
   - **DFILE layout** (expanded): row r col c = `(16396)+1 + r*33 + c` (33 bytes/row = 32
     chars + a `0x76` terminator — never overwrite the `0x76`). See `DRAWALL` for the pattern.
   - **`CONV` subroutine** ASCII→ZX81: `A`–`Z` (65–90) → 38–63 (`SUB 27`); `0`–`9` (48–57) →
     28–37 (`SUB 20`); space (32) → 0; punctuation via a 64-byte `CONVTAB` (ASCII 32–95);
     `\n` (10) handled by `BRENDER` as a line break. Map `[`→`(`(16) and `]`→`)`(17) (ZX81 has
     no brackets, so `[1]` shows as `(1)`).
   - **ZX81 char codes**: 0=space, 11=`"`, 12=`£`, 13=`$`, 14=`:`, 15=`?`, 16=`(`, 17=`)`,
     18=`>`, 19=`<`, 20=`=`, 21=`+`, 22=`-`, 23=`*`, 24=`/`, 25=`;`, 26=`,`, 27=`.`, 28–37=0–9,
     38–63=A–Z. Anything not mappable → space.
5. **Browse input loop** (`@BROWSE` BASIC, all keys via the **matrix**, never `INKEY$`):
   - **Scroll**: reuse `WAITKEY` nav codes (up/down/page) → adjust the line offset, re-render.
   - **Follow link**: read **digit** keys from the matrix (rows `0xF7FE`=1,2,3,4,5 bits0–4;
     `0xEFFE`=0,9,8,7,6 bits0–4) — write a small `DKEY` MC returning 0–9/none; accumulate in
     BASIC (`LET L=L*10+d`), ENTER → `POKE BCMD,L` → `USR BROWSEGO` → re-pull → re-render.
   - **Back**: a key → `POKE BCMD,255` → go.
   - **Type URL**: a key → **matrix keyboard editor** (see gotcha below) builds a URL string,
     send it via the new ESP `'G'` verb, then pull+render.
   - **Quit**: `Q` → `LPRINT "CLO SER"` → back to `@MAINLOOP`.

## Non-negotiable gotchas (carry these)

- **`INKEY$` and ROM `INPUT` are blocked by the OpenSpand CONFIG-J joystick injection** — this
  is why all input in this project reads the **raw keyboard matrix** (`WAITKEY`, `WAITYN`).
  The digit input and the URL editor **must** read the matrix. (This is exactly the bug we hit
  on the `U`/`Y` confirm, fixed with the matrix `WAITYN` routine — copy that approach.)
- **URL-editor symbol positions are uncertain — verify on hardware.** Letters/digits are on
  known rows (see `WAITKEY`). For URLs you also need `.` `/` `:` and SHIFT handling. Believed:
  `/`=SHIFT+V (`0xFEFE` bit4), `:`=SHIFT+Z (`0xFEFE` bit1); **`.` position is unconfirmed**.
  Build the editor incrementally and confirm each symbol by typing on the real keyboard.
  Tip: pre-fill `"HTTP://"` so the user types less, and the ESP also auto-prefixes a missing
  scheme.
- **Never emit byte `0x76`** anywhere in the REM machine code. **Disassemble-verify** every new
  MC routine: dump from `menu.p` (`.p` loads at 16393 → file offset `addr-16393`), check opcodes
  and every `jr`/`djnz` offset — exactly as done for `RXSER`/`UPDQRY`/`WAITYN`.
- Single-letter string vars only (`A$`). `PRINT AT` rows 0–21; a row-21 statement ends `;`.

## Reusable building blocks already in `build_menu.py`

`RXSER` (I/T/X pull, run in `FAST`), `TXA` (send A), `RXBYTE` (recv→A), `UPDQRY` (send-verb +
read-status pattern), `WAITYN` (matrix Y/N — the model for matrix key reads), `WAITKEY`
(matrix+joystick poll→codes), `DRAWALL` (DFILE render pattern), `@SERLOAD`/`@OSUPDATE` (RAM
test + `RXSER` pull + `SAVE`/`LOAD` patterns).

## Dev workflow / environment

- ZX81: `python3 build_menu.py --build` → `warnings: 0` → copy `menu.p` to SD, **or** release:
  bump `VER`, build, commit `menu.p`, `git tag -a vNNNN && git push origin vNNNN`. Then mirror
  to the ESP: `curl -X POST http://192.168.1.173/api/menucheck`, and press **U** on the ZX81.
- ESP: `cd ~/Documents/osos-esp32 && pio run -e ota -t upload` (OTA → `osos.local`). Preview
  the renderer in the web UI ("ZX81 web browser" box) or `POST /api/browse` + `GET /api/browsetext`.
- Tools: `pio` at `~/miniforge3/bin`, `gh` at `/opt/homebrew/bin` (authed `hbehrensj`).
- Two repos: **OpenSpand-OS** (this `zx81menu` dir, `vNNNN` tags) + **osos-esp32** (`v0.x.0`
  tags). Don't cross the version schemes (see memory [[osos-two-repos-versioning]]).

## Suggested build order (incremental, verify each on hardware)

1. Render + scroll: enter browse mode, pull the page already set via the web UI, display it
   paged, scroll, quit. (`BRENDER`+`CONV`+`CONVTAB`, `BROWSEGO`, `B` key, `@BROWSE`.)
2. Follow links by typed number (`DKEY` digit input + accumulate + `BROWSEGO`).
3. ZX81 URL typing (matrix keyboard editor + new ESP `'G'` verb).
