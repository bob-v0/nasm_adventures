; Provided by level 122: the game's checked allocator.
; It never reuses memory, fills freed blocks with 0xDD, and stops your program at the
; first access to a freed block (or outside any block), saying where it was freed.
bits 64
global malloc
global free

section .text
malloc:                         ; rdi = size -> rax = block
    mov eax, 0x1000
    syscall
    ret
free:                           ; rdi = block
    mov eax, 0x1001
    syscall
    ret
