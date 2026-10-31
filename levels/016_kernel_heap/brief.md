# Level 16 — Kernel Heap

*A kernel allocates a few dozen bytes thousands of times a second. Handing out a
4 KiB frame each time would waste most of memory.*

## The task

Write **kmalloc** and **kfree** on top of the frame allocator:

- `kmalloc(rdi = size)` returns, in rax, 16-aligned memory for 1 to 2048 bytes, or 0
  (size 0, over 2048, out of memory);
- `kfree(rdi = pointer)` takes it back.

Both follow the C calling convention, like everything a C kernel would call: keep rbx,
rbp and r12-r15. The game's test allocates and frees thousands of objects in random
order, writes into all of them, and checks:

- no overlaps, contents kept;
- the heap holds at most about twice the frames the live objects need, plus one per
  size class (`frames_used`, counted by alloc_frame and free_frame);
- once everything is freed, at most one frame left per size class.

## Lesson: slabs

Round each request up to a **size class** (16, 32, 64, … 2048 bytes) and serve each class
from **slabs**: frames cut into objects of that size.

| offset | slab header (32 bytes) |
|---|---|
| 0 | the next slab of the same class |
| 8 | the first free object |
| 16 | objects in use |
| 24 | the class |
| 32 | the first object, then the next one at 32 + size, … |

Objects of one size in one frame can't fragment the frame. Rounding up wastes some
space, at most half of each object.

## Lesson: free lists that cost nothing

Where does the slab remember which objects are free? *In the free objects.* A free
object's first 8 bytes hold the address of the next free one. The header points at the
first. kmalloc pops the head, and kfree pushes the object back. No extra memory, constant
time.

And kfree needs no size: the slab is simply the frame the pointer lies in
(`and rax, ~0xFFF`), and its header knows the rest. When a slab's in-use count reaches 0,
the frame can go back to the frame allocator (keep one per class, or a free/allocate
cycle at the boundary will thrash).

## Gate

The heap is sound for every random workload the game runs.
