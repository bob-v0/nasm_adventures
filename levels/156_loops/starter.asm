; Level 156 — Loops
;
; arr: up to 64 unsigned qwords. rsi = n (0..64), rdx = threshold t (unchanged)
;   rax = sum of arr[0..n)
;   rbx = largest element (unsigned), 0 if n = 0
;   rcx = number of elements > t (unsigned)

