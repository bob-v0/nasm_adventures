# Level 136 — Hello, libc

*Your program meets the C library: `printf`, `scanf`, and fifty years of
conventions.*

## Lesson: main and the C runtime

**libc**, the C library, is the collection of functions every C program uses:
`printf`, `scanf`, `malloc` and hundreds more. When you link with gcc, you also get the
**C runtime**: its `_start` sets things up and calls **your `main`**, a normal
function under the ABI. When main returns, the value in `eax` becomes the exit status.

You declare library functions with `extern` and call them like any other function:

```
extern printf
global main

section .text
main:
    sub rsp, 8              ; entry rsp % 16 == 8; make it 0 for our calls
    lea rdi, [fmt]          ; 1st argument: the format string
    mov esi, 42             ; 2nd: the number
    xor eax, eax            ; al = 0: no vector registers used (variadic call!)
    call printf
    xor eax, eax            ; return 0
    add rsp, 8
    ret

section .rodata
fmt: db "answer: %d", 10, 0     ; C strings end with a 0 byte
```

The game builds it with `nasm -f elf64` and links with `gcc -no-pie`. This level runs
your program **natively**, as a real process. Debug it with `gdb ./solution` in
{{terminal}}: the emulator's debugger can't run the C library.

## Lesson: variadic calls and pointers

`printf` is **variadic**: it takes a variable number of arguments. For such functions
the ABI requires **al = the number of vector (xmm) registers** used for arguments,
which is 0 when you pass only integers and pointers. Forgetting it usually works by
luck, until it doesn't.

`scanf("%ld", &n)` needs the **address** of a place to put n: a slot you reserved on
the stack (`lea rsi, [rsp]`) or a variable in `.bss`.

The two rules interact, and you can see it for yourself (measured with glibc 2.39):

| rsp at the call | al | result |
|---|---|---|
| aligned | 0 or 1 | works |
| off by 8 | 0 | happens to work |
| off by 8 | 1 | **segmentation fault inside printf** |

With al > 0, `printf` saves the vector registers using aligned stores (`movaps`), which
fault on a misaligned stack. So code with a misaligned stack can pass every test and
then crash after an innocent change. Follow both rules every time.

## Gate

Read a number n (1–20) from stdin with `scanf("%ld", ...)`, then print with `printf`:

```
 1    1      1          ← for i = 1 .. n: "%2ld %4ld %6ld\n" with i, i², i³
 2    4      8
 ...
sum of cubes: 36        ← "sum of cubes: %ld\n"
```

`main` must return 0. Constraints: at most 50 instructions; must call `printf` and
`scanf`.
