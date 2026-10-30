; Linked into every function-mode level. In the emulator the game calls the level's
; entry function directly, with its return address set to __ring_return.
; _start only exists so the program also links (and does nothing) natively.
bits 64
global _start
global __ring_return

section .text
__ring_guard:
    ud2                     ; a function without `ret` falls through to here
_start:
    mov eax, 60
    xor edi, edi
    syscall
__ring_return:
    nop
