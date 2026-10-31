# Level 17 — Bug: Stale TLB ◆◆◆

*The page table says one thing. The CPU does another. Both are correct, about different
moments.*

## Symptoms

The kernel keeps records, a page each, in frames of its own. To look at one, it maps a
single **window** page (WINDOW) to the record's frame and reads it there: one virtual
page, pointed at different physical frames in turn. Kernels do this all the time
("kmap", temporary mappings).

`show=3` prints record 3. `show=5,5` is fine. But `show=0,1`:

```
record 0: the boot log
record 0: the boot log
done
```

The page table entry for WINDOW does point at record 1's frame. Look in memory.

## Background: the TLB

Walking four tables for every memory access would make everything four times slower or
worse. So the CPU caches finished translations, virtual page to physical frame, in the
**TLB** (translation lookaside buffer). It looks there first.

The TLB is not kept in sync with the page tables. Writing a page table entry changes
memory, and the CPU may keep using what it cached before. So whoever *changes* a present
mapping has to drop the old translation:

| | drops |
|---|---|
| `invlpg [address]` | the translation of that one **virtual** address |
| `mov cr3, …` (any write) | every translation (except pages marked global) |

Mapping a page that wasn't present needs nothing, because a missing page is never cached.
Changing or removing one does.

![The page table says frame B; the TLB still says frame A](tlb.svg)

## Gate

Find an order of records that shows the wrong text (`;! witness show = "..."`, record numbers separated by commas), and fix
the kernel: every order right. At most 3 changed lines.
