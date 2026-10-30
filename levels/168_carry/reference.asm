mov r8, rdi
add r8, rdx         ; low limbs; CF = carry
mov r9, rsi         ; mov leaves CF alone
adc r9, rcx         ; high limbs + carry
mov r10, rdi
sub r10, rdx        ; low limbs; CF = borrow
mov r11, rsi
sbb r11, rcx        ; high limbs - borrow; CF = borrow out of 128 bits
