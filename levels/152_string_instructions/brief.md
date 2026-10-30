# Level 152 — String Instructions

*x86 has instructions that walk through memory by themselves. They're older than
most programmers, and still how `memcpy` begins.*

## Lesson: string instructions

Each works on fixed registers and then advances the pointers by one element:

| Instruction | Does |
|---|---|
| `movsb` | byte [rdi] = byte [rsi]; rsi++, rdi++ |
| `stosb` | byte [rdi] = al; rdi++ |
| `lodsb` | al = byte [rsi]; rsi++ |
| `scasb` | compare al with byte [rdi] (sets flags); rdi++ |
| `cmpsb` | compare byte [rsi] with byte [rdi]; rsi++, rdi++ |

`w`/`d`/`q` versions (`movsq` …) move 2/4/8 bytes at a time.

**Repeat prefixes** turn them into loops counted by `rcx`:

```
rep movsb       ; repeat rcx times              (memcpy)
rep stosb       ; repeat rcx times              (memset)
repne scasb     ; repeat while not equal and rcx > 0   (find a byte)
repe cmpsb      ; repeat while equal and rcx > 0       (compare)
```

## Lesson: the direction flag

**DF** decides whether the pointers go up (DF=0) or down (DF=1). `cld` clears it and
`std` sets it. The Linux calling convention promises DF=0 at function boundaries, but
inside a program anyone can leave it set. **Defensive code says `cld` before string
instructions.** One test here starts with DF=1.

## Gate

The game provides `src`, `dst` (64 bytes each), `fill` (32 bytes), and NUL-terminated
strings `str1`, `str2` (64 bytes each). On entry `rdx` = n (0–64), and the low byte of
`r8` is a byte value.

1. Copy the first n bytes of `src` to `dst`. The rest of `dst` must stay unchanged.
2. Set all 32 bytes of `fill` to the low byte of `r8`.
3. `rax` = strlen(str1).
4. `rbx` = memcmp(str1, str2, n): −1, 0 or 1, comparing bytes as **unsigned**; 0 if n = 0.

`rdx` and `r8` must be unchanged. Constraints: at most 40 instructions; must use
`rep movsb`, `rep stosb`, `repne scasb` and `repe cmpsb`.
