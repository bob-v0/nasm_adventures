; Level 3 — Bug: Lifetime Across CPUs (reference)

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
NODES      equ 16                   ; the list's length, always
UPDATES    equ 400
LIVE       equ 0x11FE11FE           ; a node in use says so
POISON     equ 0xDEADDEAD           ; a freed one says this
N_MAGIC    equ 0                    ; a node: magic, value, next
N_VALUE    equ 4
N_NEXT     equ 8
N_SIZE     equ 16

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
    call build_list
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
    ; the updates: take the second node out of the list, free it, and put a new one in
    ; front (the new one: the next free node)
    mov ebx, 1
.update:
    mov esi, [head]                 ; the first node...
    mov edi, [esi + N_NEXT]         ; ...and the one after it goes
    mov eax, [edi + N_NEXT]
    mov [esi + N_NEXT], eax         ; unlinked: from now on, nobody can find it
    call wait_for_readers           ; a reader may still be on it: wait until none can be
    call free_node                  ; edi
    call new_node                   ; edi = a node to use
    mov dword [edi + N_MAGIC], LIVE
    mov [edi + N_VALUE], ebx
    mov eax, [head]
    mov [edi + N_NEXT], eax         ; it's complete before anyone can see it...
    mov [head], edi                 ; ...and then it's in (x86: stores stay in order)
    inc ebx
    cmp ebx, UPDATES
    jbe .update
    mov byte [stop], 1
.wait_done:
    pause
    mov eax, [finished]
    inc eax
    cmp eax, [cpus]
    jb .wait_done
    mov esi, s_updates
    call puts
    mov eax, UPDATES
    call decimal
    mov esi, s_freed
    call puts
    mov eax, [freed_seen]
    call decimal
    call newline
    cli
    hlt

; wait_for_readers: a grace period. Every reader that might have been on the node when it
; was unlinked has finished that walk once its count of walks moves on.
wait_for_readers:
    mov ecx, 1
.copy:
    mov eax, [quiet + ecx * 4]
    mov [snapshot + ecx * 4], eax
    inc ecx
    cmp ecx, [cpus]
    jb .copy
    mov ecx, 1
.each:
    cmp ecx, [cpus]
    jae .done
.wait:
    mov eax, [quiet + ecx * 4]
    cmp eax, [snapshot + ecx * 4]
    jne .next
    pause
    jmp .wait
.next:
    inc ecx
    jmp .each
.done:
    ret

; free_node(edi): poison it, and onto the free list
free_node:
    mov dword [edi + N_MAGIC], POISON
    mov eax, [free_list]
    mov [edi + N_NEXT], eax
    mov [free_list], edi
    ret

; new_node: edi = a node from the free list
new_node:
    mov edi, [free_list]
    mov eax, [edi + N_NEXT]
    mov [free_list], eax
    ret

build_list:                         ; NODES live nodes in a list; the rest free
    mov edi, nodes
    xor ecx, ecx
.node:
    lea eax, [edi + N_SIZE]
    mov dword [edi + N_MAGIC], LIVE
    mov [edi + N_VALUE], ecx
    mov [edi + N_NEXT], eax
    add edi, N_SIZE
    inc ecx
    cmp ecx, NODES
    jb .node
    mov dword [edi - N_SIZE + N_NEXT], 0
    mov dword [head], nodes
    mov ecx, 8                      ; a few spare ones
.spare:
    call free_node
    add edi, N_SIZE
    loop .spare
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
.walk:                              ; walk the list, no lock: readers never write it
    mov esi, [head]
    mov ecx, NODES * 2              ; (a bound: a broken list mustn't hold us forever)
.node:
    test esi, esi
    jz .walked
    cmp dword [esi + N_MAGIC], LIVE
    je .live
    lock inc dword [freed_seen]     ; a freed node, reached through the list
.live:
    mov eax, [esi + N_VALUE]        ; (looking at it takes a moment)
    imul eax, eax, 31
    add [checksums + ebx * 4], eax
    mov esi, [esi + N_NEXT]
    loop .node
.walked:
    inc dword [quiet + ebx * 4]     ; between walks: holding no node
    cmp byte [stop], 0
    je .walk
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
s_updates: db "updates: ", 0
s_freed:   db ", freed nodes seen: ", 0
crlf:    db 13, 10, 0

section .bss
alignb 4
cpus:        resd 1
up:          resd 1
next_cpu:    resd 1
serial_lock: resd 1
head:        resd 1
free_list:   resd 1
stop:        resd 1
finished:    resd 1
freed_seen:  resd 1
checksums:   resd MAX_CPUS + 1
quiet:       resd MAX_CPUS + 1      ; each CPU's walks so far (it holds no node between)
snapshot:    resd MAX_CPUS + 1
alignb 16
nodes:       resb N_SIZE * (NODES + 8)
alignb 16
stack:       resb STACK_SIZE
stack_top:
ap_stacks:   resb STACK_SIZE * (MAX_CPUS + 1)
