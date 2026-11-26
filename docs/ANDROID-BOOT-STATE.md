# Android bring-up state — iPhone 4 CDMA (n92ap) — 2026-11-24 late session

Continuation of docs/BRINGUP-2026-11-24.md. **Goal: boot the touch4-idroid
Android (Linux 3.0.8 + Android 2.3.7) on n92ap ("see Android on screen").**

## STATUS: kernel entry code EXECUTES (checkpoints proven). Bisecting inside
the zImage entry. Last observation: **yellow checkpoint reached, then stuck.**

## The proven boot chain (all RAM-only, power cycle returns to iOS)

    ./a4boot artifacts/limera1n.payload artifacts/iBSS.n92ap-pwn.img3 reset
    python3 tools/dfu-upload.py artifacts/openiboot-archeyr.img3
    bash /tmp/android-boot/boot-android.sh      # see below

boot-android.sh (built by tools/oibsend.py + tools/build-t4stub.py):
    oibsend.py boot zImage 0x44000000 initramfs 0x09000000 stub.bin 0x04200000 --go "go 0x04200000"

## Critical hardware/kernel facts (hard-won, do not re-derive)

- openiboot (archeYR build b0e6178b) via our manifest-boot chain works.
  Its ACM console = OiBC protocol; tools/oibsend.py is our robust uploader
  (single session; bus-reset+retry; OiBC segfaults on EINTR — don't use it).
- RAM windows ALIAS: 0x0XXXXXXX == 0x4XXXXXXX == 0x8XXXXXXX (same DRAM
  offset). openiboot's mmu_dump: identity + 0xc0000000->0x40000000.
- **Framebuffer = physical 0x0F700000** (DisplayPipe UI0 base register
  0x89004044 via clcd_dump). Painting there is VISIBLE (proven).
- openiboot `go ADDR` = chainload: IRQs off, caches off, MMU off, BX ADDR.
  Runs stub in SVC mode. Runs fine (all our stub colors proved it).
- zImage (t4-kernel.bin = touch4-idroid bundle record "kernel"):
  - word[0] @0x00: ldr pc,[pc,#-4]; word[1]=0x44000000 (chain/entry table,
    words at 0x04/0x0C/0x14/0x1C get relocated by the kernel's own fixup
    loop at 0x120-0x130 — we PATCH them to 0x44000020 in our builds).
  - **real code entry = +0x20 (`b 0x30`)** — proven (white checkpoint).
  - +0x30: mov r7,r1 (mach); +0x34: mov r8,r2 (atags); svc-mode check
    (skips svc 0x123456 when entered in SVC — fine); disable IRQ/FIQ.
  - +0x60: ldr r4,[pc,#0x764] -> r4=0x8000 (zreladdr/decompress target).
  - +0x64: bl +0x1a0 (mov r3,#8; b 0x3ac = __lookup_processor_type /
    cache-on). **We NOP this call** — its cache-on routine (entry17's
    branch target ~0x2DC) hangs on our boot; kernel runs fine uncached.
    (The proc table DOES match Cortex-A8: entry17 id=0x000F0000
    mask=0x000F0000 at 0x524. The hang is inside the cache-on routine.)
  - +0x68..0xFC: params table at +0x17C {0x17c, 0x1493c0, 0x1493d8,
    0x1493bc, 0x149386, 0x14938c, 0x1493b0, 0x14a3d8} — offsets from
    0x44000000; delta = 0 for us. BSS=0x441493C0..D8, stack=0x4414A3D8.
  - +0x108: BSS zero loop; **+0x150 = YELLOW checkpoint** (reached!).
  - +0x154-0x15C: r0=r4(0x8000), r1=sp, r2=sp+0x10000, r3=r7(mach).
  - +0x160: `b #0x44000010` — the word-chain re-entry (design intent:
    relocatable re-entry; with our patched words it leads to 0x20).
  - +0x168: `bl #0x44000560` (decompressor!) and +0x178 `mov pc, r4`
    (jump to decompressed kernel at 0x8000) — we have NOT reached these.
- Decompressed vmlinux linked at VA 0xC0008000 (PA 0x8000); first word
  0xE321F0D3 (msr cpsr_c,#0xd3) = real kernel start code.

## Instrumented zImage builder (in this conversation's last commands; the
patcher is inline python — re-run to rebuild /tmp/android-boot/zImage):
- words 0x04/0x0C/0x14/0x1C := 0x44000020 (trampoline fix)
- 0x64 := NOP (skip cache-on)
- 0x30 := b cave1 (paint WHITE 0xFFFFFFFF at 0x0F700000..0x0FA00000, return 0x34)
- 0x150 := b cave2 (paint YELLOW 0x00FFFF00, do mov r0,r4, return 0x154)
- caves appended at file end (0x441493BC, 0x441493E4)

## LAST OBSERVATION
White appeared (entry ran) and YELLOW appeared (0x150 reached) — then the
screen STUCK ON YELLOW (not flashing). So the flow after 0x150 (mov r1,sp;
add r2,sp,#0x10000; mov r3,r7; b #0x44000010) hung silently. Suspects:
(a) the b 0x10 word-chain did not land on 0x20 as patched — VERIFY the
    bytes at 0x04/0x0C/0x14/0x1C in /tmp/android-boot/zImage;
(b) the chain reached 0x20->0x30 but cave1's return... (would re-paint
    white — stuck yellow argues against);
(c) the hang is at the 0x160 branch target in a way not yet understood.

NEXT STEPS:
1. Verify zImage word patches landed (python struct check).
2. Add a BLUE checkpoint at 0x44000168 (before bl 0x560) and REDIRECT
   0x160's `b 0x10` to skip the chain (e.g. patch 0x160 to `nop` so the
   flow FALLS THROUGH to 0x164/0x168 = the decompressor call!!!) — this is
   the likely intended flow for the non-relocated case anyway.
3. If decompressor completes: instrument before `mov pc, r4` (0x178).
4. Then the decompressed kernel at PA 0x8000 (entry 0xE321F0D3).

## Auxiliary facts
- /tmp/android-boot/ holds boot kit (zImage, initramfs, stub.bin,
  boot-android.sh) — REBUILDABLE from ~/Downloads (t4-*.bin) + tools/.
- tools/build-t4stub.py = stub builder (paints magenta=running,
  red=kernel-missing, green=kernel-verified, then ATAGs@0x100 (MEM 256M,
  INITRD2 0x09000000+0x02c5ad75, RAMDISK kb 0x14481), machine 3564,
  jump 0x44000020). Stub lives at 0x04200000 (kernel 0x44000000 =
  DRAM 0x04000000, no overlap).
- ACP/upload quirks: openiboot wedges across sessions — always one
  oibsend.py session + bus reset; writes to v>0x46000000 abort openiboot.
- Everything RAM-only. Phone: power+home 15s -> DFU dance -> run chain.

## Update: register protocol solved (this session)
- BLUE checkpoint (0x178 mov pc,r4) proved the decompressor runs and hands
  off to the vmlinux at PA 0x8000. "Stuck blue" = kernel entry got garbage
  r1/r2 (decompressor scratch) instead of the boot protocol.
- The entry code saves incoming r1->r7 (machine id) and r2->r8 (atags).
  The kernel needs the classic protocol at entry: r0=0, r1=mach, r2=atags.
- Final jump cave now does: mov r0,#0; mov r1,r7; mov r2,r8; mov pc,r4.
- Chain words 0x04/0x0C/0x14/0x1C patched to 0x44000020 (harmless now);
  0x160/0x164/0x170/0x174 NOPped (chain stubs bypassed; straight line to
  decompressor at 0x168 and handoff at 0x178).
- Color legend: magenta=stub, green=kernel-verified, white=entry(0x30),
  yellow=setup(0x150), blue=kernel handoff(0x178).
- If the kernel still dies silently after this fix, next suspect is the
  ATAGs themselves (compare vs the touch4 boot: MEM 256M/INITRD 0x09000000
  are inside our stub's blob) or the vmlinux's own proc lookup.

## Update 2: vmlinux entry runs; lookup dies
- GREEN appeared after blue = the vmlinux entry (0xC0008000 / PA 0x8000)
  executes. Chain + registers solved completely.
- Next checkpoint (BLACK at 0x800C, after the proc lookup) did NOT appear:
  the lookup (bl 0xC001AF90) never returns. Its not-found path is
  0xC001AFD4 (classic "unrecognized processor" hang).
- vmlinux proc_info: ONE entry, id=0x410FC090 mask=0xFF0FFFF0 (Cortex-A9
  part 0xC09!) at FILE OFFSET 0x139B4 (VA 0xC00139B4). The touch4 boots
  this kernel, so the A4 MIDR matches 0x410FC09x there.
- NOTE: VA<->FILE mapping for the vmlinux: file = VA - 0xC0008000.
- NEXT: instrument the error path (file 0x12FD4 = VA 0xC001AFD4) with a
  RED paint to distinguish "not found" (red) vs "hang in walk" (silence).

## Update 3: COLOR CONFOUND found — "green only" runs never reached vmlinux
- CORRECTION to Update 2: file 0x139B4 = VA **0xC001B9B4** (not 0xC00139B4).
- Panel color truth (from build-t4stub.py): 0x00FF00FF = MAGENTA,
  0x0000FF00 = GREEN, 0x00FFFF00 = green-ish. The two "comprehensive"
  rebuilds used 0x00FF00FF for the vmlinux entry cave but labeled it
  "green". User reported "green nothing but green" twice = the STUB's
  leftover green — the vmlinux entry cave (magenta) NEVER painted.
  => Those runs likely never reached the vmlinux at all; the lookup
  theories were chasing a ghost. The comprehensive zImage rebuild
  (which dropped the white/yellow/blue caves) broke the handoff somewhere.
- Lookup data block VERIFIED at file 0x12FC8: {dot=0xC001AFC8,
  begin=0xC001B9B4, end=0xC001BA1C} = TWO proc_info entries. Entry 2
  (file 0x139E8): id=0x000F0000 mask=0x000F0000 = generic ARMv7 fallback
  (matches ANY v7 MIDR). Bounded 2-entry walk => lookup can neither fail
  nor hang on this CPU. Lookup code (file 0x12F90) is the classic
  add r3,pc,#0x30 / ldm / sub / add / walk / mov pc,lr — all sane.
- Also fixed bad cave encodings from the comprehensive builds
  (movs sl,r5 = 0xE1B0A005; ldm r3,{r4,r5,r6} = 0xE8930070).

## Current build (2026-11-24 ~23:0x) — known-good zImage + full bisect
zImage = run-1 proven config restored: trampoline words 0x04/0x0C/0x14/0x1C
= 0x44000020; 0x64 NOP; 0x160/0x164/0x170/0x174 NOP; caves WHITE@0x30,
YELLOW@0x150 (mov r0,r4), BLUE@0x178 (mov r0,#0; mov r1,r7; mov r2,r8;
mov pc,r4). Piggy delta +79, trailer+params shifted, word patches verified.
vmlinux caves (appended, entry branches patched):
  MAGENTA 0x00FF00FF @ entry (file 0x00000) -> rejoin 0x8004
  RED     0xFFFF0000 @ lookup 2nd insn (file 0x12F94) -> rejoin 0x12F98
  BLACK   0x00000000 @ post-lookup (file 0x0000C) -> movs sl,r5 -> 0x8010
  CYAN    0x0000FFFF @ error path (file 0x12FD4) -> hang
Expected show: magenta(stub) -> green(stub) -> WHITE -> YELLOW -> BLUE
  -> MAGENTA(vmlinux!) -> RED(lookup) -> BLACK(lookup ok) -> ...
Diagnosis tree:
  stuck green (no white)  = zImage never ran (stub/upload issue)
  white only              = dies 0x34..0x150
  yellow only             = dies 0x154..0x168 (decompressor call region)
  blue only               = decompression/handoff broken, vmlinux never ran
  blue -> magenta         = vmlinux entry RUNS; red/black tell lookup story
  magenta -> red -> black = lookup fine; bisect further (vet/pagetables/MMU)

## Update 4: ROOT CAUSES FOUND (3 real bugs in our instrumentation)
1. **Odd-offset caves = silent death.** Odd piggy delta put appended caves at
   odd file offsets; B() integer-division truncated branch targets to
   cave_start-3 (and an odd branch target would switch to Thumb anyway).
   Previous run died at the 0x30 branch -> no white -> "stuck green".
   FIX: pad cave region to 4-byte alignment; assert branches exact+aligned.
2. **Trailer shift never worked.** Trailer words sit at file 0x14938C+4k
   (tr-relative offset 2), but the shift loop read at offset 0 -> shifted
   straddling garbage, left real words untouched in ALL builds.
   FIX: range(2, len(tr)-3, 4). input_data_end now correct.
3. **Paint caves clobbered the boot protocol.** Caves used r0/r1/r2,
   destroying r1=mach/r2=atags; cave1 also replaced 0x30's `mov r7,r1`
   without re-executing it -> r7/r8 garbage -> kernel got garbage
   mach/atags -> died at __vet_atags right after the entry paint
   (this is why run 1 died after green; NOT the processor lookup).
   FIX: caves use only dead scratch regs (entry: r0/r3/r4; lookup: r0/r4/r5;
   caveD: r3/r5/r6), cave1 re-executes mov r7,r1, caveD does bic sp,sp,#3 +
   re-sets r1/r2 before bl 0x560 (sp was odd after odd deltas).
- bl 0x560 = dispatcher (mov r3,#0xc; b 0x3ac): fn 0xc = decompress_kernel,
  fn 8 = cache_on (the hang we NOP at 0x64). Not a direct decompressor call.
- Lookup data block: 2 entries, entry2 = generic ARMv7 (id/mask 0x000F0000)
  -> lookup cannot fail. VA note: file 0x139B4 = VA 0xC001B9B4.
- Every cave now has a ~1s delay (mov #0x400000; subs; bne -3 words =
  0x1AFFFFFD) so NO checkpoint is an invisible flash.

## Current build (Update 4) — expected show, each color ~1s:
magenta -> green (stub) -> WHITE (0x30 entry) -> RED (0x150 setup)
-> CYAN (0x168 pre-decompress; stays cyan DURING decompression)
-> BLACK (decompressor returned) -> BLUE (0x178 handoff)
-> MAGENTA (vmlinux entry) -> WHITE (lookup entered) -> RED (lookup returned)
-> then kernel runs uninstrumented (vet/pagetables/MMU/start_kernel);
if it dies later, screen stays RED. If console=t4fb0 comes up: real text!
zImage 1348960 bytes, delta +125, caves @ 0x14943C/74/AC/0x149520 (aligned).

## Update 5: aligned build booted further — stops at WHITE
Show: magenta -> green -> WHITE, stops. cave1 (0x30) now runs (alignment
fix proven). Death between 0x34 and 0x150 = params/ISIZE/reloc-check/
fixup-loop/BSS-zero region. Prime suspect: fixup loop LDR/STR and BSS STR
at ODD addresses (delta +125); run-1 had 2-mod-4 and passed, so U-bit
behavior uncertain. Added 2 checkpoints (build 1349072 bytes):
  CP1 "A" 0xFF0000FF @0x6C (re-exec ldm r0,{r1,r2,r3,r6,sb,sl,fp,ip}, ret 0x70)
  CP2 "B" 0x00FF0000 @0x134 (fixup done; re-exec mov r0,#0, ret 0x138)
Tree: stops WHITE = dies 0x34..0x6C; stops A = dies 0x70..0x134
(ISIZE/reloc/fixup); stops B = dies BSS loop 0x138..0x14C;
stops RED(0x150) = dies 0x154..0x168.

## Update 6: stops at CP1 ("A" renders BLUE) -> odd-address fixup loop
Panel mapping CONFIRMED xBGR8888 (0xAABBGGRR): 0xFF0000FF=blue,
0x00FF0000=red, 0xFFFF0000=red, 0x0000FFFF=cyan, 0x000000FF=blue,
0x00FFFF00=yellow, 0x00FF00FF=magenta, 0x0000FF00=green.
Show: magenta/green/white/BLUE(CP1)/stop => death 0x70..0x134.
Prime suspect: fixup loop ldr/str [fp] at ODD addr (delta +125).
Run-1 delta +38 (2-mod-4) passed; odd deltas (+73/+65/+79/+125) all died.
FIX: pad vmlinux tail with zeros pre-gzip until piggy DELTA % 4 == 0
(pad=3 -> delta +124). All params/trailer/fixup/BSS/stack offsets now
word-aligned; gzip structure intact (ISIZE/CRC at true end).
Build 1349068 bytes, all checks passed. Expected show:
magenta green white BLUE(CP1) red(CP2) red(0x150) cyan(decompressing...)
black(decompressed) blue(handoff) magenta(kernel) white(lookup) red(lookup ok)
(two reds in a row = normal). After last red: uninstrumented kernel —
watch for t4fb console text!

## Update 7: aligned delta STILL stops at CP1 (blue). Alignment not the cause.
ISIZE verified correct in file (0x285A9F @0x149402); params verified.
Death 0x70..0x134 persists. Bisecting into thirds (build 1349180):
  CPX YELLOW 0x00FFFF00 @0xA0 (after ISIZE read; re-exec add sl,sp,#0x10000)
  CPY GREEN  0x0000FF00 @0x108 (after reloc check; re-exec teq r0,#0)
Tree: stops blue = 0x70..0xA0 (sp/delta/ISIZE); stops yellow = 0xA4..0x108
(reloc check or RELOCATION PATH TAKEN — would copy zImage to ~0x28E200 and
jump there; our absolute cave branches would then misbehave); stops green
= fixup loop 0x10C..0x134; stops red(CP2) = BSS loop.
Note: params[3] "image size" (0x1493bc+delta) does NOT cover appended
caves — matters only if relocation path runs.

## Update 8: death = THE FIXUP LOOP (0x10C..0x134). Bypassed.
Show reached CPY (green @0x108) then stopped: CP1/CPX/CPY all pass =>
death is beq+adds+fixup loop; loop = only nontrivial part. With aligned
addresses it still dies (cause unknown — possibly STR quirk); pragmatic
fix: pre-apply the fixup at BUILD time (trailer words += DELTA + 0x44000000,
all 9 incl input_data/0x9e4 get +0x44000000 exactly as the loop would) and
bypass: 0x10C := b 0x118 (keeps r2/r3 BSS adds), 0x120 := b 0x134.
Semantically identical to the loop's result. Build 1349180, checks pass.
If green->red(CP2) now appears: BSS loop next, then decompressor (cyan hold),
black, blue, magenta(kernel), white, red — then uninstrumented kernel.

## Update 9: FULL zImage path works! Decompressor returns. No kernel entry.
Show: magenta green white blue(CP1) yellow(CPX) green(CPY) red(CP2)
red(0x150) cyan black(DECOMPRESSED!) blue(0x178) — stops. Fixup bypass
worked; decompressor ran to completion; but vmlinux entry cave (magenta)
never painted. Suspects: r4 clobbered by decompressor / decompressed entry
word corrupt / cave tail not written. Diagnostic cave3 (build 1349368):
after blue paint, verifies word[0x8000]==entry branch (0xEA0A166E),
word[0x28D9C0]==c0 first word (0xE59F0020), r4==0x8000; then protocol+jump.
Failure paints: YELLOW=entry word bad, RED=c0 word bad, GREEN=r4 bad.
If all pass -> magenta should appear.

## Update 10: ROOT CAUSE — WE NEVER DECOMPRESSED! bl 0x560 = cache_off!
Diagnostic result: YELLOW after blue = word[0x8000] wrong. Dispatcher
0x3AC walks proc_types (entry size 0x14, {value,mask,fn8,fnC,fn10});
entry17 (generic v7 @0x524): fn8=b 0x2DC (cache_on, the hang), fnC=b 0x5BC
(cache_off!), fn10=b 0x68C (cache flush). So 0x168 bl 0x560 = cache_off.
REAL decompress_kernel = 0x0B0C (r0=output,r1=free,r2=free_end,r3=arch_id),
called in the ORIGINAL flow via 0x160 b 0x10 -> chain word[0x14] (their
handoff patches it; placeholders 0x44000000/04/08/0C). We had NOP'd it!
decompress_kernel computes trailer-pool base PC-relative: literal@0xBA0
(0x14886C: 0xB20+0x14886C=0x14938C=trailer). Also pool literals @0xC4C
(0x1487B0->BSS 0x1493C0) and @0xD60 (0x14865C). THESE WERE NEVER SHIFTED
when the piggy grew -> decompressor read stale pointers. (0x3A54/0x3ABC/
0x3BB0/0x3FB0 = inflate huffman table constants — do NOT shift.)
FIX (build 1349376): shift 0xBA0/0xC4C/0xD60 by DELTA; 0x160 := b caveD;
caveD: cyan, bic sp, r1=sp, r2=sp+0x10000, push {r4,r7,r8}, bl 0x0B0C,
pop, black, b 0x164; 0x164 NOP; 0x168 keeps original cache_off call.
Now ACTUAL decompression runs. Expected: ...cyan(hold) black blue [checks]
MAGENTA(kernel entry) white red -> uninstrumented kernel -> maybe TEXT.

## Update 11: decompress_kernel looped via ANOTHER unpatched chain stub
Show cycled ...cyan then back to white: decompress_kernel's first call
bl 0x7E0 = console-puts chain stub; word[0x7E4] = placeholder 0x44000010
-> chain -> our patched word[0x14] -> 0x20 -> full zImage re-run = LOOP.
(0x7E8 = t4fb puts, checks 960x640; error fn 0x9E4 calls 0x7E0 x3 then hangs.)
FIX (build 1349428): word[0x7E4] := 0x44000540 (mov pc,lr = no-op; early
console silent, fine). Also 0x9E4 := b caveE: GREEN 0xFF00FF00 paint + hang
= decompressor ERROR visibility. All chain stubs now accounted for:
0x00/08/10/18 patched, 0x170 NOP'd, 0x7E0 -> RET.
Expected: cyan(hold, real decompress) black blue MAGENTA white red -> kernel.
cyan->GREEN = decompressor error path.

## Update 12: KERNEL BOOTING — stops after proc lookup (last red). DECOMPRESSION WORKS.
Full show reached: ...cyan black blue MAGENTA(kernel entry) white(lookup)
red(lookup returned) — stops. Real kernel execution confirmed through
__lookup_processor_type. Remaining uninstrumented: 0x8010..0x803C:
beq/params, __vet_atags (0x8138: tst r2,#3; checks ATAG core 0x54410001),
__create_page_tables (0x804C), ldr sp, __v7_setup via add pc,sl,#0x10,
then 0x810C = __enable_mmu (domain=0x15, TTBR=r4, SCTLR write @0x8124,
mov pc,sp -> __mmap_switched VA). MMU ON after 0x8124 — physical-FB
paints impossible beyond that point (VA 0x0F700000 unmapped).
New kernel caves (build 1349484, delta +180):
  k1 BLUE   @0x8024: paint, bl __vet_atags, -> 0x8028
  k2 YELLOW @0x8028: paint, bl __create_page_tables, -> 0x802C
  k3 GREEN  @0x8034: paint, mov r8,r4, -> 0x8038 (CPU init)
  k4 BLACK  @0x803C: paint, -> 0x810C (MMU enable)
Tree: red=0x8010..24; blue=vet_atags; yellow=pagetables; green=__v7_setup;
black=MMU/__mmap_switched/early start_kernel (then need console/VA paints).
After black: watch for t4fb console TEXT (console=t4fb0, t4fb=0x0F700000).

## Update 13: still stops at last red (cA). k1 blue never painted.
Death between cA rejoin (0x8010) and k1 (0x8024): beq/add r3/ldm/sub/add.
Trivial insns -> suspect decompressed-image corruption in that window OR
cave tail truncation. Build 1349564 (delta +192):
- cave3 now checks FOUR words: entry, c0, k1-first-word, word[0x8024],
  plus r4. YELLOW hang = entry/k1/w24 wrong (corruption/truncation);
  RED hang = c0 wrong; GREEN hang = r4 wrong.
- new k0 CYAN @0x8018 (ldm r3,{r4,r8} re-exec, -> 0x801C), scratch (0,4,6),
  preserves r3 (ldm base) and r5 (procinfo).
Tree: blue->yellow = corruption confirmed; red->cyan->blue(k1) = progress
into vet_atags; red stays (checks pass, k0 silent) = death 0x8010..0x8018.

## Update 14: yellow after handoff blue = decompressed TAIL TRUNCATED.
cave3 word-check failed (entry/c0 ok in prior runs; k1 or w24 bad now).
Prior runs: c0/cL/cA painted (tail first 164 bytes OK) but k1 silent =>
output stops ~original_size+164..220. Decompressor loses the tail!
Build 1349752: caveD PRE-FILLS output tail [0x28D980..0x28DCB0) with
0xA5A5A5A5 before calling decompress_kernel; cave3 probes for the pattern:
  after handoff blue: GREEN hang = boundary <= cD start (+164);
  WHITE hang = boundary <= k0 start (+220); YELLOW hang = <= k1 (+276)
  [or entry bad]; RED hang = near end [or c0 bad]; CYAN = w24 bad;
  MAGENTA = no truncation, kernel runs.
Probes: cD@0x28DA64 k0@0x28DA9C k1@0x28DAD4 end@0x28DBAC.
Next after boundary known: inspect inflate flush / output-size logic.

## Update 15: NO TRUNCATION — VA/FILE offset bug in the k-cave patches!
CYAN hang = w24 check failed. Root cause: k0..k4 head patches were written
at FILE offsets 0x8018/0x8024/0x8028/0x8034/0x803C, but vmlinux file =
VA - 0xC0008000 => correct file offsets are 0x18/0x24/0x28/0x34/0x3C.
The kernel head was NEVER patched (k-caves never ran; "stops at last red"
= original code ran uninstrumented past lookup), and kernel code at file
0x8018+ (VA 0xC0010018+) was CORRUPTED with branch words — likely the
actual post-red death. Tail was always fine (c0 check passed).
FIX (build 1349752, delta +192, pad 0): patch at 0x18/0x24/0x28/0x34/0x3C.
Head now: b k0 / b k1 / b k2 / b k3 / b k4. W24 check expects 0xEA0A16AA.
Expected after last red: CYAN(k0) blue(k1 vet) yellow(k2 pgtables)
green(k3 CPU init) black(k4 MMU) -> __mmap_switched/start_kernel -> TEXT?

## Update 16: "stopped after black" (uncertain report) — simplifying.
Removed prefill+probes (truncation theory dead) and k0 (redundant).
Build 1349560 (delta +180 = same as the run that reached kernel red).
caveD back to proven shape: cyan, align sp, push {r4,r7,r8}, bl 0x0B0C,
pop, black, b 0x164. cave3 checks: entry(bad=YELLOW), c0(bad=RED),
w24(bad=WHITE), r4(bad=GREEN), then jump.
Kernel caves now: c0 magenta, cL white, cA red, k1 BLUE(vet), k2 YELLOW
(pgtables), k3 GREEN(CPU init), k4 BLACK(MMU). Full expected show:
magenta green | white blue yellow green red red | cyan black blue |
magenta white red | blue yellow green black | -> TEXT?
If stops at first black (post-decompress): death 0x164..0x178 (cache_off
region) — instrument there next.

## Update 17: ambiguous reports — UNIQUE colors per kernel stage.
"last blue" + "saw magenta and white" — could be k1(vet) or CP1; vet is
loop-free (cannot hang: tst/ldr/cmp/bne/mov pc,lr; fail path r2=0+return).
Build 1349564 (delta +184): kernel stages now UNIQUE colors:
  k1 ORANGE 0x00FF8000 (vet), k2 PURPLE 0x008000FF (pgtables),
  k3 AZURE 0x000080FF (CPU init), k4 PINK 0x00FF0080 (MMU enable).
Final color = exact stage. Everything else identical to update 16.

## Update 18: ORANGE confirmed = stops at k1 (vet stage). vet is loop-free!
Instrumented vet itself (build 1349632, delta +224):
  v1 SALMON 0x00FF8080 @0x8138 (vet entry, re-exec tst r2,#3)
  v2 LIME   0x0080FF00 @0x8160 (vet SUCCESS return)
  v3 TEAL   0x00008080 @0x8164 (vet FAIL return, r2=0)
cave3 also checks word[0x8028] now (bad -> WHITE hang).
Tree after orange: salmon->lime->purple = vet fine, death later;
salmon->teal->purple = ATAGs REJECTED (but flow continues);
salmon->hang = fault inside vet (ldr [r2]!); orange only = k1 bl never
reached vet (call mechanics). Stub ATAGs verified at PA 0x100, r2=0x100
(mov #0x100 = 0xE3A02C01: 1 ROR 24 = 0x100 ✓).

## Update 19: ORANGE again even with vet instrumented => TAIL TRUNCATION REAL.
v1 (salmon) at vmlinux+2644856 never ran; k1 (+220) painted. Boundary
~original_size+272. Decompressor loses appended tail (mechanism unknown).
ROBUST FIX: caves moved OUT of the piggy into kcaves.bin (604 bytes),
uploaded separately to PA 0x300000 (free RAM: kernel ends ~0x28D9C0,
initrd 0x09000000+, zImage 0x04000000 window). vmlinux = ORIGINAL SIZE
(2644416, delta 0!) with only branch patches -> fully decompressed.
Blob targets = KB(0x8000)+FILE offset (caught double-add bug: 0x8138 is
already PA). boot-android.sh now uploads kcaves.bin 0x00300000.
Verified: decompressed size exact, all 11 patches land in blob, blob
branches exact (k1 bl 0x8138/b 0x8028, k4 b 0x810c, v1 b 0x813c).
Expected: ...orange(k1) salmon(v1) lime(v2 ok)/teal(v3 fail) purple(k2)
azure(k3) pink(k4) -> MMU on -> start_kernel -> TEXT?

## Update 20: reached PINK (k4 = MMU enable)! Kernel almost fully up.
User saw salmon + "weird blue"(azure k3) + final dark pink(k4). So vet,
page tables, CPU init all PASS. Death at/after __enable_mmu (0x810C:
orr r0,#2 (A bit!), domain 0x15, TTBR=r4, SCTLR@0x8124, mov pc,sp).
__mmap_switched = 0x8180 (data copy/BSS clear/store mach+atags, b 0x85F4).
start_kernel = 0x85F4. Post-MMU paints must use VA: FB=0xC0F70000,
blob via VA 0xC0300000 (lowmem map covers all 256MB). Added:
  m1 OLIVE 0x00808000 @0x8184 (ldm r3!,{r4-r7} re-exec; scratch (4,5,6)
     because r0=SCTLR LIVE until 0x81C0; ret VA 0xC0008188)
  m2 MINT 0x0000FF80 @0x81C4 (-> start_kernel VA 0xC00085F4)
Caught double-add bug twice (0x8188/0x85F4 are VAs; file offs 0x188/0x5F4).
kcaves.bin 712 bytes; zImage 1349404 (delta -4, pad 65 -> decompressed
2644481 = original+65 zeros, harmless, < truncation boundary).
Tree: pink only = dies 0x810C..0x8184 (enable_mmu/transition);
olive = dies in __mmap_switched; mint = early start_kernel; TEXT = WIN.

## Update 21: pink again — m1 faulted: FB VA UNMAPPED!
__create_page_tables (0x804C): r8 = [0x48]+delta = 0xC0000000+0x40000000
= 0 (wrap!) -> pgtable PA 0x4000. Identity loop maps sections 0..0
([0x108]=0xC0008138 -> 1MB, covers transition ✓). Kernel VA loop end =
word[0xFC] = 0xC03CA01F -> only ~3.8MB mapped at 0xC0000000!!!
FB VA 0xC0F70000 UNMAPPED -> m1's first paint store aborted.
FIX: v[0xFC] := 0xD0000000 -> 256MB lowmem map (entries 0x7000..0x7400,
fits; covers FB + blob + all RAM; matches MEM ATAG 256MB; kernel's
paging_init rebuilds later anyway). Build: zImage 1349400, delta -8,
pad 65 (decompressed 2644481 < truncation boundary ✓). Blob unchanged.
Expected: pink -> OLIVE (m1 @__mmap_switched) -> MINT (m2 @start_kernel)
-> Linux console text (console=t4fb0).

## Update 22: still pink. __v7_setup checked: r4 |= 0x59 is INTENTIONAL
(TTBR attrs; TTBR0 = 0x4059 = base 0x4000 + cache attrs ✓ correct).
Full transition instrumented (kcaves 892B, zImage 1349404, delta -4 pad 342
-> decompressed 2644758; tail 70B = zero padding, truncation-harmless):
  m0 GRAY 0x00808080 @0x8110 (pre-TTBR; cmp r4,#0x4059; if wrong: RED
     paint + ldr r4,=0x4059 fix; re-exec mov r5,#0x15; -> 0x8114)
  m0b PALE GREEN 0x0080FF80 @0x8130 (POST-MMU-ON, via identity; mov r3,sp
     re-exec; -> 0x8134)
  Identity map extended: v[0x108] = 0xC1000000 (16MB: covers FB + blob!).
  m1/m2 now paint via PA FB (identity) while fetched via VA map.
Tree: pink only = dies 0x810C-10; gray only = CP15 writes 0x8114-30 fault;
gray->red = r4 was wrong (fixed); pale green only = VA jump/fetch fails;
olive only = __mmap_switched body; mint only = early start_kernel; TEXT=WIN.

## Update 23: PALE GREEN = MMU ON, identity works! Death = mov pc,sp (VA jump).
m0 passed (r4=0x4059 ✓ no red), m0b painted (MMU on, identity fetch+FB OK).
Olived never => death at 0x8134 mov pc,r3 (sp=0xC0008180) or VA fetch.
0xC0031D2C = cache maint (CP15 only, no obvious stack use) — sp clobber
uncertain. TEST: m0b now FORCES r3 = 0xC0008180 (mov #0xC0000000; add
#0x8000; add #0x180) instead of mov r3,sp. kcaves 900B; zImage UNCHANGED
(v[0x130] still -> 0x300344). If olive appears: sp was clobbered, FIXED.
If pale green again: VA fetch/map itself broken -> dump pgtable entries next.

## Update 24: FULL AUDIT — FOUND THE REAL BUG: k4 clobbered r0 (SCTLR value)!
User asked for a code review. Register-liveness audit of every cave:
k4 (pink, @0x803C) used scratch (0,3,6) — but r0 = the SCTLR value just
computed by __v7_setup, written to CP15 at 0x8124 two instructions after
k4's branch target! Paint loop leaves r0 = 0x0FA00000 (FB end) ->
SCTLR := 0x0FA00002 = M=0 (MMU NEVER ON!), EE=1, reserved bits set ->
hang or VA-jump fault. Explains ALL symptoms: pink stops (MMU off, VA
fault), pale-green stops (m0b paints via PA regardless), gray variability
(reserved-bit writes = unpredictable). Set mask 0x10C03C7D already has
M=1 — kernel enables MMU itself IF r0 survives.
FIX: k4 scratch (3,5,6) — r0 preserved. Full audit passed: all 15 vmlinux
patches, map extensions, blob returns/bl targets, zImage head/trailer/pool.
kcaves 1048B (k4 replaced in place), zImage = orr#2 version (1349404).
Expected: pink gray(m0) pale-green(m0b, PT checks pass) OLIVE(m1) MINT(m2)
-> start_kernel -> TEXT.

## Update 25: k4 fix -> STILL gray. Gray = death 0x8114-0x8130 (CP15 writes
or first MMU-on fetch). Full clean rebuild (kcaves 1172B, zImage 1349404,
delta -4 pad 88). New diagnostics:
  m0 now ALSO dumps pgtable contents pre-MMU: [0x4000]==0xC0E (identity),
  [0x7000]==0xC0E (VA C00), [0x700C]==0x300C0E (VA C03=blob).
  Fail colors: RED hang=identity bad, YELLOW hang=VA C00 bad,
  ORANGE hang=VA C03 bad. (RED then continue = r4 was wrong, fixed.)
  m0c LIGHT MAGENTA 0x00FF80FF @0x8120 (between TTBR and SCTLR writes,
  MMU still off, PA paint, scratch (3,5,6) preserves r0).
Tree: gray only = dies domain/TTBR writes 0x8114-20; gray->light magenta
only = dies SCTLR write or first MMU-on fetch; ->pale green only = VA jump
fails; ->olive/mint = PROGRESS. Offsets: m0=25c m0c=3b0 m0b=3e8 m1=428 m2=460.

## Update 26: LIGHT MAGENTA = m0c ran; its return branch had double-add bug!
m0c b target was KB+0x8124 = 0x10124 (0x8124 is already PA!) -> jumped into
kernel image garbage. Page tables VERIFIED GOOD by m0 ([0x4000]=0xC0E,
[0x7000]=0xC0E, [0x700C]=0x300C0E — no red/yellow/orange). k4 r0 fix in place.
FIX: m0c b := 0x8124 (file offset 0x124). Full blob branch audit: ALL CLEAN.
zImage unchanged. Now the flow actually reaches the SCTLR write with correct
r0. Expected: gray light-magenta pale-green OLIVE MINT -> start_kernel -> TEXT.

## Update 27: light magenta again (m0c branch fixed) -> m0b PAINT faulted:
with MMU ON, PA FB 0x0F700000 (247MB) is NOT identity-mapped (identity=16MB)!
m0b/m1/m2 painted via PA FB -> data abort. FIX: m0b/m1/m2 paint via VA FB
0xC0F70000 (256MB VA map covers it). m0/m0c stay PA (pre-MMU). kcaves 1172B,
zImage unchanged. If light-magenta AGAIN: SCTLR value itself suspect ->
next test = minimal SCTLR (M+A+U only, caches/TRE/V off) via cave @0x810C.

## Update 28: light magenta persists; do NOT infer SCTLR failure yet
@@
- (see prior text; retained below)
+ CORRECTION: the VFB arithmetic in updates 21-27 was WRONG:
+ 0xC0000000 + 0x0F700000 = 0xCF700000, NOT 0xC0F70000. Every post-MMU
+ paint since update 21 wrote ordinary RAM at PA 0x0F070000 - invisible,
+ fault-free. The kernel may have been passing the MMU transition all
+ along. Also 0x108 is the IDENTITY loop end (not the VA loop end, which
+ is 0xFC); my "16MB identity" note conflated them. /tmp kit was wiped
+ by host cleanup; exact binaries gone.

## Update 29: persistent rebuild; two more bugs found by pre-cycle checks.
New tools/build-bootkit.py rebuilds EVERYTHING from pristine sources into
bootkit/ (persistent). Bugs caught during this rebuild (user's new rule:
check all work before every DFU cycle):
1. VFB arithmetic (update 28) - fixed: post-MMU paints now use PHYSICAL
   FB via a 256MB identity map (0x108 := 0xD0000000), independent of the
   kernel VA map. Identity slots 0x4000..0x4400 (no overlap with VA table
   at 0x7000+).
2. Double-add AGAIN in patch_vmlinux: offs values are absolute PA, line
   added CB twice -> all vmlinux branches targeted 0x600000 garbage.
   Caught by the builder's own audit (it failed -> nothing booted a bad
   image). Fixed; audit re-passed.
m0 now verifies FIVE page-table words pre-MMU: [0x4000] id-section-0,
[0x7000] VA C00, [0x700C] blob, [0x73DC] VA FB, [0x43DC] identity FB.
m0b forces r3=0xC0008180. zImage 1349232 (delta -6), kcaves 1316B.
Expected show: ...pink gray lmag PALE-GREEN olive mint -> start_kernel.

## Update 30: "White" stuck = MY alignment regression (delta 2 mod 4).
The update-29 build shipped piggy delta -6: BSS/heap/stack pointers all
landed at 2-mod-4 addresses -> first misaligned STR in the BSS-zero loop
aborted -> data-abort vector = word at PA 0x14 (alias of 0x44000014,
patched to 0x44000020!) -> the zImage re-entered from the top and the show
cycled (b1 repaints WHITE first each cycle; user saw white).
ALL previously passing builds had delta 0 mod 4; I broke it in the rewrite
by removing the pad loop on a wrong premise (tail padding is fine: the
pad rides past the kernel end, below the truncation boundary, and the
real cave code is in kcaves.bin anyway).
FIX (build-bootkit.py): pad loop is back, with an INCOMPRESSIBLE filler
(0xA5+i*13) because zero-padding did NOT change gzip length at all
(empirically constant across pads 0..15 — trailing zeros fit in the last
block's spare bits). Filler grows pig ~1:1, so pads 0..3 always hit
delta%4==0. Audit now asserts delta%4==0 AND params[1]/params[7] aligned.
Current build: delta -4 (0 mod 4), pad 0, zImage 1349232, 235 internal
checks + independent audit PASS. Two of my own audit-checker bugs also
fixed (vv size vs pad; bl scan stepping 4 from a 2-mod-4 region start).

## Update 31: THE REAL BUG — new builder's return branches were CONDITIONAL.
bext() emitted word 0x00000000; finish() took the opcode from it -> cond 0
(EQ). Returns after the paint's delay loop worked BY LUCK (subs -> Z=1).
But py (CPY @0x108) re-execs `teq r0,#0` (Z=0 for nonzero delta) -> its
return NOT taken -> fell through p2 (also skipped, same cond bug) -> b2 ->
0x154, BYPASSING the fixup-BSS region entirely: the decompressor's state
variables at 0x441493xx never got zeroed -> stale file/openiboot bytes ->
wild pointer writes -> the boot died at DRAM-content-dependent points.
THIS explains the shifting stuck colors (white/green/magenta) across runs
with no code change matching them. Builds A/B/C all carried it; the old
hand-built kits never did (mkcave wrote proper 0xEA returns).
FIX: bext emits 0xEA000000 (like bl's 0xEB000000). Audit now asserts every
return-targeting branch is cond 0xE (275 internal checks PASS + independent
audit PASS incl. the same check). Also answered user's QEMU question: no
iPhone4 machine exists; generic-ARM emulation still useful for the
head.S/MMU frontier (gdb visibility) once qemu-system-arm is installed —
but this fix should be tried first.
- Light magenta means the pre-SCTLR cave painted. The next event is the
  SCTLR write at 0x8124, then instruction fetch/branch at 0x8128-0x8130,
  then m0b's first *virtual framebuffer store*. Any of those can explain
  no pale-green marker. Previous claims that this uniquely proved the
  SCTLR write failed were too strong.
- Static arithmetic from pristine kernel data: 0xFC is the end value for
  kernel VA section descriptors. Patched D0000000 gives table limit
  r6=0x7400; loop begins 0x7000 and covers entries C00..D00 inclusive.
  Thus VA C0F maps PA 0x00F00000, descriptor expected 0x00F00C0E at L1
  address 0x703C (framebuffer VA C0F70000 should be mapped). Existing m0
  only checked 0x7000 and 0x700C, NOT this framebuffer descriptor.
- 0x108 belongs to the separate {dot,start,end} relocation tuple used for
  the low identity map. C1000000 relocates to physical 16MB (inclusive
  section endpoint); it does NOT affect the VA C0F mapping. The earlier
  summary calling 0x108 the framebuffer mapping was imprecise.
- /tmp/android-boot was removed by host /tmp cleanup, so the exact last
  binaries are no longer available for byte-for-byte re-audit. Source
  payloads and docs remain. Do not flash NAND; no evidence suggests storage
  is involved, and NAND writes add risk without helping this MMU failure.
- NEXT, before another boot cycle: recreate the builder persistently and
  add a probe after SCTLR that executes from identity-mapped low RAM; read
  SCTLR back, and paint via PA only after also extending identity map to
  cover FB (while keeping kernel VA map separate). Add m0 check of [0x703C]
  == 0x00F00C0E. Distinct marker outcomes should separate SCTLR readback,
  post-write fetch, and framebuffer mapping. Keep all changes RAM-only.

## Update 32: QEMU PROOF — the whole chain works; phone kit updated.
QEMU (virt, cortex-a7, RAM@0x40000000) with a profile-parameterized kit
(build-bootkit.py phone|qemu) caught a chain of bugs the phone never could:
stub copy-loop compared value-vs-address (ran away); mov r1,#3564 bad
immediate; console-stub + b3 K8000 + 0x7CC zreladdr hardcoded to phone
values. **THE BIG ONE: __mmap_switched's BSS-CLEAR zeroes PA img_end..
0x3CA020 (head words [1d0]/[1d4]) — the kcaves blob (phone 0x300000,
qemu 0x40300000) was INSIDE -> zeroed between m1 and m2 -> m2 fetched
NOPs -> silent VA march -> zImage re-entry (the phone's shifting stuck
colors!).** FIX: blob outside bss, inside head's +-32MB branch range:
phone 0x1000000; qemu 0x41800000 (VCB derives: PAGE_OFFSET+CB-RAM_BASE).
QEMU now runs the FULL chain: stub -> zImage -> decompress -> handoff
checks -> kernel entry -> lookup -> vet -> page tables -> MMU ON ->
VA jump -> __mmap_switched -> m1 -> m2 -> START_KERNEL -> kernel .data
code (regs = kernel pointers, stack at 0xc0fffxxx) -> abort storm at
APPLE MMIO (no apple hw in QEMU; the healthy endpoint). FB ends white.
PHONE kit = blob fix + SCTLR_MINIMAL (m0c forces r0:=1, M-bit only) since
the A4 died exactly at the kernel's masked SCTLR write that QEMU's A7
accepted. Ops notes: pkill -x qemu-system-arm (pkill -f killed my own
shell); stale qemus poison snapshots; -d int storms write 1.2GB.
Expected phone show: ...pink gray lmag pgreen olive mint -> start_kernel
-> TEXT — or a later hang names itself by color.

## Update 33: PHONE BOOTED TO start_kernel!! White screen = kernel's own.
The full light show COMPLETED on the phone (all colors incl. mint) and
the screen ended WHITE — the kernel entered start_kernel; the white is
almost certainly the apple machine-init display blanking inside
setup_arch. No text = death between setup_arch and console_init
(pre-console = silent). QEMU predicted exactly this endpoint shape.
- SCTLR_MINIMAL (r0:=1) WORKED: the phone now passes 0x8124 (previously
  died at the kernel's masked SCTLR value; A4 rejected bits the A7 took).
- start_kernel bisect cascade added (m3..m10, blob 1764B, 307 audits):
    m3 purple  entry 0x85F4 | m4 dark-olive setup_arch 0x8658
    m5 brown  mm-era 0x86B8 | m6 dark-lime sched_init 0x86C0
    m7 dark-teal trap_init 0x86D4 | m8 dark-orange early_irq 0x8704
    m9 steel-blue init_IRQ 0x8708 | m10 GOLD console_init 0x8740
  bl sites RE-ENCODE the call from the cave (raw re-exec is
  position-dependent — caught in review); callee returns into the cave.
  Scratch (1,2,12): r1/r2 dead at start_kernel (head stored mach/atags
  to memory), r12 AAPCS. r0 (live args) preserved.
  Final color after mint names the failing init. GOLD = console_init
  reached -> t4fb text should follow.

## Update 34 (2026-11-26, new PC): stops at DARK OLIVE (m4 = setup_arch) -> white
See docs/SESSION-2026-11-26.md. Machine 3564 is valid; setup_arch registers the
t4fb console (white-on-black text, cannot make a solid white screen); m5..m10
faulted on the identity map that paging_init wipes (our bug, fixed in
kcaves.bin: VA bottom strip). __log_buf = PA 0x0028FCE0 (128 KB);
tools/oiblog.py reads it back via openiboot hexdump after a DFU reset.
