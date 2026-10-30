; Level 119 — Signals
;
; 1. SIGINT handler sets a flag; spin up to 100000 times; print "caught SIGINT\n"
;    or "no SIGINT\n".
; 2. SIGSEGV handler: move the saved rip ([rdx + 168]) to a recovery label;
;    then read from address 0; the label prints "recovered from SIGSEGV\n".
; 3. exit(0)
; rt_sigaction = 13, rt_sigreturn = 15, SA_RESTORER = 0x04000000

global _start

section .text
_start:
    ; TODO
