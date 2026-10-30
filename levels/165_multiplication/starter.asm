; Level 165 — Multiplication
;
; rdi = a, rsi = b   (leave unchanged)
;   rdx:rax = a * b (unsigned, 128 bits)
;   r10     = low 64 bits of a * b
;   r8      = 1 if the SIGNED product overflows 64 bits, else 0
;   r9      = a * 37

