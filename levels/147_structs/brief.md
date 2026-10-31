# Level 147 — Structs

*Bytes become data structures once you give their offsets names.*

## Lesson: struc

A **record** (a "struct" in C) is a block of memory with **fields** at fixed offsets
from its start. Writing `[rsi + 8]` everywhere for "the age" is error-prone, so
NASM's `struc` lets you name the offsets instead:

```
struc Person
    .next:  resq 1      ; offset 0: pointer to the next Person (0 = end of list)
    .age:   resd 1      ; offset 8
    .flags: resb 1      ; offset 12
            resb 3      ; padding, so .name starts at 16
    .name:  resb 16     ; offset 16
endstruc                ; defines Person_size = 32
```

![The 32-byte Person record: next at 0, age at 8, flags at 12, padding, name at 16; below, records linked by their next pointers](person-layout.svg)

`struc` reserves no memory. It only defines constants: `Person.age` is 8 and
`Person_size` is 32. Use them as offsets: `mov eax, [rsi + Person.age]`.

A NASM trap: the fields are `.local` labels of `Person`, and so is any `.label` you
write after `endstruc` until the next ordinary label. A loop label `.next:` below the
struc becomes `Person.next` and clashes with the field. Put the `struc` before your
first ordinary label, or give loop labels names like `.advance`. The error says
"label `Person.next` inconsistently redefined".

**Padding** is unused space that keeps each field aligned to its size (a qword at a
multiple of 8, a dword at a multiple of 4). Misaligned data works on x86 but is
slower, and C compilers add the same padding, so matching their layout matters once
you call C code (Arc IV).

## Lesson: istruc

To define an initialized record in `.data`:

```
bob: istruc Person
    at Person.age,   dd 42
    at Person.flags, db 1
    at Person.name,  db "bob", 0
iend                 ; fields you don't mention are zero
```

## Lesson: linked lists

In a **linked list**, each record's `next` field holds the address of the following
record, and 0 (the **null pointer**) marks the end. The records can sit anywhere in
memory, in any order. Walking the list is a loop: `mov rsi, [rsi + Person.next]`
until rsi is 0.

## Gate

The game provides `people` (8 slots of 32 bytes, holding a list in random slot order)
and `head` (a pointer to the first record, or 0 if the list is empty).

1. Define `struc Person` exactly as above (the tests check the offsets).
2. Define `newbie` in `.data` with `istruc`: age 99, flags 1, name `zed`.
3. Insert `newbie` at the **front** of the list (`head` must point to it).
4. Walk the whole list (now including newbie):

| Register | Must hold |
|---|---|
| `rax` | number of records |
| `rbx` | sum of the ages (ages are unsigned dwords) |
| `rcx` | address of the oldest record (the first one, if there's a tie) |
| `rdx` | number of records whose flags have bit 0 set |
| `r8` | address of `newbie` |

Constraint: at most 40 instructions.
