;redcode-94
;assert 1
;name PDRQ Seed Dwarf
;author PDRQ setup
;strategy simple bomber
        org start
start   add #4, ptr
        mov bomb, @ptr
        jmp start
bomb    dat #0, #0
ptr     dat #0, #0
        end start
