;redcode-94
;assert 1
;name PDRQ Seed Vampire
;author PDRQ setup
;strategy simple fang bomber
        org start
start   add #7, fang
        mov fang, @fang
        jmp start
fang    jmp trap, #100
trap    spl 0
        jmp trap
        end start
