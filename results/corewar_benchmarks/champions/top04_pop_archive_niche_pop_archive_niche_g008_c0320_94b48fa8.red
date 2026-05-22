;redcode-94
;assert 1
;name PDRQ Splitter Vampire Bomb Enhanced 9.1 (Fang and Bomb Spread Variation)
;author PDRQ setup
start   spl 0
        add #8, fang  ; Varied fang spread
        mov fang, @fang
        add #5, ptr   ; Varied bomb spacing
        mov bomb, @ptr
        spl copy
        jmp start
copy    mov <src, <dst
        djn copy, #7  ; Varied copy length
        jmp @dst
fang    jmp trap, #100
trap    spl 0
        jmp trap
bomb    dat #0, #0
src     dat #0, #0
dst     dat #0, #200
ptr     dat #0, #0
        end start
