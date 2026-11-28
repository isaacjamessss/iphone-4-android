/* pmutool - read/write the iPhone 4 (A4) PMU over I2C0 from userspace via
 * /dev/mem, polling the controller (same register sequence as openiboot
 * plat-a4/i2c.c). The T4 kernel has no I2C driver, so nothing else uses it.
 *
 *   pmutool r REG [N]        read N registers starting at REG
 *   pmutool w REG VAL        write one register
 *   pmutool set REG MASK     REG |= MASK  (read-modify-write, prints before/after)
 *   pmutool clr REG MASK     REG &= ~MASK
 *
 * Build: zig cc -target arm-linux-musleabi -O2 -static -o pmutool pmutool.c
 */
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>

#define I2C0      0x83200000u
#define PMU_ADDR  0xE8          /* 8-bit address; controller takes addr >> 1 */

static volatile uint32_t *r;
#define REG(o) r[(o) / 4]

static void sleep_us(long us) {
    struct timespec ts = { 0, us * 1000 };
    nanosleep(&ts, NULL);
}

/* one transaction: write=1 -> send buf, write=0 -> read len bytes into buf */
static int xfer(int write, uint8_t reg, uint8_t *buf, int len) {
    REG(0x0C) = REG(0x0C);              /* clear stale status */
    REG(0x00) = PMU_ADDR >> 1;
    REG(0x14) = 0;
    REG(0x10) = reg;
    REG(0x18) = len;
    if (write)
        for (int i = 0; i < len; i++) REG(0x20) = buf[i];
    REG(0x24) = (write ? 1 : 0) | 4;
    uint32_t st = 0;
    for (int t = 0; t < 2000 && !(st = REG(0x0C)); t++) sleep_us(50);
    if (!st) { fprintf(stderr, "i2c timeout\n"); return -1; }
    if (st & 0x20) { REG(0x0C) = st; fprintf(stderr, "i2c nack (st=%x)\n", st); return -1; }
    if (!write)
        for (int i = 0; i < len; i++) buf[i] = REG(0x20);
    REG(0x0C) = st;
    return 0;
}

static int rd(uint8_t reg, uint8_t *v) { return xfer(0, reg, v, 1); }
static int wr(uint8_t reg, uint8_t v)  { return xfer(1, reg, &v, 1); }

int main(int argc, char **argv) {
    if (argc < 3) {
        fprintf(stderr, "usage: pmutool r REG [N] | w REG VAL | set REG MASK | clr REG MASK\n");
        return 2;
    }
    int fd = open("/dev/mem", O_RDWR | O_SYNC);
    if (fd < 0) { perror("/dev/mem"); return 1; }
    r = mmap(NULL, 0x1000, PROT_READ | PROT_WRITE, MAP_SHARED, fd, I2C0);
    if (r == MAP_FAILED) { perror("mmap"); return 1; }

    uint8_t reg = strtoul(argv[2], NULL, 0), v;
    if (!strcmp(argv[1], "r")) {
        int n = argc > 3 ? strtoul(argv[3], NULL, 0) : 1;
        for (int i = 0; i < n; i++) {
            if (rd(reg + i, &v)) return 1;
            printf("pmu[0x%02x] = 0x%02x\n", reg + i, v);
        }
    } else if (!strcmp(argv[1], "w") && argc > 3) {
        if (wr(reg, strtoul(argv[3], NULL, 0))) return 1;
        if (rd(reg, &v)) return 1;
        printf("pmu[0x%02x] = 0x%02x\n", reg, v);
    } else if ((!strcmp(argv[1], "set") || !strcmp(argv[1], "clr")) && argc > 3) {
        uint8_t m = strtoul(argv[3], NULL, 0), nv;
        if (rd(reg, &v)) return 1;
        nv = argv[1][0] == 's' ? (v | m) : (v & ~m);
        printf("pmu[0x%02x]: 0x%02x -> 0x%02x\n", reg, v, nv);
        if (wr(reg, nv)) return 1;
        if (rd(reg, &v)) return 1;
        printf("pmu[0x%02x] = 0x%02x (readback)\n", reg, v);
    } else {
        fprintf(stderr, "bad command\n");
        return 2;
    }
    return 0;
}
