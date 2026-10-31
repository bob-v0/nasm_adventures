# Level 32 — I/O APIC

*The keyboard doesn't know which core will hear it. The I/O APIC decides, using a table
you write.*

## Lesson: routing interrupts

Devices raise interrupt lines. On modern PCs those lines go to an **I/O APIC**, which
turns each one into a message to a Local APIC (level 33): "vector V, for the core with
APIC ID D". It has 24 inputs and one **redirection entry** per input, 64 bits each:

```
bits 0-7    vector
bits 8-10   delivery mode (000: fixed)
bit 11      destination mode (0: physical APIC ID)
bit 13      polarity (0: active high)
bit 15      trigger (0: edge)
bit 16      mask (1: ignore this input)
bits 56-63  destination APIC ID
```

The old ISA IRQs (keyboard 1, COM1 4, ...) arrive on the inputs with the same numbers,
mostly: the firmware's ACPI tables (Arc XIV) list the exceptions, such as the timer's
IRQ 0 arriving on input 2.

## Lesson: indirect registers

The I/O APIC is at physical **0xFEC00000** and has only two registers: **IOREGSEL**
(offset 0x00) selects one of its internal registers, **IOWIN** (offset 0x10) reads or writes
it. Redirection entry n is internal registers 0x10 + 2n (bits 0-31) and 0x11 + 2n
(bits 32-63).

```
mov dword [0xFEC00000], 0x12        ; entry 1, low half
mov dword [0xFEC00010], 0x41        ; vector 0x41, unmasked
```

## Lesson: handlers collect, the main loop works

An interrupt handler interrupts whatever is running, so it should be short: read the
device, store the byte in a **ring buffer**, EOI, return. The main loop takes the bytes
out when it gets to them:

```
handler:    buffer[head % 16] = scancode;  head = head + 1
main loop:  if tail != head:  scancode = buffer[tail % 16];  tail = tail + 1
```

Each index has exactly one writer, so no lock is needed (as long as each update is one
store: level 31 is about that). When the buffer is empty, the main loop sleeps with `hlt`
until the next interrupt (level 30 is about doing that safely).

## Gate

Route the keyboard (ISA IRQ 1) to vector 0x41 through the I/O APIC, collect scancodes in
a ring buffer, and echo the typed text on COM1 until Esc.
