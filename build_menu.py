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
SW=28; MAXE=100; V=17; BASE=16514
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
# DRAWROW: compute DEST from RCELL, SRC from KCELL (MC multiplies, no BASIC divide)
lbl("DRAWROW")
emit(0x2A,0x0C,0x40); emit(0x23)        # LD HL,(16396); INC HL
emit(0x3A); ref("RCELL")                # LD A,(RCELL)
emit(0x11,33,0)                         # LD DE,33
emit(0xA7); jr("Z","DRA1")
emit(0x47)                              # LD B,A
lbl("DRM1")
emit(0x19); djnz("DRM1")                # ADD HL,DE ; DJNZ  -> HL=DEST
lbl("DRA1")
emit(0x3A); ref("MARK")                 # LD A,(MARK)
emit(0x77); emit(0x23)                  # (HL)=A ; INC HL
emit(0xE5)                              # PUSH HL  (name dest)
emit(0x21); ref("slot")                 # LD HL,slot
emit(0x11,SW,0)                         # LD DE,SW
emit(0x3A); ref("KCELL")                # LD A,(KCELL)
emit(0xA7); jr("Z","DRA2")
emit(0x47)                              # LD B,A
lbl("DRM2")
emit(0x19); djnz("DRM2")                # HL=slot+K*SW = SRC
lbl("DRA2")
emit(0xEB)                              # EX DE,HL  (DE=SRC)
emit(0xE1)                              # POP HL    (name dest)
emit(0x06,SW)                           # LD B,SW
lbl("DRC")
emit(0x1A); emit(0x77); emit(0x13); emit(0x23); djnz("DRC")
emit(0xC9)
# POLLJOY: read raw joystick port (0xE007 subfn 0xA0), decode active-low, return
# direction code in C (0=none,1=up,2=down,3=left,4=fire,5=right). Integer bit-test
# in MC = instant; keeps the slow ZX81 float decode out of the BASIC loop.
lbl("POLLJOY")
emit(0x01,0x07,0xE0); emit(0x3E,0xA0); emit(0xED,0x79)   # LD BC,0xE007; LD A,0xA0; OUT(C),A
emit(0x01,0x07,0x00); emit(0xED,0x78)                    # LD BC,0x0007; IN A,(C)
emit(0xCB,0x7F); jr("Z","PJU")                           # BIT 7,A; JR Z (up)
emit(0xCB,0x77); jr("Z","PJD")                           # BIT 6,A
emit(0xCB,0x6F); jr("Z","PJLF")                          # BIT 5,A
emit(0xCB,0x67); jr("Z","PJRT")                          # BIT 4,A
emit(0xCB,0x5F); jr("Z","PJFR")                          # BIT 3,A
emit(0x0E,0x00); emit(0x06,0x00); emit(0xC9)             # none
lbl("PJU"); emit(0x0E,0x01); emit(0x06,0x00); emit(0xC9)
lbl("PJD"); emit(0x0E,0x02); emit(0x06,0x00); emit(0xC9)
lbl("PJLF"); emit(0x0E,0x03); emit(0x06,0x00); emit(0xC9)
lbl("PJRT"); emit(0x0E,0x05); emit(0x06,0x00); emit(0xC9)
lbl("PJFR"); emit(0x0E,0x04); emit(0x06,0x00); emit(0xC9)
# data
lbl("sptr"); emit(0,0)
lbl("RCELL"); emit(0)
lbl("KCELL"); emit(0)
lbl("MARK"); emit(0)
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
assert not any(out[i]==0x76 for i in range(codelen)),"0x76 in code"
A=addr("OPEN");G=addr("GET");DRW=addr("DRAWROW");PJ=addr("POLLJOY")
SPTR=addr("sptr");RCELL=addr("RCELL");KCELL=addr("KCELL");MARK=addr("MARK")
BA=addr("bufA");SLOT=addr("slot")
rem="".join("[%d]"%b for b in out)
GO=["XXX","X X","X X","X X","XXX"];GS=["XXX","X  ","XXX","  X","XXX"]
logo=[GO[r]+" "+GS[r]+" "+GO[r]+" "+GS[r] for r in range(5)]
def blocks(s): return "".join("[128]" if c=="X" else " " for c in s)
L=[]
def add(s): L.append(s)
add("#!basic-start=10")
add("# OPENSPAND OS LAUNCHER - generated by build_menu.py, do not hand-edit.")
add("# MC OPEN=%d GETSLOT=%d DRAWROW=%d sptr=%d R=%d K=%d MARK=%d slot=%d"%(A,G,DRW,SPTR,RCELL,KCELL,MARK,SLOT))
add("1 REM "+rem)
add("10 POKE 16,251")
add("11 LET V=%d"%V)
add('13 LET B$=""')
add("14 FOR I=1 TO 32")
add('15 LET B$=B$+" "')
add("16 NEXT I")
add('17 LET Y$=""')
add("18 FOR I=1 TO 30")
add('19 LET Y$=Y$+"-"')
add("20 NEXT I")
add('21 LET Q$="/"')
add("22 LET P=0")
add("23 LET S=0")
add("24 LET T=0")
add("25 LET O=0")
add("26 LET L=0")
add("27 LET W=0")
add("30 CLS")
ln=31
for idx,row in enumerate(logo):
    add('%d PRINT AT %d,8;"%s"'%(ln,3+idx,blocks(row))); ln+=1
