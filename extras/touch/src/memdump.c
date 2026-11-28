/* memdump PID ADDR LEN OUT - ptrace-attach, copy memory, detach */
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/ptrace.h>
#include <sys/wait.h>
#include <unistd.h>
int main(int c, char **v) {
    if (c < 5) return 2;
    int pid = atoi(v[1]); unsigned long a = strtoul(v[2], 0, 0), n = strtoul(v[3], 0, 0);
    if (ptrace(PTRACE_ATTACH, pid, 0, 0)) { perror("attach"); return 1; }
    waitpid(pid, 0, 0);
    char p[64]; snprintf(p, sizeof p, "/proc/%d/mem", pid);
    int fd = open(p, O_RDONLY); char *b = malloc(n);
    long r = fd < 0 ? -1 : pread(fd, b, n, a);
    ptrace(PTRACE_DETACH, pid, 0, 0);
    if (r < 0) { perror("pread"); return 1; }
    FILE *o = fopen(v[4], "wb"); fwrite(b, 1, r, o); fclose(o);
    printf("%ld bytes\n", r); return 0;
}
