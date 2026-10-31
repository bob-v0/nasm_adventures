; Level 1 — Bug: Heisenbug
;
; Objects with reference counts: every CPU takes references to them, uses them, lets
; them go, 200000 times; at the end the table drops its own reference to each, and each
; must be freed then, exactly once. A freed object is poisoned; using one is counted.
;
; Run with the CPUs one at a time (QEMU's usual mode), it's perfect. With them truly in
; parallel, objects are freed while in use, or never. Find the race; fix it. At most 4
; changed lines.

bits 32

MB_FLAGS   equ 1 << 0 | 1 << 1
APIC       equ 0xFEE00000
APIC_ID    equ 0x20
APIC_SVR   equ 0xF0
ICR_LOW    equ 0x300
ICR_HIGH   equ 0x310
TRAMPOLINE equ 0x8000           ; where the other CPUs start: page 8 (the SIPI's vector)
STACK_SIZE equ 4096
MAX_CPUS   equ 16
OBJECTS    equ 64
ROUNDS     equ 200000
LIVE       equ 0x11FE11FE
POISON     equ 0xDEADDEAD
O_REFS     equ 0                    ; an object: its references, its magic
O_MAGIC    equ 4
O_SIZE     equ 8

section .multiboot
align 4
    dd 0x1BADB002, MB_FLAGS, -(0x1BADB002 + MB_FLAGS)

section .text
global _start
_start:
    mov esp, stack_top
    lgdt [gdt_pointer]
    jmp 0x08:.flat
.flat:
    mov ax, 0x10
    mov ds, ax
    mov es, ax
    mov ss, ax
    call count_cpus                 ; [cpus] = the enabled CPUs in the MADT
    mov dword [APIC + APIC_SVR], 0x1FF
    ; every object starts with one reference: the table's
    xor ecx, ecx
.object:
    mov dword [objects + ecx * O_SIZE + O_REFS], 1
    mov dword [objects + ecx * O_SIZE + O_MAGIC], LIVE
    inc ecx
    cmp ecx, OBJECTS
    jb .object
    ; wake the others (level 7)
    mov esi, trampoline
    mov edi, TRAMPOLINE
    mov ecx, trampoline_end - trampoline
    rep movsb
    mov dword [APIC + ICR_HIGH], 0
    mov dword [APIC + ICR_LOW], 0x000C4500
    call wait_sent
    mov ecx, 10000
    call delay_us
    mov dword [APIC + ICR_LOW], 0x000C4600 | (TRAMPOLINE >> 12)
    call wait_sent
    mov ecx, 200
    call delay_us
    mov dword [APIC + ICR_LOW], 0x000C4600 | (TRAMPOLINE >> 12)
    call wait_sent
.wait_up:
    mov eax, [up]
    inc eax
    cmp eax, [cpus]
    jb .wait_up
    mov byte [go], 1
    xor ebx, ebx
    call use_objects                ; me too
.wait_done:
    pause
    mov eax, [finished]
    inc eax
    cmp eax, [cpus]
    jb .wait_done
    ; the end: the table lets go of every object; each must be freed now, exactly now
    xor ecx, ecx
.release:
    lea edi, [objects + ecx * O_SIZE]
    call put
    inc ecx
    cmp ecx, OBJECTS
    jb .release
    mov esi, s_objects
    call puts
    mov eax, OBJECTS
    call decimal
    mov esi, s_freed
    call puts
    mov eax, [freed]
    call decimal
    mov esi, s_uaf
    call puts
    mov eax, [used_freed]
    call decimal
    call newline
    cli
    hlt

; use_objects (ebx = my number): ROUNDS times, take a reference to an object, use it,
; let it go
use_objects:
    mov ecx, ROUNDS
.round:
    mov eax, ecx                    ; which object: they all get shared around
    add eax, ebx
    and eax, OBJECTS - 1
    lea edi, [objects + eax * O_SIZE]
    call get
    cmp dword [edi + O_MAGIC], LIVE
    je .live
    lock inc dword [used_freed]     ; it's been freed while we hold a reference to it
.live:
    call put
    loop .round
    ret

get:                                ; edi = an object: one more reference
    inc dword [edi + O_REFS]
    ret

put:                                ; edi = an object: one fewer; the last one frees it
    dec dword [edi + O_REFS]
    jnz .still_used
    mov dword [edi + O_MAGIC], POISON
    lock inc dword [freed]
.still_used:
    ret

; the others arrive here
ap_entry:
    mov ax, 0x10
    mov ds, ax
    mov es, ax
    mov ss, ax
    mov eax, 1
    lock xadd [next_cpu], eax
    inc eax
    mov ebx, eax                    ; my number
    imul eax, eax, STACK_SIZE
    lea esp, [ap_stacks + eax]
    lock inc dword [up]
.wait_go:
    pause
    cmp byte [go], 0
    je .wait_go
    call use_objects
    lock inc dword [finished]
    cli
.halt:
    hlt
    jmp .halt

lock_serial:                        ; a spinlock: xchg is atomic, and a full barrier
.try:
    mov eax, 1
    xchg eax, [serial_lock]
    test eax, eax
    jz .mine
.spin:
    pause
    cmp dword [serial_lock], 0
    jne .spin
    jmp .try
.mine:
    ret

unlock_serial:
    mov dword [serial_lock], 0
    ret

wait_sent:                          ; until the ICR's delivery status (bit 12) clears
    pause
    test dword [APIC + ICR_LOW], 1 << 12
    jnz wait_sent
    ret

delay_us:                           ; ecx microseconds, by the PIT's channel 2
    push eax
    push ecx
    imul ecx, ecx, 1193
    add ecx, 999
    mov eax, ecx
    xor edx, edx
    mov ecx, 1000
    div ecx                         ; PIT ticks (1.193182 MHz), at most 65535 at a time
.chunk:
    mov ecx, eax
    cmp ecx, 65535
    jbe .last
    mov ecx, 65535
.last:
    sub eax, ecx
    push eax
    in al, 0x61
    and al, 0xFC
    or al, 1
    out 0x61, al
    mov al, 0xB0
    out 0x43, al
    mov al, cl
    out 0x42, al
    mov al, ch
    out 0x42, al
.pit:
    in al, 0x61
    test al, 0x20
    jz .pit
    pop eax
    test eax, eax
    jnz .chunk
    pop ecx
    pop eax
    ret

; count_cpus: [cpus] = how many enabled processors the MADT lists (level 9)
count_cpus:
    call find_rsdp
    mov dword [cpus], 1
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
    cmp dword [edi], 'APIC'
    je .madt
    add esi, edx
    sub ecx, edx
    jmp .table
.madt:
    mov dword [cpus], 0
    mov ecx, [edi + 4]
    add ecx, edi
    lea esi, [edi + 44]
.entry:
    cmp esi, ecx
    jae .out
    cmp byte [esi], 0
    jne .next
    test byte [esi + 4], 1
    jz .next
    inc dword [cpus]
.next:
    movzx eax, byte [esi + 1]
    add esi, eax
    jmp .entry
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


; ---- the trampoline: copied to TRAMPOLINE, where a woken CPU starts, in real mode ----
; (its own addresses are TRAMPOLINE + (label - trampoline): it runs away from where
; it was linked)

bits 16
trampoline:
    cli
    xor ax, ax
    mov ds, ax
    o32 lgdt [TRAMPOLINE + (t_gdt_pointer - trampoline)]
    mov eax, cr0
    or eax, 1                       ; protected mode
    mov cr0, eax
    jmp dword 0x08:ap_entry         ; (the kernel's code, at its own address)
align 4
t_gdt_pointer:
    dw gdt_end - gdt - 1
    dd gdt
trampoline_end:
bits 32

section .data
align 8
gdt:
    dq 0
    dq 0x00CF9A000000FFFF
    dq 0x00CF92000000FFFF
gdt_end:
gdt_pointer:
    dw gdt_end - gdt - 1
    dd gdt
digits:  db "0123456789abcdef"
s_objects: db "objects: ", 0
s_freed:   db ", freed at the end: ", 0
s_uaf:     db ", used after free: ", 0
crlf:    db 13, 10, 0

section .bss
alignb 4
cpus:        resd 1
up:          resd 1
next_cpu:    resd 1
serial_lock: resd 1
go:          resd 1
finished:    resd 1
freed:       resd 1
used_freed:  resd 1
alignb 8
objects:     resb O_SIZE * OBJECTS
alignb 16
stack:       resb STACK_SIZE
stack_top:
ap_stacks:   resb STACK_SIZE * (MAX_CPUS + 1)
