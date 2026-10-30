%include "_common.inc"
global _start
section .text
_start:
    WRITE 1, msg, 12
    EXIT 0
section .data
msg: db "hello world", 10
