;redcode-94
;assert 1
;name PDRQ Modified Paper Splitter
;author PDRQ setup + mutation
;strategy a replicator that splits, with an attack at the end of the copy
        org start
start   spl copy
        spl 1
copy    mov <src, <dst
        djn copy, #6
        mov #1, @-1 ; Attack after replication
        jmp @dst
src     dat #0, #last
dst     dat #0, #150
last    dat #0, #0
        end start
