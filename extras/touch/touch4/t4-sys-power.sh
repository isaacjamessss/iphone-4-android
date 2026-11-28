#!/bin/sh
# The T4 kernel has no CONFIG_PM / Android wakelocks -> no /sys/power. Then
# libhardware_legacy set_screen_state() fails, PowerManager never sets
# SCREEN_ON_BIT and InputDispatcher DROPS EVERY TOUCH. Fix: tmpfs over /sys,
# real sysfs dirs bind-mounted back, plus writable dummy power files.
bb=/sbin/busybox
[ -e /sys/power/state ] && exit 0
"$bb" mkdir -p /dev/sysreal
"$bb" mount -t sysfs sysfs /dev/sysreal || { echo '<3>T4_SYSPOWER: sysfs remount failed'; exit 1; }
"$bb" mount -t tmpfs -o mode=755 tmpfs /sys || exit 1
for d in $("$bb" ls /dev/sysreal); do
    "$bb" mkdir /sys/$d && "$bb" mount -o bind /dev/sysreal/$d /sys/$d
done
"$bb" mkdir /sys/power
for f in state wake_lock wake_unlock; do : > /sys/power/$f; done
"$bb" chmod 0666 /sys/power/state /sys/power/wake_lock /sys/power/wake_unlock
echo '<5>T4_SYSPOWER: dummy /sys/power installed (screen-on for PowerManager)'
