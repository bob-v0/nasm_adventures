# Level 171 — Echo Chamber ★

*The last gate of the outer arc. It speaks to you, and you must answer backwards.*

## Lesson: `read`

`read` is the mirror of `write`: syscall 0 copies bytes *from* a file descriptor
*into* memory you provide.

```
mov eax, 0          ; syscall 0 = read
mov edi, 0          ; fd 0 = stdin
mov rsi, buf        ; where to put the bytes
mov edx, 8          ; at most this many
syscall             ; rax = bytes actually read (0 = end of input, <0 = error)
```

`read` may return **fewer** bytes than you asked for, because input from pipes,
terminals and networks arrives in pieces. Handling that properly needs loops
(Arc III). Here the tests always provide at least 8 bytes at once.

A **buffer** is memory set aside to receive data. Buffers you read into belong in
`.bss`, since their starting contents don't matter:

```
section .bss
buf: resb 8
```

Remember that `syscall` destroys `rcx` and `r11`, and puts its result in `rax`. To
keep a value across syscalls, use a register the kernel preserves, such as `r12`.

## Gate ★

This boss uses everything from Arc I.

1. Read 8 bytes from stdin.
2. Write `echo: ` to stdout.
3. Write those 8 bytes **in reverse order**.
4. Write a newline.
5. Exit with status = the number of bytes `read` returned.

Input beyond the first 8 bytes is ignored. Make exactly these syscalls, in order:
read, write, write, write, exit.

Constraints: at most 40 instructions; must use `bswap`.

Test it for real in {{terminal}}: `printf 'ABCDEFGH' | ./solution; echo " status=$?"`
should print `echo: HGFEDCBA` and ` status=8`.
