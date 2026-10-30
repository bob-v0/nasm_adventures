; Level 157 — Bignum ★
;
; numA: rsi limbs, numB: rcx limbs (1..8 each, limb 0 least significant)
; product: write the rsi + rcx limbs of A * B (it starts full of garbage)
; Leave rsi and rcx unchanged, and limbs beyond rsi + rcx untouched.

