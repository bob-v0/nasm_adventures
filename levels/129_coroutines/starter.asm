; Level 129 — Coroutines
;
; co_switch(rdi = save, rsi = load)
;   context = 7 qwords: rsp, rbx, rbp, r12, r13, r14, r15
;   Save the current context into *save, load *load, and continue there.

global co_switch

section .text
co_switch:
    ; TODO
    ret
