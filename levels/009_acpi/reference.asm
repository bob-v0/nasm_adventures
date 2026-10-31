; Level 9 — ACPI (reference)

bits 32

MB_FLAGS equ 1 << 0 | 1 << 1

section .multiboot
align 4
    dd 0x1BADB002, MB_FLAGS, -(0x1BADB002 + MB_FLAGS)

section .text
global _start
_start:
    mov esp, stack_top
    call find_rsdp                  ; esi = the RSDP, or 0
    test esi, esi
    jz .none
    ; the root table: the XSDT (64-bit pointers) if revision >= 2, else the RSDT
    cmp byte [esi + 15], 2
    jb .rsdt
    mov ebx, [esi + 24]             ; (the XSDT's address: below 4 GiB here)
    mov dword [entry_size], 8
    jmp .root
.rsdt:
    mov ebx, [esi + 16]
    mov dword [entry_size], 4
.root:
    ; its entries: the other tables; find "APIC", the MADT
    mov ecx, [ebx + 4]              ; length
    sub ecx, 36                     ; (the header)
    lea esi, [ebx + 36]
.table:
    test ecx, ecx
    jz .none
    mov edi, [esi]
    cmp dword [edi], 'APIC'
    je .madt
    add esi, [entry_size]
    sub ecx, [entry_size]
    jmp .table
.madt:
    ; the MADT: header (36), local APIC address (4), flags (4), then entries:
    ; type (1), length (1), ...
    mov ebx, edi
    mov ecx, [ebx + 4]
    add ecx, ebx                    ; the end
    lea esi, [ebx + 44]
.count:                             ; first, how many enabled CPUs
    cmp esi, ecx
    jae .counted
    cmp byte [esi], 0
    jne .count_next
    test byte [esi + 4], 1          ; enabled
    jz .count_next
    inc dword [cpus]
.count_next:
    movzx eax, byte [esi + 1]
    add esi, eax
    jmp .count
.counted:
    push ecx
    mov esi, s_cpus
    call puts
    mov eax, [cpus]
    call decimal
    call newline
    pop ecx
    lea esi, [ebx + 44]
.entry:
    cmp esi, ecx
    jae .done
    movzx eax, byte [esi]
    cmp eax, 0
    je .cpu
    cmp eax, 1
    je .ioapic
    cmp eax, 2
    je .override
.next:
    movzx eax, byte [esi + 1]
    add esi, eax
    jmp .entry
.cpu:                               ; processor local APIC: uid (2), APIC id (3), flags (4)
    test byte [esi + 4], 1
    jz .next
    push esi
    push ecx
    push esi
    mov esi, s_cpu
    call puts
    pop esi
    movzx eax, byte [esi + 3]
    call decimal
    call newline
    pop ecx
    pop esi
    jmp .next
.ioapic:                            ; I/O APIC: id (2), address (4), GSI base (8)
    push esi
    push ecx
    push esi
    mov esi, s_ioapic
    call puts
    mov esi, [esp]
    movzx eax, byte [esi + 2]
    call decimal
    mov esi, s_at
    call puts
    mov esi, [esp]
    mov eax, [esi + 4]
    call hex
    mov esi, s_gsi
    call puts
    pop esi
    mov eax, [esi + 8]
    call decimal
    call newline
    pop ecx
    pop esi
    jmp .next
.override:                          ; ISA override: bus (2), IRQ (3), GSI (4), flags (8)
    push esi
    push ecx
    push esi
    mov esi, s_irq
    call puts
    mov esi, [esp]
    movzx eax, byte [esi + 3]
    call decimal
    mov esi, s_to
    call puts
    mov esi, [esp]
    mov eax, [esi + 4]
    call decimal
    mov esi, s_flags
    call puts
    pop esi
    movzx eax, word [esi + 8]
    call hex
    call newline
    pop ecx
    pop esi
    jmp .next
.none:
    mov esi, s_none
    call puts
.done:
    cli
    hlt

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
