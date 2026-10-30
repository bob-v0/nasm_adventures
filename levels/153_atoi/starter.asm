; Level 153 — Text to Numbers
;
; text: NUL-terminated string. Format: [+|-] ( digits | 0x hexdigits )
;   rax = value, rbx = 0           if valid and in signed 64-bit range
;   rax = 0,     rbx = 1           if invalid (bad character or no digits)
;   rax = 0,     rbx = 2           if valid but out of range

