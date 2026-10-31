; Level 8 — PCI
;
; List the PCI devices on bus 0, reading their configuration space through ECAM (its base
; is found for you, in ACPI's MCFG table, as level 9 found the MADT). For every function:
;
;     00:02.0 1af4:1005 class 00.ff.00         bus:device.function vendor:device class
;       bar 0: io 0xc140, 32 bytes              (subclass, prog-if); then each BAR in use:
;       bar 1: memory 0xfebf1000, 4096 bytes    type, address, size
;       bar 4: memory64 0x00000000fe000000, 16384 bytes
;
; Helpers: puts (esi), putc (al), decimal (eax), hex2 / hex4 / hex8_bare (digits only;
; al, ax, eax), hex8 and hex4_prefixed (with 0x), newline. The strings are in .data.

bits 32

MB_FLAGS equ 1 << 0 | 1 << 1

section .multiboot
align 4
    dd 0x1BADB002, MB_FLAGS, -(0x1BADB002 + MB_FLAGS)

section .text
global _start
_start:
    mov esp, stack_top
    call find_mcfg                  ; [ecam] = the configuration space's base (done)
    ; your code: every function on bus 0, and its BARs

    cli
    hlt

; find_mcfg: [ecam] = the base of bus 0's configuration space, from ACPI's MCFG table
find_mcfg:
    call find_rsdp
    test esi, esi
    jz .out
    cmp byte [esi + 15], 2
    jb .rsdt
    mov ebx, [esi + 24]
    mov edx, 8
    jmp .root
.rsdt:
    mov ebx, [esi + 16]
    mov edx, 4
.root:
    mov ecx, [ebx + 4]
    sub ecx, 36
    lea esi, [ebx + 36]
.table:
    test ecx, ecx
    jz .out
    mov edi, [esi]
    cmp dword [edi], 'MCFG'
    je .found
    add esi, edx
    sub ecx, edx
    jmp .table
.found:                             ; after the header, 8 reserved bytes, then entries:
    mov eax, [edi + 44]             ; base (8), segment (2), first bus (1), last bus (1)
    mov [ecam], eax
.out:
    ret

; find_rsdp: esi = the RSDP ("RSD PTR ", 16-aligned, its first 20 bytes summing to 0):
; in the first KiB of the EBDA, or in 0xE0000-0xFFFFF. 0 if not found.
find_rsdp:
    movzx esi, word [0x40E]         ; the EBDA's segment
    shl esi, 4
    lea edx, [esi + 1024]
    call .scan
    test esi, esi
    jnz .out
    mov esi, 0xE0000
    mov edx, 0x100000
.scan:
    cmp esi, edx
    jae .missing
    cmp dword [esi], 'RSD '
    jne .on
    cmp dword [esi + 4], 'PTR '
    jne .on
    xor eax, eax                    ; the checksum
    xor ecx, ecx
.sum:
    add al, [esi + ecx]
    inc ecx
    cmp ecx, 20
    jb .sum
    test al, al
    jz .out
.on:
    add esi, 16
    jmp .scan
.missing:
    xor esi, esi
.out:
    ret

newline:
    mov esi, crlf
    jmp puts

decimal:                            ; eax
    push ebx
    push ecx
    push edx
    mov ebx, 10
    xor ecx, ecx
.d:
    xor edx, edx
    div ebx
    push edx
    inc ecx
    test eax, eax
    jnz .d
.o:
    pop eax
    add al, '0'
    call putc
    loop .o
    pop edx
    pop ecx
    pop ebx
    ret

hex:                                ; eax as 0x%08x
    push ecx
    push edx
    mov edx, eax
    mov al, '0'
    call putc
    mov al, 'x'
    call putc
    mov ecx, 8
.d:
    rol edx, 4
    mov eax, edx
    and eax, 15
    mov al, [digits + eax]
    call putc
    loop .d
    pop edx
    pop ecx
    ret

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


hex2:                               ; al as 2 hex digits
    push ecx
    push edx
    mov edx, eax
    shl edx, 24
    mov ecx, 2
    jmp hexn
hex4:
    push ecx
    push edx
    mov edx, eax
    shl edx, 16
    mov ecx, 4
    jmp hexn
hex8_bare:
    push ecx
    push edx
    mov edx, eax
    mov ecx, 8
hexn:
.d:
    rol edx, 4
    mov eax, edx
    and eax, 15
    mov al, [digits + eax]
    call putc
    loop .d
    pop edx
    pop ecx
    ret
hex8:                               ; 0x and 8 digits
    push eax
    mov al, '0'
    call putc
    mov al, 'x'
    call putc
    pop eax
    jmp hex8_bare
hex4_prefixed:
    push eax
    mov al, '0'
    call putc
    mov al, 'x'
    call putc
    pop eax
    jmp hex4

section .data
digits:     db "0123456789abcdef"
s_class:    db " class ", 0
s_bar:      db "  bar ", 0
s_colon:    db ": ", 0
s_memory:   db "memory ", 0
s_memory64: db "memory64 ", 0
s_io:       db "io ", 0
s_size:     db ", ", 0
s_bytes:    db " bytes", 0
s_none:     db "no MCFG table: no ECAM", 13, 10, 0
crlf:       db 13, 10, 0

section .bss
alignb 4
ecam:     resd 1
original: resd 1
command:  resw 1
alignb 16
stack:    resb 4096
stack_top:
