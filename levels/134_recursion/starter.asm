; Level 134 — Recursion
;
; hanoi(rdi = n, rsi = from, rdx = to, rcx = via, r8 = out) -> rax = end of moves
; Each move: 2 bytes (from, to) written at out. n = 0: return out.

global hanoi

section .text
hanoi:
    ; TODO
    ret
