; Level 51 — Assembler
;
; Read assembly source from stdin (at most 64 KiB) and write the machine code to
; stdout, as `nasm -f bin` would (origin 0). The language is level 54's output, plus
; labels (a line `name:`) that branches and [rel name] may use. The brief has the
; details. The game decodes your bytes and compares what each instruction does: any
; valid encoding is fine.

global _start

section .text
_start:
    ; TODO
    mov eax, 60
    xor edi, edi
    syscall
