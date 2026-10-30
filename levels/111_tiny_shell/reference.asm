; Level 111 — Tiny Shell (reference)
global _start

MAX_WORDS  equ 64
MAX_STAGES equ 16

section .text
_start:
    mov rbx, [rsp]
    lea rax, [rsp + rbx*8 + 16]
    mov [envp], rax
.loop:
    call read_line
    test rax, rax
    js .eof
    call run_line
    jmp .loop
.eof:
    mov eax, 60
    mov rdi, [status]
    syscall

; ---- input ----------------------------------------------------------------------

read_line:                      ; one byte at a time: what's after the line stays in stdin
    xor ebx, ebx                ; length
.byte:
    xor eax, eax                ; read(0, &line[len], 1)
    xor edi, edi
    lea rsi, [line + rbx]
    mov edx, 1
    syscall
    test rax, rax
    jle .end
    cmp byte [line + rbx], 10
    je .done
    cmp rbx, 1022
    jae .byte                   ; too long: drop the rest of the line
    inc rbx
    jmp .byte
.end:
    test rbx, rbx
    jnz .done
    mov rax, -1                 ; end of input
    ret
.done:
    mov byte [line + rbx], 0
    mov rax, rbx
    ret

; ---- one line ---------------------------------------------------------------------

run_line:
    mov rax, [status]           ; "$?" will point at this text
    lea rdi, [statstr]
    call utoa
    ; split into words, in place
    lea rsi, [line]
    xor ebx, ebx                ; word count
.skip:
    mov al, [rsi]
    test al, al
    jz .split_done
    cmp al, ' '
    je .space
    cmp al, 9
    je .space
    cmp ebx, MAX_WORDS - 1
    jae .split_done
    mov [words + rbx*8], rsi
    cmp word [rsi], '$?'
    jne .word
    cmp byte [rsi + 2], 0
    je .dollar
    cmp byte [rsi + 2], ' '
    jne .word
.dollar:
    lea rax, [statstr]
    mov [words + rbx*8], rax
.word:
    inc ebx
.in_word:
    inc rsi
    mov al, [rsi]
    test al, al
    jz .split_done
    cmp al, ' '
    je .end_word
    cmp al, 9
    jne .in_word
.end_word:
    mov byte [rsi], 0
.space:
    inc rsi
    jmp .skip
.split_done:
    test ebx, ebx
    jz .ret

    ; words -> stages (argv arrays separated by NULL) and redirections
    mov qword [infile], 0
    mov qword [outfile], 0
    lea rax, [argvs]
    mov [stages], rax
    mov r12d, 1                 ; stage count
    xor ecx, ecx                ; word index
    lea rdi, [argvs]            ; next argv slot
.token:
    cmp ecx, ebx
    jae .tokens_done
    mov rsi, [words + rcx*8]
    inc ecx
    cmp word [rsi], '|'
    je .pipe
    cmp word [rsi], '<'
    je .from
    cmp word [rsi], '>'
    je .to
    mov [rdi], rsi
    add rdi, 8
    jmp .token
.pipe:
    mov qword [rdi], 0
    add rdi, 8
    cmp r12d, MAX_STAGES
    jae .token
    mov [stages + r12*8], rdi
    inc r12d
    jmp .token
.from:
    cmp ecx, ebx
    jae .tokens_done
    mov rax, [words + rcx*8]
    mov [infile], rax
    inc ecx
    jmp .token
.to:
    cmp ecx, ebx
    jae .tokens_done
    mov rax, [words + rcx*8]
    mov [outfile], rax
    inc ecx
    jmp .token
.tokens_done:
    mov qword [rdi], 0
    mov [nstages], r12

    mov rax, [stages]           ; builtins (a single command only)
    mov rsi, [rax]
    test rsi, rsi
    jz .ret
    cmp r12d, 1
    jne .pipeline
    cmp word [rsi], 'cd'
    jne .not_cd
    cmp byte [rsi + 2], 0
    je builtin_cd
.not_cd:
    cmp dword [rsi], 'exit'
    jne .pipeline
    cmp byte [rsi + 4], 0
    je builtin_exit
.pipeline:
    call run_pipeline
.ret:
    ret

builtin_cd:                     ; rax = argv
    mov rdi, [rax + 8]
    test rdi, rdi
    jz .fail
    mov r12, rdi
    mov eax, 80                 ; chdir(dir)
    syscall
    test rax, rax
    js .fail
    mov qword [status], 0
    ret
.fail:
    lea rdi, [cd_msg]
    mov rsi, r12
    call complain
    mov qword [status], 1
    ret

builtin_exit:                   ; rax = argv
    mov rsi, [rax + 8]
    mov rdi, [status]
    test rsi, rsi
    jz .exit
    xor edi, edi                ; atoi
.digit:
    movzx eax, byte [rsi]
    sub eax, '0'
    cmp eax, 9
    ja .exit
    imul rdi, rdi, 10
    add rdi, rax
    inc rsi
    jmp .digit
.exit:
    mov eax, 60
    syscall

; ---- running a pipeline -------------------------------------------------------------

run_pipeline:
    mov qword [prev_read], -1
    xor r12d, r12d              ; stage index
.stage:
    cmp r12, [nstages]
    jae .wait
    mov rax, [nstages]
    dec rax
    cmp r12, rax
    jae .fork                   ; the last stage needs no new pipe
    mov eax, 22                 ; pipe(fds)
    lea rdi, [fds]
    syscall
.fork:
    mov eax, 57
    syscall
    test rax, rax
    jz child
    mov [pids + r12*8], rax
    mov rdi, [prev_read]        ; the parent keeps no pipe ends it doesn't need
    test rdi, rdi
    js .no_prev
    mov eax, 3
    syscall
.no_prev:
    mov rax, [nstages]
    dec rax
    cmp r12, rax
    jae .next
    mov eax, 3
    mov edi, [fds + 4]
    syscall
    mov eax, [fds]
    mov [prev_read], rax
.next:
    inc r12
    jmp .stage
.wait:
    xor r12d, r12d
.wait_one:
    cmp r12, [nstages]
    jae .done
    mov eax, 61                 ; wait4(pid, &wstatus, 0, 0)
    mov rdi, [pids + r12*8]
    lea rsi, [wstatus]
    xor edx, edx
    xor r10d, r10d
    syscall
    inc r12
    jmp .wait_one
.done:
    mov eax, [wstatus]          ; the last stage's: exit code, or 128 + signal
    test eax, 0x7f
    jnz .signaled
    shr eax, 8
    and eax, 0xff
    jmp .set
.signaled:
    and eax, 0x7f
    add eax, 128
.set:
    mov [status], rax
    ret

child:                          ; r12 = stage index
    mov rdi, [prev_read]        ; stdin: the previous stage's pipe...
    test rdi, rdi
    js .first
    xor esi, esi
    call move_fd
    jmp .stdout
.first:
    mov rsi, [infile]           ; ...or < file, for the first stage
    test rsi, rsi
    jz .stdout
    xor esi, esi                ; O_RDONLY
    xor ebx, ebx                ; -> fd 0
    mov rdi, [infile]
    call open_onto
.stdout:
    mov rax, [nstages]
    dec rax
    cmp r12, rax
    jae .last
    mov eax, 3                  ; not the last stage: stdout is the new pipe
    mov edi, [fds]
    syscall
    mov edi, [fds + 4]
    mov esi, 1
    call move_fd
    jmp .exec
.last:
    mov rdi, [outfile]          ; > file, for the last stage
    test rdi, rdi
    jz .exec
    mov esi, 1 | 0o100 | 0o1000 ; O_WRONLY | O_CREAT | O_TRUNC
    mov ebx, 1
    call open_onto
.exec:
    mov r13, [stages + r12*8]   ; argv
    mov rsi, [r13]
    lea rdi, [pathbuf]          ; a name without '/' is looked up in /bin
    mov rcx, rsi
.has_slash:
    mov al, [rcx]
    test al, al
    jz .in_bin
    inc rcx
    cmp al, '/'
    jne .has_slash
    mov rdi, rsi
    jmp .execve
.in_bin:
    mov dword [rdi], '/bin'
    mov byte [rdi + 4], '/'
    add rdi, 5
.copy:
    lodsb
    stosb
    test al, al
    jnz .copy
    lea rdi, [pathbuf]
.execve:
    mov eax, 59
    mov rsi, r13
    mov rdx, [envp]
    syscall
    lea rdi, [exec_msg]
    mov rsi, [r13]
    call complain
    mov eax, 60
    mov edi, 127
    syscall

move_fd:                        ; dup2(rdi, rsi), then close(rdi)
    push rdi
    mov eax, 33
    syscall
    pop rdi
    mov eax, 3
    syscall
    ret

open_onto:                      ; open(rdi, esi, 0644) onto fd ebx, or exit(1)
    push rdi
    mov eax, 2
    mov edx, 0o644
    syscall
    pop rsi
    test rax, rax
    js .fail
    mov rdi, rax
    mov esi, ebx
    jmp move_fd
.fail:
    lea rdi, [open_msg]
    call complain
    mov eax, 60
    mov edi, 1
    syscall

; ---- output helpers -------------------------------------------------------------------

complain:                       ; stderr: "sh: " message word "\n"
    push rsi
    push rdi
    lea rsi, [sh_prefix]
    call eputs
    pop rsi
    call eputs
    pop rsi
    call eputs
    lea rsi, [newline]
eputs:                          ; rsi = C string, to stderr
    xor edx, edx
.len:
    cmp byte [rsi + rdx], 0
    je .write
    inc rdx
    jmp .len
.write:
    mov eax, 1
    mov edi, 2
    syscall
    ret

utoa:                           ; rax -> decimal C string at rdi
    mov rcx, rdi
    mov r8d, 10
    lea rsi, [rdi + 20]
    mov byte [rsi], 0
.digit:
    xor edx, edx
    div r8
    add dl, '0'
    dec rsi
    mov [rsi], dl
    test rax, rax
    jnz .digit
.move:
    mov al, [rsi]
    mov [rcx], al
    inc rsi
    inc rcx
    test al, al
    jnz .move
    ret

section .data
sh_prefix: db "sh: ", 0
cd_msg:    db "cannot cd to ", 0
exec_msg:  db "cannot execute ", 0
open_msg:  db "cannot open ", 0
newline:   db 10, 0

section .bss
envp:      resq 1
status:    resq 1
nstages:   resq 1
infile:    resq 1
outfile:   resq 1
prev_read: resq 1
fds:       resd 2
wstatus:   resd 1
words:     resq MAX_WORDS
stages:    resq MAX_STAGES
pids:      resq MAX_STAGES
argvs:     resq MAX_WORDS + MAX_STAGES
statstr:   resb 24
line:      resb 1024
pathbuf:   resb 1100
