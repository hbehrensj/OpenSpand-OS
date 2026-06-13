#!/bin/sh
# zxsvr-compatible serial server (charlierobson protocol), persistent edition.
# The ZX81 (OSOS, press S) is the client and pulls the file:
#   'I'            -> we reply 2 bytes: file length (lo,hi)
#   'T',num,len    -> we reply len bytes from offset num*256 (len 0 = 256) + 2-byte checksum
#   'X'            -> transfer done (we keep serving for the next S press)
# Usage: ./zxserver.sh Chess.p     (Ctrl-C to stop)
DEV=/dev/cu.usbserial-A9M9DV3R
BAUD=38400
[ -z "$1" ] && { echo "usage: $0 file.p"; exit 1; }
python3 - "$1" "$DEV" "$BAUD" <<'PY'
import sys,os,termios,select
data=open(sys.argv[1],'rb').read(); dev=sys.argv[2]; baud=int(sys.argv[3])
fd=os.open(dev, os.O_RDWR|os.O_NOCTTY)
a=termios.tcgetattr(fd); spd=getattr(termios,'B%d'%baud)
a[4]=spd; a[5]=spd
a[2]=(a[2] & ~(termios.CSIZE|termios.PARENB|termios.CSTOPB)) | termios.CS8 | termios.CLOCAL | termios.CREAD
a[0]=0; a[1]=0; a[3]=0; a[6][termios.VMIN]=0; a[6][termios.VTIME]=0
termios.tcsetattr(fd, termios.TCSANOW, a)
def rb(t=None):
    while True:
        r,_,_=select.select([fd],[],[],t)
        if not r: return None
        d=os.read(fd,1)
        if d: return d[0]
print("zxsvr: %s (%d bytes) ready - press S on the ZX81 (Ctrl-C to stop)"%(sys.argv[1],len(data)))
n=len(data)
while True:
    c=rb()
    if c==ord('I'):
        os.write(fd, bytes([n&0xff,(n>>8)&0xff]))
    elif c==ord('T'):
        num=rb(2.0); ln=rb(2.0)
        if num is None or ln is None: print("  T: timeout"); continue
        if ln==0: ln=256
        off=num*256; blk=data[off:off+ln]
        s=sum(blk)&0xffff
        os.write(fd, blk); os.write(fd, bytes([s&0xff,(s>>8)&0xff]))
    elif c==ord('X'):
        print("  sent %d bytes - OK (waiting for next S)"%n)
    elif c is not None:
        print("  ? 0x%02X"%c)
PY
