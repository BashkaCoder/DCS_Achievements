.include "m8def.inc"

; =========================================================
; Registers
; =========================================================
.def r_tmp      = r16
.def r_cnt_t0   = r17
.def r_cnt_t2   = r18
.def r_uart     = r19

; =========================================================
; Constants
; =========================================================
.equ F_CPU      = 16000000
.equ BAUD_RATE  = 9600
.equ UBRR_VALUE = (F_CPU/(BAUD_RATE*16))-1

.equ T0_CS_BITS = 0b00000101 ; Timer0: CS02..CS00 = 101 => /1024
.equ T2_CS_BITS = 0b00000111 ; Timer2: CS22..CS20 = 111 => /1024

; Overflow intervals
.equ T0_INTERVAL = 1
.equ T2_INTERVAL = 1

.equ STR_END    = 0x00

; =========================================================
; Macros
; =========================================================
.macro ISR_PROLOGUE
    push r_tmp
    in   r_tmp, SREG
    push r_tmp
.endmacro

.macro ISR_EPILOGUE
    pop  r_tmp
    out  SREG, r_tmp
    pop  r_tmp
    reti
.endmacro

; =========================================================
; Vectors
; =========================================================
.cseg
.org 0x0000
    rjmp RESET

.org 0x0004                 ; TIMER2 Overflow
    rjmp TIMER2_OVF_ISR

.org 0x0009                 ; TIMER0 Overflow
    rjmp TIMER0_OVF_ISR

; =========================================================
; Strings in program memory
; =========================================================
TIMER1_STR: .db "ping", 0x0d, 0x0a, STR_END
TIMER2_STR: .db "pong", 0x0d, 0x0a, STR_END

; =========================================================
; Reset / Main
; =========================================================
RESET:
    ; Stack init
    ldi r_tmp, HIGH(RAMEND)
    out SPH, r_tmp
    ldi r_tmp, LOW(RAMEND)
    out SPL, r_tmp

    rcall USART_INIT
    rcall TIMER0_INIT
    rcall TIMER2_INIT

    sei

MAIN_LOOP:
    rjmp MAIN_LOOP

; =========================================================
; USART
; =========================================================
USART_INIT:
    ldi r_tmp, HIGH(UBRR_VALUE)
    out UBRRH, r_tmp
    ldi r_tmp, LOW(UBRR_VALUE)
    out UBRRL, r_tmp

    ldi r_tmp, (1<<TXEN)|(1<<RXEN)
    out UCSRB, r_tmp

    ldi r_tmp, (1<<URSEL)|(1<<UCSZ1)|(1<<UCSZ0)
    out UCSRC, r_tmp
    ret

; Print zero-terminated string from FLASH, address in Z
USART_PRINT_PSTR:
    push r_uart
    push ZL
    push ZH

USART_PRINT_LOOP:
    lpm  r_uart, Z+
    cpi  r_uart, STR_END
    breq USART_PRINT_DONE

    rcall USART_TX_BYTE
    rjmp USART_PRINT_LOOP

USART_PRINT_DONE:
    pop  ZH
    pop  ZL
    pop  r_uart
    ret

USART_TX_BYTE:
    push r_tmp

USART_WAIT_UDRE:
    sbis UCSRA, UDRE
    rjmp USART_WAIT_UDRE

    out  UDR, r_uart

    pop  r_tmp
    ret

; =========================================================
; Timers
; =========================================================
TIMER0_INIT:
    ldi r_tmp, T0_CS_BITS
    out TCCR0, r_tmp

    clr r_tmp
    out TCNT0, r_tmp

    clr r_cnt_t0

    in  r_tmp, TIMSK
    ori r_tmp, (1<<TOIE0)
    out TIMSK, r_tmp
    ret

TIMER2_INIT:
    ldi r_tmp, T2_CS_BITS
    out TCCR2, r_tmp

    clr r_tmp
    out TCNT2, r_tmp

    clr r_cnt_t2

    in  r_tmp, TIMSK
    ori r_tmp, (1<<TOIE2)
    out TIMSK, r_tmp
    ret

; =========================================================
; ISRs
; =========================================================
TIMER0_OVF_ISR:
    ISR_PROLOGUE

    inc r_cnt_t0
    ldi r_tmp, T0_INTERVAL
    cp  r_cnt_t0, r_tmp
    brne TIMER0_EXIT

    clr r_cnt_t0
    ldi ZH, HIGH(2*TIMER1_STR)
    ldi ZL, LOW(2*TIMER1_STR)
    rcall USART_PRINT_PSTR

TIMER0_EXIT:
    ISR_EPILOGUE

TIMER2_OVF_ISR:
    ISR_PROLOGUE

    inc r_cnt_t2
    ldi r_tmp, T2_INTERVAL
    cp  r_cnt_t2, r_tmp
    brne TIMER2_EXIT

    clr r_cnt_t2
    ldi ZH, HIGH(2*TIMER2_STR)
    ldi ZL, LOW(2*TIMER2_STR)
    rcall USART_PRINT_PSTR

TIMER2_EXIT:
    ISR_EPILOGUE
