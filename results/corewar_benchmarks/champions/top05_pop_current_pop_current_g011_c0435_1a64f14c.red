;redcode-94
;assert 1
;name Rapid Spreader (Mutated)
;author AI
;strategy Focuses on rapid spreading and bombing, with a slightly smaller replication size for faster deployment.
        org start
start   spl copy        ; Start replication
        mov bomb, @ptr  ; Bomb an address pointed to by ptr
        add #5, ptr     ; Increment ptr to bomb a new location (slightly slower bombing frequency)
        add #40, dst    ; Dynamically adjust replication destination for wider spread
        spl 0, #5       ; Split, new process starts 5 instructions after this one for very fast spread
        jmp start       ; Loop back to bomb again
copy    mov <src, <dst  ; Replicate instructions
        djn copy, #12   ; Loop 12 times for replication (smaller replication size)
        jmp @dst        ; Jump to the replicated code
src     dat #0, #last   ; Source for replication
dst     dat #0, #200    ; Destination for replication
bomb    dat #0, #0      ; Bomb instruction
ptr     dat #0, #1      ; Pointer for bombing
last    dat #0, #0      ; End of replication source
        end start
