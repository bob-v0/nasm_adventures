; Level 117 — Time
;
; 1. clock_gettime(CLOCK_MONOTONIC), nanosleep 1.25 s, clock_gettime again:
;    print "slept N ms\n"
; 2. copy stdin to stdout one line per write, each line >= 400 ms after the
;    previous one (sleep only as long as needed)
; clock_gettime = 228, nanosleep = 35; timespec = { qword sec, qword nsec }

global _start

section .text
_start:
    ; TODO
