@ lowres-fb.S - t4fb 320x480 RGB565 + page flipping + 2x scale-copy.
@ Assembled by build-bootkit.py (LOWRES=1) at 0xC00334C4, i.e. INSIDE the
@ kernel image, over the debug-overlay functions (0xC00334C4..0xC003374C,
@ only caller 0xC0032F08 is NOPed). Runtime code must live in the kernel
@ image: the kcaves blob at 14 MB is not reserved and gets reused by Linux.
@
@ Kernel side (T4 3.0.8 vmlinux, see patch list in build-bootkit.py):
@   fb_info: var @+0x24 (xres +0x24 yres +0x28 xres_v +0x2c yres_v +0x30
@            bpp +0x3c), fix @+0xC4 (ypanstep halfword +0xEA)
@   t4fb state: +0 open count, +4 first-frame seen, +8 fb_info,
@               +0xC shadow VA (Android draws here), +0x10 real fb VA
@   real fb: 640x960 xRGB8888, stride 2560
.syntax unified
.arm
.text

@ Kernel return points are UNDEFINED here and supplied by ld.lld --defsym
@ (a .equ absolute target gets encoded as if this code sat at address 0):
@   PROBE_RET = 0xC000DBD8  after the var setup we replaced
@   COPY_RET  = 0xC0032F04  worker: (nop'd overlay), cache flush, unlock
@   COPY_SKIP = 0xC0032F50  worker: unlock + reschedule

.global cave_probe, cave_pan, cave_copy, fbdata

@ ---- probe: replaces 0xC000DBB8..0xC000DBD4 (r4 = fb_info) ----
cave_probe:
    mov   r3, #320
    str   r3, [r4, #0x2c]       @ xres_virtual
    str   r3, [r4, #0x24]       @ xres
    mov   r3, #480
    str   r3, [r4, #0x28]       @ yres
    mov   r3, #960
    str   r3, [r4, #0x30]       @ yres_virtual = 2 pages (gralloc page flip)
    mov   r3, #16
    str   r3, [r4, #0x3c]       @ bits_per_pixel (RGB565)
    mov   r3, #1
    strh  r3, [r4, #0xea]       @ fix.ypanstep (fb_pan_display needs != 0)
    b     PROBE_RET

@ ---- fb_pan_display(var r0, info r1): replaces 0xC0032DBC ----
cave_pan:
    ldr   r3, [r0, #0x10]       @ xoffset
    cmp   r3, #0
    bne   1f
    ldr   r3, [r0, #0x14]       @ yoffset (0 or 480)
    cmp   r3, #480
    bhi   1f
    ldr   r2, =fbdata
    str   r3, [r2, #4]          @ page to show
    mov   r3, #1
    str   r3, [r2]              @ dirty
    mov   r0, #0
    bx    lr
1:  mvn   r0, #21               @ -EINVAL
    bx    lr

@ ---- worker copy: replaces 0xC0032EB8 (r4 = t4fb state; only r4,lr saved) ----
cave_copy:
    ldr   r12, =fbdata
    ldr   r0, [r12]             @ dirty?
    ldr   r1, [r12, #8]
    add   r1, r1, #1            @ ticks since last copy
    cmp   r1, #50
    movhs r0, #1                @ safety refresh every 50 ticks (0.5 s)
    cmp   r0, #0
    streq r1, [r12, #8]
    beq   COPY_SKIP
    mov   r1, #0
    str   r1, [r12, #8]
    str   r1, [r12]             @ clear dirty before copying (pan may re-set)
    ldr   r5, [r12, #4]         @ yoffset (lines)
    push  {r4-r11}
    ldr   r6, [r4, #0xc]        @ src = shadow + yoffset * 640
    add   r6, r6, r5, lsl #9
    add   r6, r6, r5, lsl #7
    ldr   r7, [r4, #0x10]       @ dst row 2y
    mov   r8, #480
2:  add   r12, r7, #2560        @ dst row 2y+1
    mov   r9, #160              @ 2 source pixels per iteration
3:  ldr   r10, [r6], #4
    and   r0, r10, #0xF800      @ left pixel  565 -> xRGB8888
    and   r1, r10, #0x7E0
    lsl   r0, r0, #8
    orr   r0, r0, r1, lsl #5
    and   r1, r10, #0x1F
    orr   r0, r0, r1, lsl #3
    lsr   r11, r10, #16         @ right pixel
    and   r2, r11, #0xF800
    and   r1, r11, #0x7E0
    lsl   r2, r2, #8
    orr   r2, r2, r1, lsl #5
    and   r1, r11, #0x1F
    orr   r2, r2, r1, lsl #3
    mov   r1, r0
    mov   r3, r2
    stm   r7!, {r0-r3}          @ 4 dst pixels, row 2y
    stm   r12!, {r0-r3}         @ same, row 2y+1
    subs  r9, r9, #1
    bne   3b
    add   r7, r7, #2560         @ skip row 2y+1 (already written)
    subs  r8, r8, #1
    bne   2b
    pop   {r4-r11}
    b     COPY_RET

.ltorg
.align 2
fbdata:
    .word 1                     @ dirty (1 = show first frame)
    .word 0                     @ yoffset
    .word 0                     @ ticks since last copy
cave_end:
