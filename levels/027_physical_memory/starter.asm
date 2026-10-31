; Level 27 — Physical Memory
;
; A frame allocator: hands out 4 KiB frames of physical memory, one at a time, and takes
; them back.
;     alloc_frame: eax = the address of a free frame, or 0 if there's none left
;     free_frame:  eax = a frame that alloc_frame gave you
; Both keep every other register as it was.
;
; Hand out only frames the multiboot memory map says are available RAM (type 1), never
; below 1 MiB, and never the kernel's own memory (1 MiB to `kernel_end`) or its modules
; (and what the loader put between them): up to the end of the last module. Every such
; frame, exactly once, until it comes back.
;
; init_frames runs first, with [boot_info] = the multiboot information. Then the game's
; test (the first module) runs at 0x80000 and takes it from there.

bits 32

MB_FLAGS   equ 1 << 0 | 1 << 1
FRAMES     equ 1 << 20          ; 4 GiB of 4 KiB frames: one bit each
MODULE     equ 0x80000          ; where the game's test runs

section .multiboot
align 4
    dd 0x1BADB002, MB_FLAGS, -(0x1BADB002 + MB_FLAGS)

section .text
global _start, alloc_frame, free_frame
extern kernel_end
_start:
    mov esp, stack_top
    mov [boot_info], ebx
    call init_frames
    ; the game's test: the first module, copied to MODULE and called
    mov ebx, [boot_info]
    mov esi, [ebx + 24]
    mov ecx, [esi + 4]
    mov esi, [esi]
    sub ecx, esi
    mov edi, MODULE
    rep movsb
    mov eax, alloc_frame
    mov edx, free_frame
    mov ecx, [boot_info]
    mov ebx, kernel_end
    mov esi, MODULE             ; (through a register: see the brief)
    call esi
    cli
    hlt

init_frames:
    ret

alloc_frame:
    xor eax, eax
    ret

free_frame:
    ret

section .bss
alignb 4
boot_info: resd 1
alignb 16
stack:     resb 8192
stack_top:
