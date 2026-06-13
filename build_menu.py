#!/usr/bin/env python3
"""
build_menu.py - Generator for the OpenSpand launcher (menu.bas).

MC routines in the line-1 REM:
  OPEN     - open/chdir a directory (path in bufA) via low-level PRT3.
  GETSLOT  - read ONE catalog entry into the slot buffer at sptr, pad to SW,
             return name length in BC (0=end). Per-entry call from BASIC.
  DRAWROW  - draw ONE list row straight to the DFILE. Takes RCELL (screen row)
             and KCELL (slot index) as bytes and computes DEST=(16396)+1+R*33
             and SRC=slot+K*SW in machine code (so BASIC needs NO slow float
             divides), then writes marker + SW name bytes. No IX, one PUSH/POP.

Input: raw joystick (USR 8190, ACTIVE-LOW: neutral 249, pressed clears a bit;
7=up 6=down 5=left 4=right 3=fire) + keyboard (INKEY$ 7/6/5/8/0) -> K$.

Perf: ZX81 floating-point divide is slow; keep INT(x/256) OUT of the input loop
and the per-row draw (DRAWROW does the *33 / *SW multiplies in MC instead). The
joystick low byte is already <256 so no masking divide is needed.

Facts: high-level OPE CAT crashes (directory_stat); res 0x40=entry/0x3F=end; OUT
PRT0,0 before data; name chars <64 (stop 0 or >=64); never emit 0x76 in REM code;
expanded DFILE row r col c=(16396)+1+r*33+c; PRINT AT rows 0-21, row-21 ends ';';
no digit/E var names; JR/DJNZ rel = target_index-(offset_index+1); LD C,E=0x4B,
LD A,E=0x7B (NOT 0x48/0x7A).

Usage: python3 build_menu.py [--build]
"""
SW=14; MAXE=100; V=17; BASE=16514; CLKDIV=50; PCOL=16; PW=32-PCOL; PR=12; RPTN=1; HKDIV=24; SERBAUD=38400; RXIDL=8192
VER="V1986"
prog=[]; labels={}
def emit(*bs):
    for b in bs: prog.append(("b",b&0xFF))
def ref(l): prog.append(("lo",l)); prog.append(("hi",l))
def lbl(n): labels[n]=len(prog)
def ld_bc(v): emit(0x01,v&0xFF,(v>>8)&0xFF)
def ld_hl(l): emit(0x21); ref(l)
def jr(cc,l):
    op={"NZ":0x20,"Z":0x28,"NC":0x30,"C":0x38,None:0x18}[cc]; emit(op); prog.append(("jr",l))
