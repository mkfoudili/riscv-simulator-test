    .section .data
    .balign 8
value:
    .dword 0x11111111

	.section .text
	.globl _start

_start:
    #memory test
    la     x5, value

fault_injection_point:
    ld     x6, 0(x5)
    mv     x10, x6

end:
    j     end