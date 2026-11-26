.syntax unified
.cpu cortex-m3
.thumb
.section .isr_vector,"a",%progbits
.word 0x20005000
.word Reset_Handler
.rept 58
.word Default_Handler
.endr
.section .text.Reset_Handler,"ax",%progbits
.thumb_func
.global Reset_Handler
Reset_Handler:
 ldr r0, =_sbss
 ldr r1, =_ebss
 movs r2, #0
1: cmp r0,r1
 bcs 2f
 str r2,[r0],#4
 b 1b
2: bl boot_main
 b Default_Handler
.thumb_func
Default_Handler:
 b .
