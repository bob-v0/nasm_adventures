# Level 101 — Bug: Actor Lifetimes ◆◆◆

*An actor can stop. The messages already on their way to it don't know that.*

## Symptoms

Level 102's chat room was redesigned so that one slow client can't hold up the room.
Each client now has a **session**, a heap block with a mailbox and the socket, served
by two actors: a **reader** (socket → room) and a **writer** (mailbox → socket). The
room no longer writes to sockets; it sends each member a copy of every message
(`K_DELIVER`).

When a client disconnects, its reader tells the room (`K_LEAVE`) and tells its writer to
stop (`K_STOP`), and the writer frees the session. Most of the time it works. Under
some schedules, when someone leaves at the moment someone else speaks, the service
dies of a **use after free**, or leaks a message.

## Background: lifetime across actors

Inside one actor everything is sequential. **Between** actors, nothing is: messages
are in flight, mailboxes hold things not yet read, and another actor may still hold a
**reference** to you, here the room's `members[]` entry. Freeing an actor's memory is
only safe when nobody can send to it any more and nothing addressed to it is left
unhandled. The reader doesn't know that. Only the room knows when it has sent the last
`K_DELIVER` to a session: when it processes `K_LEAVE` and removes the member.

Two classic fixes:

- **Transfer ownership of the ending.** Let the actor that holds the last reference end
  the other one. Mailboxes are FIFO, so if the room sends `K_STOP` *after* removing the
  member, `K_STOP` is the last message the writer ever receives. Nothing can arrive after
  it, and freeing is safe.
- **Generation-checked handles.** Never hold raw pointers to other actors: hold
  `(slot, generation)`. Ending an actor bumps its slot's generation, and a send through
  an old handle sees the mismatch and is dropped. Erlang's pids, ECS entity ids and
  most actor runtimes work like this.

The first fits here in a few lines.

## Also: SIGPIPE

A writer can still send to a client that hung up a moment ago. By default that kills
the process with SIGPIPE, so servers ignore it: the given `_start` sets SIGPIPE to
`SIG_IGN`, and `write` returns `-EPIPE` instead.

## How the game tests it

Clients join, talk and leave. In one scenario someone leaves at the very moment someone
else speaks. Each test runs under the plain order and 25 shuffled schedules, with the
game's checked allocator watching every block: any use after free, double free or leak
fails, and the report names the schedule.

## Gate

1. Add a witness: a schedule under which the **original** breaks:
   `;! witness schedule = N`.
2. Fix the lifetimes, changing at most **10 lines**.
