; Level 18 — Virtual Memory Manager
;
; Every module is a program, all of them linked at 0x400000. Run them one after another,
; each in an address space of its own: its own PML4, its low half its own, the kernel's
; higher half shared. Memory comes on demand (level 22's idea, for programs now: their
; stack too), and when a program ends, every frame it had comes back.
;
; From here on the low half belongs to the program, so the kernel reaches physical memory
; through the direct map: physical x is at DIRECT + x, in every address space.
;
; Done for you: the process loop (run_process), loading the image, the frame allocator
; (alloc_frame zeroes, free_frame), system calls, killing a program that faults.
; Yours: new_space, free_space, map_user and user_fault.

bits 32

MB_FLAGS equ 1 << 0 | 1 << 1
P        equ 1 << 0
W        equ 1 << 1
PS       equ 1 << 7
NX_HIGH  equ 1 << 31
HIGH     equ 0xFFFFFFFF80000000     ; the higher half: virtual HIGH + x = physical x
EFER     equ 0xC0000080
USER     equ 0x400000           ; a program's lowest address: where it's loaded
USER_END equ 0x0000800000000000 ; the low half: the program's (above the first 4 MiB)
USER_STACK equ 0x00007FFFFFFFF000 ; its stack's top (pages come on demand)
DIRECT   equ 0xFFFF800000000000 ; physical x is at DIRECT + x, in every address space
FRAMES   equ 1 << 20
ADDR     equ 0x000FFFFFFFFFF000 ; an entry's address bits
U        equ 1 << 2             ; user: in an entry, at every level of the walk
KERNEL_CS equ 0x08
KERNEL_DS equ 0x10
USER_DS  equ 0x18
USER_CS  equ 0x20
TSS_SEL  equ 0x28
STAR     equ 0xC0000081
LSTAR    equ 0xC0000082
SFMASK   equ 0xC0000084
GS_BASE  equ 0xC0000101
KERNEL_GS_BASE equ 0xC0000102
EFAULT   equ 14
ENOSYS   equ 38
EINVAL   equ 22

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
    or eax, 1 << 0 | 1 << 8 | 1 << 11  ; SCE (syscall), LME, NXE
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
    call silence_pic             ; (the legacy PIC's IRQs would land on the exception vectors)
    call init_syscall
    ; every module is a program: run them one after another, each in its own address space
    mov ebx, [boot_info]
    mov ecx, [rbx + 20]             ; mods_count
    mov esi, [rbx + 24]             ; mods_addr
.next:
    jrcxz .all_done
    push rcx
    push rsi
    mov edi, [rsi]                  ; its start...
    mov ecx, [rsi + 4]              ; ...and end (physical)
    sub ecx, edi
    call run_process
    pop rsi
    pop rcx
    add esi, 16
    dec ecx
    jmp .next
.all_done:
    mov rsi, s_all
    call puts
    cli
    hlt

; ---- processes ----------------------------------------------------------------------

; run_process(rdi = the program's physical address, rcx = its size): load it at USER in a
; new address space, run it in ring 3, and when it exits (or is killed), free it all.
run_process:
    push rdi
    push rcx
    call new_space
    pop rcx
    pop rdi
    test rax, rax
    jz no_memory
    mov [space], rax
    mov cr3, rax
    ; the image, a page at a time: a frame, mapped at USER + offset, filled from the module
    mov r12, rdi                    ; source (physical)
    mov r13, rcx                    ; bytes left
    mov r14, USER                   ; where
.page:
    test r13, r13
    jz .loaded
    call alloc_frame
    test rax, rax
    jz load_failed
    mov rdi, r14
    mov rsi, rax
    call map_user
    test rax, rax
    jz load_failed
    mov rsi, DIRECT
    add rsi, r12
    mov rdi, r14                    ; (the new space is live: copy straight to USER + offset)
    mov rcx, 4096
    cmp rcx, r13
    jbe .whole
    mov rcx, r13
.whole:
    sub r13, rcx
    rep movsb
    add r12, 4096
    add r14, 4096
    jmp .page
.loaded:
    mov [process_rsp], rsp          ; exit and kill come back to here
    mov [tss + 4], rsp              ; and the program's entries into the kernel land
    mov [percpu + 0], rsp           ; below this, not on top of the loop's own frames
    mov ecx, GS_BASE                ; a fresh gs base for the program
    xor eax, eax
    xor edx, edx
    wrmsr
    push USER_DS | 3
    mov rax, USER_STACK
    push rax
    push 0x202
    push USER_CS | 3
    push USER
    iretq
process_end:                        ; (jumped to, with rsp = [process_rsp])
    mov rax, pml4                   ; the kernel's own tables again...
    mov cr3, rax
    mov rdi, [space]                ; ...so the process's can go
    call free_space
    ret
load_failed:
    mov rax, pml4
    mov cr3, rax
    mov rdi, [space]
    call free_space
no_memory:
    mov rsi, s_no_memory
    call puts
    ret

; new_space: rax = a new PML4 (physical), or 0 if out of memory. Entries 256-511 are the
; kernel's (copy them from the kernel's own PML4, pml4); the low half is the program's,
; except the first 4 MiB, which stay the kernel's: supervisor-only, shared.
new_space:
    xor eax, eax
    ret

; free_space(rdi = a PML4 from new_space): give back every frame of its low half (pages
; and tables), but not the kernel's shared first 4 MiB; then the PML4. Not while it's in CR3.
free_space:
    ret

; map_user(rdi = virtual page, rsi = frame), in the current address space (CR3): present,
; writable, user. Make missing tables. rax = 0 if out of memory.
map_user:
    xor eax, eax
    ret

; A page fault (rax = cr2, rdx = error code). If it's the program's own access to a missing
; page in its half (USER to USER_END), give it a fresh page and set CF (the handler then
; returns to retry). Otherwise clear CF.
user_fault:
    clc
    ret

; ---- frames -------------------------------------------------------------------------

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
    mov eax, ecx
    shl rax, 12
    push rax
    mov rdi, DIRECT                 ; zero it, through the direct map
    add rdi, rax
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
    pop rax
    ret

; ---- system calls ---------------------------------------------------------------------

init_syscall:
    mov ecx, STAR                   ; the selectors: syscall loads cs = 0x08, ss = 0x10;
    xor eax, eax                    ; sysret loads cs = 0x10 + 16 = 0x20 and ss = 0x10 + 8
    mov edx, KERNEL_DS << 16 | KERNEL_CS   ; = 0x18, both with RPL 3
    wrmsr
    mov ecx, LSTAR                  ; where syscall goes
    mov rax, HIGH + syscall_entry
    mov rdx, rax
    shr rdx, 32
    wrmsr
    mov ecx, SFMASK                 ; rflags bits cleared on the way in: TF, IF, DF
    mov eax, 0x700
    xor edx, edx
    wrmsr
    mov ecx, GS_BASE                ; while the program runs, gs is its own (0 for now)...
    xor eax, eax
    xor edx, edx
    wrmsr
    mov ecx, KERNEL_GS_BASE         ; ...and swapgs brings in the kernel's: percpu
    mov rax, HIGH + percpu
    mov rdx, rax
    shr rdx, 32
    wrmsr
    mov rax, HIGH + stack_top
    mov [percpu + 0], rax           ; the kernel stack
    ret

; syscall: rcx = the program's rip, r11 = its rflags, rsp = still its stack. Interrupts
; are off (SFMASK), so nothing can come between the swapgs and the stack switch.
syscall_entry:
    swapgs                          ; gs = percpu
    mov [gs:8], rsp                 ; the program's rsp
    mov rsp, [gs:0]                 ; the kernel's
    push rcx
    push r11
    push rdi
    push rsi
    push rdx
    push rbx
    cmp rax, 1
    je .write
    cmp rax, 60
    je .exit
    cmp rax, 158
    je .arch_prctl
    mov rax, -ENOSYS
.return:
    pop rbx
    pop rdx
    pop rsi
    pop rdi
    pop r11
    pop rcx
    mov rsp, [gs:8]
    swapgs                          ; gs = the program's again
    o64 sysret

.write:                             ; write(fd = rdi, buffer = rsi, count = rdx)
    mov rax, -EFAULT                ; the buffer must be the program's memory
    mov rbx, rsi
    add rbx, rdx
    jc .return                      ; (wraps around)
    cmp rsi, USER
    jb .return
    mov rcx, USER_END
    cmp rbx, rcx
    ja .return
    mov rcx, rdx
    jrcxz .written
.byte:
    lodsb                           ; (DF is clear: SFMASK)
    call putc
    loop .byte
.written:
    mov rax, [rsp + 8]              ; the count
    jmp .return

.exit:
    mov rsi, s_exit
    call puts
    mov rax, rdi
    call decimal
    mov rsi, crlf
    call puts
    swapgs                          ; (gs as the next program expects it)
    mov rsp, [process_rsp]
    jmp process_end

.arch_prctl:                        ; (ARCH_SET_GS, address)
    mov rax, -EINVAL
    cmp rdi, 0x1001
    jne .return
    mov ecx, KERNEL_GS_BASE         ; after swapgs, the program's gs base is in here
    mov rax, rsi
    mov rdx, rsi
    shr rdx, 32
    wrmsr
    xor eax, eax
    jmp .return

decimal:
    mov rbx, 10
    xor ecx, ecx
.d:
    xor edx, edx
    div rbx
    push rdx
    inc ecx
    test rax, rax
    jnz .d
.o:
    pop rax
    add al, '0'
    call putc
    loop .o
    ret

; the 8259s: remapped off the exception vectors, and masked (level 34)
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

; ---- the IDT ------------------------------------------------------------------------

init_idt:
    ; the TSS: only IST1 matters here, a stack of its own for #DF
    mov rax, HIGH + stack_top
    mov [tss + 4], rax              ; RSP0: the kernel stack, for interrupts from ring 3
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
    mov ax, TSS_SEL
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
    cmp qword [rsp + 40], 14        ; the program's page fault, in its half?
    jne .report
    mov rax, cr2
    mov rdx, [rsp + 48]
    call user_fault
    jnc .report
    pop rdi
    pop rsi
    pop rdx
    pop rcx
    pop rax
    add rsp, 16
    iretq
.report:
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
    test byte [rsp + 64], 3         ; from the program (cs at [rsp + 64])? kill it, not us
    jz .stop
    mov rsi, s_killed
    call puts
    mov rsp, [process_rsp]
    jmp process_end
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
    dq 0x0000F20000000000           ; 0x18 user data: DPL 3
    dq 0x0020FA0000000000           ; 0x20 user code: DPL 3, L
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
s_exit:  db "process exited with status ", 0
s_killed: db "process killed", 13, 10, 0
s_all:   db "all processes done", 13, 10, 0
s_no_memory: db "out of memory", 13, 10, 0
digits:  db "0123456789abcdef"
s_0x:    db "0x", 0
crlf:    db 13, 10, 0

section .bss
boot_info: resd 1
search:    resd 1
alignb 8
space:       resq 1                 ; the running process's PML4
process_rsp: resq 1                 ; the kernel's rsp while it runs
bitmap:    resd FRAMES / 32
alignb 8
percpu:    resq 2                   ; [0] the kernel stack, [8] the program's rsp
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
