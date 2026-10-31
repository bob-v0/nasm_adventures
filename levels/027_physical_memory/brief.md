# Level 27 — Physical Memory

*Everything a kernel builds from now on (page tables, stacks, processes) is made of
4 KiB frames of RAM. Something has to hand them out.*

## The task

Write a **frame allocator**:

- `alloc_frame` returns, in eax, the address of a free 4 KiB frame, or 0 when none is left;
- `free_frame` takes a frame back (eax = its address).

Both leave every other register as they found it. `init_frames` sets things up first,
from the multiboot information. Then the game's test, the first module, runs (the starter
copies it to 0x80000 and calls it). It allocates and frees thousands of frames in a random
order and writes into every one. It checks:

- every frame is 4096-aligned, in available RAM, at or above 1 MiB, and outside the
  kernel and its modules;
- no frame is handed out twice, and nothing else writes into it while it's out;
- when alloc_frame finally says 0, the count is exactly the free frames the memory map
  promises; and the same again after everything is freed.

## Lesson: what's free

The memory map (flags bit 6, `mmap_length` at +44, `mmap_addr` at +48) lists regions, each
**available** (type 1) or not: the BIOS's area, ROMs, the hole for devices below 4 GiB.

![Physical memory on a 16 MiB PC: what the allocator may hand out](memory.svg)

Available isn't the same as free, though. Some of it is already in use:

- **below 1 MiB**: the BIOS's data, the multiboot information, the game's test at
  0x80000. Real kernels keep it for things that need low addresses.
- **the kernel**, from 1 MiB to the linker's `kernel_end` (`extern kernel_end`), including
  its .bss, where the bitmap lives.
- **the modules**, and the loader's data (command lines, the module list) that QEMU puts
  between the kernel and them: everything up to the end of the last module.

Each map entry starts with its own size, which doesn't count itself, so the next entry is
at entry + size + 4. The fields after that are base (8 bytes), length (8 bytes) and
type (4 bytes). Use only whole frames: round a region's start up to a multiple of 4096
and its end down.

## Lesson: a bitmap

One bit per frame: bit n describes frame n, at address n × 4096; 1 means used. For 4 GiB
that's 2²⁰ bits, 128 KiB of .bss. x86 has instructions for exactly this:

| | |
|---|---|
| `bts [bitmap], eax` | set bit eax (and CF = what it was) |
| `btr [bitmap], eax` | clear it |
| `bt [bitmap], eax` | test it |
| `bsf edx, eax` | edx = the lowest set bit of eax |

With a register as the bit number, `bts` reaches any bit, however far from `bitmap`.
To find a free frame, look a dword at a time: a dword that isn't 0xFFFFFFFF has a 0 bit,
and `not` plus `bsf` finds it.

And frame 0 lives at address 0, the value that means "no frame". One more reason
low memory is never handed out.

## A trap: calling a fixed address

From this arc on, kernels are assembled as 64-bit object files, even while their first
instructions are 32-bit. NASM can't encode a `call` or `jmp` to a fixed address such as
`call 0x80000` in one: it would land somewhere else entirely. The game's build points
it out. Go through a register: `mov esi, 0x80000`, `call esi`.

## Gate

The game's test says `the allocator is sound`, for every memory size it tries.
