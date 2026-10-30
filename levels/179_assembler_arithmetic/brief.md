# Level 179 — The Assembler Counts

*The gate asks for numbers no one should have to count by hand.*

## Lesson: two different times

Your program "runs" twice:

1. **Assemble time.** NASM reads your text and produces bytes. Constants, label
   addresses and expressions such as `7*24*60*60` are computed here, for free.
2. **Run time.** The CPU executes the bytes. Every instruction costs time.

Anything known before the program runs can be computed by NASM. Writing
`mov rcx, 7*24*60*60` produces exactly the same bytes as `mov rcx, 604800`, and
it explains itself.

## Lesson: the tools

```
SIZE    equ 16                 ; a named constant; takes no memory
%define GREETING "hi"          ; text substitution (preprocessor)

msg:    db "hello", 10
MSG_LEN equ $ - msg            ; $ = address of the current line,
                               ;   so this is the length of msg (6)

pad:    times 13 db 0xCC       ; repeat a line N times
```

`$$` is the start of the current section. `$ - $$` is how far into the section you
are.

The **preprocessor** runs before the assembler and can generate code:

```
%assign i 0
%rep 4
    dd i * 10                  ; emits dd 0, dd 10, dd 20, dd 30
    %assign i i + 1
%endrep
```

Expressions support `+ - * / % << >> | & ^ ~` and parentheses. `/` is unsigned
integer division; `//` is signed.

## Gate

In `.data`, define these three blocks **in this order, back to back**:

1. `squares`: sixteen qwords holding 0², 1², 2², … 15². Generate them with `%rep`;
   don't type them.
2. `poem`: exactly these bytes, with no terminator:
   `Level 179: the assembler counts, so you never have to count again`
3. `ruler`: forty `-` characters followed by one newline byte (10).

Then, in code:

| Register | Must hold |
|---|---|
| `rax` | the number of entries in `squares`, computed from its size in bytes |
| `rbx` | the length of `poem`, computed with `$` |
| `rcx` | the number of seconds in a week, written as an expression |
| `rdx` | the total number of bytes from the start of `squares` to the end of `ruler` |

Constraints: at most 6 instructions. Run-time arithmetic (`add`, `sub`, `mul`, `inc`,
`lea`, …) is banned. Let the assembler do the work.

## Try this

{{listing}} shows the bytes your `%rep` block produced. Look for `mov ebx, 0x41`:
NASM computed the poem length and put the result straight into the instruction.
