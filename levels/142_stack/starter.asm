; Level 142 — The Stack
;
; text: NUL-terminated (up to 62 chars), out: 64 bytes
; 1. out <- text reversed, then a NUL byte  (use push/pop)
; 2. rax <- 1 if ()[]{} in text are balanced and nested, else 0
; rsp must end where it started. Registers start with garbage.

