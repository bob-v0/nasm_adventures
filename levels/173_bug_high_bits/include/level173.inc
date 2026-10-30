; Provided by level 173: one user record. Each test fills in different values.
section .data
rec_id:   dq 0x5EC0_0000_0000_002A   ; record id; the low byte is the exit status
name_len: db 5                       ; how many bytes of `name` are used
name:     db "alice", 0
          times 32 - ($ - name) db 0
badge_w:  dw 12                      ; width of the badge, in '#' characters
