; Level 175 — Speak
;
; stdout: "Hello, " + name + "!\n"
; stderr: "warning: the walls have ears\n"
; exit status = return value of the stderr write

%include "level175.inc"      ; name (8 bytes), NAME_LEN

global _start

section .text
_start:
    ; TODO

section .data
    ; TODO: your strings
