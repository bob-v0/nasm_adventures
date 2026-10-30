; Level 164 — Division
;
; rdi = a, rsi = b   (signed; b != 0; leave unchanged)
;   r8  = a / b  rounded toward zero (C)
;   r9  = a % b  (C: sign of a)
;   rax = a // b rounded down (Python)
;   rdx = a % b  (Python: sign of b)