def djnz(l): emit(0x10); prog.append(("jr",l))
# OPEN
lbl("OPEN")
ld_bc(0x0007); emit(0x3E,0xFF); emit(0xED,0x79)
ld_hl("bufA"); ld_bc(0x4007)
lbl("OPENL")
emit(0x7E); emit(0xED,0x79); emit(0x23); emit(0xA7); jr("NZ","OPENL")
ld_bc(0x6007); emit(0xAF); emit(0xED,0x79)
ld_bc(0x0017)
lbl("OPENW")
emit(0xED,0x78); emit(0xA7); jr("NZ","OPENW")
emit(0xC9)
# GETSLOT
lbl("GET")
ld_bc(0x6007); emit(0x3E,0x01); emit(0xED,0x79)
ld_bc(0x0017)
lbl("GEW")
emit(0xED,0x78); emit(0xA7); jr("NZ","GEW")
ld_bc(0x0007); emit(0xED,0x78)
emit(0xFE,0x40); jr("NZ","GEEND")
emit(0x3E,0x00); emit(0xED,0x79)
emit(0x2A); ref("sptr")
emit(0x1E,0x00)
lbl("GEL")
emit(0xED,0x78)
emit(0xA7); jr("Z","GEPAD")
emit(0xFE,0x40); jr("NC","GEPAD")
emit(0x77); emit(0x23); emit(0x1C)
emit(0x7B); emit(0xFE,SW); jr("C","GEL")
lbl("GEPAD")
emit(0x7B)
lbl("GEP2")
emit(0xFE,SW); jr("NC","GEDONE")
emit(0x36,0x00); emit(0x23); emit(0x3C); jr(None,"GEP2")
lbl("GEDONE")
emit(0x22); ref("sptr")
emit(0x4B); emit(0x06,0x00); emit(0xC9)
lbl("GEEND")
emit(0x01,0x00,0x00); emit(0xC9)
# DRAWALL: render the whole visible window (V rows) to the DFILE in one call.
# Reads T (top idx), S (selected idx), N (count) from RAM cells; V is baked in.
# For each row K=T..T+V-1: if K<N draw marker (">"/space) + SW name bytes from
# slot+K*SW; else blank the 29-char row. DEST base = (16396)+1+3*33 (screen row 3),
# walks +33 per row; SRC walks +SW per drawn row. No firmware handshake, no IX.
lbl("DRAWALL")
emit(0x21); ref("slot")                 # LD HL,slot
emit(0x3A); ref("TCELL")                # LD A,(TCELL)   T
emit(0xA7); jr("Z","DASRC")             # AND A; JR Z (T==0, skip multiply)
emit(0x47)                              # LD B,A
emit(0x11,SW,0)                         # LD DE,SW
lbl("DAMUL")
emit(0x19); djnz("DAMUL")               # ADD HL,DE; DJNZ -> HL=slot+T*SW
lbl("DASRC")
emit(0xEB)                              # EX DE,HL  (DE=SRC)
emit(0x2A,0x0C,0x40)                    # LD HL,(16396)
emit(0xD5); emit(0x11,100,0); emit(0x19); emit(0xD1)  # PUSH DE;LD DE,100;ADD HL,DE;POP DE -> row3 dest
emit(0x3A); ref("TCELL")                # LD A,(TCELL)
emit(0x4F)                              # LD C,A   (K=T)
emit(0x06,V)                            # LD B,V   (row counter)
lbl("DALOOP")
emit(0xE5)                              # PUSH HL  (row base)
emit(0x3A); ref("NCELL")                # LD A,(NCELL)
emit(0xB9)                              # CP C     (N-K)
jr("Z","DABLK")                         # K==N -> blank
jr("C","DABLK")                         # K>N  -> blank
emit(0x3A); ref("SCELL")                # LD A,(SCELL)
emit(0xB9)                              # CP C     (Z if selected)
emit(0x3E,0x00)                         # LD A,0   (flags preserved)
jr("NZ","DAMK")                         # not selected -> marker 0
emit(0x3E,0x12)                         # LD A,18  (">")
lbl("DAMK")
emit(0x77); emit(0x23)                  # LD (HL),A; INC HL  (marker)
emit(0xC5)                              # PUSH BC  (save rows+K)
emit(0x06,SW)                           # LD B,SW
lbl("DACP")
emit(0x1A); emit(0x13); emit(0x77); emit(0x23); djnz("DACP")  # copy SW name bytes (DE->HL)
emit(0xC1)                              # POP BC
jr(None,"DANXT")
lbl("DABLK")
emit(0xC5)                              # PUSH BC
emit(0x06,SW+1)                         # LD B,SW+1 (marker+name = list width; leaves panel cols intact)
emit(0xAF)                              # XOR A
lbl("DABL")
emit(0x77); emit(0x23); djnz("DABL")    # blank the row
emit(0xC1)                              # POP BC
lbl("DANXT")
emit(0xE1)                              # POP HL  (row base)
emit(0xD5); emit(0x11,33,0); emit(0x19); emit(0xD1)  # PUSH DE;LD DE,33;ADD HL,DE;POP DE -> next row
emit(0x0C)                              # INC C  (K++)
djnz("DALOOP")
emit(0xC9)
# WAITKEY: one quick poll of the raw joystick (0xE007/0xA0) AND the keyboard matrix,
# decoded in MC.  Returns a unified code in C:
#   0=none 1=up 2=down 3=pageup 4=fire 5=pagedown 6=quit
# Joystick: up/down move, left->pageup, right->pagedown, fire=run/enter.
# Keyboard: 7=up 6=down 5=pageup 8=pagedown 0=fire Q=quit.
# One non-blocking poll (short) -> no SLOW-mode screen blanking; keeps the slow
# ZX81 float decode entirely out of the BASIC loop.
lbl("WAITKEY")
emit(0x01,0x07,0xE0); emit(0x3E,0xA0); emit(0xED,0x79)   # LD BC,0xE007; LD A,0xA0; OUT(C),A
emit(0x01,0x07,0x00); emit(0xED,0x78)                    # LD BC,0x0007; IN A,(C)  raw joystick (active-low)
emit(0xCB,0x7F); jr("Z","WKUP")                          # BIT7 up
emit(0xCB,0x77); jr("Z","WKDN")                          # BIT6 down
emit(0xCB,0x6F); jr("Z","WKPU")                          # BIT5 left -> pageup
emit(0xCB,0x67); jr("Z","WKPD")                          # BIT4 right -> pagedown
emit(0xCB,0x5F); jr("Z","WKFR")                          # BIT3 fire
emit(0x01,0xFE,0xEF); emit(0xED,0x78)                    # LD BC,0xEFFE; IN A,(C)  keys 0,9,8,7,6
emit(0xCB,0x5F); jr("Z","WKUP")                          # bit3=key7 up
emit(0xCB,0x67); jr("Z","WKDN")                          # bit4=key6 down
emit(0xCB,0x57); jr("Z","WKPD")                          # bit2=key8 pagedown
emit(0xCB,0x47); jr("Z","WKFR")                          # bit0=key0 fire
emit(0x01,0xFE,0xF7); emit(0xED,0x78)                    # LD BC,0xF7FE; IN A,(C)  keys 1,2,3,4,5
emit(0xCB,0x67); jr("Z","WKPU")                          # bit4=key5 pageup
emit(0x01,0xFE,0xFB); emit(0xED,0x78)                    # LD BC,0xFBFE; IN A,(C)  keys Q,W,E,R,T
emit(0xCB,0x47); jr("Z","WKQT")                          # bit0=keyQ quit
emit(0x01,0xFE,0xFE); emit(0xED,0x78)                    # LD BC,0xFEFE; IN A,(C)  keys SHIFT,Z,X,C,V
emit(0xCB,0x5F); jr("Z","WKCFG")                         # bit3=key C -> config edit
emit(0x01,0xFE,0xFD); emit(0xED,0x78)                    # LD BC,0xFDFE; IN A,(C)  keys A,S,D,F,G
emit(0xCB,0x4F); jr("Z","WKSER")                         # bit1=key S -> serial load
emit(0x0E,0x00); emit(0x06,0x00); emit(0xC9)             # none
lbl("WKUP"); emit(0x0E,0x01); emit(0x06,0x00); emit(0xC9)
lbl("WKDN"); emit(0x0E,0x02); emit(0x06,0x00); emit(0xC9)
lbl("WKPU"); emit(0x0E,0x03); emit(0x06,0x00); emit(0xC9)
lbl("WKFR"); emit(0x0E,0x04); emit(0x06,0x00); emit(0xC9)
lbl("WKPD"); emit(0x0E,0x05); emit(0x06,0x00); emit(0xC9)
lbl("WKQT"); emit(0x0E,0x06); emit(0x06,0x00); emit(0xC9)
lbl("WKCFG"); emit(0x0E,0x07); emit(0x06,0x00); emit(0xC9)
lbl("WKSER"); emit(0x0E,10); emit(0x06,0x00); emit(0xC9)
# PANELMC: blit the PR x PW panel buffer (pbuf) to the DFILE at screen rows 3..,
# cols PCOL.. (DEST=(16396)+1+3*33+PCOL = +100+PCOL, walks +33 per row). Straight
# copy (DE=SRC walks pbuf continuously). Replaces ~9 slow PRINT AT per panel update.
lbl("PANELMC")
emit(0x11); ref("pbuf")                                 # LD DE,pbuf (SRC)
emit(0x2A,0x0C,0x40)                                    # LD HL,(16396)
emit(0xD5); emit(0x11,(100+PCOL)&0xFF,((100+PCOL)>>8)&0xFF); emit(0x19); emit(0xD1)  # HL=row3 colPCOL
emit(0x06,PR)                                           # LD B,PR (rows)
lbl("PMROW")
emit(0xC5); emit(0xE5)                                  # PUSH BC; PUSH HL
emit(0x06,PW)                                           # LD B,PW
lbl("PMCOL")
emit(0x1A); emit(0x13); emit(0x77); emit(0x23); djnz("PMCOL")  # copy PW bytes DE->HL
emit(0xE1)                                              # POP HL (row base)
emit(0xD5); emit(0x11,33,0); emit(0x19); emit(0xD1)     # next row (preserve DE/SRC)
emit(0xC1)                                              # POP BC
djnz("PMROW")
emit(0xC9)
# PANELCLR: fill the same panel region with spaces (folders / no selection).
lbl("PANELCLR")
emit(0x2A,0x0C,0x40)                                    # LD HL,(16396)
emit(0x11,(100+PCOL)&0xFF,((100+PCOL)>>8)&0xFF); emit(0x19)  # HL=row3 colPCOL
emit(0x06,PR)                                           # LD B,PR
lbl("PCROW")
emit(0xC5); emit(0xE5)                                  # PUSH BC; PUSH HL
emit(0x06,PW); emit(0xAF)                               # LD B,PW; XOR A
lbl("PCCOL")
emit(0x77); emit(0x23); djnz("PCCOL")                   # LD (HL),0; INC HL; DJNZ
emit(0xE1)                                              # POP HL
emit(0x11,33,0); emit(0x19)                             # LD DE,33; ADD HL,DE
emit(0xC1)                                              # POP BC
djnz("PCROW")
emit(0xC9)
# NAV: machine-code navigation loop body. CALL WAITKEY, then for up/down/page it
# updates S/T (SCELL/TCELL) and redraws (CALL DRAWALL) entirely in MC, throttled by
# the RPT counter. Returns C: 8=navigated (BASIC just loops), 0=idle, 4/6/7=
# fire/quit/config for BASIC. Kills the ~15 interpreted statements per move.
lbl("NAV")
emit(0xCD); ref("WAITKEY")              # CALL WAITKEY -> C=code, B=0
emit(0x79)                              # LD A,C
emit(0xFE,0x04); jr("Z","NAVACT")       # 4 fire -> action
emit(0xFE,0x06); jr("NC","NAVACT")      # >=6 quit/config -> action
emit(0xAF); emit(0x32); ref("ACTDN")    # not an action: clear ACTDN (release)
emit(0x79); emit(0xA7); jr("Z","NAVIDLE")   # LD A,C; AND A; 0 -> idle
jr(None,"NAV3")                         # 1,2,3,5 -> navigation
lbl("NAVACT")                           # action key (4/6/7): edge-detect (debounce)
emit(0x3A); ref("ACTDN")                # LD A,(ACTDN)
emit(0xA7); jr("NZ","NAVZ0")            # already down -> return 0 (ignore repeat)
emit(0x3E,0x01); emit(0x32); ref("ACTDN")   # LD A,1; LD (ACTDN),A
emit(0xC9)                              # edge: RET with code in C (4/6/7), B=0
lbl("NAVZ0")
emit(0x0E,0x00); emit(0x06,0x00); emit(0xC9)   # LD C,0; LD B,0; RET
lbl("NAVIDLE")                          # nothing pressed
emit(0xAF); emit(0x32); ref("RPT")      # XOR A; LD (RPT),A (reset repeat)
emit(0x3A); ref("IDLECNT")              # LD A,(IDLECNT)
emit(0x3C)                              # INC A
emit(0xFE,HKDIV); jr("C","NAVIDL2")     # CP HKDIV; < HKDIV -> keep counting
emit(0xAF); emit(0x32); ref("IDLECNT")  # reached HKDIV: reset counter
emit(0x0E,0x09); emit(0x06,0x00); emit(0xC9)   # LD C,9; LD B,0; RET (housekeeping tick)
lbl("NAVIDL2")
emit(0x32); ref("IDLECNT")              # store incremented count
emit(0x0E,0x00); emit(0x06,0x00); emit(0xC9)   # LD C,0; LD B,0; RET (idle)
lbl("NAV3")
emit(0x3A); ref("RPT")                  # LD A,(RPT)  repeat throttle
emit(0xA7); jr("Z","NAVMOVE")           # RPT==0 -> move now
emit(0x3D); emit(0x32); ref("RPT")      # DEC A; LD (RPT),A
emit(0x0E,0x08); emit(0x06,0x00); emit(0xC9)   # throttled tick: C=8; B=0; RET
lbl("NAVMOVE")
emit(0x3E,RPTN); emit(0x32); ref("RPT") # LD A,RPTN; LD (RPT),A
emit(0x79)                              # LD A,C
emit(0xFE,0x01); jr("Z","NAVUP")
emit(0xFE,0x02); jr("Z","NAVDN")
emit(0xFE,0x03); jr("Z","NAVPU")
jr(None,"NAVPD")                        # code 5 = pagedown
lbl("NAVUP")
emit(0x3A); ref("SCELL")                # LD A,(SCELL)
emit(0xA7); jr("Z","NAVR8")             # S==0 -> no move
emit(0x3D); emit(0x32); ref("SCELL")    # DEC A; LD (SCELL),A  (S=S-1)
emit(0x21); ref("TCELL")                # LD HL,TCELL
emit(0xBE); jr("NC","NAVDRAW")          # CP (HL): if newS>=T no scroll
emit(0x77)                              # LD (HL),A : T=newS
jr(None,"NAVDRAW")
lbl("NAVDN")
emit(0x3A); ref("NCELL")                # LD A,(NCELL)
emit(0xA7); jr("Z","NAVR8")             # N==0 -> no move
emit(0x3D)                              # DEC A (N-1)
emit(0x21); ref("SCELL")                # LD HL,SCELL
emit(0xBE); jr("C","NAVR8")             # (N-1)<S safety
jr("Z","NAVR8")                         # S==N-1 -> bottom
emit(0x3A); ref("SCELL")                # LD A,(SCELL)
emit(0x3C); emit(0x32); ref("SCELL")    # INC A; LD (SCELL),A  (S=S+1)
emit(0x47)                              # LD B,A (newS)
emit(0x3A); ref("TCELL")                # LD A,(TCELL)
emit(0xC6,V-1)                          # ADD A,V-1  (T+V-1)
emit(0xB8); jr("NC","NAVDRAW")          # CP B: if T+V-1>=newS no scroll
emit(0x78); emit(0xD6,V-1)              # LD A,B; SUB V-1  (newS-V+1)
emit(0x32); ref("TCELL")                # LD (TCELL),A
jr(None,"NAVDRAW")
lbl("NAVPU")
emit(0x3A); ref("TCELL")                # LD A,(TCELL)
emit(0xD6,V); jr("NC","NAVPU2")         # SUB V
emit(0xAF)                              # XOR A (clamp 0)
lbl("NAVPU2")
emit(0x32); ref("TCELL")                # LD (TCELL),A
emit(0x32); ref("SCELL")                # LD (SCELL),A  (S=T)
jr(None,"NAVDRAW")
lbl("NAVPD")
emit(0x3A); ref("TCELL")                # LD A,(TCELL)
emit(0xC6,V); emit(0x47)                # ADD A,V; LD B,A  (candidate=T+V)
emit(0x3A); ref("NCELL")                # LD A,(NCELL)
emit(0xD6,V); jr("NC","NAVPD2")         # SUB V  (cap=N-V)
emit(0xAF)                              # XOR A (clamp 0)
lbl("NAVPD2")
emit(0xB8); jr("NC","NAVPD3")           # CP B: if cap>=candidate use candidate
jr(None,"NAVPD4")                       # cap<candidate -> T=cap (A=cap)
lbl("NAVPD3")
emit(0x78)                              # LD A,B (candidate)
lbl("NAVPD4")
emit(0x32); ref("TCELL")                # LD (TCELL),A
emit(0x32); ref("SCELL")                # LD (SCELL),A  (S=T)
lbl("NAVDRAW")
emit(0xCD); ref("DRAWALL")              # CALL DRAWALL (redraw list with new S/T)
lbl("NAVR8")
emit(0x0E,0x08); emit(0x06,0x00); emit(0xC9)   # LD C,8; LD B,0; RET (navigated)
# BLITDAT/BLITTIM: copy the RTC text from the IO buffer (16449) straight to the screen
# (row 0 col 13 / col 24) with one LDIR - replaces the BASIC PEEK-loop + string + PRINT.
lbl("BLITDAT")
emit(0x2A,0x0C,0x40)                    # LD HL,(16396)
emit(0x11,14,0); emit(0x19); emit(0xEB)  # LD DE,14; ADD HL,DE; EX DE,HL  (DE=row0 col13)
emit(0x21,0x41,0x40)                    # LD HL,16449  (IO buffer)
emit(0x01,10,0)                         # LD BC,10
emit(0xED,0xB0); emit(0xC9)             # LDIR; RET
lbl("BLITTIM")
emit(0x2A,0x0C,0x40)                    # LD HL,(16396)
emit(0x11,25,0); emit(0x19); emit(0xEB)  # LD DE,25; ADD HL,DE; EX DE,HL  (DE=row0 col24)
emit(0x21,0x41,0x40)                    # LD HL,16449
emit(0x01,8,0)                          # LD BC,8
emit(0xED,0xB0); emit(0xC9)             # LDIR; RET
# RXSER: zxsvr (charlierobson) serial-server CLIENT, ZX81-initiated pull.
#   send 'I'            -> server returns the file length as 2 bytes (lo,hi)
#   per 256-byte block: send 'T', blockNum, blockLenByte (0=256)
#                       -> server returns blockLen data bytes + a 2-byte checksum
#   send 'X'            -> server done.
# Data bytes arrive back-to-back at 38400 with no per-byte handshake, so the caller runs
# this in FAST mode (full CPU keeps the 32-byte FIFO drained). Returns the length in BC.
lbl("RXSER")
emit(0x3E,0x49); emit(0xCD); ref("TXA")       # LD A,'I'; CALL TXA   (request info)
emit(0xCD); ref("RXBYTE"); emit(0x5F)         # CALL RXBYTE; LD E,A  (len lo)
emit(0xCD); ref("RXBYTE"); emit(0x57)         # CALL RXBYTE; LD D,A  (len hi) -> DE=length
emit(0xED,0x53); ref("RXLEN")                 # LD (RXLEN),DE
emit(0x2A); ref("RXPTR")                       # LD HL,(RXPTR)  (write ptr)
emit(0xAF); emit(0x32); ref("RXBN")           # XOR A; LD (RXBN),A  (blockNum=0)
lbl("BLKLOOP")
emit(0x7A); emit(0xB3); jr("Z","RXDONE")      # LD A,D; OR E -> remaining==0 -> done
emit(0x7A); emit(0xA7); jr("Z","PARTBL")      # LD A,D; AND A -> D==0 -> partial block
emit(0xAF); jr(None,"STBL")                   # full block: blockLenByte = 0 (=256)
lbl("PARTBL")
emit(0x7B)                                     # LD A,E  (partial len = low byte)
lbl("STBL")
emit(0x32); ref("RXBL")                        # LD (RXBL),A  (blockLenByte)
emit(0x3E,0x54); emit(0xCD); ref("TXA")       # LD A,'T'; CALL TXA
emit(0x3A); ref("RXBN"); emit(0xCD); ref("TXA")  # LD A,(RXBN); CALL TXA  (blockNum)
emit(0x3A); ref("RXBL"); emit(0xCD); ref("TXA")  # LD A,(RXBL); CALL TXA  (blockLenByte)
emit(0x3A); ref("RXBL"); emit(0x47)           # LD A,(RXBL); LD B,A  (B=count; 0 -> 256 via DJNZ)
lbl("RXIN")
emit(0xC5); emit(0xCD); ref("RXBYTE"); emit(0xC1)  # PUSH BC; CALL RXBYTE; POP BC
emit(0x77); emit(0x23)                         # LD (HL),A; INC HL
djnz("RXIN")
emit(0xCD); ref("RXBYTE"); emit(0xCD); ref("RXBYTE")   # consume 2-byte checksum
emit(0x3A); ref("RXBL"); emit(0xA7); jr("Z","SUB256")  # LD A,(RXBL); AND A -> 0 means 256
emit(0x4F)                                     # LD C,A
emit(0x7B); emit(0x91); emit(0x5F)            # LD A,E; SUB C; LD E,A  (remaining -= len)
jr("NC","NEXTBN"); emit(0x15)                  # JR NC; DEC D (borrow)
jr(None,"NEXTBN")
lbl("SUB256")
emit(0x15)                                     # DEC D  (remaining -= 256)
lbl("NEXTBN")
emit(0x3A); ref("RXBN"); emit(0x3C); emit(0x32); ref("RXBN")  # blockNum++
jr(None,"BLKLOOP")
lbl("RXDONE")
emit(0x3E,0x58); emit(0xCD); ref("TXA")       # LD A,'X'; CALL TXA  (terminate)
emit(0xED,0x4B); ref("RXLEN")                  # LD BC,(RXLEN)  (return length)
emit(0xC9)
lbl("RXBYTE")                           # wait for and return one received byte in A
emit(0x01,0xEB,0x00); emit(0xED,0x78); emit(0xCB,0x4F); jr("Z","RXBYTE")
emit(0x01,0xE3,0x00); emit(0xED,0x78); emit(0xC9)
lbl("TXA")                              # transmit the byte in A once TX is ready (status bit2)
emit(0xF5)                              # PUSH AF
lbl("TXAW")
emit(0x01,0xEB,0x00); emit(0xED,0x78); emit(0xCB,0x57); jr("Z","TXAW")
emit(0xF1)                              # POP AF
emit(0x01,0xE3,0x00); emit(0xED,0x79); emit(0xC9)   # LD BC,0x00E3; OUT(C),A; RET
# data
lbl("sptr"); emit(0,0)
lbl("TCELL"); emit(0)
lbl("SCELL"); emit(0)
lbl("NCELL"); emit(0)
lbl("RPT"); emit(0)
lbl("ACTDN"); emit(0)
lbl("IDLECNT"); emit(0)
lbl("RXPTR"); emit(0,0)
lbl("RXEHI"); emit(0)
lbl("RXBN"); emit(0)
lbl("RXBL"); emit(0)
lbl("RXLEN"); emit(0,0)
lbl("cfgbuf")
for _ in range(16): emit(0)
# panel render buffer (PR rows x PW cols), pre-filled with the static labels.
# BASIC pokes only the dynamic value bytes (offsets below), then PANELMC blits it.
def zc(ch):
    if ch==" ": return 0
    return {".":27,"=":20,">":18,"/":24,"-":22,",":26}.get(ch,
        28+ord(ch)-48 if "0"<=ch<="9" else 38+ord(ch)-65)
