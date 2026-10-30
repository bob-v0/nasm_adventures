; Level 180 — Names for Places
;
; The game provides:   input: dq <value>   (in .data)
;
; Your code runs from here, in .text:

; TODO: copy [input] to [slot]
; TODO: rax = address of greeting
; TODO: rbx = byte at greeting+7, zero-extended
; TODO: counter = 0xBEEF


section .data
; TODO: greeting (the bytes "Hello, Ring!" then a 0 byte)
; TODO: counter (16 bits)


section .bss
; TODO: slot (8 bytes)
