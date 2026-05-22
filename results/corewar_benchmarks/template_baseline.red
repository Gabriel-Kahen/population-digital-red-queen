;redcode-94
;assert 1
;name Template Bomber 14
;author deterministic no-LLM baseline
;strategy simple add/mov bomber template
        org start
start   add #7, ptr
        mov bomb, @ptr
        jmp start
bomb    dat #0, #0
ptr     dat #0, #1958
        end start
