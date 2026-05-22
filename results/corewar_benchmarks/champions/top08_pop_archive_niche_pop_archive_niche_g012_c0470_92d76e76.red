;redcode-94
;assert 1
;name Hybrid Dwarf Spread Faster (Aggressive Bomb Recomb)
;author PDRQ setup (modified)
start   spl 0
        add #1, fang
        mov bomb, @fang
        jmp -2
fang    jmp bomb, #10
bomb    mov 0, <0 ; Changed to MOV bomb for more aggressive killing
        end start
