; Level 4 — Bug: TLB Shootdown Race (reference)

bits 32

MB_FLAGS   equ 1 << 0 | 1 << 1
APIC       equ 0xFEE00000
APIC_ID    equ 0x20
APIC_EOI   equ 0xB0
APIC_SVR   equ 0xF0
ICR_LOW    equ 0x300
ICR_HIGH   equ 0x310
TRAMPOLINE equ 0x8000
STACK_SIZE equ 4096
MAX_CPUS   equ 16
ROUNDS     equ 300
WINDOW     equ 0x300000             ; one page, remapped round after round
FRAME_A    equ 0x380000             ; the two frames it alternates between
FRAME_B    equ 0x381000
SHOOTDOWN  equ 0xF0                 ; the IPI's vector

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
    call count_cpus
    call build_tables
    call paging_on
    mov eax, shootdown              ; the IDT: just the shootdown's gate
    mov [idt + SHOOTDOWN * 8], ax
    mov word [idt + SHOOTDOWN * 8 + 2], 0x08
    mov word [idt + SHOOTDOWN * 8 + 4], 0x8E00
    shr eax, 16
    mov [idt + SHOOTDOWN * 8 + 6], ax
    lidt [idt_pointer]
    mov dword [APIC + APIC_SVR], 0x1FF
    mov eax, FRAME_A                ; round 0: frame A, all zeros
    or eax, 3
    mov [page_table + (WINDOW >> 12) * 4], eax
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
    ; the rounds: fill the frame WINDOW isn't showing, all of it, with the round's number,
    ; then show it; the other one is free for the next round
    mov ebx, 1
.round:
    mov edi, FRAME_A
    test ebx, 1
    jz .fill
    mov edi, FRAME_B
.fill:
    push edi
    mov eax, ebx
    mov ecx, 1024
    rep stosd
    pop eax
    or eax, 3
    mov [page_table + (WINDOW >> 12) * 4], eax
    invlpg [WINDOW]
    call shoot_down                 ; nobody uses the old frame any more: it's free
    inc ebx
    cmp ebx, ROUNDS
    jbe .round
    mov byte [stop], 1              ; the end: what did the readers see?
.wait_done:
    pause
    mov eax, [finished]
    inc eax
    cmp eax, [cpus]
    jb .wait_done
    mov esi, s_rounds
    call puts
    mov eax, ROUNDS
    call decimal
    mov esi, s_torn
    call puts
    mov eax, [torn]
    call decimal
    call newline
    cli
    hlt

; the others arrive here, in protected mode, from the trampoline
ap_entry:
    mov ax, 0x10
    mov ds, ax
    mov es, ax
    mov ss, ax
    mov eax, 1
    lock xadd [next_cpu], eax
    inc eax                         ; my number (the BSP is 0)
    mov ebx, eax
    imul eax, eax, STACK_SIZE
    lea esp, [ap_stacks + eax]
    call paging_on                  ; the same page tables as everyone
    lidt [idt_pointer]
    mov dword [APIC + APIC_SVR], 0x1FF
    lock inc dword [up]
.wait_go:
    pause
    cmp byte [go], 0
    je .wait_go
.snapshot:                          ; read the whole window, interrupts off: one round's page
    cli
    mov esi, WINDOW
    mov edx, [esi]
    mov ecx, 1024
.word:
    cmp [esi], edx
    jne .torn
    add esi, 4
    loop .word
    jmp .whole
.torn:                              ; two rounds' numbers in one page: the frame changed
    lock inc dword [torn]           ; under our feet
.whole:
    sti                             ; (between snapshots: the shootdown may come in)
    nop
    cmp byte [stop], 0
    je .snapshot
    lock inc dword [finished]
    cli
.halt:
    hlt
    jmp .halt

; shoot_down: every other CPU forgets WINDOW's translation, and I wait until they have
shoot_down:
    mov dword [acks], 0
    mov dword [APIC + ICR_HIGH], 0
    mov dword [APIC + ICR_LOW], 0x000C0000 | SHOOTDOWN   ; everyone but me, fixed
    call wait_sent
.wait:                              ; until every one of them has: before that, some CPU
    pause                           ; may still read the old frame, which we're about to
    mov eax, [acks]                 ; reuse
    inc eax
    cmp eax, [cpus]
    jb .wait
    ret

shootdown:                          ; the IPI, on every other CPU
    push eax
    invlpg [WINDOW]
    lock inc dword [acks]
    mov dword [APIC + APIC_EOI], 0
    pop eax
    iret

; build_tables: 32-bit paging: the first 4 MiB in 4 KiB pages (so WINDOW can be
; remapped alone), and the APICs' 4 MiB (0xFEC00000 up) as one large page
build_tables:
    xor ecx, ecx
.pte:
    mov eax, ecx
    shl eax, 12
    or eax, 3
    mov [page_table + ecx * 4], eax
    inc ecx
    cmp ecx, 1024
    jb .pte
    mov eax, page_table
    or eax, 3
    mov [page_dir], eax
    mov dword [page_dir + (0xFEC00000 >> 22) * 4], 0xFEC00000 | 0x83 | 0x18   ; PS, PCD, PWT
    ret

paging_on:
    mov eax, cr4
    or eax, 1 << 4                  ; PSE: large pages
    mov cr4, eax
    mov eax, page_dir
    mov cr3, eax
    mov eax, cr0
    or eax, 1 << 31
    mov cr0, eax
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



; ---- the trampoline (level 7) ----

bits 16
trampoline:
    cli
    xor ax, ax
    mov ds, ax
    o32 lgdt [TRAMPOLINE + (t_gdt_pointer - trampoline)]
    mov eax, cr0
    or eax, 1
    mov cr0, eax
    jmp dword 0x08:ap_entry
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
idt_pointer:
    dw 256 * 8 - 1
    dd idt
digits:    db "0123456789abcdef"
s_rounds:  db "rounds: ", 0
s_torn:    db ", torn reads: ", 0
crlf:      db 13, 10, 0

section .bss
alignb 4096
page_dir:   resd 1024
page_table: resd 1024
alignb 8
idt:        resq 256
cpus:       resd 1
up:         resd 1
next_cpu:   resd 1
go:         resd 1
acks:       resd 1
torn:       resd 1
stop:       resd 1
finished:   resd 1
alignb 16
stack:      resb STACK_SIZE
stack_top:
ap_stacks:  resb STACK_SIZE * (MAX_CPUS + 1)
