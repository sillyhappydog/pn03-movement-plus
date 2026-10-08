
lis 10,32793
lwz 0,-12928(10)
lis 11,17479
ori 11,11,16690
cmpw 0,11
beq init_ok
stw 11,-12928(10)
li 0,63
stw 0,-12924(10)
li 0,100
stw 0,-12920(10)
li 0,0
stw 0,-12916(10)
li 0,2
stw 0,-12912(10)
li 0,0
stw 0,-12876(10)
li 0,20
stw 0,-12872(10)
li 0,55
stw 0,-12868(10)
li 0,57
stw 0,-12864(10)
li 0,0
stw 0,-12908(10)
stw 0,-12904(10)
stw 0,-12900(10)
stw 0,-12896(10)
stw 0,-12892(10)
stw 0,-12888(10)
stw 0,-12884(10)
stw 0,-12880(10)
stw 0,-12860(10)
stw 0,-12856(10)
stw 0,-12852(10)
stw 0,-12848(10)
init_ok:
stw 31,-12908(10)
lwz 11,-12860(10)
addi 11,11,1
stw 11,-12860(10)
lwz 0,-12924(10)
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
lwz 6,-12904(10)
cmpwi 5,0
beq store_prev
cmpwi 6,0
bne keep
li 0,0
stw 0,-12900(10)
lwz 7,-12888(10)
addi 7,7,1
stw 7,-12888(10)
keep:
lwz 0,-12924(10)
andi. 0,0,4
beq store_prev
lbz 7,1249(31)
andi. 0,7,128
bne store_prev
lwz 8,-12912(10)
cmplw 7,8
bge store_prev
stb 8,1249(31)
store_prev:
stw 5,-12904(10)
done0:
lfs 0,-28168(9)

; ---- stubs ----

stub_a:
cmpwi 0,0
beq cont_a
lis 10,32793
lwz 12,-12928(10)
lis 9,17479
ori 9,9,16690
cmpw 12,9
bne skip_a
lwz 12,-12880(10)
addi 12,12,1
stw 12,-12880(10)
lwz 12,-12924(10)
andi. 0,12,1
beq skip_a
lwz 12,-12908(10)
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
stw 11,-12884(10)
bl absorb_common
skip_a:
b 2147531144
cont_a:
b 2147531092

stub_b:
cmpwi 0,0
beq cont_b
cmpwi 6,0
beqlr

mflr 0
lis 10,32793
stw 0,-12980(10)
lwz 9,-12928(10)
lis 11,17479
ori 11,11,16690
cmpw 9,11
bne ret_b
lwz 9,-12880(10)
addi 9,9,1
stw 9,-12880(10)
lwz 9,-12924(10)
andi. 0,9,3
cmpwi 0,3
bne ret_b
lwz 11,-12908(10)
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
stw 11,-12884(10)
bl absorb_common
ret_b:
lis 10,32793
lwz 0,-12980(10)
mtlr 0
blr
cont_b:
b 2147533340

absorb_common:
mflr 0
stw 0,-12984(10)
stwu 1,-32(1)
lwz 12,-12916(10)
cmpwi 12,0
beq cap_ok
lwz 0,-12900(10)
cmplw 0,12
bge absorb_exit
cap_ok:
lwz 12,-12900(10)
addi 12,12,1
stw 12,-12900(10)
lwz 12,-12896(10)
addi 12,12,1
stw 12,-12896(10)
lwz 9,-29868(13)
lha 12,26420(9)
lha 0,26422(9)
lwz 11,-12920(10)
add 12,12,11
cmpw 12,0
ble no_clamp
mr 12,0
no_clamp:
sth 12,26420(9)
lwz 12,-12892(10)
add 12,12,11
stw 12,-12892(10)
lis 3,32793
addi 3,3,7072
lis 0,32777
ori 0,0,23756
mtctr 0
bctrl
lis 10,32793
lwz 12,-12924(10)
andi. 0,12,24
beq absorb_exit
andi. 0,12,32
beq fx_go
lwz 11,-12860(10)
lwz 0,-12856(10)
cmpw 11,0
beq absorb_exit
fx_go:
lwz 11,-12860(10)
stw 11,-12856(10)
andi. 0,12,8
beq sound
lwz 3,-12876(10)
lwz 4,-12872(10)
lis 0,32776
ori 0,0,6892
mtctr 0
bctrl
lis 10,32793
cmpwi 3,0
beq sound
stw 3,-12976(10)
lwz 3,-12876(10)
lis 0,32776
ori 0,0,7156
mtctr 0
bctrl
lis 10,32793
mr 7,3
lwz 6,-12976(10)
lwz 3,-12908(10)
mr 10,3
li 4,0
li 5,0
li 8,0
li 9,0
li 0,0
stw 0,8(1)
lis 0,32776
ori 0,0,60996
mtctr 0
bctrl
lis 10,32793
lwz 12,-12852(10)
addi 12,12,1
stw 12,-12852(10)
sound:
lis 10,32793
lwz 12,-12924(10)
andi. 0,12,16
beq absorb_exit
lwz 4,-12868(10)
cmpwi 4,0
beq se_second
li 3,0
li 5,0
li 6,0
lis 0,32780
ori 0,0,37908
mtctr 0
bctrl
lis 10,32793
se_second:
lwz 4,-12864(10)
cmpwi 4,0
beq absorb_exit
li 3,0
li 5,0
li 6,0
lis 0,32780
ori 0,0,37908
mtctr 0
bctrl
absorb_exit:
lis 10,32793
addi 1,1,32
lwz 0,-12984(10)
mtlr 0
blr
