; Level 111 — Tiny Shell (boss)
;
; Read commands from stdin, one per line, until the end of input, and run them:
;
;   words are separated by spaces or tabs; blank lines do nothing
;   NAME ARGS...        run a program: NAME with a '/' is a path, otherwise /bin/NAME
;   A ... | B ... | C   a pipeline: all stages run at the same time
;   < FILE   > FILE     stdin of the first stage / stdout of the last stage
;                       (> creates or truncates, mode 0644)
;   cd DIR              builtin: change the shell's directory
;   exit [N]            builtin: exit with N, or with $?
;   $?                  a word that is exactly $? becomes the last status
;
; Status ($?): the last stage's exit code, or 128 + signal; 0 after a successful cd,
; 1 after a failed one. At the end of input, exit with $?.
; Errors, on stderr (then the command's status):
;   sh: cannot execute NAME     (from the child; exit 127)
;   sh: cannot open FILE        (from the child; exit 1)
;   sh: cannot cd to DIR        (status 1)
;
; Read stdin one byte at a time: the programs you start share it, and must find the
; rest of the script there. Wait for every child; close every pipe end you don't use.

global _start

section .text
_start:
    ; TODO
    mov eax, 60
    xor edi, edi
    syscall
