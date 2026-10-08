stwu 1,-416(1)
stw 0,8(1)
stw 3,12(1)
stw 4,16(1)
stw 5,20(1)
stw 6,24(1)
stw 7,28(1)
stw 8,32(1)
stw 9,36(1)
stw 10,40(1)
stw 11,44(1)
stw 12,48(1)
mflr 0
stw 0,52(1)
mfcr 0
stw 0,56(1)
mfctr 0
stw 0,60(1)
mfxer 0
stw 0,64(1)
mfspr 0,912
stw 0,68(1)
li 0,0
mtspr 912,0
stfd 0,80(1)
.long 0xf0010058
stfd 1,96(1)
.long 0xf0210068
stfd 2,112(1)
.long 0xf0410078
stfd 3,128(1)
.long 0xf0610088
stfd 4,144(1)
.long 0xf0810098
stfd 5,160(1)
.long 0xf0a100a8
stfd 6,176(1)
.long 0xf0c100b8
stfd 7,192(1)
.long 0xf0e100c8
stfd 8,208(1)
.long 0xf10100d8
stfd 9,224(1)
.long 0xf12100e8
stfd 10,240(1)
.long 0xf14100f8
stfd 11,256(1)
.long 0xf1610108
stfd 12,272(1)
.long 0xf1810118
stfd 13,288(1)
.long 0xf1a10128
mffs 0
stfd 0,72(1)
nop
bl data_end
data:
.long 0x00000000
.long 0x3b6bedfa
.long 0x41200000
.long 0x44610000
.long 0x3f800000
.long 0x00000000
.long 0x40490fdb
.long 0x40c90fdb
.long 0x43300000
.long 0x80000000
.long 0xc0490fdb
.long 0x3f800000
.long 0x38d1b717
.long 0x3951b717
.long 0x3d4ccccd
.long 0x3a1d4952
.long 0x461c4000
.long 0x42c80000
.long 0x3f000000
.long 0x00000004
.long 0x0000001e
.long 0x3ec90fdb
.long 0x3f96cbe4
.long 0x3ffb53d1
.long 0x402feddf
.long 0x00000000
.long 0x000003e8
.long 0x3ca3d70a
.long 0x3f490fdb
.long 0x3fc90fdb
.long 0x3f490fdb
.long 0x00000000
.long 0x00000000
.long 0x00000000
.long 0x00000000
.long 0x3fb426c8
.long 0x82638264
.long 0x82618274
.long 0x82668140
.long 0x82628260
.long 0x826c8140
.long 0x82728264
.long 0x826d8272
.long 0x8140824f
.long 0x8144824f
.long 0x824f824f
.long 0x824f8140
.long 0x8277824f
.long 0x824f8144
.long 0x824f824f
.long 0x00826982
.long 0x74826c82
.long 0x6f814082
.long 0x76826882
.long 0x6d814082
.long 0x4f824f81
.long 0x40826081
.long 0x5e826100
.long 0x8263826f
.long 0x82608263
.long 0x81818272
.long 0x8264826d
.long 0x82728140
.long 0x82778181
.long 0x82718264
.long 0x82728264
.long 0x82738140
.long 0x826b817b
.long 0x8271817b
.long 0x82798181
.long 0x82648277
.long 0x82688273
.long 0x00000000
.long 0x00000000
data_end:
mflr 12
stw 12,320(1)
lis 11,32793
lwz 0,5824(11)
lis 9,0x504e
ori 9,9,0x3034
cmpw 0,9
beq config_ok
stw 9,5824(11)
li 0,3
stw 0,5828(11)
lwz 0,4(12)
stw 0,5832(11)
lwz 0,8(12)
stw 0,5836(11)
lwz 0,12(12)
stw 0,5840(11)
lwz 0,16(12)
stw 0,5844(11)
lwz 0,20(12)
stw 0,5848(11)
lwz 0,76(12)
stw 0,5856(11)
li 0,0
stw 0,5852(11)
stw 0,5860(11)
stw 0,5864(11)
stw 0,5868(11)
stw 0,5872(11)
stw 0,5876(11)
stw 0,5880(11)
stw 0,5884(11)
b config_ready
config_ok:
lwz 0,5828(11)
cmpwi 0,3
bge config_ready
cmpwi 0,2
bge upgrade_v3
lwz 0,76(12)
stw 0,5856(11)
upgrade_v3:
li 0,3
stw 0,5828(11)
li 0,0
stw 0,5860(11)
stw 0,5864(11)
stw 0,5868(11)
stw 0,5872(11)
stw 0,5876(11)
stw 0,5880(11)
lwz 0,5852(11)
rlwinm 0,0,0,29,27
stw 0,5852(11)
config_ready:
lis 8,0x801a
lwz 0,-26860(8)
rlwinm 0,0,0,12,9
lbz 9,-26878(8)
extsb 9,9
lbz 10,-26877(8)
extsb 10,10
srawi 7,9,31
xor 9,9,7
subf 9,7,9
srawi 7,10,31
xor 10,10,7
subf 10,7,10
cmpw 9,10
blt cstick_done
rlwinm 0,0,0,10,7
cstick_done:
stw 0,-26860(8)
addi 10,30,-1388
lwz 0,5852(11)
rlwinm 0,0,0,31,29
rlwinm 0,0,0,28,26
lwz 9,5868(11)
cmpwi 9,0
beq follow_done
addi 9,9,-1
stw 9,5868(11)
ori 0,0,2
follow_done:
stw 0,5852(11)
lwz 12,320(1)
lbz 9,248(10)
cmpwi 9,1
bne turn_not_active
lbz 9,249(10)
cmpwi 9,8
bne turn_not_active
lwz 0,5852(11)
ori 0,0,16
stw 0,5852(11)
li 9,2
stw 9,136(12)
b turn_track_done
turn_not_active:
lwz 9,136(12)
cmpwi 9,0
beq turn_end_check
addi 9,9,-1
stw 9,136(12)
lwz 0,5852(11)
ori 0,0,16
stw 0,5852(11)
cmpwi 9,0
bne turn_track_done
turn_end_check:
lwz 9,124(12)
cmpwi 9,0
beq turn_track_done
li 9,0
stw 9,124(12)
li 9,1
stw 9,5868(11)
turn_track_done:
lwz 0,-26864(8)
andi. 7,0,0x60
cmpwi 7,0x60
bne no_toggle
lwz 0,-26860(8)
andi. 0,0,0x10
beq no_toggle
lwz 0,5852(11)
xori 0,0,1
stw 0,5852(11)
li 0,0
stw 0,140(30)
b done
no_toggle:
lwz 0,5852(11)
andi. 0,0,1
beq normal_mode
li 0,0
stw 0,140(30)
lwz 9,-26860(8)
andi. 0,9,8
beq no_dpad_up

lfs 1,5832(11)
lfs 2,60(12)
fadds 1,1,2
lfs 3,56(12)
fcmpu 0,1,3
ble step_hi_ok_up_60
fmr 1,3
step_hi_ok_up_60:
lfs 3,52(12)
fcmpu 0,1,3
bge step_lo_ok_up_60
fmr 1,3
step_lo_ok_up_60:
stfs 1,5832(11)

no_dpad_up:
andi. 0,9,4
beq no_dpad_down

lfs 1,5832(11)
lfs 2,60(12)
fsubs 1,1,2
lfs 3,56(12)
fcmpu 0,1,3
ble step_hi_ok_down_60
fmr 1,3
step_hi_ok_down_60:
lfs 3,52(12)
fcmpu 0,1,3
bge step_lo_ok_down_60
fmr 1,3
step_lo_ok_down_60:
stfs 1,5832(11)

no_dpad_down:
andi. 0,9,2
beq no_dpad_right

lfs 1,5832(11)
lfs 2,48(12)
fadds 1,1,2
lfs 3,56(12)
fcmpu 0,1,3
ble step_hi_ok_up_48
fmr 1,3
step_hi_ok_up_48:
lfs 3,52(12)
fcmpu 0,1,3
bge step_lo_ok_up_48
fmr 1,3
step_lo_ok_up_48:
stfs 1,5832(11)

no_dpad_right:
andi. 0,9,1
beq no_dpad_left

lfs 1,5832(11)
lfs 2,48(12)
fsubs 1,1,2
lfs 3,56(12)
fcmpu 0,1,3
ble step_hi_ok_down_48
fmr 1,3
step_hi_ok_down_48:
lfs 3,52(12)
fcmpu 0,1,3
bge step_lo_ok_down_48
fmr 1,3
step_lo_ok_down_48:
stfs 1,5832(11)

no_dpad_left:
andi. 0,9,0x400
beq no_x_reset
lwz 0,4(12)
stw 0,5832(11)
lwz 0,76(12)
stw 0,5856(11)
no_x_reset:
andi. 0,9,0x100
beq no_a_step
lwz 7,5856(11)
lwz 0,80(12)
cmpw 7,0
bge no_a_step
addi 7,7,1
stw 7,5856(11)
no_a_step:
andi. 0,9,0x200
beq no_b_step
lwz 7,5856(11)
cmpwi 7,0
ble no_b_step
addi 7,7,-1
stw 7,5856(11)
no_b_step:

lwz 0,-26864(8)
rlwinm 0,0,0,0,27
rlwinm 0,0,0,24,21
rlwinm 0,0,0,21,19
stw 0,-26864(8)


lwz 0,-26860(8)
rlwinm 0,0,0,0,27
rlwinm 0,0,0,24,21
rlwinm 0,0,0,21,19
stw 0,-26860(8)


lwz 0,-26856(8)
rlwinm 0,0,0,0,27
rlwinm 0,0,0,24,21
rlwinm 0,0,0,21,19
stw 0,-26856(8)

compose_text:
lfs 1,5832(11)
lfs 2,64(12)
fmuls 3,1,2
lfs 2,72(12)
fadds 3,3,2
fctiwz 3,3
stfd 3,344(1)
lwz 9,348(1)
cmpwi 9,9999
ble sens_clamped
li 9,9999
sens_clamped:
cmpwi 9,0
bge sens_positive
li 9,0
sens_positive:
li 0,1000
divwu 10,9,0
mullw 0,10,0
subf 9,0,9

li 0,0x82
stb 0,178(12)
addi 0,10,0x4f
stb 0,179(12)
li 0,100
divwu 10,9,0
mullw 0,10,0
subf 9,0,9

li 0,0x82
stb 0,180(12)
addi 0,10,0x4f
stb 0,181(12)
li 0,10
divwu 10,9,0
mullw 0,10,0
subf 9,0,9

li 0,0x82
stb 0,182(12)
addi 0,10,0x4f
stb 0,183(12)
li 0,0x82
stb 0,184(12)
addi 0,9,0x4f
stb 0,185(12)
lfs 2,60(12)
fdivs 3,1,2
lfs 2,68(12)
fmuls 3,3,2
lfs 2,72(12)
fadds 3,3,2
fctiwz 3,3
stfd 3,344(1)
lwz 9,348(1)
cmpwi 9,9999
ble mult_clamped
li 9,9999
mult_clamped:
cmpwi 9,0
bge mult_positive
li 9,0
mult_positive:
li 0,1000
divwu 10,9,0
mullw 0,10,0
subf 9,0,9

cmpwi 10,0
bne digit_190

li 0,0x81
stb 0,190(12)
li 0,0x40
stb 0,191(12)

b digit_done_190
digit_190:

li 0,0x82
stb 0,190(12)
addi 0,10,0x4f
stb 0,191(12)
digit_done_190:
li 0,100
divwu 10,9,0
mullw 0,10,0
subf 9,0,9

li 0,0x82
stb 0,192(12)
addi 0,10,0x4f
stb 0,193(12)
li 0,10
divwu 10,9,0
mullw 0,10,0
subf 9,0,9

li 0,0x82
stb 0,196(12)
addi 0,10,0x4f
stb 0,197(12)
li 0,0x82
stb 0,198(12)
addi 0,9,0x4f
stb 0,199(12)
lwz 9,5856(11)
cmpwi 9,99
ble win_clamped
li 9,99
win_clamped:
cmpwi 9,0
bge win_positive
li 9,0
win_positive:
li 0,10
divwu 10,9,0
mullw 0,10,0
subf 9,0,9

li 0,0x82
stb 0,219(12)
addi 0,10,0x4f
stb 0,220(12)
li 0,0x82
stb 0,221(12)
addi 0,9,0x4f
stb 0,222(12)
li 3,1
lis 11,32776
ori 11,11,356
mtctr 11
bctrl
stw 3,340(1)
lwz 12,320(1)
li 3,16
li 4,396
li 5,0
li 6,0
addi 7,12,144
crxor 6,6,6
lis 11,32776
ori 11,11,376
mtctr 11
bctrl
lwz 12,320(1)
li 3,16
li 4,412
li 5,0
li 6,0
addi 7,12,201
crxor 6,6,6
lis 11,32776
ori 11,11,376
mtctr 11
bctrl
lwz 12,320(1)
li 3,16
li 4,428
li 5,0
li 6,0
addi 7,12,232
crxor 6,6,6
lis 11,32776
ori 11,11,376
mtctr 11
bctrl

lwz 3,340(1)
lis 11,32776
ori 11,11,356
mtctr 11
bctrl
b done
normal_mode:
lis 8,0x801a
lis 11,32793
lbz 0,-26872(8)
cmpwi 0,0
beq pad_ok
li 0,0
stw 0,5860(11)
stw 0,5864(11)
b done
pad_ok:
lwz 0,5876(11)
li 9,0
stw 9,5876(11)
addi 10,30,-1388
lbz 9,248(10)
cmpwi 9,1
bne focus_done
cmpwi 0,0
beq focus_press
lwz 3,72(30)
cmpwi 3,0
beq focus_reset
lwz 0,1236(3)
cmpwi 0,0
ble focus_reset
stw 3,380(1)
lwz 5,240(3)
cmpwi 5,0
beq focus_actor_pos
lbz 4,293(3)
mr 3,5
lis 11,32777
ori 11,11,61360
mtctr 11
bctrl
addi 3,3,264
b focus_have_pos
focus_actor_pos:
addi 3,3,192
focus_have_pos:
lwz 12,320(1)
addi 10,30,-1388
lfs 1,0(3)
lfs 2,192(10)
fsubs 1,1,2
lfs 2,8(3)
lfs 3,200(10)
fsubs 2,2,3
lis 11,32781
ori 11,11,60848
mtctr 11
bctrl
lwz 12,320(1)
addi 10,30,-1388
lis 11,32793
stfs 1,5872(11)
li 0,0
stw 0,5880(11)
lwz 0,5852(11)
ori 0,0,8
stw 0,5852(11)
b focus_press
focus_reset:
lis 11,32793
li 0,1
stw 0,5868(11)
focus_press:
lis 8,0x801a
lis 11,32793
lwz 0,140(30)
andi. 0,0,0x400
beq focus_done
lhz 0,2140(30)
cmpwi 0,0
bne focus_targets
li 0,1
stw 0,5868(11)
b focus_done
focus_targets:
li 0,1
stw 0,5876(11)
focus_done:
lbz 9,-26880(8)
extsb 9,9
lbz 7,-26879(8)
extsb 7,7
lis 0,0x4330
stw 0,328(1)
xoris 0,9,0x8000
stw 0,332(1)
lfd 3,328(1)
lfd 5,32(12)
fsub 3,3,5
frsp 3,3
xoris 0,7,0x8000
stw 0,332(1)
lfd 4,328(1)
fsub 4,4,5
frsp 4,4
fmuls 6,3,3
fmadds 6,4,4,6
lfs 7,5840(11)
lwz 9,5860(11)
fcmpu 0,6,7
ble stick_idle
addi 9,9,1
lwz 0,104(12)
cmpw 9,0
ble counter_ok
mr 9,0
counter_ok:
li 0,1
b counter_store
stick_idle:
li 9,0
li 0,0
counter_store:
stw 9,5860(11)
stw 9,372(1)
stw 0,360(1)
lwz 0,5864(11)
stw 0,356(1)
li 0,0
stw 0,5864(11)
addi 10,30,-1388
lbz 0,248(10)
cmpwi 0,1
bne done
lwz 0,360(1)
cmpwi 0,0
beq no_stick_angle
lfs 7,5844(11)
fmuls 1,3,7
fmr 2,4
lis 11,32781
ori 11,11,60848
mtctr 11
bctrl
stfs 1,336(1)
no_stick_angle:
lwz 12,320(1)
lis 11,32791
lwz 11,-10740(11)
cmpwi 11,0
beq use_last
lfs 1,268(11)
lfs 2,256(11)
fsubs 1,1,2
lfs 2,276(11)
lfs 3,264(11)
fsubs 2,2,3
fmuls 6,1,1
fmadds 6,2,2,6
lfs 7,44(12)
fcmpu 0,6,7
ble use_last
lis 11,32781
ori 11,11,60848
mtctr 11
bctrl
lwz 12,320(1)
stfs 1,0(12)
b have_camera
use_last:
lfs 1,0(12)
have_camera:
stfs 1,352(1)
lwz 0,360(1)
cmpwi 0,0
beq no_intended
lis 9,32793
lfs 2,5848(9)
fadds 1,1,2
lfs 2,336(1)
fsubs 1,1,2

lfs 5,28(12)
lfs 6,24(12)
wrap_high_intended:
fcmpu 0,1,6
ble wrap_low_check_intended
fsubs 1,1,5
b wrap_high_intended
wrap_low_check_intended:
lfs 6,40(12)
wrap_low_intended:
fcmpu 0,1,6
bge wrap_done_intended
fadds 1,1,5
b wrap_low_intended
wrap_done_intended:

stfs 1,364(1)
no_intended:
addi 10,30,-1388
lbz 0,249(10)
cmpwi 0,0
beq explore
cmpwi 0,1
beq explore
cmpwi 0,11
beq explore
cmpwi 0,12
beq explore
cmpwi 0,5
beq crouch_state
side_swap:
lwz 9,140(30)
andis. 0,9,3
beq side_done
lfs 1,208(10)
lfs 2,352(1)
fsubs 1,1,2

lfs 5,28(12)
lfs 6,24(12)
wrap_high_side:
fcmpu 0,1,6
ble wrap_low_check_side
fsubs 1,1,5
b wrap_high_side
wrap_low_check_side:
lfs 6,40(12)
wrap_low_side:
fcmpu 0,1,6
bge wrap_done_side
fadds 1,1,5
b wrap_low_side
wrap_done_side:

fabs 1,1
lfs 3,116(12)
fcmpu 0,1,3
ble side_done
andis. 11,9,2
andis. 7,9,1
andi. 8,9,0x8000
andi. 6,9,0x4000
rlwinm 9,9,0,18,13
rlwinm 11,11,31,1,31
rlwinm 7,7,1,0,30
rlwinm 8,8,31,1,31
rlwinm 6,6,1,0,30
or 9,9,11
or 9,9,7
or 9,9,8
or 9,9,6
stw 9,140(30)
side_done:
lbz 0,249(10)
cmpwi 0,3
beq jump_state
cmpwi 0,8
beq turn_state
b done
crouch_state:
lwz 9,140(30)
andis. 0,9,4
beq explore
andis. 0,9,3
bne side_swap
rlwinm 9,9,0,0,27
lwz 0,360(1)
cmpwi 0,0
beq crouch_store
rlwinm 9,9,0,18,13
lfs 1,364(1)
lfs 2,208(10)
fsubs 1,1,2

lfs 5,28(12)
lfs 6,24(12)
wrap_high_crouch:
fcmpu 0,1,6
ble wrap_low_check_crouch
fsubs 1,1,5
b wrap_high_crouch
wrap_low_check_crouch:
lfs 6,40(12)
wrap_low_crouch:
fcmpu 0,1,6
bge wrap_done_crouch
fadds 1,1,5
b wrap_low_crouch
wrap_done_crouch:

fabs 2,1
lfs 3,120(12)
fcmpu 0,2,3
bge crouch_not_forward
ori 9,9,1
b crouch_store
crouch_not_forward:
lfs 4,24(12)
fsubs 3,4,3
fcmpu 0,2,3
ble crouch_side
ori 9,9,2
b crouch_store
crouch_side:
lfs 3,100(12)
fcmpu 0,1,3
blt crouch_right
oris 9,9,2
ori 9,9,0x8000
b crouch_store
crouch_right:
oris 9,9,1
ori 9,9,0x4000
crouch_store:
stw 9,140(30)
b done
turn_state:
lbz 0,250(10)
cmpwi 0,0
bne done
lwz 12,320(1)
lis 8,0x801a
lbz 9,-26878(8)
extsb 9,9
lwz 0,-26864(8)
rlwinm 0,0,0,16,13
lfs 1,208(10)
stfs 1,128(12)
lfs 2,24(12)
cmpwi 9,-40
bge turn_not_left
oris 0,0,1
lfs 2,140(12)
b turn_store
turn_not_left:
cmpwi 9,40
ble turn_store
oris 0,0,2
lfs 2,140(12)
fneg 2,2
turn_store:
stw 0,-26864(8)
stfs 2,132(12)
li 9,1
stw 9,124(12)
fadds 1,1,2

lfs 5,28(12)
lfs 6,24(12)
wrap_high_turn_goal:
fcmpu 0,1,6
ble wrap_low_check_turn_goal
fsubs 1,1,5
b wrap_high_turn_goal
wrap_low_check_turn_goal:
lfs 6,40(12)
wrap_low_turn_goal:
fcmpu 0,1,6
bge wrap_done_turn_goal
fadds 1,1,5
b wrap_low_turn_goal
wrap_done_turn_goal:

lis 11,32793
stfs 1,5872(11)
li 0,0
stw 0,5880(11)
lwz 0,5852(11)
ori 0,0,40
stw 0,5852(11)
b done
jump_state:
lbz 0,250(10)
cmpwi 0,0
bne air_control
lwz 0,356(1)
cmpwi 0,1
bne kind_not_camera
lfs 1,352(1)
stfs 1,208(10)
b air_control
kind_not_camera:
cmpwi 0,2
bne air_control
lwz 0,360(1)
cmpwi 0,0
beq air_control
lfs 1,364(1)
stfs 1,208(10)
air_control:
lwz 0,140(30)
rlwinm 0,0,0,0,27
lwz 9,360(1)
cmpwi 9,0
beq store_ctrl_jump
lfs 1,364(1)
lfs 2,208(10)
fsubs 1,1,2

lfs 5,28(12)
lfs 6,24(12)
wrap_high_relative:
fcmpu 0,1,6
ble wrap_low_check_relative
fsubs 1,1,5
b wrap_high_relative
wrap_low_check_relative:
lfs 6,40(12)
wrap_low_relative:
fcmpu 0,1,6
bge wrap_done_relative
fadds 1,1,5
b wrap_low_relative
wrap_done_relative:

fabs 2,1
lfs 3,88(12)
fcmpu 0,2,3
bge not_up
ori 0,0,1
not_up:
lfs 3,92(12)
fcmpu 0,2,3
ble not_down
ori 0,0,2
not_down:
lfs 3,84(12)
fcmpu 0,2,3
ble store_ctrl_jump
lfs 3,96(12)
fcmpu 0,2,3
bge store_ctrl_jump
lfs 3,100(12)
fcmpu 0,1,3
blt right_side
ori 0,0,8
b store_ctrl_jump
right_side:
ori 0,0,4
store_ctrl_jump:
stw 0,140(30)
b done
explore:
lwz 9,140(30)
andis. 0,9,3
beq no_sidestep
lfs 1,352(1)
stfs 1,208(10)
rlwinm 9,9,0,0,27
stw 9,140(30)
b done
no_sidestep:
lwz 7,360(1)
lwz 8,372(1)
lis 11,32793
lwz 0,5856(11)
li 6,0
cmpwi 7,0
beq zone_done
cmpw 8,0
bgt zone_done
lis 5,0x801a
lwz 5,-26864(5)
andis. 5,5,4
beq zone_done
li 6,1
zone_done:
andi. 9,9,0x2000
beq no_jump_press
cmpwi 7,0
beq kind_zero
cmpwi 6,0
beq kind_running
li 0,1
stw 0,5864(11)
b hold
kind_running:
li 0,2
stw 0,5864(11)
b run_convert
kind_zero:
li 0,0
stw 0,5864(11)
b done
no_jump_press:
cmpwi 7,0
beq done
cmpwi 6,0
beq run_convert
lwz 0,5852(11)
andi. 0,0,4
bne hold
lfs 1,364(1)
lfs 2,208(10)
fsubs 1,1,2

lfs 5,28(12)
lfs 6,24(12)
wrap_high_arc_turn:
fcmpu 0,1,6
ble wrap_low_check_arc_turn
fsubs 1,1,5
b wrap_high_arc_turn
wrap_low_check_arc_turn:
lfs 6,40(12)
wrap_low_arc_turn:
fcmpu 0,1,6
bge wrap_done_arc_turn
fadds 1,1,5
b wrap_low_arc_turn
wrap_done_arc_turn:

fabs 7,1
fmr 9,7
lfs 1,352(1)
lfs 2,364(1)
fsubs 1,1,2

lfs 5,28(12)
lfs 6,24(12)
wrap_high_arc_snap:
fcmpu 0,1,6
ble wrap_low_check_arc_snap
fsubs 1,1,5
b wrap_high_arc_snap
wrap_low_check_arc_snap:
lfs 6,40(12)
wrap_low_arc_snap:
fcmpu 0,1,6
bge wrap_done_arc_snap
fadds 1,1,5
b wrap_low_arc_snap
wrap_done_arc_snap:

fabs 8,1
fadds 7,7,8
lfs 1,352(1)
lfs 2,208(10)
fsubs 1,1,2

lfs 5,28(12)
lfs 6,24(12)
wrap_high_arc_direct:
fcmpu 0,1,6
ble wrap_low_check_arc_direct
fsubs 1,1,5
b wrap_high_arc_direct
wrap_low_check_arc_direct:
lfs 6,40(12)
wrap_low_arc_direct:
fcmpu 0,1,6
bge wrap_done_arc_direct
fadds 1,1,5
b wrap_low_arc_direct
wrap_done_arc_direct:

fabs 8,1
fsubs 7,7,8
lfs 8,108(12)
fcmpu 0,7,8
blt run_convert
lfs 3,112(12)
fcmpu 0,9,3
bge hold
lwz 0,140(30)
rlwinm 0,0,0,0,27
ori 0,0,1
stw 0,140(30)
b done
hold:
lwz 0,140(30)
rlwinm 0,0,0,0,27
stw 0,140(30)
b done
run_convert:
lwz 0,140(30)
rlwinm 0,0,0,0,27
ori 0,0,1
stw 0,140(30)
lfs 1,364(1)
stfs 1,208(10)
done:
lfd 0,72(1)
mtfsf 255,0
.long 0xe0010058
lfd 0,80(1)
.long 0xe0210068
lfd 1,96(1)
.long 0xe0410078
lfd 2,112(1)
.long 0xe0610088
lfd 3,128(1)
.long 0xe0810098
lfd 4,144(1)
.long 0xe0a100a8
lfd 5,160(1)
.long 0xe0c100b8
lfd 6,176(1)
.long 0xe0e100c8
lfd 7,192(1)
.long 0xe10100d8
lfd 8,208(1)
.long 0xe12100e8
lfd 9,224(1)
.long 0xe14100f8
lfd 10,240(1)
.long 0xe1610108
lfd 11,256(1)
.long 0xe1810118
lfd 12,272(1)
.long 0xe1a10128
lfd 13,288(1)
lwz 0,68(1)
mtspr 912,0
lwz 0,64(1)
mtxer 0
lwz 0,60(1)
mtctr 0
lwz 0,56(1)
mtcrf 255,0
lwz 0,52(1)
mtlr 0
lwz 3,12(1)
lwz 4,16(1)
lwz 5,20(1)
lwz 6,24(1)
lwz 7,28(1)
lwz 8,32(1)
lwz 9,36(1)
lwz 10,40(1)
lwz 11,44(1)
lwz 12,48(1)
lwz 0,8(1)
addi 1,1,416
lwz 11,-29868(13)
