; Level 147 — Structs
;
; people: 8 slots of 32 bytes; head: pointer to the first record (0 = empty)
; 1. struc Person: .next (qword, 0) .age (dword, 8) .flags (byte, 12) .name (16 bytes, 16)
; 2. newbie (istruc): age 99, flags 1, name "zed"
; 3. put newbie at the front of the list
; 4. rax = count, rbx = sum of ages, rcx = oldest (first on ties),
;    rdx = count with flags bit 0, r8 = address of newbie

