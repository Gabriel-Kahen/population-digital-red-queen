;redcode-94
;assert 1
;name PDRQ Heldout Stone
;author PDRQ setup
;strategy fixed-step stone
        org start
start   mov bomb, 20
        add #20, start
        jmp start
bomb    dat #0, #0
        end start
