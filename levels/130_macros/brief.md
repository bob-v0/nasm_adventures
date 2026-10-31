# Level 130 — Macros

*Assembly gets repetitive. NASM's preprocessor is a small programming language for
generating it.*

## Lesson: %macro

A **macro** is a named piece of source text with parameters. NASM's *preprocessor*
replaces each use of it with its body before assembling:

```
%macro sys_write 3          ; name, number of parameters
    mov rdx, %3             ; %1, %2, %3 are the arguments, pasted as text
    mov rsi, %2
    mov edi, %1
    mov eax, 1
    syscall
%endmacro

    sys_write 1, buffer, 42     ; expands into the five lines above
```

A macro isn't a function: there's no `call`, no stack, no return. Its body is **pasted**
at every use, with the arguments substituted as text. That makes macros free at run
time, but each use adds code, and arguments are evaluated where they're pasted.

For example, `sys_write 1, rdx, rsi` breaks with the macro above. It expands to
`mov rdx, rsi` first, which destroys the buffer address before `mov rsi, rdx` reads it.

## Lesson: labels and sections inside macros

A label in a macro body would be defined twice if you used the macro twice. `%%name`
creates a fresh label for each expansion. A macro can also switch sections, so it can
place its own data:

```
%macro print 1
section .rodata
%%str: db %1
%%len equ $ - %%str
section .text
    sys_write 1, %%str, %%len
%endmacro

    print "hello", 10           ; one argument: the whole list after the name?
```

Careful: arguments are separated by commas, so `print "hello", 10` passes **two**, and
a macro declared with 1 parameter rejects it. Use `%macro print 1+`: the `+` makes the
last parameter swallow the rest of the line, commas and all. `%0` is the number of
arguments given.

Put macros in a `.inc` file and `%include` it, and you have a macro library.

## Gate

Define three macros: `sys_write fd, buf, len`, `print "text"` (data placed by the macro
itself, with `%%` labels) and `exit code`. Then write a program **using them** that:

1. reads up to 256 bytes from stdin,
2. prints `you said: `, then the bytes read, then a newline,
3. prints `bye` and a newline,
4. exits with status 0.

The tests check the macro definitions in your source as well as the output.
Constraint: at most 60 instructions (after expansion).
