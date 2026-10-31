; Level 27 — Physical Memory (reference)

bits 32

MB_FLAGS   equ 1 << 0 | 1 << 1
FRAMES     equ 1 << 20          ; 4 GiB of 4 KiB frames: one bit each
MODULE     equ 0x80000          ; where the game's test runs

section .multiboot
align 4
    dd 0x1BADB002, MB_FLAGS, -(0x1BADB002 + MB_FLAGS)

section .text
global _start, alloc_frame, free_frame
extern kernel_end
_start:
    mov esp, stack_top
    mov [boot_info], ebx
    call init_frames
    ; the game's test: the first module, copied to MODULE and called
    mov ebx, [boot_info]
    mov esi, [ebx + 24]
    mov ecx, [esi + 4]
    mov esi, [esi]
    sub ecx, esi
    mov edi, MODULE
    rep movsb
    mov eax, alloc_frame
    mov edx, free_frame
    mov ecx, [boot_info]
    mov ebx, kernel_end
    mov esi, MODULE             ; (through a register: see the brief)
    call esi
    cli
    hlt

; The bitmap: bit n set = frame n (address n * 4096) is in use, or isn't RAM at all.
init_frames:
    pushad
    mov edi, bitmap             ; everything used...
    mov ecx, FRAMES / 32
    mov eax, 0xFFFFFFFF
    rep stosd
    ; ...except the frames inside available regions of the memory map
    mov ebx, [boot_info]
    mov esi, [ebx + 48]         ; mmap_addr
    mov ebp, esi
    add ebp, [ebx + 44]         ; + mmap_length
.entry:
    cmp esi, ebp
    jae .reserve
    cmp dword [esi + 20], 1     ; type 1: available RAM
    jne .next
    cmp dword [esi + 8], 0      ; (starts above 4 GiB: not ours)
    jne .next
    mov eax, [esi + 4]          ; base
    mov edx, eax
    add edx, [esi + 12]         ; end = base + length
    jnc .fits
    mov edx, 0xFFFFF000         ; (or it runs past 4 GiB)
.fits:
    add eax, 0xFFF              ; whole frames only: round the start up, the end down
    shr eax, 12
    shr edx, 12
.free:
    cmp eax, edx
    jae .next
    btr [bitmap], eax
    inc eax
    jmp .free
.next:
    add esi, [esi]              ; each entry: its size (not counting itself), then the entry
    add esi, 4
    jmp .entry
.reserve:
    ; below 1 MiB, and from 1 MiB to the end of the kernel and its modules: never
    mov edx, kernel_end
    mov ebx, [boot_info]
    test dword [ebx], 1 << 3
    jz .end_known
    mov esi, [ebx + 24]
    mov ecx, [ebx + 20]
    jecxz .end_known
.module:
    cmp [esi + 4], edx
    jbe .next_module
    mov edx, [esi + 4]
.next_module:
    add esi, 16
    loop .module
.end_known:
    add edx, 0xFFF
    shr edx, 12
    xor eax, eax
.used:
    cmp eax, edx
    jae .done
    bts [bitmap], eax
    inc eax
    jmp .used
.done:
    mov dword [search], 0
    popad
    ret

alloc_frame:                    ; eax = a free frame's address, or 0; nothing else changes
    push ecx
    push edx
    mov ecx, [search]           ; dwords before this one are all used
.scan:
    cmp ecx, FRAMES / 32
    jae .none
    mov eax, [bitmap + ecx * 4]
    not eax
    bsf edx, eax                ; the first 0 bit
    jnz .found
    inc ecx
    jmp .scan
.found:
    mov [search], ecx
    shl ecx, 5
    add ecx, edx
    bts [bitmap], ecx
    mov eax, ecx
    shl eax, 12
    pop edx
    pop ecx
    ret
.none:
    mov [search], ecx
    xor eax, eax
    pop edx
    pop ecx
    ret

free_frame:                     ; eax = a frame from alloc_frame; nothing changes
    push eax
    shr eax, 12
    btr [bitmap], eax
    shr eax, 5
    cmp eax, [search]
    jae .out
    mov [search], eax
.out:
    pop eax
    ret

section .bss
alignb 4
boot_info: resd 1
search:    resd 1
bitmap:    resd FRAMES / 32
alignb 16
stack:     resb 8192
stack_top:
