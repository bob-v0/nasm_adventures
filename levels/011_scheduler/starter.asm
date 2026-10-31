; Level 11 — Scheduler
;
; Level 12's tasks were always ready to run. Real tasks wait: for time, for input, for
; each other. Three things, on top of level 12's kernel:
;   nanosleep (35): sleep at least that long, using no CPU; the timer now ticks at
;       HZ = 100 (calibrated), [ticks] counts; a sleeper wakes at a tick (wake_sleepers)
;   setpriority (141): (0, 0, nice) sets the caller's nice, -20 to 19 (clamped); a task
;       with a lower nice always runs before a higher one; equals take turns
;   idling: when every task is asleep, the kernel waits for the timer (hlt), not spins
;
; Done for you: tasks, switch_to, the timer handler (it calls wake_sleepers, then
; schedule). Yours: wake_sleepers, schedule, nanosleep, setpriority.

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
TASKS    equ 8
APIC     equ 0xFEE00000         ; the Local APIC (mapped below: it's above the first 1 GiB)
APIC_EOI equ 0xB0
APIC_SVR equ 0xF0
LVT_TIMER equ 0x320
INITIAL  equ 0x380
DIVIDE   equ 0x3E0
TIMER_VECTOR equ 0x40
PCD      equ 1 << 4
T_KSP    equ 0                  ; a task: its saved kernel rsp,
T_SPACE  equ 8                  ; its PML4,
T_STACK  equ 16                 ; its kernel stack's frame,
T_STATE  equ 24                 ; 0 empty, 1 ready, 2 done, 3 asleep
T_NICE   equ 32                 ; -20 (first) to 19 (last)
T_WAKE   equ 40                 ; asleep: the tick to wake at
T_SIZE   equ 48
HZ       equ 100
CURRENT  equ 0x390
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
EBADF    equ 9

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
    ; 3-4 GiB: just the 2 MiB that hold the Local APIC's registers
    mov dword [pdpt_low + 3 * 8], pd_apic + P + W
    mov dword [pd_apic + ((APIC >> 21) & 511) * 8], (APIC & ~0x1FFFFF) + P + W + PS + PCD
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
    ; every module is a program: a task each, then run them, taking turns
    mov ebx, [boot_info]
    mov ecx, [rbx + 20]
    mov esi, [rbx + 24]
    xor r15d, r15d                  ; the task's number
.load:
    jrcxz .go
    cmp r15d, TASKS
    jae .go
    push rcx
    push rsi
    mov edi, [rsi]
    mov ecx, [rsi + 4]
    sub ecx, edi
    mov rdx, r15
    call create_task
    pop rsi
    pop rcx
    add esi, 16
    dec ecx
    inc r15d
    jmp .load
.go:
    call init_timer
    mov qword [current], -1         ; nobody yet: schedule picks task 0
    call schedule                   ; (never comes back here)

; ---- processes ----------------------------------------------------------------------

; create_task(rdi = an ELF file's physical address, rcx = its size, rdx = its number):
; its address space, loaded; its kernel stack, made to look like one that switch_to left,
; so that the first switch to it "returns" into first_run, which drops to ring 3.
create_task:
    push rbx
    push r12
    push r13
    push r14
    imul r14, rdx, T_SIZE
    add r14, tasks                  ; the task
    push rdi
    push rcx
    call new_space
    pop rcx
    pop rdi
    test rax, rax
    jz .fail
    mov [r14 + T_SPACE], rax
    mov cr3, rax                    ; (loading writes into the new space)
    mov r12, DIRECT
    add r12, rdi
    mov r13, rcx
    call load_elf
    test rax, rax
    jz .bad
    mov rbx, rax                    ; the entry
    call make_stack
    test rax, rax
    jz .bad
    push rax
    call alloc_frame                ; its kernel stack: one frame, through the direct map
    pop rcx
    test rax, rax
    jz .bad
    mov [r14 + T_STACK], rax
    mov rdi, DIRECT + 4096
    add rdi, rax                    ; the stack's top
    mov rsi, rbx                    ; the entry
    mov rdx, rcx                    ; the program's rsp
    call prepare_stack
    mov rdi, rax
    mov [r14 + T_KSP], rdi
    mov qword [r14 + T_STATE], 1
    jmp .out
.bad:
    mov rsi, s_bad_elf
    call puts
.fail:
.out:
    mov rax, pml4
    mov cr3, rax
    pop r14
    pop r13
    pop r12
    pop rbx
    ret

; prepare_stack(rdi = a kernel stack's top, rsi = the program's entry, rdx = its rsp):
; make the stack look as if switch_to had left a task there, about to return into
; first_run, with the iretq frame into the program above it. rax = the rsp to keep.
prepare_stack:
    sub rdi, 8                      ; what iretq takes, at the top: ss, rsp, rflags, cs, rip
    mov qword [rdi], USER_DS | 3
    sub rdi, 8
    mov [rdi], rdx
    sub rdi, 8
    mov qword [rdi], 0x202
    sub rdi, 8
    mov qword [rdi], USER_CS | 3
    sub rdi, 8
    mov [rdi], rsi
    sub rdi, 8                      ; below it, what switch_to pops: a return address
    mov rax, HIGH + first_run       ; (first_run), then rbx, rbp, r12-r15
    mov [rdi], rax
    mov ecx, 6
.zero:
    sub rdi, 8
    mov qword [rdi], 0
    loop .zero
    mov rax, rdi
    ret

; A new task's first run: switch_to "returned" here, on its kernel stack, whose top
; holds the iretq frame into its program.
first_run:
    mov ecx, GS_BASE                ; a fresh gs base for the program
    xor eax, eax
    xor edx, edx
    wrmsr
    xor ebx, ebx                    ; (no kernel values left in registers)
    xor ecx, ecx
    xor edx, edx
    xor esi, esi
    xor edi, edi
    xor ebp, ebp
    xor r8d, r8d
    xor r9d, r9d
    xor r10d, r10d
    xor r11d, r11d
    xor r12d, r12d
    xor r13d, r13d
    xor r14d, r14d
    xor r15d, r15d
    iretq

; schedule: yours. Switch (switch_to) to the ready task (T_STATE 1) with the best
; priority, the lowest T_NICE; among equals, the first one after [current], in turn.
; It's the current one: just return. Nobody ready but someone asleep (T_STATE 3): idle
; (sti, hlt, cli) until the timer wakes someone, then look again. Nobody at all: s_all,
; cli, hlt. Keep rbx, rbp, r12-r15.
schedule:
    mov rsi, s_all
    call puts
    cli
    hlt

; switch_to(rdi = from (or -1), rsi = to): keep from's place (its kernel rsp, after
; pushing what a called function must keep), load to's, and return into to.
switch_to:
    push rbx
    push rbp
    push r12
    push r13
    push r14
    push r15
    cmp rdi, -1
    je .load
    imul rdi, rdi, T_SIZE
    mov [tasks + rdi + T_KSP], rsp
.load:
    mov [current], rsi
    imul rsi, rsi, T_SIZE
    add rsi, tasks
    mov rax, [rsi + T_SPACE]        ; its memory
    mov cr3, rax
    mov rax, [rsi + T_STACK]        ; its kernel stack, for entries from ring 3
    mov rdx, DIRECT + 4096
    add rax, rdx
    mov [tss + 4], rax
    mov [percpu + 0], rax
    mov rsp, [rsi + T_KSP]
    pop r15
    pop r14
    pop r13
    pop r12
    pop rbp
    pop rbx
    ret

; the current task is done (exit, or killed): free its memory, run the others
task_end:
    mov rax, [current]
    imul rax, rax, T_SIZE
    mov qword [tasks + rax + T_STATE], 2
    mov rdi, [tasks + rax + T_SPACE]
    mov rax, pml4                   ; (not while it's in CR3)
    mov cr3, rax
    call free_space
    call schedule                   ; (its kernel stack is a frame we stay on: kept)
    ; (never returns: the task is no longer ready)

no_memory:
    mov rsi, s_no_memory
    call puts
    ret

; load_elf(r12 = the file, r13 = its size), in the new space (CR3): map and fill every
; PT_LOAD segment. rax = the entry point, or 0 if it isn't an x86-64 executable we can load.
load_elf:
    push rbx
    push r14
    push r15
    xor eax, eax
    cmp r13, 64
    jb .out
    cmp dword [r12], 0x464C457F     ; 0x7F "ELF"
    jne .bad
    cmp byte [r12 + 4], 2           ; 64-bit
    jne .bad
    cmp byte [r12 + 5], 1           ; little-endian
    jne .bad
    cmp word [r12 + 16], 2          ; ET_EXEC
    jne .bad
    cmp word [r12 + 18], 0x3E       ; x86-64
    jne .bad
    mov rbx, [r12 + 32]             ; e_phoff
    movzx r14d, word [r12 + 56]     ; e_phnum
    movzx r15d, word [r12 + 54]     ; e_phentsize
.segment:
    test r14d, r14d
    jz .loaded
    lea rax, [rbx + r15]
    cmp rax, r13
    ja .bad
    lea rsi, [r12 + rbx]            ; this program header
    cmp dword [rsi], 1              ; PT_LOAD
    jne .next
    call load_segment
    test rax, rax
    jz .bad
.next:
    add rbx, r15
    dec r14d
    jmp .segment
.loaded:
    mov rax, [r12 + 24]             ; e_entry
    jmp .out
.bad:
    xor eax, eax
.out:
    pop r15
    pop r14
    pop rbx
    ret

; load_segment(rsi = a PT_LOAD program header): rax = 0 on failure
load_segment:
    push rbx
    push rcx
    push rdi
    push rsi
    push r8
    mov r8, rsi
    mov rdi, [r8 + 16]              ; p_vaddr
    mov rcx, [r8 + 40]              ; p_memsz
    mov rax, [r8 + 32]              ; p_filesz
    cmp rax, rcx
    ja .bad
    mov rbx, [r8 + 8]               ; p_offset + p_filesz within the file
    add rbx, rax
    jc .bad
    cmp rbx, r13
    ja .bad
    cmp rdi, USER                   ; and all of it in the program's half
    jb .bad
    lea rbx, [rdi + rcx]
    mov rax, USER_END
    cmp rbx, rax
    ja .bad
    ; the pages, fresh (zero: that's the .bss), unless an earlier segment has the page
    and rdi, ~0xFFF
.page:
    cmp rdi, rbx
    jae .fill
    call user_page_present
    jc .have
    call alloc_frame
    test rax, rax
    jz .bad
    mov rsi, rax
    call map_user
    test rax, rax
    jz .bad
.have:
    add rdi, 4096
    jmp .page
.fill:
    mov rdi, [r8 + 16]              ; the file's bytes (the rest stays zero)
    mov rsi, r12
    add rsi, [r8 + 8]
    mov rcx, [r8 + 32]
    rep movsb
    mov eax, 1
    jmp .out
.bad:
    xor eax, eax
.out:
    pop r8
    pop rsi
    pop rdi
    pop rcx
    pop rbx
    ret

; CF = the page at rdi is mapped in the current space
user_page_present:
    push rax
    push rbx
    push rcx
    push rdx
    mov rbx, cr3
    mov ecx, 39
.level:
    mov rax, ADDR
    and rbx, rax
    mov rdx, rdi
    shr rdx, cl
    and edx, 511
    mov rax, DIRECT
    add rax, rbx
    mov rbx, [rax + rdx * 8]
    test ebx, 1
    jz .no
    sub ecx, 9
    cmp ecx, 12
    jae .level
    stc
    jmp .out
.no:
    clc
.out:
    pop rdx
    pop rcx
    pop rbx
    pop rax
    ret

; make_stack: the stack's top page, with what Linux puts there: argc, argv, envp, auxv.
; rax = the initial rsp, or 0.
make_stack:
    push rdi
    push rsi
    push rcx
    mov rdi, USER_STACK - 4096
    call alloc_frame
    test rax, rax
    jz .out
    mov rsi, rax
    call map_user
    test rax, rax
    jz .out
    mov rdi, USER_STACK - 16        ; argv[0]'s text: "program"
    mov rsi, s_program
    mov ecx, 8
    rep movsb
    mov rax, USER_STACK - 64        ; 16-aligned: argc, argv[0], NULL, NULL (envp), AT_NULL
    mov qword [rax], 1
    mov rcx, USER_STACK - 16
    mov [rax + 8], rcx
    mov qword [rax + 16], 0
    mov qword [rax + 24], 0
    mov qword [rax + 32], 0
    mov qword [rax + 40], 0
.out:
    pop rcx
    pop rsi
    pop rdi
    ret

; new_space: rax = a new PML4 (physical), or 0. The kernel's half (entries 256-511) is
; shared; the low half gets a PDPT and PD of its own, whose first 4 MiB (PD entries 0-1)
; are the kernel's, supervisor-only.
new_space:
    push rbx
    push rcx
    push rsi
    push rdi
    call alloc_frame
    test rax, rax
    jz .fail
    mov rbx, rax                    ; the PML4
    mov rsi, DIRECT + pml4          ; (the kernel's PML4, through the direct map)
    mov rdi, DIRECT
    add rdi, rbx
    mov ecx, 256                    ; entries 256-511: the kernel's
.copy:
    mov rax, [rsi + rcx * 8]
    mov [rdi + rcx * 8], rax
    inc ecx
    cmp ecx, 512
    jb .copy
    call alloc_frame                ; the PDPT for 0-512 GiB
    test rax, rax
    jz .fail_pml4
    mov rsi, rax
    or rax, P + W + U
    mov [rdi], rax                  ; PML4[0]
    call alloc_frame                ; the PD for 0-1 GiB
    test rax, rax
    jz .fail_pml4
    mov rcx, rax
    or rax, P + W + U
    mov rdi, DIRECT
    add rdi, rsi
    mov [rdi], rax                  ; PDPT[0]
    mov rdi, DIRECT
    add rdi, rcx
    mov rsi, DIRECT + pd            ; the kernel's first 4 MiB: PD entries 0 and 1
    mov rax, [rsi]
    mov [rdi], rax
    mov rax, [rsi + 8]
    mov [rdi + 8], rax
    mov rax, rbx
    jmp .out
.fail_pml4:
    mov rdi, rbx
    call free_space
.fail:
    xor eax, eax
.out:
    pop rdi
    pop rsi
    pop rcx
    pop rbx
    ret

; free_space(rdi = a PML4 from new_space): every frame of the low half (pages and tables),
; except the kernel's shared first 4 MiB, then the PML4 itself. (Not while it's in CR3.)
free_space:
    push rax
    push rbx
    push rcx
    push rdx
    push rsi
    push r8
    push r9
    push r10
    mov r8, DIRECT
    add r8, rdi                     ; the PML4
    xor r9d, r9d
.pml4:
    mov rax, [r8 + r9 * 8]
    test al, 1
    jz .pml4_next
    mov rsi, rax
    mov rax, 1                      ; level 3: a PDPT; r9 = 0 marks the first one
    test r9d, r9d
    setz dl                         ; (dl = 1: this PDPT holds the kernel's 4 MiB)
    call free_table
.pml4_next:
    inc r9d
    cmp r9d, 256
    jb .pml4
    mov rax, rdi
    call free_frame
    pop r10
    pop r9
    pop r8
    pop rsi
    pop rdx
    pop rcx
    pop rbx
    pop rax
    ret

; free_table(rsi = the entry pointing at it, rax = its level: 1 PDPT, 2 PD, 3 PT,
; dl = 1 if it's on the path to the kernel's shared 4 MiB): free what it maps, then it.
free_table:
    push rax
    push rcx
    push rdx
    push rsi
    push rdi
    mov rdi, ADDR
    and rsi, rdi                    ; the table (physical)
    push rsi
    mov rdi, DIRECT
    add rdi, rsi                    ; ... and where to read it
    xor ecx, ecx
.entry:
    mov rsi, [rdi + rcx * 8]
    test esi, 1
    jz .next
    test dl, dl                     ; the kernel's first 4 MiB (PD entries 0-1): shared
    jz .mine
    cmp rax, 2
    jne .on_path
    cmp ecx, 2
    jb .next
    jmp .mine
.on_path:
    test ecx, ecx                   ; (PDPT entry 0 leads to the shared PD entries)
    jnz .mine
    push rax
    push rdx
    inc rax
    call free_table
    pop rdx
    pop rax
    jmp .next
.mine:
    cmp rax, 3
    je .page
    push rax
    push rdx
    inc rax
    xor edx, edx
    call free_table
    pop rdx
    pop rax
    jmp .next
.page:
    push rax
    mov rax, ADDR
    and rax, rsi
    call free_frame
    pop rax
.next:
    inc ecx
    cmp ecx, 512
    jb .entry
    pop rax                         ; the table itself
    call free_frame
    pop rdi
    pop rsi
    pop rdx
    pop rcx
    pop rax
    ret

; map_user(rdi = virtual page, rsi = frame) in the current address space: present,
; writable, user at every level; makes missing tables. rax = 0 if out of memory.
map_user:
    push rbx
    push rcx
    push rdx
    mov rbx, cr3
    mov rax, ADDR
    and rbx, rax
    mov ecx, 39
.level:
    mov rdx, rdi
    shr rdx, cl
    and edx, 511
    mov rax, DIRECT
    add rax, rbx
    lea rdx, [rax + rdx * 8]        ; the entry, through the direct map
    mov rbx, [rdx]
    test ebx, 1
    jnz .present
    call alloc_frame
    test rax, rax
    jz .fail
    or rax, P + W + U
    mov [rdx], rax
    mov rbx, rax
.present:
    mov rax, ADDR
    and rbx, rax
    sub ecx, 9
    cmp ecx, 12
    ja .level
    mov rdx, rdi
    shr rdx, 12
    and edx, 511
    mov rax, DIRECT
    add rax, rbx
    lea rdx, [rax + rdx * 8]
    mov rax, rsi
    or rax, P + W + U
    mov [rdx], rax
    invlpg [rdi]
.fail:
    pop rdx
    pop rcx
    pop rbx
    ret

; a page fault from the program, on a page that isn't there, in its half: a fresh page.
; rax = cr2, rdx = error code. CF = handled.
user_fault:
    test edx, 1                     ; present: a protection fault
    jnz .no
    test edx, 4                     ; only the program's own accesses
    jz .no
    mov rdi, USER
    cmp rax, rdi
    jb .no
    mov rdi, USER_END
    cmp rax, rdi
    jae .no
    mov rdi, rax
    and rdi, ~0xFFF
    call alloc_frame
    test rax, rax
    jz .no
    mov rsi, rax
    call map_user
    test rax, rax
    jz .no
    stc
    ret
.no:
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

; ---- the timer --------------------------------------------------------------------

init_timer:                         ; the APIC timer at HZ: calibrated against the PIT (level 33)
    mov rbx, DIRECT + APIC
    mov dword [rbx + APIC_SVR], 0x1FF
    mov dword [rbx + DIVIDE], 0x3   ; /16
    in al, 0x61                     ; PIT channel 2: 10 ms
    and al, 0xFC
    or al, 1
    out 0x61, al
    mov al, 0xB0
    out 0x43, al
    mov ax, 11932
    out 0x42, al
    mov al, ah
    out 0x42, al
    mov dword [rbx + INITIAL], 0xFFFFFFFF
.pit:
    in al, 0x61
    test al, 0x20
    jz .pit
    mov eax, 0xFFFFFFFF
    sub eax, [rbx + CURRENT]        ; counts per 10 ms
    mov dword [rbx + LVT_TIMER], 1 << 17 | TIMER_VECTOR
    mov [rbx + INITIAL], eax
    ret

; The timer: a task's time is up. It was interrupted anywhere, so everything it had
; in registers must be kept: all of them, on its kernel stack, then the switch.
; (Interrupts are off in the kernel, so this always comes from ring 3: gs is the program's.)
timer:
    push rax
    push rbx
    push rcx
    push rdx
    push rsi
    push rdi
    push rbp
    push r8
    push r9
    push r10
    push r11
    push r12
    push r13
    push r14
    push r15
    inc qword [ticks]
    call wake_sleepers
    mov rax, DIRECT + APIC
    mov dword [rax + APIC_EOI], 0
    test byte [rsp + 15 * 8 + 8], 3 ; from the idle loop (ring 0)? it looks again itself
    jz .back
    inc qword [preemptions]
    mov ecx, GS_BASE
    rdmsr
    push rdx
    push rax
    call schedule
    pop rax
    pop rdx
    mov ecx, GS_BASE
    wrmsr
.back:
    pop r15
    pop r14
    pop r13
    pop r12
    pop r11
    pop r10
    pop r9
    pop r8
    pop rbp
    pop rdi
    pop rsi
    pop rdx
    pop rcx
    pop rbx
    pop rax
    iretq

wake_sleepers:                      ; every task asleep (T_STATE 3) whose T_WAKE <= [ticks]:
    ret                             ; ready again (1). Yours.

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
    mov [gs:8], rsp                 ; the program's rsp (for a moment: gs:8 is shared)
    mov rsp, [gs:0]                 ; the task's kernel stack
    push qword [gs:8]               ; (on it: the task's own)
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
    test rax, rax
    je .read
    cmp rax, 24
    je .yield
    cmp rax, 35
    je .nanosleep
    cmp rax, 141
    je .setpriority
    cmp rax, 39
    je .getpid
    mov rax, -ENOSYS
.return:
    pop rbx
    pop rdx
    pop rsi
    pop rdi
    pop r11
    pop rcx
    pop rsp                         ; the program's rsp
    swapgs                          ; gs = the program's again
    o64 sysret

.write:                             ; write(fd = rdi, buffer = rsi, count = rdx)
    mov rax, -EBADF                 ; stdout and stderr: both the serial port
    cmp rdi, 1
    jb .return
    cmp rdi, 2
    ja .return
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
    movzx eax, dil                  ; an exit status is 8 bits
    call decimal
    mov rsi, crlf
    call puts
    swapgs
    jmp task_end

.read:                              ; read(fd = rdi, buffer = rsi, count = rdx): stdin only
    mov rax, -EBADF
    test rdi, rdi
    jnz .return
    mov rax, -EFAULT
    mov rbx, rsi
    add rbx, rdx
    jc .return
    cmp rsi, USER
    jb .return
    mov rcx, USER_END
    cmp rbx, rcx
    ja .return
    mov rcx, [stdin_left]           ; as much as there is
    cmp rcx, rdx
    jbe .some
    mov rcx, rdx
.some:
    mov rax, rcx
    sub [stdin_left], rcx
    push rsi
    mov rdi, rsi
    mov rsi, [stdin_at]
    rep movsb
    mov [stdin_at], rsi
    pop rsi
    jmp .return

.yield:                             ; sched_yield: someone else's turn; back here after
    push rbx
    push rdx
    push rsi
    push rdi
    push r8
    push r9
    push r10
    swapgs                          ; (gs as a program would leave it: the next task
    mov ecx, GS_BASE                ;  may be a fresh one, entering by iretq)
    rdmsr                           ; this task's own gs base: the next one will
    push rdx                        ; change it
    push rax
    call schedule
    pop rax
    pop rdx
    mov ecx, GS_BASE
    wrmsr
    swapgs
    pop r10
    pop r9
    pop r8
    pop rdi
    pop rsi
    pop rdx
    pop rbx
    xor eax, eax
    jmp .return

.nanosleep:                         ; nanosleep(rdi = &{seconds, nanoseconds}): yours
    mov rax, -ENOSYS
    jmp .return

.setpriority:                       ; setpriority(0, 0, nice): yours
    mov rax, -ENOSYS
    jmp .return

.getpid:
    mov rax, [current]
    inc rax
    jmp .return

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
    mov rax, HIGH + timer           ; the timer: vector 0x40
    mov [idt + TIMER_VECTOR * 16], ax
    mov word [idt + TIMER_VECTOR * 16 + 2], KERNEL_CS
    mov byte [idt + TIMER_VECTOR * 16 + 5], 0x8E
    shr rax, 16
    mov [idt + TIMER_VECTOR * 16 + 6], ax
    shr rax, 16
    mov [idt + TIMER_VECTOR * 16 + 8], eax
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
    jmp task_end
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
    dw 256 * 16 - 1
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
s_all:   db "all tasks done", 13, 10, 0
s_bad_elf: db "exec failed: not an x86-64 executable this kernel can load", 13, 10, 0
s_program: db "program", 0
s_no_memory: db "out of memory", 13, 10, 0
digits:  db "0123456789abcdef"
s_0x:    db "0x", 0
crlf:    db 13, 10, 0

section .bss
boot_info: resd 1
search:    resd 1
alignb 8
current:     resq 1                 ; the running task's number
global preemptions
preemptions: resq 1
ticks:       resq 1
tasks:       resb TASKS * T_SIZE
stdin_at:    resq 1                 ; (no stdin here: read gives 0)
stdin_left:  resq 1
bitmap:    resd FRAMES / 32
alignb 8
percpu:    resq 2                   ; [0] the kernel stack, [8] the program's rsp
alignb 16
idt:       resb 256 * 16
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
pd_apic:   resq 512
alignb 16
stack:     resb 8192
stack_top:
