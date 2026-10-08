
lwz 5,0(3)
lwz 0,0x14(3)
or 5,5,0
lwz 0,0x28(3)
or 5,5,0
lwz 0,0x2c(3)
or 5,5,0
rlwinm. 5,5,0,1,31
bne original
lis 5,52225
li 0,0x10
stb 0,-0x8000(5)
lis 0,6
ori 0,0,0x1020
stw 0,-0x8000(5)
li 0,0
stw 0,-0x8000(5)
lis 0,16672
stw 0,-0x8000(5)
li 0,0
stw 0,-0x8000(5)
lis 0,16672
stw 0,-0x8000(5)
li 0,0
stw 0,-0x8000(5)
stw 0,-0x8000(5)
li 0,1
stw 0,-0x8000(5)
lwz 4,-23136(13)
sth 0,2(4)
blr
original:
lwz 5,-23136(13)
