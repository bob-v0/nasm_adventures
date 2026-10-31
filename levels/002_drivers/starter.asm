; Level 2 — Drivers
;
; A disk the BIOS knows nothing about: a virtio-blk device on the PCI bus (the legacy
; interface, through its I/O BAR). Write its driver, interrupt-driven: a request goes into
; the device's queue, the CPU sleeps (hlt), and the device's interrupt (MSI-X, straight to
; this CPU's APIC) says it's done.
;
; With it, the kernel (done for you) reads the disk's tiny filesystem: sector 0 lists the
; files; it prints the list, then each file named on the command line.
;
; Yours: find_disk, virtio_init, read_sectors, disk_irq. Done: config_read / config_write
; (PCI configuration space through ports 0xCF8 / 0xCFC: [config] = 0x80000000 | device << 11,
; edx = offset), the IDT (DISK_VECTOR goes to disk_irq), the APIC, the rest.

bits 32

MB_FLAGS   equ 1 << 0 | 1 << 1
APIC       equ 0xFEE00000
APIC_EOI   equ 0xB0
APIC_SVR   equ 0xF0
DISK_VECTOR equ 0x50
QSIZE_MAX  equ 256
; legacy virtio, through the I/O BAR (with MSI-X on, device config starts at 24)
V_FEATURES equ 0
V_GUEST    equ 4
V_QADDR    equ 8                    ; the queue's page number
V_QSIZE    equ 12
V_QSELECT  equ 14
V_NOTIFY   equ 16
V_STATUS   equ 18
V_ISR      equ 19
V_CONF_VEC equ 20
V_Q_VEC    equ 22
SECTORS_PER_READ equ 8

section .multiboot
align 4
    dd 0x1BADB002, MB_FLAGS, -(0x1BADB002 + MB_FLAGS)

section .text
global _start, requests, completions
_start:
    mov esp, stack_top
    mov [boot_info], ebx
    lgdt [gdt_pointer]
    jmp 0x08:.flat
.flat:
    mov ax, 0x10
    mov ds, ax
    mov es, ax
    mov ss, ax
    call silence_pic
    mov eax, disk_irq
    mov ecx, DISK_VECTOR
    call set_gate
    mov eax, spurious
    mov ecx, 0xFF
    call set_gate
    lidt [idt_pointer]
    mov dword [APIC + APIC_SVR], 0x1FF
    call find_disk                  ; [io] = its I/O ports, the MSI-X table set up
    test eax, eax
    jz .no_disk
    call virtio_init
    sti
    ; the directory: sector 0
    mov eax, 0
    mov ecx, 1
    mov edi, directory
    call read_sectors
    cmp dword [directory], 'RING'
    jne .no_fs
    mov esi, s_files
    call puts
    mov eax, [directory + 8]
    call decimal
    call newline
    mov ebx, directory + 16
    mov ecx, [directory + 8]
.list:
    jecxz .listed
    push ecx
    mov esi, s_indent
    call puts
    mov esi, ebx
    call puts
    mov al, ' '
    call putc
    mov eax, [ebx + 36]
    call decimal
    mov esi, s_bytes
    call puts
    pop ecx
    add ebx, 48
    dec ecx
    jmp .list
.listed:
    ; the files named on the command line, one after another
    mov ebx, [boot_info]
    mov esi, [ebx + 16]
.skip_kernel:                       ; (the first word is the kernel's own name)
    lodsb
    test al, al
    jz .done
    cmp al, ' '
    jne .skip_kernel
.word:
    cmp byte [esi], ' '
    jne .start
    inc esi
    jmp .word
.start:
    cmp byte [esi], 0
    je .done
    mov edi, name
.copy:
    lodsb
    cmp al, ' '
    je .copied
    test al, al
    jz .last
    stosb
    jmp .copy
.last:
    dec esi
.copied:
    mov byte [edi], 0
    push esi
    call cat
    pop esi
    jmp .word
.done:
    cli
    hlt
.no_disk:
    mov esi, s_no_disk
    call puts
    jmp .done
.no_fs:
    mov esi, s_no_fs
    call puts
    jmp .done

; cat: print the file called [name]
cat:
    mov ebx, directory + 16
    mov ecx, [directory + 8]
.find:
    jecxz .missing
    mov esi, ebx
    mov edi, name
.cmp:
    mov al, [esi]
    cmp al, [edi]
    jne .next
    test al, al
    jz .found
    inc esi
    inc edi
    jmp .cmp
.next:
    add ebx, 48
    dec ecx
    jmp .find
.missing:
    mov esi, name
    call puts
    mov esi, s_missing
    call puts
    ret
.found:
    mov esi, s_head
    call puts
    mov esi, name
    call puts
    mov esi, s_tail
    call puts
    mov ebp, [ebx + 36]             ; bytes left
    mov edx, [ebx + 32]             ; the next sector
.chunk:
    test ebp, ebp
    jz .end
    mov ecx, ebp                    ; as many sectors as are left, at most SECTORS_PER_READ
    add ecx, 511
    shr ecx, 9
    cmp ecx, SECTORS_PER_READ
    jbe .count
    mov ecx, SECTORS_PER_READ
.count:
    mov eax, edx
    mov edi, buffer
    push edx
    call read_sectors
    pop edx
    cmp byte [status], 0            ; the device's verdict: 0 = done
    jne .failed
    add edx, SECTORS_PER_READ
    mov ecx, SECTORS_PER_READ * 512
    cmp ecx, ebp
    jbe .print
    mov ecx, ebp
.print:
    sub ebp, ecx
    mov esi, buffer
.byte:
    lodsb
    call putc
    loop .byte
    jmp .chunk
.end:
    ret
.failed:
    mov esi, s_failed
    call puts
    ret

; ---- the disk -------------------------------------------------------------------------

; find_disk: the virtio-blk device (1af4:1001, legacy) on bus 0; its I/O ports in [io];
; its MSI-X table entry 0 pointed at this CPU, vector DISK_VECTOR. eax = 0: not found.
find_disk:
    xor eax, eax                    ; yours
    ret
config_read:                        ; eax = the dword at offset edx of [config]
    push edx
    mov eax, [config]
    or eax, edx
    mov dx, 0xCF8
    out dx, eax
    mov dx, 0xCFC
    in eax, dx
    pop edx
    ret

config_write:                       ; the dword at offset edx of [config] = eax
    push edx
    push eax
    mov eax, [config]
    or eax, edx
    mov dx, 0xCF8
    out dx, eax
    pop eax
    mov dx, 0xCFC
    out dx, eax
    pop edx
    ret

; virtio_init: reset, acknowledge, no features, queue 0 set up, its interrupts to MSI-X
; entry 0, ready
virtio_init:
    ret                             ; yours
; read_sectors(eax = first sector, ecx = how many, edi = where): one request, three
; descriptors (header, data, status), then sleep until the device's interrupt says done
read_sectors:
    ret                             ; yours
disk_irq:
    iret                            ; yours
spurious:
    iret

silence_pic:
    mov al, 0x11
    out 0x20, al
    out 0xA0, al
    mov al, 0x20
    out 0x21, al
    mov al, 0x28
    out 0xA1, al
    mov al, 0x04
    out 0x21, al
    mov al, 0x02
    out 0xA1, al
    mov al, 0x01
    out 0x21, al
    out 0xA1, al
    mov al, 0xFF
    out 0x21, al
    out 0xA1, al
    ret

set_gate:                           ; ecx = vector, eax = handler
    mov [idt + ecx * 8], ax
    mov word [idt + ecx * 8 + 2], 0x08
    mov word [idt + ecx * 8 + 4], 0x8E00
    shr eax, 16
    mov [idt + ecx * 8 + 6], ax
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
s_files:   db "files: ", 0
s_indent:  db "  ", 0
s_bytes:   db " bytes", 13, 10, 0
s_head:    db "== ", 0
s_tail:    db " ==", 13, 10, 0
s_missing: db ": no such file", 13, 10, 0
s_no_disk: db "no virtio disk", 13, 10, 0
s_no_fs:   db "no filesystem on the disk", 13, 10, 0
s_failed:  db 13, 10, "the disk said no", 13, 10, 0
crlf:      db 13, 10, 0

section .bss
alignb 4
boot_info:   resd 1
config:      resd 1
io:          resd 1
qsize:       resd 1
avail:       resd 1
used:        resd 1
requests:    resd 1
completions: resd 1
seen_used:   resd 1
alignb 16
request:     resb 16
status:      resb 1
name:        resb 64
alignb 8
idt:         resq 256
alignb 4096
queue:       resb 4096 * 3          ; descriptors and available ring, then the used ring
directory:   resb 512
buffer:      resb SECTORS_PER_READ * 512
alignb 16
stack:       resb 8192
stack_top:
