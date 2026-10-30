; Level 144 — Bug: Assumed Zero
;
; Scans the NUL-terminated `text`:
;   rax = number of vowels (a e i o u, either case)
;   rbx = sum of the digit values ('7' counts 7)
;   rcx = length of the string
;
; Its author tested it and it worked. In this level the registers you don't set
; start with garbage, as they do when real code calls yours.
; Fix it, changing at most 4 lines.

    mov rsi, text
.scan:
    mov dl, [rsi]
    test dl, dl
    jz .done
    inc rcx                     ; length
    cmp dl, '0'
    jb .letter
    cmp dl, '9'
    ja .letter
    sub dl, '0'
    add rbx, rdx                ; digit sum
    jmp .advance
.letter:
    or dl, 0x20                 ; lowercase
    cmp dl, 'a'
    je .vowel
    cmp dl, 'e'
    je .vowel
    cmp dl, 'i'
    je .vowel
    cmp dl, 'o'
    je .vowel
    cmp dl, 'u'
    jne .advance
.vowel:
    inc rax
.advance:
    inc rsi
    jmp .scan
.done:
