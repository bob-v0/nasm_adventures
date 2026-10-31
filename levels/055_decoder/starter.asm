; Level 55 — Decoder
;
; ring_insn_length(code): the length in bytes of the instruction at code. Every test
; instruction comes from the subset in the brief (and is valid); the bytes after it are
; the next instruction or junk.

global ring_insn_length

section .text
ring_insn_length:               ; rdi = code
    ; TODO
    mov eax, 1
    ret
