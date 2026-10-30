# Level 102 — Actors

*Locks protect shared data. Actors avoid having shared data at all: each piece of
state has exactly one owner, and everyone else asks it by message.*

## Lesson: actors

An **actor** is a task with **private state** and a **mailbox**. Other actors never
touch its state; they send it **messages**. The actor handles one message at a time, so
inside it there are no races and no locks. Erlang/Elixir, Akka, Orleans and Swift's
`actor` are built on this; so, in spirit, is every "one goroutine owns this map" design.

Here a chat room:

- one **reader** actor per client (given): it reads the client's socket and posts
  `K_JOIN` once, `K_SAY` with the text for everything the client sends, and `K_LEAVE`
  when the client goes;
- one **room** actor (yours): the only one that knows who's in the room and the only one
  that writes to sockets.

## Lesson: ownership moves with the message

Messages are heap blocks (`rt_malloc`). `mb_send` doesn't copy: it **hands the block
over**. From then on the receiver owns it, and the sender must not touch it again. The
receiver frees it when it's done. The game's checked allocator notices leaks,
use-after-free and double frees.

Resources move the same way. After `K_JOIN`, the client's socket **belongs to the
room**: the reader never closes it, the room closes it after `K_LEAVE`. One owner per
resource, so nobody writes to a closed fd, or to an fd number that was already reused
for somebody else. (Level 101 is about getting that wrong.)

## Lesson: a mailbox

A mailbox is an unbounded queue of messages (a linked list through `M_NEXT`) with one
receiver. `mb_send` appends, and wakes the receiver if it's parked. `mb_recv` takes the
oldest message, or leaves its waker and parks if there is none. That's level 106 with
one consumer and no capacity: check, register and park with **no await in between**.

## Gate

A chat room on 127.0.0.1:**7000**: everything a client sends goes to every **other**
client currently in the room, in order. Write `mb_send`, `mb_recv` and the `room` actor.
The acceptor and the reader actors are given. The tests have people joining, talking
and leaving at different times; when it's over, every message must have been freed and
every departed client's socket closed. Constraint: at most 200 instructions.
