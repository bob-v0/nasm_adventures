# Level 122 — Bug: Use After Free ◆◆

*The output is right, the tests pass, and the program reads memory it gave back
moments ago. One day the allocator reuses that memory, and the program reads
something else's data.*

## Symptoms

`dedupe` removes repeated words from a list and prints the rest. Its output is correct.
But this level links it with the game's **checked allocator**, which stops it at the first
access to a freed block.

## Background

`free(p)` returns the block to the allocator, and from that moment the memory belongs to
the allocator again. Reading or writing it afterwards is a **use after free**:

- usually the bytes are still there, so it "works"
- after the next `malloc` reuses the block, the old pointer reads or overwrites someone
  else's data, which can be far away in time and code from the bug
- **double free** (freeing the same block twice) corrupts the allocator's own lists, as
  your free list from level 125 would show

These are among the most exploited bugs in C and C++ software. Tools such as
AddressSanitizer and Valgrind find them the way the game's allocator does:

- **quarantine:** freed memory isn't reused for a while
- **poisoning:** freed blocks are filled with a recognisable pattern (here `0xDD`)
- **watching:** every access to a freed block is reported, with where it was freed

## Gate

Fix both use-after-free bugs, changing at most **6 lines**. The checked allocator must
not find anything.
