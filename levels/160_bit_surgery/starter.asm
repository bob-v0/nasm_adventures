; Level 160 — Bit Surgery
;
; setA, setB: 256-bit sets (4 qwords each). rdi, rsi, rdx: bit indexes (unchanged).
; 1. set bit rdi in setA, clear bit rsi in setB
; 2. rax = |setA|, rbx = lowest bit of setA, rcx = bit rdx of setB,
;    r8 = highest bit of setB (or -1 if empty)

