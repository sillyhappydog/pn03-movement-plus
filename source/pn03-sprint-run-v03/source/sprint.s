
lis 9,32793
lwz 0,-8832(9)
lis 10,0x5350
ori 10,10,0x5233
cmpw 0,10
beq init_ok
stw 10,-8832(9)
li 0,7
stw 0,-8828(9)
li 0,45
stw 0,-8824(9)
li 0,15
stw 0,-8820(9)
lfs 0,-8932(9)
stfs 0,-8816(9)
lfs 0,-8928(9)
stfs 0,-8812(9)
lfs 0,-8924(9)
stfs 0,-8808(9)
li 0,0
stw 0,-8804(9)
stw 0,-8800(9)
stw 0,-8796(9)
stw 0,-8792(9)
stw 0,-8788(9)
stw 0,-8776(9)
stw 0,-8772(9)
lfs 0,-8960(9)
stfs 0,-8784(9)
init_ok:
stw 31,-8780(9)
lwz 12,-8828(9)
andi. 0,12,1
beq done
lbz 0,248(31)
lbz 3,249(31)
lbz 4,250(31)
lwz 5,1528(31)
lwz 6,-8800(9)
lwz 7,-8796(9)
cmpwi 0,1
bne reset
cmpwi 3,1
beq run_state
cmpwi 3,3
beq jump_state
cmpwi 3,0
bne reset
cmpwi 7,3
bne reset
li 7,48
b store_state
run_state:
andi. 0,5,1
beq reset
lfs 1,208(31)
cmpwi 7,1
bne run_first
lfs 2,-8792(9)
fsubs 3,1,2
lfs 4,-8952(9)
fcmpu 0,3,4
ble wrap_lo
lfs 4,-8956(9)
fsubs 3,3,4
b wrapped
wrap_lo:
lfs 4,-8948(9)
fcmpu 0,3,4
bge wrapped
lfs 4,-8956(9)
fadds 3,3,4
wrapped:
fabs 3,3
lfs 4,-8812(9)
fcmpu 0,3,4
bgt reset_turn
run_first:
stfs 1,-8792(9)
addi 6,6,1
cmplwi 6,30000
ble run_ok
li 6,30000
run_ok:
li 7,1
b store_state
reset_turn:
stfs 1,-8792(9)
li 6,0
li 7,1
b store_state
jump_state:
lfs 1,208(31)
stfs 1,-8792(9)
li 7,3
b store_state
reset:
li 6,0
li 7,0
store_state:
stw 6,-8800(9)
stw 7,-8796(9)
lfs 5,-8960(9)
lwz 8,-8824(9)
cmplw 6,8
blt factor_done
lfs 5,-8816(9)
lwz 11,-8820(9)
cmpwi 11,0
ble factor_done
subf 0,8,6
cmplw 0,11
bge factor_done
lis 10,0x4330
stw 10,-8896(9)
stw 0,-8892(9)
lfd 6,-8896(9)
lfd 7,-8920(9)
fsub 6,6,7
frsp 6,6
stw 11,-8892(9)
lfd 7,-8896(9)
lfd 8,-8920(9)
fsub 7,7,8
frsp 7,7
fdivs 6,6,7
lfs 7,-8960(9)
fsubs 5,5,7
fmuls 5,5,6
fadds 5,5,7
factor_done:
stfs 5,-8784(9)
cmpwi 7,1
bne not_running
lfs 7,-8960(9)
fcmpu 0,5,7
ble not_running
lfs 6,-8788(9)
fsubs 8,5,7
fadds 6,6,8
addi 8,31,380
fcmpu 0,6,7
blt no_extra
lbz 0,574(8)
stw 0,-8772(9)
mr 3,8
lis 0,0x800a
ori 0,0,0x1770
mtctr 0
bctrl
lis 9,32793
addi 8,31,380
lwz 0,-8772(9)
cmpwi 0,1
bne loop_ok
li 0,1
stb 0,574(8)
loop_ok:
lhz 10,688(8)
cmpwi 10,6
beq footstep
cmpwi 10,15
bne foot_ok
footstep:
mr 3,31
lis 0,0x800b
ori 0,0,0x5564
mtctr 0
bctrl
lis 9,32793
addi 8,31,380
lwz 10,-8776(9)
addi 10,10,1
stw 10,-8776(9)
foot_ok:
lfs 6,-8788(9)
lfs 5,-8784(9)
lfs 7,-8960(9)
fsubs 8,5,7
fadds 6,6,8
fsubs 6,6,7
no_extra:
fmr 12,6
lfs 7,-8944(9)
fcmpu 0,12,7
ble frac_ok
fmr 12,7
frac_ok:
lfs 7,-8940(9)
fmuls 12,12,7
fctiwz 12,12
stfd 12,-8896(9)
lwz 0,-8892(9)
lhz 10,688(8)
slwi 10,10,6
or 10,10,0
sth 10,680(8)
stfs 6,-8788(9)
b apply_jump
not_running:
lfs 6,-8936(9)
stfs 6,-8788(9)
apply_jump:
cmpwi 7,3
bne done
lwz 12,-8828(9)
andi. 0,12,2
beq done
lbz 4,250(31)
cmpwi 4,6
bne done
lfs 7,-8960(9)
fcmpu 0,5,7
ble done
lfs 8,264(31)
fmuls 8,8,5
stfs 8,264(31)
done:
lis 9,0x8017

; ---- body2 (hook 0x800A08E8) ----

lis 9,32793
lwz 0,-8832(9)
lis 10,0x5350
ori 10,10,0x5233
cmpw 0,10
bne call
lwz 0,-8780(9)
cmpw 0,3
bne call
lwz 0,-8828(9)
andi. 0,0,4
beq call
lwz 0,-8796(9)
cmpwi 0,1
bne call
lbz 0,248(3)
cmpwi 0,1
bne call
lbz 0,249(3)
cmpwi 0,1
bne call
lhz 0,572(4)
andi. 0,0,4
beq call
lhz 11,690(4)
cmpwi 11,0
beq call
lfs 1,-8784(9)
lfs 2,-8960(9)
fcmpu 0,1,2
ble call
lis 12,0x4330
stw 12,-8896(9)
stw 11,-8892(9)
lfd 4,-8896(9)
lfd 5,-8920(9)
fsub 4,4,5
frsp 4,4
lfs 6,612(4)
fdivs 6,6,4
fmuls 6,6,1
lfs 7,-8808(9)
fmuls 6,6,7
stfs 6,8(5)
call:
lis 0,0x800a
ori 0,0,0x15ac
mtctr 0
bctrl
