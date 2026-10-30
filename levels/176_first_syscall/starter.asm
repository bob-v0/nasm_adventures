; Level 176 — Asking the Kernel
;
; Exit with status = [secret]. From now on this is a complete program.

%include "level176.inc"      ; defines secret (in .data)

global _start

section .text
_start:
    ; TODO: exit(secret)
