# Level 133 — Bug: Unchecked Length ◆◆

*Every name fits until the one that doesn't, and the bytes that don't fit have to go
somewhere.*

## Symptoms

`set_name` stores a customer's new name in their account record. Most renames work.
Customers with long names report that their **balance** changed afterwards.

## Background

Memory has no fences between variables. A record is just consecutive bytes:

```
account: [ n a m e . . . . . . . . . . . . ][ b a l a n c e ]
           +0                           +15  +16
```

A copy that runs until the *source* ends, instead of until the *destination* is full,
writes past the field into whatever comes next. Here that's the balance; elsewhere it
might be a pointer, a length or a flag. This is the most common memory-safety bug in
C (`strcpy`, `gets`, `sprintf`), and the reason bounded functions exist (`strlcpy`,
`snprintf`). Every copy into a fixed-size space needs a limit.

## Gate

1. **Witness:** a name that makes the original corrupt the balance, as a line
   `;! witness name = "..."` (up to 63 characters). A *witness* is an input that
   proves the bug exists.
2. **Fix** `set_name` so a name always fits: copy at most 15 characters and always
   end with a NUL inside the field. Longer names are cut short. At most **5 changed
   lines**.

The tests check the name field and that the balance is untouched.
