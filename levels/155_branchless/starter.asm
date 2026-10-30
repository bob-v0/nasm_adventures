; Level 155 — Branchless   (no jumps of any kind)
;
; rdi = a, rsi = b (unchanged)
;   rax = |a|            rbx = min(a, b) signed     rcx = max(a, b) unsigned
;   rdx = sign(a)        r8  = (a == b)

