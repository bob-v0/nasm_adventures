; Level 162 — Bitwise Logic
;
; rdi = v (leave unchanged)
;   rax = v rounded down to 4096      rbx = v with low 12 bits set
;   rcx = v with bit 63 flipped       rdx = ~v
;   r8  = v rounded up to 4096        r9  = 0 (xor idiom)
;   r10 = 1 if v % 8 == 0, else 0

