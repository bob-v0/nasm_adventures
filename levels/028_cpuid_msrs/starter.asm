; Level 28 — CPUID & MSRs
;
; Before a kernel switches to 64-bit mode it asks the CPU whether it can. Report, on the
; serial port, one line each (hex as 0x%08x, lowercase):
;
;     vendor: GenuineIntel
;     max leaf: 0x0000000d
;     max extended leaf: 0x80000008
;     pae: yes
;     apic: yes
;     long mode: yes
;     nx: yes
;     1g pages: no
;     efer: 0x00000800
;
; The last line: EFER (MSR 0xC0000080) after you've turned on NXE (bit 11), if the CPU
; has NX. A CPU without long mode gets, instead of the efer line:
;     this CPU can't run a 64-bit kernel
;
; Helpers below: puts (esi = string), putc (al), hex (eax, then a new line),
; yes_no (esi = label, CF = the bit: `bt edx, 6` sets CF to bit 6). The vendor has no
; new line of its own: s_max starts with the one that ends the vendor line.

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
    ; your code

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
