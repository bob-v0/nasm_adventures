; Level 166 — Signed vs Unsigned
;
; rdi = a, rsi = b   (leave unchanged). Each output is 1 (true) or 0 (false):
;   rax: a + b overflows unsigned     rbx: a + b overflows signed
;   rcx: a - b overflows unsigned     rdx: a - b overflows signed
;   r8:  a < b signed                 r9:  a < b unsigned

