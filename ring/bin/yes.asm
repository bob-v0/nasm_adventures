; yes: prints "y" lines forever (until a write fails, e.g. SIGPIPE/EPIPE).
%include "_common.inc"
global _start
section .text
_start:
    WRITE 1, line, 2
    test rax, rax
    jg _start
    EXIT 1
section .data
line: db "y", 10
