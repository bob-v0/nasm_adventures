; Level 174 — Debugger Eyes
;
; 1. Find the key: ring debug --binary vault   (or: gdb ./vault)
; 2. Write its 8 bytes to stdout, then exit(0).

global _start

section .text
_start:
    ; TODO

section .data
key: dq 0       ; TODO: the key
