#!/usr/bin/env bash
# Trigger the limera1n bootrom exploit on a device sitting in DFU.
# The exploit payload is built into libirecovery; the shell command takes no file.
printf '/limera1n\n/exit\n' | irecovery -s
