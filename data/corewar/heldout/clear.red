;redcode-94
;assert 1
;name PDRQ Heldout Clear
;author PDRQ setup
;strategy linear core clear
        org start
start   mov bomb, >ptr
        jmp start
bomb    dat #0, #0
ptr     dat #0, #50
        end start
