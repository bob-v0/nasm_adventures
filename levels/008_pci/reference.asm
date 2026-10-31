; Level 8 — PCI (reference)

bits 32

MB_FLAGS equ 1 << 0 | 1 << 1

section .multiboot
align 4
    dd 0x1BADB002, MB_FLAGS, -(0x1BADB002 + MB_FLAGS)

section .text
global _start
_start:
    mov esp, stack_top
    call find_mcfg                  ; [ecam] = the configuration space's base
    cmp dword [ecam], 0
    je .none
    xor ebx, ebx                    ; bus 0: devices 0-31, functions 0-7
.device:
    xor ecx, ecx
.function:
    mov eax, ebx
    shl eax, 15
    mov edx, ecx
    shl edx, 12
    or eax, edx
    add eax, [ecam]
    mov edi, eax                    ; this function's 4 KiB of configuration space
    cmp word [edi], 0xFFFF          ; vendor 0xFFFF: nobody there
    je .absent
    call show
    test ecx, ecx                   ; function 0 says if there are more (header type bit 7)
    jnz .next_function
    test byte [edi + 14], 0x80
    jz .next_device
.next_function:
    inc ecx
    cmp ecx, 8
    jb .function
    jmp .next_device
.absent:
    test ecx, ecx
    jz .next_device                 ; (no function 0: no device)
    jmp .next_function
.next_device:
    inc ebx
    cmp ebx, 32
    jb .device
    jmp .done
.none:
    mov esi, s_none
    call puts
.done:
    cli
    hlt

; show(edi = configuration space, ebx = device, ecx = function)
show:
    pushad
    mov eax, 0                      ; "bb:dd.f vvvv:dddd class cc.ss.pp"
    call hex2
    mov al, ':'
    call putc
    mov eax, ebx
    call hex2
    mov al, '.'
    call putc
    mov eax, ecx
    add al, '0'
    call putc
    mov al, ' '
    call putc
    movzx eax, word [edi]
    call hex4
    mov al, ':'
    call putc
    movzx eax, word [edi + 2]
    call hex4
    mov esi, s_class
    call puts
    movzx eax, byte [edi + 11]
    call hex2
    mov al, '.'
    call putc
    movzx eax, byte [edi + 10]
    call hex2
    mov al, '.'
    call putc
    movzx eax, byte [edi + 9]
    call hex2
    call newline
    ; the BARs: 6 for an ordinary device (header type 0), 2 for a bridge (1)
    mov al, [edi + 14]
    and al, 0x7F
    mov ebp, 6
    cmp al, 0
    je .bars
    mov ebp, 2
    cmp al, 1
    je .bars
    jmp .out
.bars:
    mov ax, [edi + 4]               ; the command register: decoding off while probing
    mov [command], ax
    and word [edi + 4], ~3
    xor ebx, ebx                    ; BAR number
.bar:
    cmp ebx, ebp
    jae .bars_done
    lea esi, [edi + 0x10 + ebx * 4]
    mov eax, [esi]                  ; probe: write all ones, see which bits stick
    mov [original], eax
    mov dword [esi], 0xFFFFFFFF
    mov edx, [esi]
    mov eax, [original]
    mov [esi], eax
    test eax, 1
    jnz .io
    ; memory: type in bits 1-2 (2: 64-bit, two BARs), address bits 4 up
    and edx, ~0xF
    jz .next_bar                    ; (nothing implemented: no BAR)
    mov ecx, eax
    and ecx, 6
    cmp ecx, 4
    je .bar64
    neg edx                         ; size = ~mask + 1
    push edx
    push eax
    call bar_head
    mov esi, s_memory
    call puts
    pop eax
    and eax, ~0xF
    call hex8
    jmp .size
.bar64:
    neg edx
    push edx
    push eax
    call bar_head
    mov esi, s_memory64
    call puts
    lea esi, [edi + 0x14 + ebx * 4] ; the high half: the next BAR
    mov eax, [esi]
    call hex8
    pop eax
    and eax, ~0xF
    call hex8_bare
    inc ebx                         ; (it used two)
    jmp .size
.io:
    and edx, ~3
    and edx, 0xFFFF
    jz .next_bar
    neg edx
    and edx, 0xFFFF
    push edx
    push eax
    call bar_head
    mov esi, s_io
    call puts
    pop eax
    and eax, ~3
    call hex4_prefixed
.size:
    mov esi, s_size
    call puts
    pop eax
    call decimal
    mov esi, s_bytes
    call puts
    call newline
.next_bar:
    inc ebx
    jmp .bar
.bars_done:
    mov ax, [command]
    mov [edi + 4], ax
.out:
    popad
    ret

bar_head:                           ; "  bar N: "
    push eax
    mov esi, s_bar
    call puts
    mov eax, ebx
    call decimal
    mov esi, s_colon
    call puts
    pop eax
    ret

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