pbuf_init=[0]*(PR*PW)
def pput(pr,col,s):
    for i,ch in enumerate(s): pbuf_init[pr*PW+col+i]=zc(ch)
pput(0,0,"OS CONFIG")
pput(2,1,"UP");  pput(3,1,"DOWN"); pput(4,1,"LEFT"); pput(5,1,"RIGHT"); pput(6,1,"FIRE")
pput(8,1,"CFG"); pput(9,1,"RUN");  pput(11,0,"C=EDIT")
lbl("pbuf")
for b in pbuf_init: emit(b)
lbl("bufA")
for _ in range(24): emit(0)
lbl("slot")
for _ in range(SW*MAXE): emit(0)
out=[None]*len(prog); codelen=labels["sptr"]
def addr(n): return BASE+labels[n]
for i,(t,v) in enumerate(prog):
    if t=="b": out[i]=v
    elif t=="lo": out[i]=addr(v)&0xFF
    elif t=="hi": out[i]=(addr(v)>>8)&0xFF
    elif t=="jr":
        e=labels[v]-(i+1); assert -128<=e<=127,(v,e); out[i]=e&0xFF
assert not any(out[i]==0x76 for i in range(len(out))),"0x76 in REM"
A=addr("OPEN");G=addr("GET");DA=addr("DRAWALL");WK=addr("WAITKEY")
SPTR=addr("sptr");TC=addr("TCELL");SC=addr("SCELL");NC=addr("NCELL")
CFGB=addr("cfgbuf");BA=addr("bufA");SLOT=addr("slot")
PMC=addr("PANELMC");PCLR=addr("PANELCLR");PBUF=addr("pbuf");NAVA=addr("NAV")
RXS=addr("RXSER");RXP=addr("RXPTR");REH=addr("RXEHI")
BD=addr("BLITDAT");BT=addr("BLITTIM")
rem="".join("[%d]"%b for b in out)
# OSOS splash logo: solid block letters at ~2x resolution. Each letter is a 12x12-px
# bitmap; every 2x2 px is packed into one ZX81 quadrant-graphic char (codes 0-7 cover
# the bottom-right-clear combos, 128-135 the bottom-right-set ones via inverse video).
_OL=["  ########  "," ########## ","###      ###","##        ##","##        ##","##        ##","##        ##","##        ##","##        ##","###      ###"," ########## ","  ########  "]
_SL=[" ###########","############","###         ","###         ","####        "," ########## ","  ##########","         ###","         ###","        ####","############","########### "]
def _solid(b):  # fill each row's interior (solid letters)
    o=[]
    for r in b:
        i=r.find('#'); j=r.rfind('#'); o.append(r if i<0 else r[:i]+'#'*(j-i+1)+r[j+1:])
    return o
