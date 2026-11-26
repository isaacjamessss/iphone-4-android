#!/usr/bin/env bash
# QEMU run (virt, 256M, cortex-a7; trace exceptions; HMP on :5555).
cd "/home/sakura/Documents/Default Project/iphone33-android/bootkit/qemu"
qemu-system-arm -M virt -cpu cortex-a7 -m 256M -nographic -serial none \
  -device loader,file=zImage,addr=0x41000000 \
  -device loader,file=kcaves.bin,addr=0x41800000 \
  -device loader,file=stub.bin,addr=0x42000000 \
  -device loader,addr=0x42000000,cpu-num=0 \
  -d int,guest_errors -D qemu-trace.log \
  -monitor telnet:127.0.0.1:5555,server,nowait
