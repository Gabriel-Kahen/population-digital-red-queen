;redcode-94
;assert 1
;name PDRQ Heldout Quick Clear
;author PDRQ setup
;strategy bounded clear loop
        org start
start   mov bomb, >ptr
        djn start, #20
        jmp start
bomb    dat #0, #0
ptr     dat #0, #0
        end start