def _zx(tl,tr,bl,br):  # 2x2 pixel mask -> ZX81 char code
    return (tl+2*tr+4*bl) if not br else 128+((1-tl)+2*(1-tr)+4*(1-bl))
def _pack(b):  # pixel bitmap -> char-rows of ZX81 codes
    w=max(len(r) for r in b); b=[r.ljust(w) for r in b]
    if len(b)%2: b.append(" "*w)
    rows=[]
    for y in range(0,len(b),2):
        rows.append([_zx(int(b[y][x]!=" "),int(x+1<w and b[y][x+1]!=" "),
                         int(b[y+1][x]!=" "),int(x+1<w and b[y+1][x+1]!=" ")) for x in range(0,w,2)])
    return rows
_O=_pack(_solid(_OL)); _S=_pack(_solid(_SL))
logo=[]
for r in range(len(_O)):
    cells=_O[r]+[0]+_S[r]+[0]+_O[r]+[0]+_S[r]
    logo.append("".join(" " if c==0 else "[%d]"%c for c in cells))
_lc=(32-(len(_O[0])*4+3))//2     # centered start column
_tr=3+len(logo)+1                # title row (one blank line under the logo)
# --- BASIC emitter: statements carry no line numbers; mark a jump target with
# LBL("NAME") and reference it as @NAME. The two passes at the end assign line
# numbers (line 1 stays the REM so the MC stays at 16514) and resolve @NAME. ---
import re as _re
basic=[]
def B(s): basic.append(("L",s))
def LBL(n): basic.append(("@",n))
# Startup: splash FIRST (instant), then build helper strings / init the vars.
B("POKE 16,251")
B("CLS")
for idx,row in enumerate(logo):
    B('PRINT AT %d,%d;"%s"'%(3+idx,_lc,row))
