;redcode-94
;assert 1
;name PDRQ Hybrid Bomb-Vampire (Adaptive Spread, Dual Offset) - Optimized
;author PDRQ setup (Recombination) - Optimized
start   spl 0
        mov bomb, <bomb_target
        mov fang, @fang_target
        add #28, bomb_target ; Slightly increased bomb spread
        add #22, fang_target ; Slightly increased vampire spread
        jmp start
bomb    dat #0, #0
fang    jmp trap, #100
trap    spl -1
        jmp trap
bomb_target dat #0, #110 ; Adjusted initial offset
fang_target dat #0, #90  ; Adjusted initial offset
end start
