# Level 180 — Names for Places

*Registers are not enough storage. The gate wants you to write to memory.*

## Lesson: sections

Sixteen registers fill up fast. Everything else lives in **memory**: a long row of
bytes, each with a numbered **address**.

A program's memory is divided into **sections**, and the operating system gives each
one different permissions:

| Section | Holds | Permissions |
|---|---|---|
| `.text` | code | read, execute |
| `.data` | initialized variables | read, write |
| `.rodata` | constants | read only |
| `.bss` | variables that start at zero | read, write; takes no space in the file |

`section .data` switches to that section, and everything after it goes there until
the next `section` line. You can switch back and forth as often as you like.

## Lesson: defining data

The `d` directives put bytes into the program: `db` (define byte, 1 byte each),
`dw` (word, 2), `dd` (doubleword, 4) and `dq` (quadword, 8). The `res` directives
reserve space without choosing its contents:

```
section .data
greeting: db "Hi!", 10, 0      ; bytes: 48 69 21 0A 00
year:     dw 2026              ; 2 bytes
count:    dd 7                 ; 4 bytes
big:      dq 0x1122334455667788; 8 bytes

section .bss
buffer:   resb 64              ; reserve 64 bytes
total:    resq 1               ; reserve one 8-byte slot
```

## Lesson: a label is an address

`greeting` is not a variable. It is the **address** where its bytes start. Square
brackets mean "the memory at this address":

![The label greeting is the address 0x402000. With brackets and an offset of 1 you read the byte stored at the next address: 'i'](label-address.svg)

```
mov rax, greeting          ; rax = the ADDRESS of greeting (e.g. 0x402000)
mov rax, [big]             ; rax = the 8 bytes stored at big
mov [total], rax           ; store rax's 8 bytes at total
mov al, [greeting + 1]     ; al = 'i'; you can add offsets to an address
```

Think of a label as a house number and `[label]` as what is inside the house.

Two rules:

1. **No memory-to-memory moves.** `mov [a], [b]` doesn't exist. Load into a
   register, then store.
2. **Say the size when it is ambiguous.** In `mov [count], 5` NASM can't tell whether
   you mean 1, 2, 4 or 8 bytes, so write `mov dword [count], 5`. The size words are
   `byte`, `word`, `dword` and `qword`. When a register is involved, the register's
   size decides.

## Gate

The game provides `input: dq <value>` in `.data`, filled in by each test.

1. In `.data`, define `greeting` as the bytes `Hello, Ring!` followed by a 0 byte.
2. In `.data`, define a 16-bit `counter` (any starting value).
3. In `.bss`, reserve an 8-byte `slot`.

Then, in code:

- copy the 8-byte value at `input` into `slot`
- put the **address** of `greeting` in `rax`
- put the byte at `greeting + 7`, zero-extended, into `rbx`. A hidden test changes
  that byte, so read it from memory.
- store `0xBEEF` into `counter`

Constraint: at most 8 instructions.

## Try this

In {{debug}}, show the memory at `greeting` to see your string as bytes, and at
`slot` to watch it fill in as you step.
