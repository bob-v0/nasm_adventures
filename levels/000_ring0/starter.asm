; Level 0 — Ring 0 (boss)
;
; Everything, one last time, on your own terms:
;
; 1. Your bootloader. The BIOS loads sector 0 of this image. From there: load the rest of
;    the image (the kernel follows the second stage, sector-aligned; it is linked at 1 MiB);
;    read the game's data (from sector 2048: a header "RINGDISK", the filesystem image's
;    sectors and bytes, stdin's sectors and bytes; then the image; then stdin); collect the
;    memory map (int 0x15, e820); build the information block the kernel reads (multiboot's
;    layout: flags, modules (the filesystem, stdin), memory map); enter protected mode; put
;    the kernel at 1 MiB with its .bss zeroed; jump to it with ebx = the block.
; 2. Your kernel, on every CPU (-smp 4): level 10's kernel is below, as it was, for one
;    CPU. Wake the others (levels 7 and 25: their trampoline must reach long mode); give
;    each its own TSS, per-CPU data, system call MSRs; one scheduler for them all, any
;    process on any CPU; and a lock (or several) wherever CPUs share kernel state.
; 3. Your programs, concurrently: besides /bin/sh, start every program in /init at boot.
;    Their output, line by line (a whole line at a time: nothing in the middle of another
;    program's line), each line starting with [name]; when each ends:
;        [name] exited with status N          (the shell: shell exited with status N)
;    and when the last one has, `all done: user code ran on N cpus`, and every CPU stops.

; ---- sector 0: yours ---------------------------------------------------------------------

section boot start=0 vstart=0x7C00
bits 16
    cli                             ; yours: load the second stage (the sectors after this
    hlt                             ; one), and go there
    times 510 - ($ - $$) db 0
    dw 0xAA55

; ---- the second stage: yours ---------------------------------------------------------------

section stage2 follows=boot vstart=0x7E00
bits 16
stage2_main:
    cli                             ; yours: the kernel, the game's data, the information
    hlt                             ; block, protected mode, the kernel at 1 MiB, jump
    align 512, db 0
STAGE2_SECTORS equ ($ - $$) / 512


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
TASKS    equ 16
NFD      equ 16                 ; file descriptors per task
CWD_MAX  equ 128
T_KSP    equ 0                  ; a task: its saved kernel rsp,
T_SPACE  equ 8                  ; its PML4,
T_STACK  equ 16                 ; its kernel stack's frame,
T_STATE  equ 24                 ; 0 free, 1 ready, 2 zombie, 4 waiting
T_PID    equ 32
T_PPID   equ 40
T_STATUS equ 48                 ; (a zombie) what wait4 reports
T_FDS    equ 56                 ; NFD open files
T_CWD    equ T_FDS + NFD * 8    ; the current directory
T_SIZE   equ T_CWD + CWD_MAX
OFILES   equ 64                 ; open files, shared by the fds that point at them
O_TYPE   equ 0
O_REFS   equ 8
O_FILE   equ 16
O_POS    equ 24
O_PIPE   equ 32
O_SIZE   equ 40
CONSOLE  equ 1
FILE_R   equ 2
FILE_W   equ 3
PIPE_R   equ 4
PIPE_W   equ 5
PIPES    equ 16                 ; a pipe: a frame of buffer, counted in and out
P_BUF    equ 0
P_HEAD   equ 8
P_TAIL   equ 16
P_READERS equ 24
P_WRITERS equ 32
P_SIZE   equ 40
FILES    equ 64                 ; files and directories
NAME_MAX equ 96
I_DATA   equ 96
I_SIZE   equ 104
I_CAP    equ 112                ; 0: the image's, read-only (until written: then a frame)
I_DIR    equ 120
I_USED   equ 128
I_SIZE_  equ 136
PATH_MAX equ 128
MAX_ARGS equ 32
ARGBUF   equ 4096
O_CREAT  equ 0x40
O_TRUNC  equ 0x200
ENOENT   equ 2
E2BIG    equ 7
ENOEXEC  equ 8
ECHILD   equ 10
ENOMEM   equ 12
ENFILE   equ 23
EMFILE   equ 24
ENOSPC   equ 28
EPIPE    equ 32
ERANGE   equ 34
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

; ---- the kernel: at 1 MiB, as if a multiboot loader had put it there ---------------------

section .text follows=stage2 align=512 vstart=0x100000
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
    call load_files                 ; module 0: the filesystem
    mov ebx, [boot_info]            ; module 1: the console's input
    mov esi, [rbx + 24]
    mov eax, [rsi + 16]
    mov ecx, [rsi + 20]
    sub ecx, eax
    mov rdx, DIRECT
    add rax, rdx
    mov [stdin_at], rax
    mov [stdin_left], rcx
    ; the first process: /bin/sh, in /work, with the console as fds 0, 1 and 2
    mov qword [next_pid], 1
    call new_task
    mov r12, rax
    mov dword [r12 + T_CWD], '/wor'
    mov word [r12 + T_CWD + 4], 'k'
    mov edi, CONSOLE
    call new_ofile
    mov qword [rax + O_REFS], 3
    mov [r12 + T_FDS], rax
    mov [r12 + T_FDS + 8], rax
    mov [r12 + T_FDS + 16], rax
    call new_space
    mov [r12 + T_SPACE], rax
    mov cr3, rax
    mov rsi, s_sh_path
    mov rdi, pathbuf
    mov ecx, 8
    rep movsb
    call lookup
    mov r13, [rax + I_SIZE]
    mov r12, [rax + I_DATA]
    call load_elf
    mov r14, rax
    mov rax, argbuf                 ; argv: "sh"
    mov dword [rax], 'sh'
    mov [argv_at], rax
    mov qword [argc], 1
    call make_stack
    mov qword [boot_frame + F_R11], 0x202
    mov [boot_frame + F_RCX], r14
    mov [boot_frame + F_RSP], rax
    mov rdi, tasks
    mov rsi, boot_frame
    call start_frame
    mov rax, pml4
    mov cr3, rax
    mov qword [current], -1
    call schedule                   ; (never comes back here)

; ---- processes ----------------------------------------------------------------------

; the frame a system call leaves on the task's kernel stack (rsp = rbx = its base)
F_R15   equ 0
F_R14   equ 8
F_R13   equ 16
F_R12   equ 24
F_R10   equ 32
F_R9    equ 40
F_R8    equ 48
F_RBP   equ 56
F_RDI   equ 64
F_RSI   equ 72
F_RDX   equ 80
F_RBX   equ 88
F_RAX   equ 96
F_R11   equ 104                     ; the program's rflags
F_RCX   equ 112                     ; its rip
F_RSP   equ 120                     ; its rsp
F_SIZE  equ 128

; new_task: rax = a free task slot (zeroed, with a pid and a kernel stack), or 0
new_task:
    push rcx
    push rdx
    push rdi
    mov rdx, tasks
    mov ecx, TASKS
.find:
    cmp qword [rdx + T_STATE], 0
    je .found
    add rdx, T_SIZE
    loop .find
    xor eax, eax
    jmp .out
.found:
    mov rdi, rdx                    ; clear it
    mov ecx, T_SIZE / 8
    xor eax, eax
    rep stosq
    call alloc_frame                ; its kernel stack
    test rax, rax
    jz .out
    mov [rdx + T_STACK], rax
    mov rax, [next_pid]
    inc qword [next_pid]
    mov [rdx + T_PID], rax
    mov rax, rdx
.out:
    pop rdi
    pop rdx
    pop rcx
    ret

; start_frame(rdi = task, rsi = the frame to copy (F_SIZE bytes)): the task's kernel stack
; gets that frame at its top, and below it what switch_to pops, returning into fork_ret
start_frame:
    push rcx
    push rsi
    push rdi
    mov rdx, rdi
    mov rdi, [rdx + T_STACK]
    mov rax, DIRECT + 4096 - F_SIZE
    add rdi, rax
    mov ecx, F_SIZE / 8
    rep movsq
    sub rdi, F_SIZE
    sub rdi, 8
    mov rax, HIGH + fork_ret
    mov [rdi], rax
    mov ecx, 6
.zero:
    sub rdi, 8
    mov qword [rdi], 0
    loop .zero
    mov [rdx + T_KSP], rdi
    mov qword [rdx + T_STATE], 1
    pop rdi
    pop rsi
    pop rcx
    ret

; where a new task (forked, or the first one) starts: as if returning from a system call
fork_ret:
    swapgs                          ; (inside a system call, gs is the kernel's)
    mov rbx, rsp
    jmp syscall_exit

; schedule: the next ready task after the current one, round robin. Returns when this task
; runs again. Call it with gs as a program has it (swapgs first, inside a system call).
schedule:
    mov rax, [current]
    mov ecx, TASKS
.find:
    inc rax
    cmp rax, TASKS
    jb .look
    xor eax, eax
.look:
    imul rdx, rax, T_SIZE
    cmp qword [tasks + rdx + T_STATE], 1
    je .found
    loop .find
    mov rsi, s_deadlock             ; everyone is waiting for someone
    call puts
    cli
    hlt
.found:
    cmp rax, [current]
    je .same
    mov rdi, [current]
    mov rsi, rax
    jmp switch_to
.same:
    ret

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

; block: wait until something changes (a wake_all), then return
block:
    push rax
    push rcx
    push rdx
    push rsi
    push rdi
    push r8
    push r9
    push r10
    push r11
    mov rax, [current]
    imul rax, rax, T_SIZE
    mov qword [tasks + rax + T_STATE], 4
    swapgs
    call schedule
    swapgs
    pop r11
    pop r10
    pop r9
    pop r8
    pop rdi
    pop rsi
    pop rdx
    pop rcx
    pop rax
    ret

wake_all:                           ; every waiting task: ready (each looks again itself)
    push rax
    push rcx
    mov rax, tasks
    mov ecx, TASKS
.task:
    cmp qword [rax + T_STATE], 4
    jne .next
    mov qword [rax + T_STATE], 1
.next:
    add rax, T_SIZE
    loop .task
    pop rcx
    pop rax
    ret

; do_exit(rdi = the wait status): close everything, free the memory, become a zombie for
; the parent to collect. Called with gs as a program has it. Never returns.
do_exit:
    mov r12, rdi
    mov rax, [current]
    imul r13, rax, T_SIZE
    add r13, tasks
    xor r14d, r14d
.fd:
    mov rdi, r14
    call close_fd
    inc r14d
    cmp r14d, NFD
    jb .fd
    mov rax, pml4
    mov cr3, rax
    mov rdi, [r13 + T_SPACE]
    test rdi, rdi
    jz .no_space
    call free_space
    mov qword [r13 + T_SPACE], 0
.no_space:
    mov [r13 + T_STATUS], r12
    mov qword [r13 + T_STATE], 2
    cmp qword [r13 + T_PID], 1
    jne .wake
    mov rsi, s_shell                ; the shell: that's the end
    call puts
    mov eax, r12d
    test eax, 0x7F
    jz .exited
    and eax, 0x7F
    add eax, 128
    jmp .say
.exited:
    shr eax, 8
    and eax, 0xFF
.say:
    call decimal
    mov rsi, crlf
    call puts
    cli
    hlt
.wake:
    call wake_all
    call schedule
    ; (a zombie is never scheduled again)

; ---- system calls ---------------------------------------------------------------------

syscall_entry:
    swapgs                          ; gs = percpu
    mov [gs:8], rsp
    mov rsp, [gs:0]                 ; this task's kernel stack
    push qword [gs:8]               ; the frame: rsp, rip, rflags, then every register
    push rcx
    push r11
    push rax
    push rbx
    push rdx
    push rsi
    push rdi
    push rbp
    push r8
    push r9
    push r10
    push r12
    push r13
    push r14
    push r15
    mov rbx, rsp                    ; the frame, for the handlers
    cmp rax, CALLS
    jae .unknown
    mov rax, [calls + rax * 8]
    test rax, rax
    jz .unknown
    call rax
    jmp .done
.unknown:
    mov rax, -ENOSYS
.done:
    mov [rbx + F_RAX], rax
syscall_exit:                       ; rsp = rbx = the frame
    pop r15
    pop r14
    pop r13
    pop r12
    pop r10
    pop r9
    pop r8
    pop rbp
    pop rdi
    pop rsi
    pop rdx
    pop rbx
    pop rax
    pop r11
    pop rcx
    pop rsp
    swapgs
    o64 sysret

; user_range(rdi = address, rsi = length): CF = it's not all in the program's half
user_range:
    push rax
    cmp rdi, USER
    jb .bad
    mov rax, rdi
    add rax, rsi
    jc .bad
    push rcx
    mov rcx, USER_END
    cmp rax, rcx
    pop rcx
    ja .bad
    pop rax
    clc
    ret
.bad:
    pop rax
    stc
    ret

sys_exit:                           ; exit(status)
    movzx edi, byte [rbx + F_RDI]
    shl edi, 8
    swapgs
    jmp do_exit

sys_fork:
    call new_task
    test rax, rax
    jz .no_memory
    mov r12, rax                    ; the child
    mov rax, [current]
    imul r13, rax, T_SIZE
    add r13, tasks                  ; the parent
    mov rax, [r13 + T_PID]
    mov [r12 + T_PPID], rax
    lea rsi, [r13 + T_CWD]          ; its directory
    lea rdi, [r12 + T_CWD]
    mov ecx, CWD_MAX / 8
    rep movsq
    xor ecx, ecx                    ; its open files, shared
.fd:
    mov rax, [r13 + T_FDS + rcx * 8]
    mov [r12 + T_FDS + rcx * 8], rax
    test rax, rax
    jz .next_fd
    inc qword [rax + O_REFS]
.next_fd:
    inc ecx
    cmp ecx, NFD
    jb .fd
    call new_space                  ; its memory: a copy
    test rax, rax
    jz .undo
    mov [r12 + T_SPACE], rax
    mov rdi, rax
    mov rsi, [r13 + T_SPACE]
    call copy_space
    test rax, rax
    jz .undo
    mov rdi, r12                    ; it returns from this same system call, with 0
    mov rsi, rbx
    call start_frame
    mov rax, [r12 + T_STACK]
    mov rdx, DIRECT + 4096 - F_SIZE + F_RAX
    add rax, rdx
    mov qword [rax], 0
    mov rax, [r12 + T_PID]
    ret
.undo:                              ; (out of memory half way: give it all back)
    xor ecx, ecx
.undo_fd:
    mov rax, [r12 + T_FDS + rcx * 8]
    test rax, rax
    jz .undo_next
    dec qword [rax + O_REFS]
.undo_next:
    inc ecx
    cmp ecx, NFD
    jb .undo_fd
    mov rdi, [r12 + T_SPACE]
    test rdi, rdi
    jz .undo_stack
    call free_space
.undo_stack:
    mov rax, [r12 + T_STACK]
    call free_frame
    mov qword [r12 + T_STATE], 0
.no_memory:
    mov rax, -ENOMEM
    ret

; copy_space(rdi = the new PML4, rsi = the old one): every page of the old one's low half,
; copied into a fresh frame at the same address in the new one. rax = 0: out of memory.
copy_space:
    push rbx
    push r12
    push r13
    push r14
    push r15
    mov r15, rdi
    mov rax, DIRECT
    add rsi, rax
    xor r8d, r8d                    ; PML4 index
.l4:
    mov r12, [rsi + r8 * 8]
    test r12d, 1
    jz .n4
    mov rax, ADDR
    and r12, rax
    mov rax, DIRECT
    add r12, rax                    ; the PDPT
    xor r9d, r9d
.l3:
    mov r13, [r12 + r9 * 8]
    test r13d, 1
    jz .n3
    mov rax, ADDR
    and r13, rax
    mov rax, DIRECT
    add r13, rax                    ; the PD
    xor r10d, r10d
.l2:
    mov r14, r8                     ; (PML4 0, PDPT 0, PD 0-1: the kernel's 4 MiB)
    or r14, r9
    jnz .mine
    cmp r10, 2
    jb .n2
.mine:
    mov r14, [r13 + r10 * 8]
    test r14d, 1
    jz .n2
    mov rax, ADDR
    and r14, rax
    mov rax, DIRECT
    add r14, rax                    ; the PT
    xor r11d, r11d
.l1:
    mov rax, [r14 + r11 * 8]
    test eax, 1
    jz .n1
    push rsi
    mov rsi, ADDR
    and rax, rsi
    mov rsi, DIRECT
    add rax, rsi                    ; the old page, readable
    push rax
    call alloc_frame
    pop rsi
    test rax, rax
    jz .full
    push rax
    mov rdi, DIRECT
    add rdi, rax
    mov ecx, 512
    rep movsq
    pop rsi                         ; the new frame
    mov rdi, r8                     ; its virtual address, from the four indexes
    shl rdi, 39
    mov rax, r9
    shl rax, 30
    or rdi, rax
    mov rax, r10
    shl rax, 21
    or rdi, rax
    mov rax, r11
    shl rax, 12
    or rdi, rax
    mov rdx, r15
    call map_in
    pop rsi
    test rax, rax
    jz .fail
.n1:
    inc r11d
    cmp r11d, 512
    jb .l1
.n2:
    inc r10d
    cmp r10d, 512
    jb .l2
.n3:
    inc r9d
    cmp r9d, 512
    jb .l3
.n4:
    inc r8d
    cmp r8d, 256
    jb .l4
    mov eax, 1
    jmp .out
.full:
    pop rsi
.fail:
    xor eax, eax
.out:
    pop r15
    pop r14
    pop r13
    pop r12
    pop rbx
    ret

sys_wait4:                          ; wait4(pid, &status, options, rusage)
    mov rax, [current]
    imul r12, rax, T_SIZE
    add r12, tasks
    mov r13, [r12 + T_PID]          ; me
.again:
    xor r14d, r14d                  ; any child at all?
    mov rdx, tasks
    mov ecx, TASKS
.task:
    cmp qword [rdx + T_STATE], 0
    je .next
    cmp [rdx + T_PPID], r13
    jne .next
    mov rax, [rbx + F_RDI]
    cmp rax, -1
    je .mine
    cmp rax, [rdx + T_PID]
    jne .next
.mine:
    inc r14d
    cmp qword [rdx + T_STATE], 2
    je .reap
.next:
    add rdx, T_SIZE
    loop .task
    test r14d, r14d
    jz .none
    call block
    jmp .again
.none:
    mov rax, -ECHILD
    ret
.reap:
    mov rdi, [rbx + F_RSI]
    test rdi, rdi
    jz .no_status
    mov esi, 4
    call user_range
    mov rax, -EFAULT
    jc .out
    mov eax, [rdx + T_STATUS]
    mov [rdi], eax
.no_status:
    mov rax, [rdx + T_STACK]        ; its kernel stack: nobody runs on it any more
    call free_frame
    mov qword [rdx + T_STATE], 0
    mov rax, [rdx + T_PID]
.out:
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
sys_execve:                         ; execve(path, argv, envp)
    mov rdi, [rbx + F_RDI]
    call resolve
    test rax, rax
    jz .no_file
    call lookup
    test rax, rax
    jz .no_file
    cmp qword [rax + I_DIR], 0
    jne .no_file
    mov r14, rax                    ; the file
    ; the arguments, into the kernel (the old memory is about to go)
    mov r12, [rbx + F_RSI]          ; argv
    xor r13d, r13d                  ; argc
    mov rdi, argbuf                 ; where their text goes
.arg:
    cmp r13d, MAX_ARGS
    jae .too_many
    push rdi
    mov rdi, r12
    mov esi, 8
    call user_range
    pop rdi
    jc .fault
    mov r8, [r12]
    test r8, r8
    jz .args_done
    mov [argv_at + r13 * 8], rdi
    push rdi
    mov rdi, r8
    mov esi, 1
    call user_range
    pop rdi
    jc .fault
    mov rsi, r8
.char:
    mov rax, argbuf + ARGBUF
    cmp rdi, rax
    jae .too_many
    lodsb
    stosb
    test al, al
    jnz .char
    inc r13d
    add r12, 8
    jmp .arg
.args_done:
    mov [argc], r13
    ; a new address space, and the program in it
    mov rax, [current]
    imul r15, rax, T_SIZE
    add r15, tasks
    call new_space
    test rax, rax
    jz .no_memory
    push rax
    mov cr3, rax
    mov r12, [r14 + I_DATA]
    mov r13, [r14 + I_SIZE]
    call load_elf
    mov r14, rax                    ; the entry point
    pop rax
    test r14, r14
    jz .not_exec
    push rax
    call make_stack                 ; (with argc and argv)
    mov r13, rax
    pop rax
    test r13, r13
    jz .not_exec
    xchg rax, [r15 + T_SPACE]       ; the old memory goes
    mov rdi, rax
    call free_space
    ; return into the new program: a frame with its entry, its stack, nothing else
    mov rdi, rbx
    mov ecx, F_SIZE / 8
    xor eax, eax
    rep stosq
    mov [rbx + F_RCX], r14
    mov qword [rbx + F_R11], 0x202
    mov [rbx + F_RSP], r13
    xor eax, eax
    ret
.not_exec:
    mov rdi, rax                    ; (the new space, half built)
    mov rax, [r15 + T_SPACE]
    mov cr3, rax
    call free_space
    mov rax, -ENOEXEC
    ret
.no_memory:
    mov rax, -ENOMEM
    ret
.too_many:
    mov rax, -E2BIG
    ret
.fault:
    mov rax, -EFAULT
    ret
.no_file:
    mov rax, -ENOENT
    ret

; make_stack: the new program's stack top page: its argument strings, then (16-aligned)
; argc, argv[0..argc-1], NULL, NULL (no environment), AT_NULL. rax = the rsp, or 0.
make_stack:
    push rbx
    push r12
    mov rdi, USER_STACK - 4096
    call alloc_frame
    test rax, rax
    jz .out
    mov rsi, rax
    call map_user
    test rax, rax
    jz .out
    mov rdi, USER_STACK             ; the strings, from the top down
    mov rcx, [argc]
.string:
    jrcxz .strings_done
    dec rcx
    mov rsi, [argv_at + rcx * 8]
    xor edx, edx
.len:
    cmp byte [rsi + rdx], 0
    je .copy
    inc rdx
    jmp .len
.copy:
    inc rdx                         ; (with the 0)
    sub rdi, rdx
    push rdi
    push rcx
    mov rcx, rdx
    rep movsb
    pop rcx
    pop rdi
    mov [argv_user + rcx * 8], rdi  ; where it is, for the program
    jmp .string
.strings_done:
    mov rax, [argc]                 ; the table: argc + 1 + argc + 1 + 1 + 2 qwords
    lea rax, [rax * 2 + 5]
    shl rax, 3
    sub rdi, rax
    and rdi, ~15
    mov r12, rdi                    ; the rsp
    mov rax, [argc]
    mov [rdi], rax
    add rdi, 8
    xor ecx, ecx
.ptr:
    cmp rcx, [argc]
    jae .ptrs_done
    mov rax, [argv_user + rcx * 8]
    mov [rdi], rax
    add rdi, 8
    inc rcx
    jmp .ptr
.ptrs_done:
    xor eax, eax
    mov ecx, 4                      ; NULL, NULL, AT_NULL (0, 0)
    rep stosq
    mov rax, r12
.out:
    pop r12
    pop rbx
    ret

; ---- files ----------------------------------------------------------------------------

; the image (module 0): records of (u16 name length, name, u32 size, data); size
; 0xFFFFFFFF is a directory; a name length of 0 ends it
load_files:
    mov ebx, [boot_info]
    mov esi, [rbx + 24]
    mov esi, [rsi]                  ; module 0's start
    mov rax, DIRECT
    add rsi, rax
    mov rdi, files
.record:
    movzx ecx, word [rsi]
    add rsi, 2
    test ecx, ecx
    jz .done
    mov rax, files + FILES * I_SIZE_
    cmp rdi, rax
    jae .done
    push rdi                        ; the name
    lea rdx, [rsi + rcx]            ; (where the record goes on)
    cmp ecx, NAME_MAX - 1
    jbe .fits
    mov ecx, NAME_MAX - 1
.fits:
    rep movsb
    mov byte [rdi], 0
    pop rdi
    mov rsi, rdx
    mov eax, [rsi]
    add rsi, 4
    cmp eax, 0xFFFFFFFF
    jne .file
    mov qword [rdi + I_DIR], 1
    jmp .next
.file:
    mov [rdi + I_DATA], rsi
    mov [rdi + I_SIZE], rax
    mov qword [rdi + I_CAP], 0      ; (read-only: it's the image)
    add rsi, rax
.next:
    mov qword [rdi + I_USED], 1
    add rdi, I_SIZE_
    jmp .record
.done:
    ret

; resolve(rdi = a path in the program's memory): pathbuf = it, absolute and without
; "." and "..". rax = 0 if it isn't readable.
resolve:
    push rbx
    push r12
    mov esi, 1
    call user_range
    jc .bad
    mov r12, rdi
    xor ecx, ecx                    ; pathbuf's length
    cmp byte [r12], '/'
    je .parts
    mov rax, [current]              ; relative: from the current directory
    imul rax, rax, T_SIZE
    lea rsi, [tasks + rax + T_CWD]
    cmp word [rsi], '/'             ; ("/" itself: nothing to copy)
    je .parts
.cwd:
    lodsb
    test al, al
    jz .parts
    mov [pathbuf + rcx], al
    inc ecx
    jmp .cwd
.parts:                             ; one part of the path at a time
    cmp byte [r12], 0
    je .end
    cmp byte [r12], '/'
    jne .part
    inc r12
    jmp .parts
.part:
    mov rsi, r12                    ; [rsi, r12): the part
.scan:
    cmp byte [r12], 0
    je .got
    cmp byte [r12], '/'
    je .got
    inc r12
    jmp .scan
.got:
    mov rdx, r12
    sub rdx, rsi
    cmp rdx, 1
    jne .not_dot
    cmp byte [rsi], '.'
    je .parts                       ; "."
.not_dot:
    cmp rdx, 2
    jne .name
    cmp word [rsi], '..'
    jne .name
.up:                                ; "..": drop the last part
    test ecx, ecx
    jz .parts
    dec ecx
    cmp byte [pathbuf + rcx], '/'
    jne .up
    jmp .parts
.name:
    lea rax, [rcx + rdx + 1]
    cmp rax, PATH_MAX - 1
    jae .bad
    mov byte [pathbuf + rcx], '/'
    inc ecx
.copy:
    mov al, [rsi]
    mov [pathbuf + rcx], al
    inc rsi
    inc ecx
    cmp rsi, r12
    jb .copy
    jmp .parts
.end:
    test ecx, ecx
    jnz .terminate
    mov byte [pathbuf], '/'
    inc ecx
.terminate:
    mov byte [pathbuf + rcx], 0
    mov eax, 1
    jmp .out
.bad:
    xor eax, eax
.out:
    pop r12
    pop rbx
    ret

; lookup: rax = the file (or directory) named pathbuf, or 0
lookup:
    push rcx
    push rsi
    push rdi
    mov rax, files
    mov ecx, FILES
.file:
    cmp qword [rax + I_USED], 0
    je .next
    mov rsi, rax
    mov rdi, pathbuf
.cmp:
    mov dl, [rsi]
    cmp dl, [rdi]
    jne .next
    test dl, dl
    jz .out
    inc rsi
    inc rdi
    jmp .cmp
.next:
    add rax, I_SIZE_
    loop .file
    xor eax, eax
.out:
    pop rdi
    pop rsi
    pop rcx
    ret

; ---- open files ---------------------------------------------------------------------

; fd_of(rdi = fd): rax = its open file, or 0
fd_of:
    xor eax, eax
    cmp rdi, NFD
    jae .out
    mov rax, [current]
    imul rax, rax, T_SIZE
    mov rax, [tasks + rax + T_FDS + rdi * 8]
.out:
    ret

; new_ofile(rdi = type): rax = an open file (one reference), or 0
new_ofile:
    push rcx
    mov rax, ofiles
    mov ecx, OFILES
.find:
    cmp qword [rax + O_REFS], 0
    je .found
    add rax, O_SIZE
    loop .find
    xor eax, eax
    pop rcx
    ret
.found:
    mov [rax + O_TYPE], rdi
    mov qword [rax + O_REFS], 1
    mov qword [rax + O_FILE], 0
    mov qword [rax + O_POS], 0
    mov qword [rax + O_PIPE], 0
    pop rcx
    ret

; new_fd(rdi = an open file): rax = the lowest free fd, now pointing at it; or -EMFILE
new_fd:
    push rcx
    push rdx
    mov rdx, [current]
    imul rdx, rdx, T_SIZE
    add rdx, tasks
    xor ecx, ecx
.find:
    cmp qword [rdx + T_FDS + rcx * 8], 0
    je .found
    inc ecx
    cmp ecx, NFD
    jb .find
    mov rax, -EMFILE
    jmp .out
.found:
    mov [rdx + T_FDS + rcx * 8], rdi
    mov eax, ecx
.out:
    pop rdx
    pop rcx
    ret

; put_ofile(rdi = an open file): one reference fewer; the last one closes it
put_ofile:
    dec qword [rdi + O_REFS]
    jnz .out
    mov rax, [rdi + O_PIPE]
    cmp qword [rdi + O_TYPE], PIPE_R
    jne .writer
    dec qword [rax + P_READERS]
    jmp .pipe
.writer:
    cmp qword [rdi + O_TYPE], PIPE_W
    jne .out
    dec qword [rax + P_WRITERS]
.pipe:
    call wake_all                   ; (someone may be waiting for this end)
    cmp qword [rax + P_READERS], 0
    jne .out
    cmp qword [rax + P_WRITERS], 0
    jne .out
    push rax
    mov rax, [rax + P_BUF]          ; nobody left: the buffer goes
    mov rdx, DIRECT
    sub rax, rdx
    call free_frame
    pop rax
    mov qword [rax + P_BUF], 0
.out:
    ret

close_fd:                           ; rdi = fd: rax = 0, or -EBADF
    push rdi
    call fd_of
    pop rdi
    test rax, rax
    jz .bad
    mov rdx, [current]
    imul rdx, rdx, T_SIZE
    mov qword [tasks + rdx + T_FDS + rdi * 8], 0
    mov rdi, rax
    call put_ofile
    xor eax, eax
    ret
.bad:
    mov rax, -EBADF
    ret

sys_close:
    mov rdi, [rbx + F_RDI]
    jmp close_fd

sys_dup2:                           ; dup2(old, new)
    mov rdi, [rbx + F_RDI]
    call fd_of
    test rax, rax
    jz .bad
    mov r12, rax
    mov rdi, [rbx + F_RSI]
    cmp rdi, NFD
    jae .bad
    cmp rdi, [rbx + F_RDI]
    je .same
    call close_fd                   ; (whatever it was)
    mov rdi, [rbx + F_RSI]
    mov rax, [current]
    imul rax, rax, T_SIZE
    mov [tasks + rax + T_FDS + rdi * 8], r12
    inc qword [r12 + O_REFS]
.same:
    mov rax, [rbx + F_RSI]
    ret
.bad:
    mov rax, -EBADF
    ret

sys_pipe:                           ; pipe(int fds[2])
    mov rdi, [rbx + F_RDI]
    mov esi, 8
    call user_range
    jc .fault
    mov r12, pipes                  ; a free pipe
    mov ecx, PIPES
.find:
    cmp qword [r12 + P_BUF], 0
    je .found
    add r12, P_SIZE
    loop .find
    jmp .full
.found:
    call alloc_frame
    test rax, rax
    jz .full
    mov rdx, DIRECT
    add rax, rdx
    mov [r12 + P_BUF], rax
    mov qword [r12 + P_HEAD], 0
    mov qword [r12 + P_TAIL], 0
    mov qword [r12 + P_READERS], 1
    mov qword [r12 + P_WRITERS], 1
    mov edi, PIPE_R
    call new_ofile
    mov [rax + O_PIPE], r12
    mov r13, rax
    mov edi, PIPE_W
    call new_ofile
    mov [rax + O_PIPE], r12
    mov r14, rax
    mov rdi, r13
    call new_fd
    mov r15, rax
    mov rdi, r14
    call new_fd
    mov rdi, [rbx + F_RDI]
    mov [rdi], r15d
    mov [rdi + 4], eax
    xor eax, eax
    ret
.full:
    mov rax, -ENFILE
    ret
.fault:
    mov rax, -EFAULT
    ret

sys_open:                           ; open(path, flags, mode)
    mov rdi, [rbx + F_RDI]
    call resolve
    test rax, rax
    jz .fault
    call lookup
    mov r12, rax
    mov rax, [rbx + F_RSI]
    test eax, 3
    jnz .write
    test r12, r12                   ; reading: it must exist, and not be a directory
    jz .missing
    cmp qword [r12 + I_DIR], 0
    jne .missing
    mov edi, FILE_R
    jmp .opened
.write:
    test r12, r12
    jnz .exists
    test eax, O_CREAT
    jz .missing
    mov r12, files                  ; a new file: a free slot, and its name
    mov ecx, FILES
.slot:
    cmp qword [r12 + I_USED], 0
    je .new
    add r12, I_SIZE_
    loop .slot
    mov rax, -ENOSPC
    ret
.new:
    mov qword [r12 + I_USED], 1
    mov rsi, pathbuf
    mov rdi, r12
.name:
    lodsb
    stosb
    test al, al
    jnz .name
    mov qword [r12 + I_CAP], 0
    mov qword [r12 + I_SIZE], 0
.exists:
    cmp qword [r12 + I_DIR], 0
    jne .missing
    cmp qword [r12 + I_CAP], 0      ; still the image's: it gets a frame of its own
    jne .writable
    call alloc_frame
    test rax, rax
    jz .no_space
    mov rdx, DIRECT
    add rax, rdx
    mov rsi, [r12 + I_DATA]         ; (what it had, as far as it fits)
    mov rdi, rax
    mov rcx, [r12 + I_SIZE]
    cmp rcx, 4096
    jbe .keep
    mov ecx, 4096
.keep:
    mov [r12 + I_SIZE], rcx
    rep movsb
    mov [r12 + I_DATA], rax
    mov qword [r12 + I_CAP], 4096
.writable:
    mov rax, [rbx + F_RSI]
    test eax, O_TRUNC
    jz .no_trunc
    mov qword [r12 + I_SIZE], 0
.no_trunc:
    mov edi, FILE_W
.opened:
    call new_ofile
    test rax, rax
    jz .no_space
    mov [rax + O_FILE], r12
    mov rdi, rax
    call new_fd
    test rax, rax
    jns .out
    push rax
    mov qword [rdi + O_REFS], 0
    pop rax
.out:
    ret
.missing:
    mov rax, -ENOENT
    ret
.no_space:
    mov rax, -ENOSPC
    ret
.fault:
    mov rax, -EFAULT
    ret

sys_read:                           ; read(fd, buffer, count)
    mov rdi, [rbx + F_RSI]
    mov rsi, [rbx + F_RDX]
    call user_range
    jc .fault
    mov rdi, [rbx + F_RDI]
    call fd_of
    test rax, rax
    jz .bad
    mov r12, rax
    mov rdi, [rbx + F_RSI]
    mov rdx, [rbx + F_RDX]
    mov rax, [r12 + O_TYPE]
    cmp rax, CONSOLE
    je .console
    cmp rax, FILE_R
    je .file
    cmp rax, PIPE_R
    je .pipe
.bad:
    mov rax, -EBADF
    ret
.fault:
    mov rax, -EFAULT
    ret
.console:                           ; the script: everyone shares it
    mov rcx, [stdin_left]
    cmp rcx, rdx
    jbe .some
    mov rcx, rdx
.some:
    mov rax, rcx
    sub [stdin_left], rcx
    mov rsi, [stdin_at]
    rep movsb
    mov [stdin_at], rsi
    ret
.file:
    mov r13, [r12 + O_FILE]
    mov rcx, [r13 + I_SIZE]
    sub rcx, [r12 + O_POS]
    jbe .eof
    cmp rcx, rdx
    jbe .take
    mov rcx, rdx
.take:
    mov rsi, [r13 + I_DATA]
    add rsi, [r12 + O_POS]
    add [r12 + O_POS], rcx
    mov rax, rcx
    rep movsb
    ret
.eof:
    xor eax, eax
    ret
.pipe:
    mov r13, [r12 + O_PIPE]
.wait:
    mov rcx, [r13 + P_HEAD]
    sub rcx, [r13 + P_TAIL]         ; bytes in it
    jnz .data
    cmp qword [r13 + P_WRITERS], 0
    je .eof                         ; empty, and nobody can write any more: the end
    call block
    jmp .wait
.data:
    cmp rcx, rdx
    jbe .count
    mov rcx, rdx
.count:
    mov rax, rcx
.byte:
    jrcxz .read
    mov rsi, [r13 + P_TAIL]
    and esi, 4095
    add rsi, [r13 + P_BUF]
    movsb
    inc qword [r13 + P_TAIL]
    dec rcx
    jmp .byte
.read:
    call wake_all                   ; (room for a writer)
    ret

sys_write:                          ; write(fd, buffer, count)
    mov rdi, [rbx + F_RSI]
    mov rsi, [rbx + F_RDX]
    call user_range
    jc .fault
    mov rdi, [rbx + F_RDI]
    call fd_of
    test rax, rax
    jz .bad
    mov r12, rax
    mov rsi, [rbx + F_RSI]
    mov rdx, [rbx + F_RDX]
    mov rax, [r12 + O_TYPE]
    cmp rax, CONSOLE
    je .console
    cmp rax, FILE_W
    je .file
    cmp rax, PIPE_W
    je .pipe
.bad:
    mov rax, -EBADF
    ret
.fault:
    mov rax, -EFAULT
    ret
.console:
    mov rcx, rdx
    mov rax, rdx
    jrcxz .done
.out:
    push rax
    lodsb
    call putc
    pop rax
    loop .out
.done:
    ret
.file:
    mov r13, [r12 + O_FILE]
    mov rcx, [r13 + I_CAP]
    sub rcx, [r12 + O_POS]
    jbe .no_space
    cmp rcx, rdx
    jbe .put
    mov rcx, rdx
.put:
    mov rdi, [r13 + I_DATA]
    add rdi, [r12 + O_POS]
    add [r12 + O_POS], rcx
    mov rax, rcx
    rep movsb
    mov rcx, [r12 + O_POS]
    cmp rcx, [r13 + I_SIZE]
    jbe .grown
    mov [r13 + I_SIZE], rcx
.grown:
    ret
.no_space:
    mov rax, -ENOSPC
    test rdx, rdx
    jnz .grown
    xor eax, eax
    ret
.pipe:
    mov r13, [r12 + O_PIPE]
    xor r14d, r14d                  ; written so far
.wait:
    cmp qword [r13 + P_READERS], 0
    je .broken                      ; nobody will ever read it
    mov rcx, [r13 + P_HEAD]
    sub rcx, [r13 + P_TAIL]
    neg rcx
    add rcx, 4096                   ; room
    jnz .room
    call block
    jmp .wait
.room:
    mov rax, rdx
    sub rax, r14                    ; still to write
    cmp rcx, rax
    jbe .chunk
    mov rcx, rax
.chunk:
    add r14, rcx
.byte:
    jrcxz .wrote
    mov rdi, [r13 + P_HEAD]
    and edi, 4095
    add rdi, [r13 + P_BUF]
    movsb
    inc qword [r13 + P_HEAD]
    dec rcx
    jmp .byte
.wrote:
    call wake_all                   ; (something for a reader)
    cmp r14, rdx
    jb .wait
    mov rax, r14
    ret
.broken:
    mov rax, r14
    test rax, rax
    jnz .partly
    mov rax, -EPIPE
.partly:
    ret

sys_getcwd:                         ; getcwd(buffer, size): the length, with the 0
    mov rax, [current]
    imul rax, rax, T_SIZE
    lea rsi, [tasks + rax + T_CWD]
    xor ecx, ecx
.len:
    cmp byte [rsi + rcx], 0
    je .got
    inc ecx
    jmp .len
.got:
    inc ecx
    cmp rcx, [rbx + F_RSI]
    ja .range
    mov rdi, [rbx + F_RDI]
    push rsi
    mov rsi, rcx
    call user_range
    pop rsi
    jc .fault
    mov rax, rcx
    rep movsb
    ret
.range:
    mov rax, -ERANGE
    ret
.fault:
    mov rax, -EFAULT
    ret

sys_chdir:                          ; chdir(path)
    mov rdi, [rbx + F_RDI]
    call resolve
    test rax, rax
    jz .fault
    call lookup
    test rax, rax
    jz .missing
    cmp qword [rax + I_DIR], 0
    je .missing
    mov rax, [current]
    imul rax, rax, T_SIZE
    lea rdi, [tasks + rax + T_CWD]
    mov rsi, pathbuf
.copy:
    lodsb
    stosb
    test al, al
    jnz .copy
    xor eax, eax
    ret
.missing:
    mov rax, -ENOENT
    ret
.fault:
    mov rax, -EFAULT
    ret

; map_in(rdx = a PML4, rdi = virtual page, rsi = frame): like map_user, in any space
map_in:
    push rbx
    push rcx
    push rdx
    mov rbx, rdx
    mov ecx, 39
.level:
    mov rax, ADDR
    and rbx, rax
    mov rdx, rdi
    shr rdx, cl
    and edx, 511
    mov rax, DIRECT
    add rax, rbx
    lea rdx, [rax + rdx * 8]
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
    sub ecx, 9
    cmp ecx, 12
    ja .level
    mov rax, ADDR
    and rbx, rax
    mov rdx, rdi
    shr rdx, 12
    and edx, 511
    mov rax, DIRECT
    add rax, rbx
    lea rdx, [rax + rdx * 8]
    mov rax, rsi
    or rax, P + W + U
    mov [rdx], rax
.fail:
    pop rdx
    pop rcx
    pop rbx
    ret

CALLS equ 81

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
    test byte [rsp + 64], 3         ; a program's fault: no report, it just dies
    jz .kernel_fault
    mov rax, [rsp + 40]             ; killed, as a signal would: SIGFPE (8) for a divide
    mov edi, 11                     ; error, SIGILL (4) for #UD, SIGSEGV (11) for the rest
    cmp eax, 0
    jne .nde
    mov edi, 8
.nde:
    cmp eax, 6
    jne .sig
    mov edi, 4
.sig:
    jmp do_exit
.kernel_fault:
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
    mov rax, [rsp + 40]             ; killed, as a signal would: SIGFPE (8) for a divide
    mov edi, 11                     ; error, SIGILL (4) for #UD, SIGSEGV (11) for the rest
    cmp eax, 0
    jne .not_de
    mov edi, 8
.not_de:
    cmp eax, 6
    jne .signal
    mov edi, 4
.signal:
    jmp do_exit
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

section .data follows=.text vfollows=.text align=16 valign=16
align 8
calls:                              ; the system calls, by number
    dq HIGH + sys_read, HIGH + sys_write, HIGH + sys_open, HIGH + sys_close, 0, 0
    dq 0, 0, 0, 0, 0, 0
    dq 0, 0, 0, 0, 0, 0
    dq 0, 0, 0, 0, HIGH + sys_pipe, 0
    dq 0, 0, 0, 0, 0, 0
    dq 0, 0, 0, HIGH + sys_dup2, 0, 0
    dq 0, 0, 0, 0, 0, 0
    dq 0, 0, 0, 0, 0, 0
    dq 0, 0, 0, 0, 0, 0
    dq 0, 0, 0, HIGH + sys_fork, 0, HIGH + sys_execve
    dq HIGH + sys_exit, HIGH + sys_wait4, 0, 0, 0, 0
    dq 0, 0, 0, 0, 0, 0
    dq 0, 0, 0, 0, 0, 0
    dq 0, HIGH + sys_getcwd, HIGH + sys_chdir
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
s_shell: db "shell exited with status ", 0
s_deadlock: db "deadlock: every task is waiting", 13, 10, 0
s_sh_path: db "/bin/sh", 0
s_bad_elf: db "exec failed: not an x86-64 executable this kernel can load", 13, 10, 0
s_program: db "program", 0
s_no_memory: db "out of memory", 13, 10, 0
digits:  db "0123456789abcdef"
s_0x:    db "0x", 0
crlf:    db 13, 10, 0

section kbss nobits follows=.data align=4096
boot_info: resd 1
search:    resd 1
alignb 8
current:     resq 1                 ; the running task's number
next_pid:    resq 1
tasks:       resb TASKS * T_SIZE
ofiles:      resb OFILES * O_SIZE
pipes:       resb PIPES * P_SIZE
files:       resb FILES * I_SIZE_
stdin_at:    resq 1                 ; what the console's read gives next
stdin_left:  resq 1
argc:        resq 1
argv_at:     resq MAX_ARGS          ; the arguments, while execve builds a stack
argv_user:   resq MAX_ARGS
boot_frame:  resb F_SIZE
pathbuf:     resb PATH_MAX
argbuf:      resb ARGBUF
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
kernel_end:
