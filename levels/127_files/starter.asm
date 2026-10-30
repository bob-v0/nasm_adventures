; Level 127 — Files
;
; 1. open "in.txt"; on failure: stderr "cannot open in.txt\n", exit(errno)
; 2. copy it to "out.txt" (O_WRONLY|O_CREAT|O_TRUNC, 0644), 4096 bytes at a time
; 3. stdout: "N lines\n" (N = number of newline bytes)
; 4. close both, exit 0

global _start

section .text
_start:
    ; TODO
