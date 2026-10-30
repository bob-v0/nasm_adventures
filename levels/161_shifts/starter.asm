; Level 161 — Shifts & Rotates
;
; rdi = r, rsi = g, rdx = b (0..255)           ->  rax = RGB565
; r11:r10 = 128-bit value, rcx = n (0..127)    ->  r9:r8 = value << n
; Leave rdi, rsi, rdx, r10, r11 unchanged.

