# Level 171 — Echo Chamber ★

*The last gate of the outer arc. It speaks to you, and you must answer backwards.*

## Lesson: `read`

```
mov eax, 0          ; syscall 0 = read
mov edi, 0          ; fd 0 = stdin
mov rsi, buf        ; where to put the bytes
mov edx, 8          ; at most this many
syscall             ; rax = bytes actually read (0 = end of input, <0 = error)
```

`read` may return **fewer** bytes than you asked for: input arrives in pieces from
pipes, terminals and networks. Handling that properly needs loops (Arc III). Here the
tests always provide at least 8 bytes at once.

Buffers you read into belong in `.bss`:

```
section .bss
buf: resb 8
```

Remember that `syscall` destroys `rcx` and `r11`, and `rax` gets the result. To keep a
value across syscalls, use a register the kernel preserves, such as `r12`.

## Gate ★

This boss uses everything from Arc I.

1. Read 8 bytes from stdin.
2. Write `echo: ` to stdout.
3. Write those 8 bytes **in reverse order**.
4. Write a newline.
5. Exit with status = the number of bytes `read` returned.

Input beyond the first 8 bytes is ignored. Exactly these syscalls, in order: read,
write, write, write, exit.

Constraints: at most 40 instructions; must use `bswap`.

Test it for real: `printf 'ABCDEFGH' | ./solution; echo " status=$?"`
