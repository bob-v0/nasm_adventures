; Level 126 — argv, envp, auxv
;
; Print: each argv[1..] on its own line; then $HOME (or "(no HOME)"); then the
; AT_PAGESZ value from the auxiliary vector. Exit with argc - 1.

global _start

section .text
_start:
    ; TODO
