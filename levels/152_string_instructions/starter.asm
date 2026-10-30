; Level 152 — String Instructions
;
; rdx = n (0..64), r8b = a byte value (rdx, r8 unchanged)
; 1. copy n bytes src -> dst          (rep movsb)
; 2. fill all 32 bytes of fill with r8b (rep stosb)
; 3. rax = strlen(str1)               (repne scasb)
; 4. rbx = memcmp(str1, str2, n) as -1/0/1, unsigned bytes   (repe cmpsb)

