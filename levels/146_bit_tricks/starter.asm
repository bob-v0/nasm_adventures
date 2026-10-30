; Level 146 — Bit Tricks   (no jumps)
;
; rdi = x (1 .. 2^63), rsi = y   (unchanged)
;   rax = lowest set bit of x       rbx = x with that bit cleared
;   rcx = 1 if x is a power of 2    rdx = smallest power of 2 >= x
;   r8  = parity of x               r9  = |x - y| (unsigned)

