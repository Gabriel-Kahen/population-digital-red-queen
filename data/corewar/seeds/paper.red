;redcode-94
;assert 1
;name PDRQ Seed Paper
;author PDRQ setup
;strategy tiny replicator
        org start
start   spl copy
        spl 1
copy    mov <src, <dst
        djn copy, #6
        jmp @dst
src     dat #0, #last
dst     dat #0, #300
last    dat #0, #0
        end start
