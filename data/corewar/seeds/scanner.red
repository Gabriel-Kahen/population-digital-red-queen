;redcode-94
;assert 1
;name PDRQ Seed Scanner
;author PDRQ setup
;strategy tiny linear scanner
        org scan
scan    seq target, target+4
        jmp attack
        add #4, target
        jmp scan
attack  mov bomb, @target
        jmp scan
bomb    dat #0, #0
target  dat #0, #100
        end scan
