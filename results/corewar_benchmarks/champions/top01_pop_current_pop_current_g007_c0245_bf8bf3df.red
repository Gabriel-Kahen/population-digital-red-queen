;redcode-94
;assert 1
;name Hybrid Bomb Spreader 7.0
;author Generated
start   spl 0
        mov.i clear_val, <ptr_clear
        add #14, ptr
        mov bomb, @ptr
        add #21, ptr2
        mov bomb2, @ptr2
        add #28, ptr3
        mov bomb3, @ptr3
        add #35, ptr4
        mov bomb4, @ptr4
        add #42, ptr_clear
        jmp start
bomb    dat #0, #1
ptr     dat #0, #0
bomb2   dat #0, #2
ptr2    dat #0, #0
bomb3   dat #0, #3
ptr3    dat #0, #0
bomb4   dat #0, #4
ptr4    dat #0, #0
clear_val dat #0, #0
ptr_clear dat #0, #0
        end start
