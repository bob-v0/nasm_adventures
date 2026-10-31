; Level 37 — Multiboot (reference)

bits 32

MB_MAGIC  equ 0x1BADB002
MB_FLAGS  equ 1 << 0 | 1 << 1   ; modules page-aligned; give us the memory sizes
BOOTED    equ 0x2BADB002        ; what the loader leaves in eax

section .multiboot
align 4
    dd MB_MAGIC, MB_FLAGS, -(MB_MAGIC + MB_FLAGS)

section .text
global _start
_start:
    mov esp, stack_top
    cmp eax, BOOTED
    jne .not_multiboot
    mov ebx, ebx                ; ebx = the multiboot information structure
    mov esi, s_ok
    call puts
    mov esi, s_cmdline
    call puts
    mov esi, [ebx + 16]         ; cmdline (flags bit 2)
    call puts
    call newline
    mov esi, s_memory
    call puts
    mov eax, [ebx + 4]          ; mem_lower (flags bit 0), KiB
    call number
    mov esi, s_low
    call puts
    mov eax, [ebx + 8]          ; mem_upper
    call number
    mov esi, s_high
    call puts
    mov esi, s_modules
    call puts
    mov eax, [ebx + 20]         ; mods_count (flags bit 3)
    call number
    call newline
    mov ecx, [ebx + 20]
    mov ebp, [ebx + 24]         ; mods_addr: 16 bytes per module
.module:
    test ecx, ecx
    jz .done
    mov esi, [ebp]              ; mod_start
    mov edi, [ebp + 4]          ; mod_end
.byte:
    cmp esi, edi
    jae .next
    lodsb
    call putc
    jmp .byte
.next:
    add ebp, 16
    dec ecx
    jmp .module
.done:
    cli
    hlt
.not_multiboot:
    mov esi, s_bad
    call puts
    cli
    hlt

number:                         ; eax in decimal
    push ebx
    push ecx
    push edx
    mov ebx, 10
    xor ecx, ecx
.digit:
    xor edx, edx
    div ebx
    push edx
    inc ecx
    test eax, eax
    jnz .digit
.out:
    pop eax
    add al, '0'
    call putc
    loop .out
    pop edx
    pop ecx
    pop ebx
    ret

newline:
    mov al, 13
    call putc
    mov al, 10
putc:                           ; al -> COM1
    push edx
    push eax
    mov dx, 0x3FD
.wait:
    in al, dx
    test al, 0x20
    jz .wait
    pop eax
    mov dx, 0x3F8
    out dx, al
    pop edx
    ret

puts:                           ; esi = a NUL-terminated string
    lodsb
    test al, al
    jz .end
    call putc
    jmp puts
.end:
    ret

section .rodata
s_ok:      db "booted by a multiboot loader", 13, 10, 0
s_bad:     db "eax isn't 0x2BADB002: not booted by a multiboot loader", 13, 10, 0
s_cmdline: db "command line: ", 0
s_memory:  db "memory: ", 0
s_low:     db " KiB low, ", 0
s_high:    db " KiB high", 13, 10, 0
s_modules: db "modules: ", 0

section .bss
alignb 16
stack:     resb 4096
stack_top:
