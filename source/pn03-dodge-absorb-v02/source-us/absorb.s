
lis 10,32793
lwz 0,2432(10)
lis 11,17479
ori 11,11,16690
cmpw 0,11
beq init_ok
stw 11,2432(10)
li 0,63
stw 0,2436(10)
li 0,100
stw 0,2440(10)
li 0,0
stw 0,2444(10)
li 0,2
stw 0,2448(10)
li 0,0
stw 0,2484(10)
li 0,20
stw 0,2488(10)
li 0,55
stw 0,2492(10)
li 0,57
stw 0,2496(10)
li 0,0
stw 0,2452(10)
stw 0,2456(10)
stw 0,2460(10)
stw 0,2464(10)
stw 0,2468(10)
stw 0,2472(10)
stw 0,2476(10)
stw 0,2480(10)
stw 0,2500(10)
stw 0,2504(10)
stw 0,2508(10)
stw 0,2512(10)
init_ok:
stw 31,2452(10)
lwz 11,2500(10)
addi 11,11,1
stw 11,2500(10)
lwz 0,2436(10)
andi. 0,0,1
beq done0
lbz 3,248(31)
lbz 4,249(31)
li 5,0
cmpwi 3,1
bne state_known
cmpwi 4,2
bne state_known
li 5,1
state_known:
lwz 6,2456(10)
cmpwi 5,0
beq store_prev
cmpwi 6,0
bne keep
li 0,0
stw 0,2460(10)
lwz 7,2472(10)
addi 7,7,1
stw 7,2472(10)
keep:
lwz 0,2436(10)
andi. 0,0,4
beq store_prev
lbz 7,1249(31)
andi. 0,7,128
bne store_prev
lwz 8,2448(10)
cmplw 7,8
bge store_prev
stb 8,1249(31)
store_prev:
stw 5,2456(10)
done0:
lfs 0,-13576(9)

; ---- stubs ----

stub_a:
cmpwi 0,0
beq cont_a
lis 10,32793
lwz 12,2432(10)
lis 9,17479
ori 9,9,16690
cmpw 12,9
bne skip_a
lwz 12,2480(10)
addi 12,12,1
stw 12,2480(10)
lwz 12,2436(10)
andi. 0,12,1
beq skip_a
lwz 12,2452(10)
cmpwi 12,0
beq skip_a
cmpw 11,12
bne skip_a
lbz 0,248(12)
cmpwi 0,1
bne skip_a
lbz 0,249(12)
cmpwi 0,2
bne skip_a
stw 11,2476(10)
bl absorb_common
skip_a:
b 2147531528
cont_a:
b 2147531476

stub_b:
cmpwi 0,0
beq cont_b
cmpwi 6,0
beqlr

mflr 0
lis 10,32793
stw 0,2380(10)
lwz 9,2432(10)
lis 11,17479
ori 11,11,16690
cmpw 9,11
bne ret_b
lwz 9,2480(10)
addi 9,9,1
stw 9,2480(10)
lwz 9,2436(10)
andi. 0,9,3
cmpwi 0,3
bne ret_b
lwz 11,2452(10)
cmpwi 11,0
beq ret_b
cmpw 12,11
bne ret_b
lbz 0,248(11)
cmpwi 0,1
bne ret_b
lbz 0,249(11)
cmpwi 0,2
bne ret_b
stw 11,2476(10)
bl absorb_common
ret_b:
lis 10,32793
lwz 0,2380(10)
mtlr 0
blr
cont_b:
b 2147533724

absorb_common:
mflr 0
stw 0,2376(10)
stwu 1,-32(1)
lwz 12,2444(10)
cmpwi 12,0
beq cap_ok
lwz 0,2460(10)
cmplw 0,12
bge absorb_exit
cap_ok:
lwz 12,2460(10)
addi 12,12,1
stw 12,2460(10)
lwz 12,2464(10)
addi 12,12,1
stw 12,2464(10)
lwz 9,-29836(13)
lha 12,26644(9)
lha 0,26646(9)
lwz 11,2440(10)
add 12,12,11
cmpw 12,0
ble no_clamp
mr 12,0
no_clamp:
sth 12,26644(9)
lwz 12,2468(10)
add 12,12,11
stw 12,2468(10)
lis 3,32793
addi 3,3,22592
lis 0,32777
ori 0,0,30100
mtctr 0
bctrl
lis 10,32793
lwz 12,2436(10)
andi. 0,12,24
beq absorb_exit
andi. 0,12,32
beq fx_go
lwz 11,2500(10)
lwz 0,2504(10)
cmpw 11,0
beq absorb_exit
fx_go:
lwz 11,2500(10)
stw 11,2504(10)
andi. 0,12,8
beq sound
lwz 3,2484(10)
lwz 4,2488(10)
lis 0,32776
ori 0,0,13220
mtctr 0
bctrl
lis 10,32793
cmpwi 3,0
beq sound
stw 3,2384(10)
lwz 3,2484(10)
lis 0,32776
ori 0,0,13484
mtctr 0
bctrl
lis 10,32793
mr 7,3
lwz 6,2384(10)
lwz 3,2452(10)
mr 10,3
li 4,0
li 5,0
li 8,0
li 9,0
li 0,0
stw 0,8(1)
lis 0,32777
ori 0,0,1788
mtctr 0
bctrl
lis 10,32793
lwz 12,2508(10)
addi 12,12,1
stw 12,2508(10)
sound:
lis 10,32793
lwz 12,2436(10)
andi. 0,12,16
beq absorb_exit
lwz 4,2492(10)
cmpwi 4,0
beq se_second
li 3,0
li 5,0
li 6,0
lis 0,32780
ori 0,0,47068
mtctr 0
bctrl
lis 10,32793
se_second:
lwz 4,2496(10)
cmpwi 4,0
beq absorb_exit
li 3,0
li 5,0
li 6,0
lis 0,32780
ori 0,0,47068
mtctr 0
bctrl
absorb_exit:
lis 10,32793
addi 1,1,32
lwz 0,2376(10)
mtlr 0
blr

andi. 10,0,1
bne hurtbox_done
andi. 10,0,2
beq hurtbox_done
stwu 1,-16(1)
stw 9,8(1)
lis 9,32793
lwz 10,2432(9)
xoris 10,10,17479
xori 10,10,16690
cmpwi 10,0
bne hurtbox_deny
lwz 10,2436(9)
andi. 10,10,1
beq hurtbox_deny
lwz 10,2452(9)
cmpw 31,10
bne hurtbox_deny
lbz 10,248(31)
cmpwi 10,1
bne hurtbox_deny
lbz 10,249(31)
cmpwi 10,2
bne hurtbox_deny
lbz 10,1249(31)
cmpwi 10,0
beq hurtbox_deny
li 10,1
b hurtbox_restore
hurtbox_deny:
li 10,0
hurtbox_restore:
lwz 9,8(1)
addi 1,1,16
hurtbox_done:
cmpwi 10,0
b 2147531844
