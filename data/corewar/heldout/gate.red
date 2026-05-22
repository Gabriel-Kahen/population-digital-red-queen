;redcode-94
;assert 1
;name PDRQ Heldout Gate
;author PDRQ setup
;strategy small core gate
        org start
start   spl 0
        mov gate, <gate
        jmp start
gate    dat #0, #-5
        end start
