#!/bin/sh
# /dev and /data are RAM filesystems in this build. No block-device operation.
# n92ap (iPhone 4): touch controller is powered by PMU LDO12 (reg 0x16 bit 1),
# the iPod touch 4 used LDO10 - switch it on before the controller is reset.
bb=/sbin/busybox
/sbin/pmutool set 0x16 0x02 > /dev/kmsg 2>&1
"$bb" usleep 20000
if [ ! -e /sys/class/misc/uinput/dev ]; then
    echo '<3>T4_INPUT: kernel uinput missing' > /dev/kmsg
    exit 1
fi
node=$("$bb" cat /sys/class/misc/uinput/dev)
[ "$node" = '10:223' ] || exit 1
if [ ! -e /dev/uinput ]; then
    "$bb" mknod /dev/uinput c 10 223 || exit 1
fi
exec /sbin/t4-touch-input
