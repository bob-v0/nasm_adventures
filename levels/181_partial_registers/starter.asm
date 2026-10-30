; Level 181 — Nested Registers
;
; On entry: rax = R (keep it unchanged)
;   rbx = low byte of R, zero-extended
;   rcx = low 16 bits of R, sign-extended
;   rdx = low 32 bits of R, sign-extended
;   rsi = bits 8..15 of R, zero-extended
;   rdi = low 32 bits of R, zero-extended
;   r8  = R with the low byte replaced by 0x7F

