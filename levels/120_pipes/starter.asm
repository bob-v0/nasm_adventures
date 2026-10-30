; Level 120 — Pipes & dup
;
; argv: LEFT... "|" RIGHT...   e.g.  /bin/echo one two | /bin/wc
; Run LEFT with its stdout going into a pipe, and RIGHT reading that pipe as its stdin,
; both at the same time (like a shell's `left | right`). Pass your envp on.
; Wait for both, close everything you opened, and exit with RIGHT's status
; (its exit code, or 128 + the signal number if it was killed).

global _start

section .text
_start:
    ; TODO
    mov eax, 60
    xor edi, edi
    syscall
