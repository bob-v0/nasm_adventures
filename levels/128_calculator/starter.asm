; Level 128 — Calculator ★
;
; Read one line; evaluate:  expr := term {(+|-) term}
;                           term := factor {(*|/) factor}
;                           factor := number | ( expr ) | - factor
; Print the signed result + "\n", exit 0. On any error print "error\n", exit 1.

global _start

section .text
_start:
    ; TODO
