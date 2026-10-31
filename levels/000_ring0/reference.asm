; Level 0 — Ring 0 (reference)
;
; One image: a boot sector, a second stage, the kernel. The BIOS loads sector 0; it loads
; the second stage, which gathers what the kernel needs (the memory map, the game's data
; from the disk) into a multiboot-style information block, enters protected mode, puts
; the kernel at 1 MiB and jumps to it, as QEMU's multiboot loader did until now.

KERNEL_LOAD  equ 0x20000            ; where the second stage reads the kernel first
KERNEL_READ  equ 256                ; sectors of it (128 KiB: the rest is the disk's zeros)
DATA_LBA     equ 2048               ; the game's data: a header sector, the files, stdin
DATA_LOAD    equ 0x40000
MBI          equ 0x6000             ; the information block, and its module list
MODS         equ 0x6040
MMAP         equ 0x6100             ; the memory map, multiboot style: size, base, length, type

; ---- sector 0 -------------------------------------------------------------------------

section boot start=0 vstart=0x7C00
bits 16
    cli
    xor ax, ax
    mov ds, ax
    mov es, ax
    mov ss, ax
    mov sp, 0x7C00
    sti
    mov [boot_drive], dl
    mov eax, 1                      ; the second stage: right after this sector
    mov cx, STAGE2_SECTORS
    mov bx, 0x07E0                  ; at 0x7E00
    call read
    jmp 0:stage2_main

; read(eax = first sector, cx = how many, bx = segment): through the BIOS (int 0x13,
; extended read), 64 sectors (32 KiB) at a time
read:
    pushad
.chunk:
    mov dx, cx
    cmp dx, 64
    jbe .some
    mov dx, 64
.some:
    mov word [dap + 2], dx
    mov word [dap + 4], 0
    mov [dap + 6], bx
    mov [dap + 8], eax
    mov dword [dap + 12], 0
    push eax                        ; (the BIOS may change any register)
    push bx
    push cx
    push dx
    mov si, dap
    mov dl, [boot_drive]
    mov ah, 0x42
    int 0x13
    pop dx
    pop cx
    pop bx
    pop eax
    jc .fail
    movzx edx, dx
    add eax, edx
    shl dx, 5                       ; 512 / 16: the segment moves on
    add bx, dx
    shr dx, 5
    sub cx, dx
    jnz .chunk
    popad
    ret
.fail:
    mov si, s_disk
.say:
    lodsb
    test al, al
    jz .stop
    mov ah, 0x0E
    int 0x10
    jmp .say
.stop:
    cli
    hlt

boot_drive: db 0
align 4
dap:        db 16, 0
            times 14 db 0
s_disk:     db "disk read failed", 0
    times 510 - ($ - $$) db 0
    dw 0xAA55

; ---- the second stage ------------------------------------------------------------------

section stage2 follows=boot vstart=0x7E00
bits 16
stage2_main:
    ; the kernel, to KERNEL_LOAD for now (the BIOS can't reach 1 MiB)
    mov eax, 1 + STAGE2_SECTORS     ; (the kernel follows the second stage)
    mov cx, KERNEL_READ
    mov bx, KERNEL_LOAD >> 4
    call read
    ; the game's data: its header, then the files, then stdin
    mov eax, DATA_LBA
    mov cx, 1
    mov bx, 0x0500 >> 4
    call read
    cmp dword [0x500], 'RING'
    jne .no_data
    mov eax, DATA_LBA + 1
    mov cx, [0x508]                 ; the files' sectors
    mov bx, DATA_LOAD >> 4
    call read
    mov eax, [0x508]
    shl eax, 9
    add eax, DATA_LOAD
    mov [loader_stdin], eax
    mov eax, DATA_LBA + 1
    add eax, [0x508]
    mov cx, [0x510]                 ; stdin's sectors
    test cx, cx
    jz .loaded
    mov ebx, [loader_stdin]
    shr ebx, 4
    call read
.loaded:
    ; the information block: modules (bit 3), memory map (bit 6)
    mov dword [MBI], 1 << 3 | 1 << 6
    mov dword [MBI + 20], 2
    mov dword [MBI + 24], MODS
    mov dword [MODS], DATA_LOAD
    mov eax, [0x50C]                ; the files' bytes
    add eax, DATA_LOAD
    mov [MODS + 4], eax
    mov dword [MODS + 8], 0
    mov eax, [loader_stdin]
    mov [MODS + 16], eax
    add eax, [0x514]                ; stdin's bytes
    mov [MODS + 20], eax
    mov dword [MODS + 24], 0
    ; the memory map: e820, each entry with its size (20) in front, as multiboot has it
    mov di, MMAP
    xor ebx, ebx
.e820:
    mov eax, 0xE820
    mov edx, 'PAMS'                 ; ("SMAP")
    mov ecx, 20
    push di
    add di, 4
    int 0x15
    pop di
    jc .mapped
    mov dword [di], 20
    add di, 24
    test ebx, ebx
    jnz .e820
.mapped:
    mov word [MBI + 48], MMAP
    mov word [MBI + 50], 0
    sub di, MMAP
    movzx eax, di
    mov [MBI + 44], eax
    ; A20 on (the fast way), then protected mode
    in al, 0x92
    or al, 2
    and al, 0xFE
    out 0x92, al
    cli
    lgdt [pm_gdt_pointer]
    mov eax, cr0
    or eax, 1
    mov cr0, eax
    jmp dword 0x08:pm32
.no_data:
    mov si, s_no_data
.say:
    lodsb
    test al, al
    jz .stop
    mov ah, 0x0E
    int 0x10
    jmp .say
.stop:
    cli
    hlt

bits 32
pm32:
    mov ax, 0x10
    mov ds, ax
    mov es, ax
    mov ss, ax
    mov esp, 0x7C00
    mov esi, KERNEL_LOAD            ; the kernel to 1 MiB
    mov edi, 0x100000
    mov ecx, KERNEL_READ * 512 / 4
    rep movsd
    mov ecx, kernel_end             ; and the rest of its .bss: zeros
    sub ecx, edi
    jbe .zeroed
    shr ecx, 2
    xor eax, eax
    rep stosd
.zeroed:
    mov eax, 0x2BADB002             ; what a multiboot loader says
    mov ebx, MBI
    jmp 0x08:0x100000

align 8
pm_gdt:
    dq 0
    dq 0x00CF9A000000FFFF
    dq 0x00CF92000000FFFF
pm_gdt_pointer:
    dw 23
    dd pm_gdt
loader_stdin: dd 0
s_no_data: db "no game data on the disk", 0
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
MAX_CPUS equ 8
TASKS    equ MAX_CPUS + 24          ; slots 0 to MAX_CPUS - 1: each CPU's idle task
IDLE     equ 5                      ; (T_STATE: an idle task, never anyone else's)
RUNNING  equ 3
PC_KSTACK equ 0                     ; per-CPU data (gs, in the kernel): the running task's
PC_USER_RSP equ 8                   ; kernel stack top; a program's rsp, for a moment;
PC_CURRENT equ 16                   ; the running task; this CPU's number; its TSS
PC_CPU   equ 24
PC_TSS   equ 32
PC_SIZE  equ 64
TSS_SIZE equ 128
IDLE_STACK equ 8192
APIC     equ 0xFEE00000
APIC_SVR equ 0xF0
ICR_LOW  equ 0x300
ICR_HIGH equ 0x310
PCD      equ 1 << 4
TRAMPOLINE equ 0x8000
NFD      equ 16                 ; file descriptors per task
CWD_MAX  equ 128
T_KSP    equ 0                  ; a task: its saved kernel rsp,
T_SPACE  equ 8                  ; its PML4,
T_STACK  equ 16                 ; its kernel stack's frame,
T_STATE  equ 24                 ; 0 free, 1 ready, 2 zombie, 3 running, 4 waiting, 5 idle
T_PID    equ 32
T_PPID   equ 40
T_STATUS equ 48                 ; (a zombie) what wait4 reports
T_FDS    equ 56                 ; NFD open files
T_CWD    equ T_FDS + NFD * 8    ; the current directory
T_NAME   equ T_CWD + CWD_MAX    ; a program started at boot: its name (its lines say it)
NAME_LEN equ 32
T_LINELEN equ T_NAME + NAME_LEN ; what it has written to the console, a line at a time
T_LINE   equ T_LINELEN + 8
LINE_MAX equ 240
T_SIZE   equ T_LINE + LINE_MAX
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
    mov rsp, HIGH + idle_stacks + IDLE_STACK    ; CPU 0's idle stack
    call init_idt                   ; (the IDT and the GDT, shared by all CPUs)
    call silence_pic
    xor edi, edi
    call cpu_init                   ; CPU 0's own: TSS, gs, system call MSRs, its APIC
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
    mov qword [next_pid], 1
    call wake_cpus                  ; the others start in their idle loops...
    mov ecx, 20000                  ; (time to get there)
    call delay_us
    call lock_kernel                ; (they look for work: the tasks are made under the lock)
    call start_shell
    call start_inits
    call unlock_kernel
    jmp idle                        ; ...and so does this one

; start_shell: the first process: /bin/sh, in /work, the console as fds 0, 1 and 2
start_shell:
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
    push r12
    mov r12, [rax + I_DATA]
    call load_elf
    pop r12
    mov r14, rax
    mov rax, argbuf                 ; argv: "sh"
    mov dword [rax], 'sh'
    mov [argv_at], rax
    mov qword [argc], 1
    call make_stack
    mov qword [boot_frame + F_R11], 0x202
    mov [boot_frame + F_RCX], r14
    mov [boot_frame + F_RSP], rax
    mov rdi, r12
    mov rsi, boot_frame
    call start_frame
    inc qword [alive]
    mov rax, pml4
    mov cr3, rax
    ret

; start_inits: every program in /init too, at the same time, named after its file
start_inits:
    push rbx
    mov rbx, files
.file:
    cmp qword [rbx + I_USED], 0
    je .next
    cmp qword [rbx + I_DIR], 0
    jne .next
    cmp dword [rbx], '/ini'
    jne .next
    cmp word [rbx + 4], 't/'
    jne .next
    call start_program
.next:
    add rbx, I_SIZE_
    mov rax, files + FILES * I_SIZE_
    cmp rbx, rax
    jb .file
    pop rbx
    ret

; start_program(rbx = the file): a task running it, in /, its name the file's (after
; "/init/"), the console as fds 0, 1 and 2
start_program:
    push r12
    push r13
    push r14
    call new_task
    test rax, rax
    jz .out
    mov r12, rax
    mov word [r12 + T_CWD], '/'
    lea rsi, [rbx + 6]              ; the name
    lea rdi, [r12 + T_NAME]
    mov ecx, NAME_LEN - 1
.name:
    lodsb
    stosb
    test al, al
    loopnz .name
    mov byte [rdi], 0
    mov rax, [tasks + MAX_CPUS * T_SIZE + T_FDS]   ; (the shell's console)
    add qword [rax + O_REFS], 3
    mov [r12 + T_FDS], rax
    mov [r12 + T_FDS + 8], rax
    mov [r12 + T_FDS + 16], rax
    call new_space
    mov [r12 + T_SPACE], rax
    mov cr3, rax
    mov r13, [rbx + I_SIZE]
    push r12
    mov r12, [rbx + I_DATA]
    call load_elf
    pop r12
    mov r14, rax
    lea rax, [r12 + T_NAME]         ; argv: its name
    mov [argv_at], rax
    mov qword [argc], 1
    call make_stack
    mov qword [boot_frame + F_R11], 0x202
    mov [boot_frame + F_RCX], r14
    mov [boot_frame + F_RSP], rax
    mov rdi, r12
    mov rsi, boot_frame
    call start_frame
    inc qword [alive]
    mov rax, pml4
    mov cr3, rax
.out:
    pop r14
    pop r13
    pop r12
    ret

; console_write(rsi = bytes, rdx = how many), for the current task: a line at a time, so
; that nothing another CPU prints lands in the middle of one; a named task's lines begin
; with [its name]. rax = how many.
console_write:
    push r8
    mov rax, [gs:PC_CURRENT]
    imul r8, rax, T_SIZE
    add r8, tasks
    mov rcx, rdx
    jrcxz .done
.byte:
    lodsb
    mov r9, [r8 + T_LINELEN]
    mov [r8 + T_LINE + r9], al
    inc qword [r8 + T_LINELEN]
    cmp al, 10
    je .flush
    cmp qword [r8 + T_LINELEN], LINE_MAX
    jb .next
.flush:
    call flush_line
.next:
    loop .byte
.done:
    mov rax, rdx
    pop r8
    ret

flush_line:                         ; r8 = a task: print what its line holds
    push rax
    push rcx
    push rsi
    mov rcx, [r8 + T_LINELEN]
    jrcxz .out
    cmp byte [r8 + T_NAME], 0
    je .text
    mov al, '['
    call putc
    lea rsi, [r8 + T_NAME]
    call puts
    mov al, ']'
    call putc
    mov al, ' '
    call putc
.text:
    lea rsi, [r8 + T_LINE]
.char:
    lodsb
    call putc
    loop .char
    mov qword [r8 + T_LINELEN], 0
.out:
    pop rsi
    pop rcx
    pop rax
    ret

; ---- CPUs ----------------------------------------------------------------------------

; cpu_init(rdi = this CPU's number): its TSS (RSP0 later, IST1 now) and GDT entry, its
; per-CPU data in gs (in the kernel gs is always this; a program's is 0), the system call
; MSRs, its APIC, and its idle task
cpu_init:
    push rbx
    mov rbx, rdi
    imul rsi, rbx, PC_SIZE
    mov rax, HIGH + percpu
    add rsi, rax                    ; its per-CPU data
    imul rdi, rbx, TSS_SIZE
    mov rax, HIGH + tss
    add rdi, rax                    ; its TSS
    mov [rsi + PC_CPU], rbx
    mov [rsi + PC_CURRENT], rbx     ; (task slot n: CPU n's idle task)
    mov [rsi + PC_TSS], rdi
    imul rax, rbx, 4096
    mov rdx, HIGH + df_stacks + 4096
    add rax, rdx
    mov [rdi + 36], rax             ; IST1: a stack of its own for #DF
    mov word [rdi + 102], 104
    mov rax, rdi                    ; its TSS descriptor: 16 bytes, at 0x28 + 16n
    mov rdx, HIGH
    sub rax, rdx                    ; (the descriptor holds the TSS's address as the
    mov rdx, HIGH                   ;  kernel uses it: the higher half)
    add rax, rdx
    imul rcx, rbx, 16
    add rcx, gdt_tss
    mov word [rcx], 103
    mov [rcx + 2], ax
    shr rax, 16
    mov [rcx + 4], al
    mov byte [rcx + 5], 0x89
    mov [rcx + 7], ah
    shr rax, 16
    mov [rcx + 8], eax
    lgdt [gdt_pointer]
    lea eax, [TSS_SEL + rbx * 8]
    lea eax, [rax + rbx * 8]        ; TSS_SEL + 16n
    ltr ax
    lidt [idt_pointer]
    mov ecx, GS_BASE                ; gs = its per-CPU data, from now on, in the kernel
    mov rax, rsi
    mov rdx, rsi
    shr rdx, 32
    wrmsr
    mov ecx, KERNEL_GS_BASE         ; (what swapgs gives a program: 0)
    xor eax, eax
    xor edx, edx
    wrmsr
    mov ecx, STAR
    xor eax, eax
    mov edx, KERNEL_DS << 16 | KERNEL_CS
    wrmsr
    mov ecx, LSTAR
    mov rax, HIGH + syscall_entry
    mov rdx, rax
    shr rdx, 32
    wrmsr
    mov ecx, SFMASK
    mov eax, 0x700
    xor edx, edx
    wrmsr
    mov rax, DIRECT + APIC          ; its APIC on
    mov dword [rax + APIC_SVR], 0x1FF
    imul rax, rbx, T_SIZE           ; its idle task
    add rax, tasks
    mov qword [rax + T_STATE], IDLE
    mov rdx, pml4
    mov [rax + T_SPACE], rdx
    pop rbx
    ret

; wake_cpus: the trampoline to TRAMPOLINE, then INIT, STARTUP, STARTUP to everyone else
wake_cpus:
    mov rsi, HIGH + trampoline
    mov rdi, TRAMPOLINE
    mov ecx, trampoline_end - trampoline
    rep movsb
    mov rbx, DIRECT + APIC
    mov dword [rbx + ICR_HIGH], 0
    mov dword [rbx + ICR_LOW], 0x000C4500
    call wait_sent
    mov ecx, 10000
    call delay_us
    mov dword [rbx + ICR_LOW], 0x000C4600 | (TRAMPOLINE >> 12)
    call wait_sent
    mov ecx, 200
    call delay_us
    mov dword [rbx + ICR_LOW], 0x000C4600 | (TRAMPOLINE >> 12)
    call wait_sent
    ret

wait_sent:                          ; rbx = the APIC
    pause
    test dword [rbx + ICR_LOW], 1 << 12
    jnz wait_sent
    ret

delay_us:                           ; ecx microseconds, by the PIT's channel 2
    push rax
    push rdx
    imul eax, ecx, 1193
    add eax, 999
    xor edx, edx
    mov ecx, 1000
    div ecx
.chunk:
    mov ecx, eax
    cmp ecx, 65535
    jbe .last
    mov ecx, 65535
.last:
    sub eax, ecx
    push rax
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
    pop rax
    test eax, eax
    jnz .chunk
    pop rdx
    pop rax
    ret

; where every other CPU arrives from the trampoline: 64-bit, at its higher-half address
ap_main:
    mov eax, 1                      ; my number (the first CPU is 0), and so my stack
    lock xadd [next_cpu], eax
    inc eax
    cmp eax, MAX_CPUS
    jae .spare
    imul rsp, rax, IDLE_STACK
    mov rdx, HIGH + idle_stacks + IDLE_STACK
    add rsp, rdx
    lgdt [gdt_pointer]              ; the kernel's GDT (the trampoline had its own)
    mov dx, KERNEL_DS
    mov ds, dx
    mov es, dx
    mov ss, dx
    push KERNEL_CS
    mov rdx, HIGH + .cs
    push rdx
    retfq
.cs:
    mov edi, eax
    call cpu_init
    lock inc dword [cpus_up]
    jmp idle
.spare:
    cli
.halt:
    hlt
    jmp .halt

; idle: this CPU's idle task. Look (without the lock) for a ready task; when there seems
; to be one, take the lock, pick it, switch to it. When this CPU has nothing to run, it
; comes back here, still holding the lock: let it go and look again.
idle:
.look:
    cmp byte [the_end], 0
    jne .stop
    mov rax, tasks
    mov ecx, TASKS
.task:
    cmp qword [rax + T_STATE], 1
    je .take
    add rax, T_SIZE
    loop .task
    pause
    jmp .look
.take:
    call lock_kernel
    call pick                       ; rax = a ready task, now running, or -1
    cmp rax, -1
    je .none
    mov rdi, [gs:PC_CURRENT]
    mov rsi, rax
    call switch_to                  ; (back here when this CPU is idle again)
.none:
    call unlock_kernel
    jmp .look
.stop:
    jmp halt_forever

; the big kernel lock: whoever runs kernel code that touches shared state holds it
lock_kernel:
    push rax
.try:
    mov eax, 1
    xchg eax, [kernel_lock]
    test eax, eax
    jz .mine
.spin:
    pause
    cmp byte [the_end], 0
    jne halt_forever
    cmp dword [kernel_lock], 0
    jne .spin
    jmp .try
.mine:
    pop rax
    ret

halt_forever:                       ; the end: this CPU stops (and stays stopped)
    cli
    hlt
    jmp halt_forever

unlock_kernel:
    mov dword [kernel_lock], 0
    ret

; pick (lock held): a ready task, round robin from [next_pick], marked running; or -1
pick:
    push rcx
    push rdx
    mov rax, [next_pick]
    mov ecx, TASKS
.look:
    cmp rax, TASKS
    jb .in
    xor eax, eax
.in:
    imul rdx, rax, T_SIZE
    cmp qword [tasks + rdx + T_STATE], 1
    je .found
    inc rax
    loop .look
    mov rax, -1
    jmp .out
.found:
    mov qword [tasks + rdx + T_STATE], RUNNING
    lea rcx, [rax + 1]
    mov [next_pick], rcx
.out:
    pop rdx
    pop rcx
    ret

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
    mov rdx, tasks + MAX_CPUS * T_SIZE  ; (not the idle tasks' slots)
    mov ecx, TASKS - MAX_CPUS
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
fork_ret:                           ; (holding the lock, as switch_to's callers do)
    mov rbx, rsp
    jmp syscall_exit

; schedule (the lock held; the current task isn't ready: waiting, or a zombie): run
; another ready task on this CPU, or this CPU's idle task. Returns when this task runs again.
schedule:
    call pick
    cmp rax, -1
    jne .found
    mov rax, [gs:PC_CPU]            ; nothing: idle
.found:
    mov rdi, [gs:PC_CURRENT]
    mov rsi, rax
    jmp switch_to

; switch_to(rdi = from, rsi = to): keep from's place (its kernel rsp, after pushing what a
; called function must keep), load to's, and return into to, on this CPU
switch_to:
    push rbx
    push rbp
    push r12
    push r13
    push r14
    push r15
    imul rdi, rdi, T_SIZE
    mov [tasks + rdi + T_KSP], rsp
    mov [gs:PC_CURRENT], rsi
    imul rsi, rsi, T_SIZE
    add rsi, tasks
    mov rax, [rsi + T_SPACE]        ; its memory
    mov cr3, rax
    cmp qword [rsi + T_STATE], IDLE
    je .stack
    mov rax, [gs:PC_CPU]            ; (this CPU has run a program)
    lock bts [cpus_used], rax
    mov rax, [rsi + T_STACK]        ; its kernel stack, for entries from ring 3
    mov rdx, DIRECT + 4096
    add rax, rdx
    mov rdx, [gs:PC_TSS]
    mov [rdx + 4], rax
    mov [gs:PC_KSTACK], rax
.stack:
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
    mov rax, [gs:PC_CURRENT]
    imul rax, rax, T_SIZE
    mov qword [tasks + rax + T_STATE], 4
    call schedule
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
; the parent to collect. The lock held. Never returns.
do_exit:
    mov r12, rdi
    mov rax, [gs:PC_CURRENT]
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
    push r8
    mov r8, r13                     ; what's left of its last line
    call flush_line
    pop r8
    mov [r13 + T_STATUS], r12
    mov qword [r13 + T_STATE], 2
    cmp qword [r13 + T_PPID], 0     ; started at boot? it says how it ended
    jne .wake
    cmp qword [r13 + T_PID], 1
    jne .named
    mov rsi, s_shell
    call puts
    jmp .status
.named:
    mov al, '['
    call putc
    lea rsi, [r13 + T_NAME]
    call puts
    mov rsi, s_exited
    call puts
.status:
    mov eax, r12d                   ; the exit status, or 128 + the signal
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
    dec qword [alive]
    jnz .wake
    mov rsi, s_all_done             ; the last of them: the end
    call puts
    mov rdx, [cpus_used]            ; (how many bits are set)
    xor eax, eax
.count:
    test rdx, rdx
    jz .counted
    lea rcx, [rdx - 1]
    and rdx, rcx                    ; (drops the lowest set bit)
    inc eax
    jmp .count
.counted:
    call decimal
    mov rsi, s_cpus
    call puts
    mov byte [the_end], 1           ; every CPU stops, wherever it is
    call unlock_kernel
    jmp halt_forever
.wake:
    call wake_all
    call schedule
    ; (a zombie is never scheduled again)

; ---- system calls ---------------------------------------------------------------------

syscall_entry:
    swapgs                          ; gs = this CPU's data
    mov [gs:PC_USER_RSP], rsp
    mov rsp, [gs:PC_KSTACK]         ; this task's kernel stack
    push qword [gs:PC_USER_RSP]     ; the frame: rsp, rip, rflags, then every register
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
    call lock_kernel                ; one CPU in the kernel at a time
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
    call unlock_kernel
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
    jmp do_exit

sys_fork:
    call new_task
    test rax, rax
    jz .no_memory
    mov r12, rax                    ; the child
    mov rax, [gs:PC_CURRENT]
    imul r13, rax, T_SIZE
    add r13, tasks                  ; the parent
    mov rax, [r13 + T_PID]
    mov [r12 + T_PPID], rax
    lea rsi, [r13 + T_CWD]          ; its directory, and its name
    lea rdi, [r12 + T_CWD]
    mov ecx, (CWD_MAX + NAME_LEN) / 8
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
    mov rax, [gs:PC_CURRENT]
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
    mov rax, [gs:PC_CURRENT]
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
    mov rax, [gs:PC_CURRENT]              ; relative: from the current directory
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
    mov rax, [gs:PC_CURRENT]
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
    mov rdx, [gs:PC_CURRENT]
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
    mov rdx, [gs:PC_CURRENT]
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
    mov rax, [gs:PC_CURRENT]
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
    jmp console_write
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
    mov rax, [gs:PC_CURRENT]
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
    mov rax, [gs:PC_CURRENT]
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
    test byte [rsp + 24], 3         ; from a program? gs = this CPU's, and the lock
    jz .in_kernel
    swapgs
    call lock_kernel
.in_kernel:
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
    call unlock_kernel              ; (only a program's faults get here)
    swapgs
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

; ---- the trampoline: copied to TRAMPOLINE, where a woken CPU starts, in real mode ----

bits 16
trampoline:
    cli
    xor ax, ax
    mov ds, ax
    o32 lgdt [TRAMPOLINE + (t_gdt_pointer - trampoline)]
    mov eax, cr0
    or eax, 1
    mov cr0, eax
    jmp dword 0x08:TRAMPOLINE + (.pm - trampoline)
bits 32
.pm:
    mov ax, 0x10
    mov ds, ax
    mov es, ax
    mov ss, ax
    mov eax, cr4
    or eax, 1 << 5                  ; PAE
    mov cr4, eax
    mov eax, pml4
    mov cr3, eax
    mov ecx, EFER
    rdmsr
    or eax, 1 << 0 | 1 << 8 | 1 << 11  ; SCE, LME, NXE
    wrmsr
    mov eax, cr0
    or eax, 1 << 31
    mov cr0, eax
    jmp 0x18:TRAMPOLINE + (.lm - trampoline)
bits 64
.lm:
    mov rax, HIGH + ap_main
    jmp rax
align 8
t_gdt:
    dq 0
    dq 0x00CF9A000000FFFF           ; 0x08: 32-bit code
    dq 0x00CF92000000FFFF           ; 0x10: data
    dq 0x00209A0000000000           ; 0x18: 64-bit code
t_gdt_pointer:
    dw 31
    dd TRAMPOLINE + (t_gdt - trampoline)
trampoline_end:
bits 64

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
    times MAX_CPUS dq 0, 0          ; each CPU's TSS (filled in by cpu_init)
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
s_exited: db "] exited with status ", 0
s_all_done: db "all done: user code ran on ", 0
s_cpus: db " cpus", 13, 10, 0
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
next_pid:    resq 1
next_pick:   resq 1
alive:       resq 1                 ; programs started at boot, still running
cpus_used:   resq 1
next_cpu:    resd 1
cpus_up:     resd 1
kernel_lock: resd 1
the_end:     resb 1
alignb 8
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
alignb 16
idt:       resb 32 * 16
alignb 16
percpu:    resb PC_SIZE * MAX_CPUS
tss:       resb TSS_SIZE * MAX_CPUS
alignb 16
df_stacks: resb 4096 * MAX_CPUS
idle_stacks: resb IDLE_STACK * MAX_CPUS
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
kernel_end:
