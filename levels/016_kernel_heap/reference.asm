; Level 16 — Kernel Heap (reference)

bits 32

MB_FLAGS equ 1 << 0 | 1 << 1
P        equ 1 << 0
W        equ 1 << 1
PS       equ 1 << 7
NX_HIGH  equ 1 << 31
HIGH     equ 0xFFFFFFFF80000000     ; the higher half: virtual HIGH + x = physical x
EFER     equ 0xC0000080
MODULE   equ 0x80000
FRAMES   equ 1 << 20

section .multiboot
align 4
    dd 0x1BADB002, MB_FLAGS, -(0x1BADB002 + MB_FLAGS)

section .text
global _start
extern kernel_end
_start:
    mov esp, stack_top
    mov [boot_info], ebx
    call init_frames
    ; One PD maps the first 1 GiB, and all three regions share it:
    ;   PML4[0]   -> pdpt_low[0]    -> pd   identity
    ;   PML4[511] -> pdpt_high[510] -> pd   0xFFFFFFFF80000000
    ;   PML4[256] -> pdpt_low[0]    -> pd   0xFFFF800000000000, NX at the PML4 level
    mov dword [pml4 + 0 * 8], pdpt_low + P + W
    mov dword [pml4 + 256 * 8], pdpt_low + P + W
    mov dword [pml4 + 256 * 8 + 4], NX_HIGH
    mov dword [pml4 + 511 * 8], pdpt_high + P + W
    mov dword [pdpt_low + 0 * 8], pd + P + W
    mov dword [pdpt_high + 510 * 8], pd + P + W
    ; the first 2 MiB through a page table, so its first 4 KiB can stay unmapped
    mov dword [pd + 0 * 8], pt + P + W
    mov ecx, 1
.small:
    mov eax, ecx
    shl eax, 12
    or eax, P + W
    mov [pt + ecx * 8], eax
    inc ecx
    cmp ecx, 512
    jb .small
    ; the rest: 2 MiB pages
    mov ecx, 1
.large:
    mov eax, ecx
    shl eax, 21
    or eax, P + W + PS
    mov [pd + ecx * 8], eax
    inc ecx
    cmp ecx, 512
    jb .large
    ; the switch: PAE on, CR3 = the PML4, EFER.LME (and NXE: the direct map uses NX),
    ; then paging on, which (with LME) activates long mode
    mov eax, cr4
    or eax, 1 << 5              ; PAE
    mov cr4, eax
    mov eax, pml4
    mov cr3, eax
    mov ecx, EFER
    rdmsr
    or eax, 1 << 8 | 1 << 11    ; LME, NXE
    wrmsr
    mov eax, cr0
    or eax, 1 << 31             ; PG
    mov cr0, eax
    ; still running 32-bit code ("compatibility mode") until CS is a 64-bit segment
    lgdt [gdt_pointer]
    jmp 0x08:long_mode

; The bitmap: bit n set = frame n (address n * 4096) is in use, or isn't RAM at all.
init_frames:                    ; (32-bit: it runs before the switch)
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

bits 64
long_mode:
    mov ax, 0x10
    mov ds, ax
    mov es, ax
    mov ss, ax
    xor ax, ax
    mov fs, ax
    mov gs, ax
    mov rax, HIGH + higher_half     ; the same code, through the higher half's mapping
    jmp rax
higher_half:
    mov rsp, HIGH + stack_top
    call init_idt
    ; the game's test: the first module, copied to MODULE and called
    mov ebx, [boot_info]
    mov esi, [rbx + 24]
    mov ecx, [rsi + 4]
    mov esi, [rsi]
    sub ecx, esi
    mov edi, MODULE
    rep movsb
    mov rdi, kmalloc                ; the game's test: kmalloc, kfree, and the frame count
    mov rsi, kfree
    mov rdx, frames_used
    mov rax, MODULE
    call rax
    mov rsi, s_done
    call puts
    cli
    hlt


; ---- memory -------------------------------------------------------------------------

alloc_frame:                        ; rax = a free frame (zeroed), or 0
    push rcx
    push rdx
    push rdi
    mov ecx, [search]
.scan:
    cmp ecx, FRAMES / 32
    jae .none
    mov eax, [bitmap + rcx * 4]
    not eax
    bsf edx, eax
    jnz .found
    inc ecx
    jmp .scan
.found:
    mov [search], ecx
    shl ecx, 5
    add ecx, edx
    bts [bitmap], ecx
    inc qword [frames_used]
    mov eax, ecx
    shl rax, 12
    push rax
    mov rdi, rax                    ; (identity-mapped: RAM is below 1 GiB)
    mov ecx, 4096 / 8
    xor eax, eax
    rep stosq
    pop rax
    jmp .out
.none:
    xor eax, eax
.out:
    pop rdi
    pop rdx
    pop rcx
    ret

free_frame:                         ; rax = a frame from alloc_frame
    push rax
    shr rax, 12
    btr [bitmap], eax
    shr eax, 5
    cmp eax, [search]
    jae .out
    mov [search], eax
.out:
    dec qword [frames_used]
    pop rax
    ret

; ---- the heap -----------------------------------------------------------------------
;
; Eight size classes, 16 to 2048 bytes. A slab is one frame: a header, then objects of
; one class. A free object holds the address of the next free one in its slab.
;
;   header: +0 next slab of this class, +8 the first free object, +16 objects in use,
;           +24 the class (0-7); objects from +32
SLAB_NEXT  equ 0
SLAB_FREE  equ 8
SLAB_USED  equ 16
SLAB_CLASS equ 24
SLAB_HEAD  equ 32

; kmalloc(rdi = size): rax = 16-aligned memory for it, or 0 (size 0, over 2048, or no
; memory). The C convention: rbx, rbp, r12-r15 kept.
kmalloc:
    xor eax, eax
    test rdi, rdi
    jz .out
    cmp rdi, 2048
    ja .out
    ; the class: the smallest 16 << c that fits
    xor ecx, ecx
    mov edx, 16
.class:
    cmp rdi, rdx
    jbe .found_class
    inc ecx
    shl edx, 1
    jmp .class
.found_class:
    ; a slab of this class with a free object
    mov rax, [slabs + rcx * 8]
.slab:
    test rax, rax
    jz .new_slab
    cmp qword [rax + SLAB_FREE], 0
    jne .take
    mov rax, [rax + SLAB_NEXT]
    jmp .slab
.new_slab:
    push rcx
    push rdx
    call alloc_frame
    pop rdx
    pop rcx
    test rax, rax
    jz .out
    mov rsi, [slabs + rcx * 8]      ; at the front of the class's list
    mov [rax + SLAB_NEXT], rsi
    mov [slabs + rcx * 8], rax
    mov [rax + SLAB_CLASS], rcx
    mov qword [rax + SLAB_USED], 0
    ; chain its objects: each free one points to the next
    lea rsi, [rax + SLAB_HEAD]
    mov [rax + SLAB_FREE], rsi
.chain:
    lea rdi, [rsi + rdx]            ; the next object
    lea r8, [rdi + rdx]
    lea r9, [rax + 4096]
    cmp r8, r9
    ja .last
    mov [rsi], rdi
    mov rsi, rdi
    jmp .chain
.last:
    mov qword [rsi], 0
.take:
    mov rsi, [rax + SLAB_FREE]
    mov rdi, [rsi]
    mov [rax + SLAB_FREE], rdi
    inc qword [rax + SLAB_USED]
    mov rax, rsi
.out:
    ret

; kfree(rdi = what kmalloc returned)
kfree:
    test rdi, rdi
    jz .out
    mov rax, rdi
    and rax, ~0xFFF                 ; its slab: the frame it's in
    mov rsi, [rax + SLAB_FREE]      ; back on the slab's free list
    mov [rdi], rsi
    mov [rax + SLAB_FREE], rdi
    dec qword [rax + SLAB_USED]
    jnz .out
    ; an empty slab: give the frame back, unless it's the only one of its class
    mov rcx, [rax + SLAB_CLASS]
    lea rdx, [slabs + rcx * 8]      ; the link that points to it
.find:
    mov rsi, [rdx]
    cmp rsi, rax
    je .unlink
    lea rdx, [rsi + SLAB_NEXT]
    jmp .find
.unlink:
    cmp qword [slabs + rcx * 8], rax
    jne .release
    cmp qword [rax + SLAB_NEXT], 0
    je .out                         ; the class's only slab: keep it
.release:
    mov rsi, [rax + SLAB_NEXT]
    mov [rdx], rsi
    call free_frame
.out:
    ret

; ---- the IDT ------------------------------------------------------------------------

init_idt:
    ; the TSS: only IST1 matters here, a stack of its own for #DF
    mov rax, HIGH + df_stack_top
    mov [tss + 36], rax             ; IST1
    mov word [tss + 102], 104       ; I/O map base: none
    ; its descriptor: 16 bytes in the GDT
    mov rax, tss
    mov word [gdt_tss], 103         ; limit
    mov [gdt_tss + 2], ax           ; base 0-15
    shr rax, 16
    mov [gdt_tss + 4], al           ; base 16-23
    mov byte [gdt_tss + 5], 0x89    ; present, 64-bit TSS (available)
    mov [gdt_tss + 7], ah           ; base 24-31
    shr rax, 16
    mov [gdt_tss + 8], eax          ; base 32-63
    lgdt [gdt_pointer]
    mov ax, 0x18
    ltr ax
    ; 32 gates: stub n is at stubs + n * STUB
    xor ecx, ecx
