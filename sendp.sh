#!/bin/sh
# Send a .p to OSOS: sync (AA 55) + 2-byte LE size + data. Usage: ./sendp.sh Chess.p
DEV=/dev/cu.usbserial-A9M9DV3R
[ -z "$1" ] && { echo "usage: $0 file.p"; exit 1; }
stty -f "$DEV" 9600 cs8 -cstopb -parenb -ixon raw
python3 -c "import sys;d=open(sys.argv[1],'rb').read();sys.stdout.buffer.write(bytes([0xAA,0x55,len(d)&255,len(d)>>8])+d)" "$1" > "$DEV"
echo "sent $(stat -f%z "$1") bytes ($1)"
