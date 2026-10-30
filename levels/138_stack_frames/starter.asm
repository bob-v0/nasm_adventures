; Level 138 — Stack Frames
;
; backtrace(rdi = buf, rsi = max) -> rax = entries written
;   buf[0] = your own return address; then [rbp + 8] of each frame along the
;   rbp chain, until the next rbp is 0 or max entries are written.

global backtrace

section .text
backtrace:
    ; TODO
    ret