.gate:
    mov rax, HIGH + stubs
    imul rdx, rcx, STUB
    add rax, rdx
    shl rcx, 4                      ; 16 bytes a gate
    mov [idt + rcx], ax             ; offset 0-15
    mov word [idt + rcx + 2], 0x08  ; code segment
    mov byte [idt + rcx + 4], 0     ; IST: none...
    mov byte [idt + rcx + 5], 0x8E  ; present, ring 0, interrupt gate
    shr rax, 16
    mov [idt + rcx + 6], ax         ; offset 16-31
    shr rax, 16
    mov [idt + rcx + 8], eax        ; offset 32-63
    shr rcx, 4
    inc ecx
    cmp ecx, 32
    jb .gate
    mov byte [idt + 8 * 16 + 4], 1  ; ...except #DF: IST1
    lidt [idt_pointer]
    ret

; one stub per vector, each STUB bytes: push a 0 where the CPU pushes no error code,
; then the vector, then the common handler
STUB equ 16
%macro stub 1
    align STUB
%if %1 = 8 || (%1 >= 10 && %1 <= 14) || %1 = 17 || %1 = 21 || %1 = 29 || %1 = 30
    nop
    nop
%else
    push 0
%endif
    push %1
    jmp exception
%endmacro
align STUB
stubs:
%assign n 0
%rep 32
    stub n
%assign n n + 1
%endrep

; the frame: [rsp] vector, [rsp+8] error code, [rsp+16] rip, cs, rflags, rsp, ss
exception:
    push rax
    push rcx
    push rdx
    push rsi
    push rdi
    mov rcx, [rsp + 40]             ; the vector
    lea rsi, [names + rcx * 4]
    call puts
    mov rsi, s_at
    call puts
    mov rax, [rsp + 56]
    call hex64
    mov rcx, [rsp + 40]
    bt [has_error], ecx
    jnc .no_error
    mov rsi, s_error
    call puts
    mov rax, [rsp + 48]
    call hex64
.no_error:
    mov rcx, [rsp + 40]             ; (hex64 used rcx)
    cmp rcx, 14
    jne .no_cr2
    mov rsi, s_cr2
    call puts
    mov rax, cr2
    call hex64
.no_cr2:
    mov rsi, crlf
    call puts
    cmp qword [rsp + 40], 3                      ; #BP is a trap: carry on after the int3
    jne .stop
    pop rdi
    pop rsi
    pop rdx
    pop rcx
    pop rax
    add rsp, 16                     ; the vector and the error code
    iretq
.stop:
    cli
    hlt
    jmp .stop

hex64:                              ; rax as 0x + 16 hex digits
    push rax
    mov rsi, s_0x
    call puts
    pop rdx
    mov ecx, 16
.digit:
    rol rdx, 4
    mov eax, edx
    and eax, 15
    mov al, [digits + rax]
    call putc
    loop .digit
    ret

putc:
    push rdx
    push rax
    mov dx, 0x3FD
.ready:
    in al, dx
    test al, 0x20
    jz .ready
    pop rax
    mov dx, 0x3F8
    out dx, al
    pop rdx
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
    dq 0x00209A0000000000           ; code: present, ring 0, L (64-bit)
    dq 0x0000920000000000           ; data: present, writable
gdt_tss:
    dq 0, 0                         ; the TSS (filled in by init_idt)
gdt_end:
gdt_pointer:
    dw gdt_end - gdt - 1
    dq gdt
idt_pointer:
    dw 32 * 16 - 1
    dq idt
has_error:  dd 1 << 8 | 1 << 10 | 1 << 11 | 1 << 12 | 1 << 13 | 1 << 14 | 1 << 17 | 1 << 21 | 1 << 29 | 1 << 30
names:                              ; 4 bytes each
    db "#DE", 0, "#DB", 0, "NMI", 0, "#BP", 0, "#OF", 0, "#BR", 0, "#UD", 0, "#NM", 0
    db "#DF", 0, "#CS", 0, "#TS", 0, "#NP", 0, "#SS", 0, "#GP", 0, "#PF", 0, "#15", 0
    db "#MF", 0, "#AC", 0, "#MC", 0, "#XM", 0, "#VE", 0, "#CP", 0, "#22", 0, "#23", 0
    db "#24", 0, "#25", 0, "#26", 0, "#27", 0, "#HV", 0, "#VC", 0, "#SX", 0, "#31", 0
s_at:    db " at ", 0
s_error: db ", error code ", 0
s_cr2:   db ", cr2 ", 0
s_done:  db "done", 13, 10, 0
digits:  db "0123456789abcdef"
s_0x:    db "0x", 0
crlf:    db 13, 10, 0

section .bss
boot_info: resd 1
search:    resd 1
alignb 8
frames_used: resq 1                 ; frames taken from the allocator, now
slabs:     resq 8                   ; each size class's slabs (a list)
bitmap:    resd FRAMES / 32
alignb 16
idt:       resb 32 * 16
tss:       resb 104
alignb 16
df_stack:  resb 4096
df_stack_top:
alignb 4096
pml4:      resq 512
pdpt_low:  resq 512
pdpt_high: resq 512
pd:        resq 512
pt:        resq 512
alignb 16
stack:     resb 8192
stack_top:
