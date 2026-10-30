; Level 121 — Processes
;
; argv[1..] are paths of programs. For each one, in order:
;   fork; the child execve()s it with argv = [path] and your envp;
;   if execve fails, the child writes "PATH: cannot execute\n" to stderr and exits 127.
;   The parent waits for the child, then prints one of
;       PATH: exited N
;       PATH: killed by signal N
; Exit with the number of commands that did not exit 0.

global _start

section .text
_start:
    ; TODO
    mov eax, 60
    xor edi, edi
    syscall
