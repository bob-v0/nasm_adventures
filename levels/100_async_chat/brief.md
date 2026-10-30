# Level 100 — Async Chat Server ★

*The last gate of Arc VI. One thread, any number of clients, some of them slow, some of
them cancelled mid-sentence, and a grader that tries the task orders you didn't think
of.*

## The protocol

On 127.0.0.1:**7000**, line by line (each line ends with a newline):

- A client's **first line is its name** (up to 31 bytes; cut longer ones).
- Every later line (up to 400 bytes) goes to **every other** client as `name: line`.
- When a client joins or leaves, everyone else gets `* name joined` or `* name left`.
- A client that disconnects before sending its name was never in the room: nobody hears
  about it.

## What makes it hard

- **Slow clients.** A client that doesn't read fills its socket buffer; after that your
  writes return `-EAGAIN`. Never block the room on it: queue, and wait for writability in
  that client's own writer. If more than **16 384 bytes** are queued for one client,
  **kick** it: remove it, close its connection, tell the others `* name left`.
- **Cancellation.** The game cancels `reader` tasks at every await point, one run each.
  A cancelled reader must behave like a client that left, and everything still has to be
  freed and closed. Keep the name `reader`: that's how the game finds those tasks.
- **Schedules.** Tests run under many task orders. Only the order of events in time
  (≥ 5 ms apart) is guaranteed.
- **Lifetimes.** A session is used by its reader, its writer and the room. It may only be
  freed when none of them can touch it again (levels 101, 103).

## The pieces you have

The game's task runtime (`rt_*`, level 106), and your levels 102–101 code. The starter
gives you `_start`, the acceptor (it spawns `reader(fd)` per client) and mailboxes whose
`mb_recv` returns 0 when the waiting task was cancelled. One design that works:

| actor | does |
|---|---|
| `reader` (per client) | owns the session's line buffer; turns bytes into lines; posts JOIN, SAY, LEAVE |
| `writer` (per client) | owns writing to the socket; mailbox → socket, waiting for writability |
| `room` (one) | owns the member list; formats, delivers, counts queued bytes, kicks |

Make "who frees the session" a rule rather than a race, for example a reference count of
two (reader and writer): the last one to finish closes the socket and frees it. The room
only touches members, and a writer only stops after the room has removed its session.

## Gate

Pass everything: exact transcripts for every client under shuffled schedules; a client
that never reads while another sends 80 KB (everyone else gets every line); readers
cancelled at every await; clients that leave without a name. After each test, every heap
block is freed and every client socket closed. Constraint: at most 450 instructions.

Arc VI cleared. Next: the machine underneath, and what makes code fast.