B('PRINT AT %d,3;"OPENSPAND OPERATING SYSTEM"'%_tr)
B('PRINT AT %d,%d;"%s"'%(_tr+2,(32-len(VER))//2,VER))
for stmt in ['LET V=%d'%V,'LET B$=""','FOR I=1 TO 32','LET B$=B$+" "','NEXT I',
             'LET Y$=""','FOR I=1 TO 30','LET Y$=Y$+"-"','NEXT I',
             'LET Q$="/"','LET P=0','POKE %d,0'%SC,'POKE %d,0'%TC,'LET O=0','LET L=0','LET W=0',
             'LET PD=0']:
    B(stmt)
B("GOSUB @LISTDIR")
B("GOSUB @REDRAW")
B("GOTO @MAINLOOP")
# LISTDIR: read the current directory into the slot buffer (one GETSLOT per entry).
LBL("LISTDIR")
B('PRINT AT 1,0;"READING SD CARD...";')
B("POKE %d,0"%BA)
B("LET X=USR %d"%A)
B("IF P=0 THEN GOTO @LISTN")
B("POKE %d,27"%SLOT)
B("POKE %d,27"%(SLOT+1))
B("FOR I=2 TO %d"%(SW-1))
B("POKE %d+I,0"%SLOT)
B("NEXT I")
LBL("LISTN")
B("LET N=P>0")
B("LET SA=%d+%d*N"%(SLOT,SW))
B("POKE %d,SA-256*INT (SA/256)"%SPTR)
B("POKE %d,INT (SA/256)"%(SPTR+1))
LBL("GETLOOP")
B("LET M=USR %d"%G)
B("IF M=0 THEN GOTO @LISTDONE")
B("IF M<2 THEN GOTO @KEEP")
B("IF PEEK (SA+M-2)<>27 THEN GOTO @KEEP")
B("IF PEEK (SA+M-1)<>40 THEN GOTO @KEEP")
B("POKE %d,SA-256*INT (SA/256)"%SPTR)
B("POKE %d,INT (SA/256)"%(SPTR+1))
B("GOTO @GETLOOP")
LBL("KEEP")
B("LET N=N+1")
B("LET SA=SA+%d"%SW)
B("IF N>%d THEN GOTO @LISTDONE"%MAXE)
B("GOTO @GETLOOP")
LBL("LISTDONE")
B("RETURN")
# CHDIR: chdir to ('>'+N$) via OPEN (N$ holds the leading '>').
LBL("CHDIR")
B("POKE %d,18"%BA)
B("FOR I=1 TO LEN N$")
B("POKE %d+I,CODE N$(I)"%BA)
B("NEXT I")
B("POKE %d+LEN N$+1,0"%BA)
B("LET X=USR %d"%A)
B("RETURN")
# READSEL: read the selected slot S into N$ (len D).
LBL("READSEL")
B('LET N$=""')
B("LET D=0")
B("LET SA=%d+%d*PEEK (%d)"%(SLOT,SW,SC))
B("FOR I=0 TO %d"%(SW-1))
B("LET C=PEEK (SA+I)")
B("IF C=0 THEN GOTO @READSELDONE")
B("LET N$=N$+CHR$ C")
B("LET D=D+1")
B("NEXT I")
LBL("READSELDONE")
B("RETURN")
# DRAW: render the whole visible window via DRAWALL (cols 0..SW; panel cols PCOL+ untouched).
LBL("DRAW")
B("POKE %d,N"%NC)
B("LET X=USR %d"%DA)
B("RETURN")
# cfgbuf layout: [0]=magic 211, [1..5]=joystick key char codes (up,down,left,right,fire).
# Config is loaded ONLY when editing (C) or launching - never while browsing.
# CFGNAME: build the config file base name C$ from the selected game N$ (".P"->".C").
LBL("CFGNAME")
B('LET C$=N$( TO D-1)+"C"')
B("RETURN")
# CFGLOAD: load NAME.C into cfgbuf; CV=1 if it existed, else CV=0 + default keys 7/6/5/8/0.
LBL("CFGLOAD")
B("GOSUB @CFGNAME")
B('LET F$=C$+";"+STR$ %d'%CFGB)
B("POKE %d,0"%CFGB)
B("LOAD F$")
B("LET CV=1")
B("IF PEEK (%d)=212 THEN RETURN"%CFGB)
B("LET CV=0")
B("POKE %d,212"%CFGB)
B("POKE %d,35"%(CFGB+1))
B("POKE %d,34"%(CFGB+2))
B("POKE %d,33"%(CFGB+3))
B("POKE %d,36"%(CFGB+4))
B("POKE %d,28"%(CFGB+5))
B("RETURN")
# CFGSAVE: write the 6-byte cfgbuf (magic + 5 keys) to NAME.C (overwrite).
LBL("CFGSAVE")
B("POKE %d,212"%CFGB)
B("GOSUB @CFGNAME")
B('LET F$=">"+C$+";"+STR$ %d+",6"'%CFGB)
B("SAVE F$")
B("RETURN")
# CFGAPPLY: if a saved config exists, issue CONFIG "J=<5 keys>" (LLIST token) before LOAD.
LBL("CFGAPPLY")
B("IF CV=0 THEN RETURN")
B('LET G$="J="')
B("FOR I=1 TO 5")
B("LET G$=G$+CHR$ PEEK (%d+I)"%CFGB)
B("NEXT I")
B("LLIST G$")
B("RETURN")
# GETKEY: wait for key release, then a fresh press; return its code in KC.
LBL("GETKEY")
B('IF INKEY$<>"" THEN GOTO @GETKEY')
LBL("GETKEY2")
B("LET G$=INKEY$")
B('IF G$="" THEN GOTO @GETKEY2')
B("LET KC=CODE G$")
B("RETURN")
# CFGEDIT (C key): prompt the user to press a key for each joystick direction, then save.
LBL("CFGEDIT")
B("GOSUB @READSEL")
B("IF N=0 THEN GOTO @MAINLOOP")
B('IF N$=".." THEN GOTO @MAINLOOP')
B('IF N$(D)="/" THEN GOTO @MAINLOOP')
B("GOSUB @CFGLOAD")
B("FOR I=3 TO 14")
B("PRINT AT I,%d;B$( TO 15)"%PCOL)
B("NEXT I")
B('PRINT AT 3,%d;"SET KEYS"'%PCOL)
B('PRINT AT 5,%d;"UP"'%PCOL)
B('PRINT AT 6,%d;"DOWN"'%PCOL)
B('PRINT AT 7,%d;"LEFT"'%PCOL)
B('PRINT AT 8,%d;"RIGHT"'%PCOL)
B('PRINT AT 9,%d;"FIRE"'%PCOL)
B("LET F=1")
LBL("EDPR")
B('PRINT AT 11,%d;"PRESS KEY"'%PCOL)
B('IF F=1 THEN PRINT AT 12,%d;"FOR UP   "'%PCOL)
B('IF F=2 THEN PRINT AT 12,%d;"FOR DOWN "'%PCOL)
B('IF F=3 THEN PRINT AT 12,%d;"FOR LEFT "'%PCOL)
B('IF F=4 THEN PRINT AT 12,%d;"FOR RIGHT"'%PCOL)
B('IF F=5 THEN PRINT AT 12,%d;"FOR FIRE "'%PCOL)
B("GOSUB @GETKEY")
B("POKE %d+F,KC"%CFGB)
B("PRINT AT 4+F,%d;CHR$ KC"%(PCOL+6))
B("LET F=F+1")
B("IF F<=5 THEN GOTO @EDPR")
B("GOSUB @CFGSAVE")
B("GOSUB @REDRAW")
B("GOTO @MAINLOOP")
# MAINLOOP: poll input (WAITKEY), dispatch, idle = throttled clock refresh.
LBL("MAINLOOP")
B("LET K=USR %d"%NAVA)
B("IF K=0 THEN GOTO @MAINLOOP")
B("IF K=8 THEN GOTO @MAINLOOP")
B("IF K=9 THEN GOTO @HOUSE")
B("IF K=4 THEN GOTO @FIRE")
B("IF K=6 THEN GOTO @QUIT")
B("IF K=7 THEN GOTO @CFGEDIT")
B("IF K=10 THEN GOTO @SERLOAD")
B("GOTO @MAINLOOP")
LBL("HOUSE")
B("GOSUB @GETTIME")
B("GOTO @MAINLOOP")
LBL("FIRE")
B("GOSUB @ACTIVATE")
B("GOTO @MAINLOOP")
LBL("QUIT")
B("CLS")
B("STOP")
# SERLOAD (S key): receive a streamed .p over serial into a high-RAM buffer, save it
# to SER.P on the SD card, then LOAD it. Buffer sits just below RAMTOP (no .bas bloat).
LBL("SERLOAD")
B("CLS")
B('PRINT AT 4,2;"SERIAL LOAD"')
B("LET RM=PEEK 16388+256*PEEK 16389")
B("LET BA=RM+256")
B("LET EN=RM+15872")
B("POKE EN,170")
B("POKE BA,85")
B("IF PEEK EN<>170 THEN GOTO @SERNOR")
B("IF PEEK BA<>85 THEN GOTO @SERNOR")
B("POKE %d,BA-256*INT (BA/256)"%RXP)
B("POKE %d,INT (BA/256)"%(RXP+1))
B("POKE %d,INT (EN/256)"%REH)
B('PRINT AT 6,2;"START ZXSVR ON PC"')
B('PRINT AT 7,2;"(SCREEN BLANKS)"')
B('LPRINT "OPE SER %d"'%SERBAUD)
B("FAST")
B("LET RL=USR %d"%RXS)
B("SLOW")
B('LPRINT "CLO SER"')
B("IF RL=0 THEN GOTO @SERCAN")
B('PRINT AT 9,2;"GOT ";RL;" BYTES"')
B('LET F$=">INBOX.P;"+STR$ BA+","+STR$ RL')
B("SAVE F$")
B("GOTO @SERCAN")
LBL("SERNOR")
B('PRINT AT 6,2;"NO FREE RAM ABOVE RAMTOP"')
B("GOSUB @GETKEY")
LBL("SERCAN")
B("GOSUB @LISTDIR")
B("GOSUB @REDRAW")
B("GOTO @MAINLOOP")
# GOUP: go up one directory level (chdir '..', pop path).
LBL("GOUP")
B("IF P=0 THEN RETURN")
B('LET N$=".."')
B("GOSUB @CHDIR")
B("LET P=P-1")
B("LET Q$=Q$( TO LEN Q$-1)")
B("LET J=0")
B("FOR I=1 TO LEN Q$")
B('IF Q$(I)="/" THEN LET J=I')
B("NEXT I")
B("LET Q$=Q$( TO J)")
B("POKE %d,0"%SC)
B("POKE %d,0"%TC)
B("GOSUB @LISTDIR")
B("GOSUB @REDRAW")
B("RETURN")
# REDRAW: full screen (header + separators + footer + list).
LBL("REDRAW")
B("CLS")
B('PRINT AT 0,0;"OPENSPAND OS"')
B("GOSUB @GETDATE")
B('PRINT AT 1,0;"DIR:";Q$')
B("PRINT AT 2,0;Y$")
B("PRINT AT 20,0;Y$")
B('PRINT AT 21,0;"7UP 6DN 5,8PG 0RUN C=KEY Q=X";')
B("GOSUB @DRAW")
B('PRINT AT 3,%d;"CONFIG"'%PCOL)
B('PRINT AT 5,%d;"C=SET KEYS"'%PCOL)
B('PRINT AT 7,%d;"S=SERIAL IN"'%PCOL)
B("RETURN")
# ACTIVATE: fire on the selected entry - run file / enter dir / go up.
LBL("ACTIVATE")
B("IF N=0 THEN RETURN")
B("GOSUB @READSEL")
B("IF D=0 THEN RETURN")
B('IF N$=".." THEN GOTO @DOUP')
B('IF N$(D)="/" THEN GOTO @CHDIRIN')
B("GOSUB @CFGLOAD")
B("GOSUB @CFGAPPLY")
B('PRINT AT 21,0;"LOADING ";N$;B$( TO 8);')
B("LOAD N$")
B("RETURN")
LBL("CHDIRIN")
B("LET N$=N$( TO D-1)")
B('LET Q$=Q$+N$+"/"')
B("GOSUB @CHDIR")
B("LET P=P+1")
B("POKE %d,0"%SC)
B("POKE %d,0"%TC)
B("GOSUB @LISTDIR")
B("GOSUB @REDRAW")
B("RETURN")
LBL("DOUP")
B("GOSUB @GOUP")
B("RETURN")
# GETDATE/GETTIME: read the RTC into D$/M$ from the IO buffer at 16449.
LBL("GETDATE")
B('LPRINT "GET DAT"')
B("LET X=USR %d"%BD)
B("GOSUB @GETTIME")
B("RETURN")
LBL("GETTIME")
B('LPRINT "GET TIM"')
B("LET X=USR %d"%BT)
B("RETURN")
# --- resolve labels to line numbers (line 1 is the REM) and emit ---
lineno={}; _pending=[]; _n=2
for _k,_v in basic:
    if _k=="@": _pending.append(_v)
    else:
        for _p in _pending: lineno[_p]=_n
        _pending=[]; _n+=1
assert not _pending,"trailing label(s): %r"%_pending
def _resolve(t):
    def _r(m):
        assert m.group(1) in lineno,"undefined label @"+m.group(1)
        return str(lineno[m.group(1)])
    return _re.sub(r"@(\w+)",_r,t)
L=[]
L.append("#!basic-start=2")
L.append("# OPENSPAND OS LAUNCHER - generated by build_menu.py, do not hand-edit.")
L.append("# MC OPEN=%d GETSLOT=%d DRAWALL=%d sptr=%d T=%d S=%d N=%d slot=%d"%(A,G,DA,SPTR,TC,SC,NC,SLOT))
L.append("1 REM "+rem)
_n=2
for _k,_v in basic:
    if _k=="@": continue
    L.append("%d %s"%(_n,_resolve(_v))); _n+=1
import os,sys
here=os.path.dirname(os.path.abspath(__file__))
bas=os.path.join(here,"menu.bas")
open(bas,"w").write("\n".join(L)+"\n")
print("Wrote %s (%d lines). OPEN=%d GETSLOT=%d DRAWALL=%d slot=%d code=%d"%(bas,len(L),A,G,DA,SLOT,codelen))
if "--build" in sys.argv:
    import subprocess,tempfile,glob
    mg=sorted(glob.glob(os.path.expanduser("~/.vscode/extensions/maziac.zx81-bastop-*/out/extension.js")))
    el="/Applications/Visual Studio Code.app/Contents/MacOS/Electron"
    if not mg or not os.path.exists(el):
        print("--build: extension/Electron not found; use the VSCode task."); sys.exit(0)
    pp=os.path.join(tempfile.gettempdir(),"zx81_ext.js")
    open(pp,"w").write(open(mg[-1]).read()+"\n;try{module.exports.O=O;}catch(e){}\n")
    rn=os.path.join(tempfile.gettempdir(),"zx81_run.js")
    open(rn,"w").write("const M=require('module'),o=M._load;M._load=function(r){if(r==='vscode'){const n=()=>{};return{languages:{createDiagnosticCollection:()=>({clear:n,set:n,delete:n,dispose:n})},window:{showErrorMessage:n,showInformationMessage:n,createOutputChannel:()=>({appendLine:n,show:n})},commands:{registerCommand:n,executeCommand:n},tasks:{registerTaskProvider:n},workspace:{workspaceFolders:[],openTextDocument:n},Uri:{file:p=>({fsPath:p})},EventEmitter:class{fire(){}event(){}},Range:class{},Diagnostic:class{},DiagnosticSeverity:{Warning:1,Error:0}};}return o.apply(this,arguments);};\nconst fs=require('fs'),ext=require(process.argv[2]),O=ext.O,f=process.argv[3];\nconst n=new O(fs.readFileSync(f,'utf8'));let ws=[];if(n.on)n.on('warning',(m,l,c)=>ws.push('L'+l+':'+c+' '+m));\nlet b;try{b=Buffer.from(new Uint8Array(n.createPfile()));}catch(e){console.error('BUILD ERROR:',e.message,'line',e.line);process.exit(1);}\nfs.writeFileSync(f.replace(/\\.bas$/,'.p'),b);console.log('Wrote '+f.replace(/\\.bas$/,'.p')+' ('+b.length+' bytes), warnings: '+ws.length);ws.forEach(x=>console.log('  '+x));\n")
    subprocess.run([el,rn,pp,bas], env=dict(os.environ,ELECTRON_RUN_AS_NODE="1"), check=False)
