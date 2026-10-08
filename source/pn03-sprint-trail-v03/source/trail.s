
lis 10,32793
lwz 0,-10496(10)
lis 11,21586
ori 11,11,19507
cmpw 0,11
beq init_ok
stw 11,-10496(10)
li 0,5
stw 0,-10492(10)
lis 0,65416
ori 0,0,0
stw 0,-10488(10)
lis 0,20580
ori 0,0,65365
stw 0,-10484(10)
li 0,9
stw 0,-10480(10)
li 0,0
stw 0,-10476(10)
stw 0,-10472(10)
stw 0,-10468(10)
stw 0,-10464(10)
stw 0,-10460(10)
init_ok:
lwz 0,-10492(10)
andi. 0,0,1
beq done
lwz 0,-8832(10)
lis 11,21328
ori 11,11,21043
cmpw 0,11
bne zero_t
lfs 2,-10624(10)
lfs 4,-10620(10)
lfs 1,-8784(10)
fsubs 1,1,2
lfs 3,-8816(10)
fsubs 3,3,2
fcmpu 0,3,4
ble zero_t
fdivs 1,1,3
fcmpu 0,1,4
bge t_lo_ok
fmr 1,4
t_lo_ok:
fcmpu 0,1,2
ble t_hi_ok
fmr 1,2
t_hi_ok:
lwz 0,-10492(10)
andi. 0,0,2
beq t_done
lfs 5,-10616(10)
fcmpu 0,1,5
blt step_zero
fmr 1,2
b t_done
step_zero:
fmr 1,4
b t_done
zero_t:
lfs 1,-10620(10)
t_done:
stfs 1,-10476(10)
li 0,0
stw 0,-10472(10)
lfs 4,-10620(10)
fcmpu 0,1,4
bne do_scan
lwz 0,-10468(10)
cmpwi 0,0
beq done
do_scan:
lwz 3,-29940(13)
cmpwi 3,0
beq done
addis 4,3,1
lwz 5,-31424(4)
lwz 6,-31432(4)
cmpwi 6,0
beq done
li 7,0
lfd 8,-10608(10)
lis 12,0x4330
stw 12,-10560(10)
loop:
cmplw 7,5
bge scan_done
lbz 0,24(6)
andi. 11,0,1
beq next
andi. 11,0,2
bne next
lwz 11,-10480(10)
cmpwi 11,-1
beq id_ok
lbz 0,25(6)
cmpw 0,11
bne next
id_ok:
lwz 11,-10484(10)
cmpwi 11,0
beq match_ok
lwz 0,136(6)
cmpw 0,11
bne next
match_ok:
lwz 0,-10492(10)
andi. 0,0,4
beq parent_ok
lwz 0,36(6)
cmpw 0,31
bne next
parent_ok:
li 11,0
channel:
add 8,6,11
lbz 0,136(8)
stw 0,-10556(10)
lfd 9,-10560(10)
fsub 9,9,8
frsp 9,9
addi 8,10,-10488
lbzx 0,8,11
stw 0,-10556(10)
lfd 10,-10560(10)
fsub 10,10,8
frsp 10,10
fsubs 10,10,9
fmuls 10,10,1
fadds 10,10,9
slwi 0,11,2
add 8,6,0
stfs 10,140(8)
addi 11,11,1
cmpwi 11,3
blt channel
lwz 8,-10472(10)
addi 8,8,1
stw 8,-10472(10)
lwz 8,-10464(10)
addi 8,8,1
stw 8,-10464(10)
next:
addi 6,6,336
addi 7,7,1
b loop
scan_done:
li 0,0
lfs 4,-10620(10)
fcmpu 0,1,4
beq set_dirty
li 0,1
set_dirty:
stw 0,-10468(10)
done:
lis 9,0x8017
lfs 13,0xd0(31)
