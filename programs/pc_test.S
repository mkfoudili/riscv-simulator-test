	.section .text
	.globl _start

_start:
    #pc test
    li    x5, 0x11111111

fault_injection_point:
    li    x5, 0x22222222

end:
    j     end