add('%d PRINT AT 9,3;"OPENSPAND OPERATING SYSTEM"'%ln); ln+=1
add("%d GOSUB 200"%ln); ln+=1
add("%d GOSUB 700"%ln); ln+=1
add("%d GOTO 300"%ln); ln+=1
assert ln<=199
add("200 POKE %d,0"%BA)
add("201 LET X=USR %d"%A)
add("202 IF P=0 THEN GOTO 209")
add("203 POKE %d,27"%SLOT)
add("204 POKE %d,27"%(SLOT+1))
add("205 FOR I=2 TO %d"%(SW-1))
add("206 POKE %d+I,0"%SLOT)
add("207 NEXT I")
add("209 LET N=P>0")
add("210 LET SA=%d+%d*N"%(SLOT,SW))
add("211 POKE %d,SA-256*INT (SA/256)"%SPTR)
add("212 POKE %d,INT (SA/256)"%(SPTR+1))
add("213 LET M=USR %d"%G)
add("214 IF M=0 THEN GOTO 220")
add("215 LET N=N+1")
add("216 IF N>%d THEN GOTO 220"%MAXE)
add("217 GOTO 213")
add("220 RETURN")
add("250 POKE %d,18"%BA)
add("251 FOR I=1 TO LEN N$")
add("252 POKE %d+I,CODE N$(I)"%BA)
add("253 NEXT I")
add("254 POKE %d+LEN N$+1,0"%BA)
add("255 LET X=USR %d"%A)
add("256 RETURN")
add('270 LET N$=""')
add("271 LET D=0")
add("272 LET SA=%d+%d*S"%(SLOT,SW))
add("273 FOR I=0 TO %d"%(SW-1))
add("274 LET C=PEEK (SA+I)")
add("275 IF C=0 THEN GOTO 279")
add("276 LET N$=N$+CHR$ C")
add("277 LET D=D+1")
add("278 NEXT I")
add("279 RETURN")
add("280 LET R=3+K-T")
add("281 IF R<3 THEN RETURN")
add("282 IF R>19 THEN RETURN")
add("283 IF K>=N THEN GOTO 293")
add("284 POKE %d,R"%RCELL)
add("285 POKE %d,K"%KCELL)
add("286 POKE %d,(K=S)*18"%MARK)
add("287 LET X=USR %d"%DRW)
add("288 RETURN")
add("293 PRINT AT R,0;B$( TO 29)")
add("294 RETURN")
add("295 FOR K=T TO T+V-1")
add("296 GOSUB 280")
add("297 NEXT K")
add("298 RETURN")
add("300 LET K=USR %d"%PJ)
add("301 IF K>0 THEN GOTO 330")
add("302 LET K$=INKEY$")
add('303 IF K$="" THEN GOTO 310')
add('304 IF K$="7" THEN LET K=1')
add('305 IF K$="6" THEN LET K=2')
add('306 IF K$="5" THEN LET K=3')
add('307 IF K$="0" THEN LET K=4')
add('308 IF K$="8" THEN LET K=5')
add("309 IF K>0 THEN GOTO 330")
add("310 LET O=0")
add("311 LET L=0")
add("312 LET W=W+1")
add("313 IF W<150 THEN GOTO 300")
add("314 LET W=0")
add("315 GOSUB 9100")
add("316 PRINT AT 0,24;M$")
add("317 GOTO 300")
add("330 IF K=1 THEN GOTO 340")
add("331 IF K=2 THEN GOTO 350")
add("332 IF K=3 THEN GOTO 360")
add("333 IF K=4 THEN GOTO 370")
add("334 GOTO 370")
add("340 IF S<=0 THEN GOTO 300")
add("341 LET X=S")
add("342 LET S=S-1")
add("343 GOSUB 600")
add("344 GOSUB 800")
add("345 GOTO 300")
add("350 IF S>=N-1 THEN GOTO 300")
add("351 LET X=S")
add("352 LET S=S+1")
add("353 GOSUB 600")
add("354 GOSUB 800")
add("355 GOTO 300")
add("360 IF L=1 THEN GOTO 300")
add("361 LET L=1")
add("362 GOSUB 500")
add("363 GOTO 300")
add("370 IF O=1 THEN GOTO 300")
add("371 LET O=1")
add("372 GOSUB 900")
add("373 GOTO 300")
add("500 IF P=0 THEN RETURN")
add('501 LET N$=".."')
add("502 GOSUB 250")
add("503 LET P=P-1")
add("504 LET Q$=Q$( TO LEN Q$-1)")
add("505 LET J=0")
add("506 FOR I=1 TO LEN Q$")
add('507 IF Q$(I)="/" THEN LET J=I')
add("508 NEXT I")
add("509 LET Q$=Q$( TO J)")
add("510 LET S=0")
add("511 LET T=0")
add("512 GOSUB 200")
add("513 GOSUB 700")
add("514 RETURN")
add("600 IF S<T THEN GOTO 620")
add("601 IF S>T+V-1 THEN GOTO 620")
add("602 LET K=X")
add("603 GOSUB 280")
add("604 LET K=S")
add("605 GOSUB 280")
add("606 RETURN")
add("620 IF S<T THEN LET T=S")
add("621 IF S>T+V-1 THEN LET T=S-V+1")
add("622 GOSUB 295")
add("623 RETURN")
add("700 CLS")
add('701 PRINT AT 0,0;"OPENSPAND OS"')
add("702 GOSUB 9000")
add("703 PRINT AT 0,13;D$")
add("704 PRINT AT 0,24;M$")
add('705 PRINT AT 1,0;"DIR:";Q$')
add("706 PRINT AT 2,0;Y$")
add("707 PRINT AT 20,0;Y$")
add('708 PRINT AT 21,0;"7UP 6DN 0RUN 5BACK";')
add("709 GOSUB 295")
add("710 RETURN")
add("800 FOR I=1 TO 3")
add("801 NEXT I")
add("802 RETURN")
add("900 IF N=0 THEN RETURN")
add("901 GOSUB 270")
add("902 IF D=0 THEN RETURN")
add('903 IF N$=".." THEN GOTO 930')
add('904 IF N$(D)="/" THEN GOTO 920')
add('905 PRINT AT 21,0;"LOADING ";N$;B$( TO 8);')
add("906 LOAD N$")
add("907 RETURN")
add("920 LET N$=N$( TO D-1)")
add('921 LET Q$=Q$+N$+"/"')
add("922 GOSUB 250")
add("923 LET P=P+1")
add("924 LET S=0")
add("925 LET T=0")
add("926 GOSUB 200")
add("927 GOSUB 700")
add("928 RETURN")
add("930 GOSUB 500")
add("931 RETURN")
add('9000 LPRINT "GET DAT"')
add('9001 LET D$=""')
add("9002 FOR I=0 TO 9")
add("9003 LET D$=D$+CHR$ PEEK (16449+I)")
add("9004 NEXT I")
add("9005 GOSUB 9100")
add("9006 RETURN")
add('9100 LPRINT "GET TIM"')
add('9101 LET M$=""')
add("9102 FOR I=0 TO 7")
add("9103 LET M$=M$+CHR$ PEEK (16449+I)")
add("9104 NEXT I")
add("9105 RETURN")
import os,sys
here=os.path.dirname(os.path.abspath(__file__))
bas=os.path.join(here,"menu.bas")
open(bas,"w").write("\n".join(L)+"\n")
print("Wrote %s (%d lines). OPEN=%d GETSLOT=%d DRAWROW=%d slot=%d code=%d"%(bas,len(L),A,G,DRW,SLOT,codelen))
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
