; Level 28 — CPUID & MSRs (reference)

bits 32

MB_FLAGS equ 1 << 0 | 1 << 1
EFER     equ 0xC0000080
EFER_NXE equ 1 << 11

section .multiboot
align 4
    dd 0x1BADB002, MB_FLAGS, -(0x1BADB002 + MB_FLAGS)

section .text
global _start
_start:
    mov esp, stack_top
    ; the vendor: leaf 0 returns it in ebx, edx, ecx (in that order), and the highest leaf
    xor eax, eax
    cpuid
    mov [vendor], ebx
    mov [vendor + 4], edx
    mov [vendor + 8], ecx
    mov [max_leaf], eax
    mov esi, s_vendor
    call puts
    mov esi, vendor
    call puts
    mov esi, s_max
    call puts
    mov eax, [max_leaf]
    call hex
    ; the extended leaves: 0x80000000 says how far they go
    mov eax, 0x80000000
    cpuid
    mov [max_ext], eax
    mov esi, s_max_ext
    call puts
    mov eax, [max_ext]
    call hex
    ; leaf 1: edx bit 6 PAE, bit 9 APIC
    mov eax, 1
    cpuid
    mov esi, s_pae
    bt edx, 6
    call yes_no
    mov esi, s_apic
    bt edx, 9
    call yes_no
    ; leaf 0x80000001, if there is one: edx bit 29 long mode, 20 NX, 26 1 GiB pages
    xor edx, edx
    cmp dword [max_ext], 0x80000001
    jb .no_ext
    mov eax, 0x80000001
    cpuid
.no_ext:
    mov [ext_edx], edx
    mov esi, s_lm
    bt edx, 29
    call yes_no
    mov esi, s_nx
    bt dword [ext_edx], 20
    call yes_no
    mov esi, s_1g
    bt dword [ext_edx], 26
    call yes_no
    bt dword [ext_edx], 29
    jc .long_ok
    mov esi, s_no_lm
    call puts
    jmp .end
.long_ok:
    ; EFER: turn on NXE, but only if the CPU has NX (otherwise wrmsr faults: #GP)
    mov ecx, EFER
    rdmsr
    bt dword [ext_edx], 20
    jnc .show
    or eax, EFER_NXE
    wrmsr
    rdmsr                       ; (read it back: what the CPU kept)
.show:
    push eax
    mov esi, s_efer
    call puts
    pop eax
    call hex
.end:
    cli
    hlt

yes_no:                         ; esi = label; CF = the feature bit
    pushf
    call puts
    popf
    mov esi, s_yes
    jc .out
    mov esi, s_no
.out:
    jmp puts

hex:                            ; eax as 0x%08x, then a new line
    push eax
    mov esi, s_0x
    call puts
    pop edx
    mov ecx, 8
.digit:
    rol edx, 4
    mov eax, edx
    and eax, 15
    mov al, [digits + eax]
    call putc
    loop .digit
    mov esi, crlf
    jmp puts

putc:
    push edx
    push eax
    mov dx, 0x3FD
.ready:
    in al, dx
    test al, 0x20
    jz .ready
    pop eax
    mov dx, 0x3F8
    out dx, al
    pop edx
    ret

puts:
    lodsb
    test al, al
    jz .end
    call putc
    jmp puts
.end:
    ret

section .data
digits:    db "0123456789abcdef"
s_vendor:  db "vendor: ", 0
s_max:     db 13, 10, "max leaf: ", 0
s_max_ext: db "max extended leaf: ", 0
s_pae:     db "pae: ", 0
s_apic:    db "apic: ", 0
s_lm:      db "long mode: ", 0
s_nx:      db "nx: ", 0
s_1g:      db "1g pages: ", 0
s_efer:    db "efer: ", 0
s_yes:     db "yes", 13, 10, 0
s_no:      db "no", 13, 10, 0
s_0x:      db "0x", 0
s_no_lm:   db "this CPU can't run a 64-bit kernel", 13, 10, 0
crlf:      db 13, 10, 0

section .bss
vendor:   resb 13
alignb 4
max_leaf: resd 1
max_ext:  resd 1
ext_edx:  resd 1
alignb 16
stack:    resb 4096
stack_top:
