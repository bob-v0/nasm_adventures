; Level 9 — ACPI
;
; How many CPUs does this machine have, and where are its interrupt controllers? The
; firmware says so, in ACPI tables. Find them and report the MADT, on the serial port:
;
;     cpus: 4                       (the enabled processors)
;     cpu: apic id 0                (each enabled processor's APIC id, in table order)
;     ...
;     io apic: id 0, address 0xfec00000, gsi base 0
;     override: irq 0 -> gsi 2, flags 0x00000000
;
; one line per entry, in the order the table has them (CPUs, I/O APICs, overrides; other
; entries: nothing). Paging is off: every physical address is usable as it is.
; Helpers: puts (esi), decimal (eax), hex (eax: 0x%08x), newline.

bits 32

MB_FLAGS equ 1 << 0 | 1 << 1

section .multiboot
align 4
    dd 0x1BADB002, MB_FLAGS, -(0x1BADB002 + MB_FLAGS)

section .text
global _start
_start:
    mov esp, stack_top
    ; your code: find the RSDP, its root table, the MADT; report it

    cli
    hlt

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

section .data
digits:   db "0123456789abcdef"
s_cpus:   db "cpus: ", 0
s_cpu:    db "cpu: apic id ", 0
s_ioapic: db "io apic: id ", 0
s_at:     db ", address ", 0
s_gsi:    db ", gsi base ", 0
s_irq:    db "override: irq ", 0
s_to:     db " -> gsi ", 0
s_flags:  db ", flags ", 0
s_none:   db "no ACPI tables found", 13, 10, 0
crlf:     db 13, 10, 0

section .bss
alignb 4
cpus:       resd 1
entry_size: resd 1
alignb 16
stack:      resb 4096
stack_top:
