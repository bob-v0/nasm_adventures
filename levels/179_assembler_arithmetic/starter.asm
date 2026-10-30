; Level 179 — The Assembler Counts
;
; rax = number of entries in squares   (computed, not typed)
; rbx = length of poem                 (computed with $)
; rcx = seconds in a week              (an expression)
; rdx = bytes from start of squares to end of ruler


section .data
; squares: 0*0, 1*1, ... 15*15 as qwords (use %assign and %rep)

; poem: Level 179: the assembler counts, so you never have to count again

; ruler: 40 '-' characters and a newline (use times)
