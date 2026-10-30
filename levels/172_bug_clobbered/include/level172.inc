; Provided by level 172: three 16-byte log lines. Tests change the text.
section .data
lines:
    db "boot: cpu ok   ", 10
    db "boot: mem ok   ", 10
    db "boot: disk ok  ", 10
LINE_LEN equ 16
