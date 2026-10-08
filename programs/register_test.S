	.section .text
	.globl _start

_start:
    #register test
    li      x5, 0x11111111

fault_injection_point:
	mv		x10, x5

end:
	j 		end