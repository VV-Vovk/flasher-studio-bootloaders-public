/* SPDX-License-Identifier: Apache-2.0
 * STM32F103C8T6 only, factory HSI 8 MHz, USART1 PA9/PA10, PB12 low entry.
 * No option-byte writes; application partition only. RM0008 / PM0075.
 */
#include <stdint.h>
#include <stddef.h>
#define R(a) (*(volatile uint32_t *)(uintptr_t)(a))
#define H(a) (*(volatile uint16_t *)(uintptr_t)(a))
#define APP 0x08004000u
#define META 0x0800fc00u
#define MAX (META-APP)
#define MAGIC 0x46534d32u
#define RCC 0x40021000u
#define GPIOA 0x40010800u
#define GPIOB 0x40010c00u
#define USART 0x40013800u
#define FLASH 0x40022000u
#define SR R(FLASH+0x0c)
#define CR R(FLASH+0x10)
#define ACK 0x79u
#define NACK 0x1fu
static uint8_t buf[256];
static void tx(uint8_t b){while(!(R(USART)&(1u<<7))){} R(USART+4)=b;}
static uint8_t rx(void){while(!(R(USART)&(1u<<5))){} return (uint8_t)R(USART+4);}
static uint32_t rx32(void){uint32_t v=0;for(unsigned i=0;i<4;i++)v|=(uint32_t)rx()<<(8*i);return v;}
static void tx32(uint32_t v){for(unsigned i=0;i<4;i++)tx(v>>(8*i));}
static uint32_t crc32(const uint8_t *p,uint32_t n){uint32_t c=~0u;while(n--){c^=*p++;for(int i=0;i<8;i++)c=(c>>1)^(0xedb88320u & (0u-(c&1)));}return ~c;}
static int vectors(uint32_t n){uint32_t sp=R(APP),pc=R(APP+4);return n>=8&&n<=MAX&&sp>0x20000000u&&sp<=0x20005000u&&!(sp&7)&& (pc&1)&&pc-1>=APP&&pc-1<APP+n;}
static int valid(void){uint32_t n=R(META+4);return R(META)==MAGIC&&vectors(n)&&crc32((const uint8_t*)APP,n)==R(META+8);}
static int wait_flash(void){while(SR&1u){} uint32_t status=SR;SR=(1u<<5)|(1u<<4)|(1u<<2);return !(status&((1u<<4)|(1u<<2)));}
static int unlock(void){if(CR&(1u<<7)){R(FLASH+4)=0x45670123u;R(FLASH+4)=0xcdef89abu;}return !(CR&(1u<<7));}
static void lock(void){CR=1u<<7;}
static int erase(uint32_t a){if(a<APP||a>META||(a&1023)||!wait_flash())return 0;CR=2;R(FLASH+0x14)=a;CR=2|(1u<<6);int ok=wait_flash();CR=0;return ok&&R(a)==0xffffffffu;}
static int prog(uint32_t a,uint16_t v){if(a<APP||a>=META+1024||(a&1)||!wait_flash())return 0;if(v==0xffff)return H(a)==v;CR=1;H(a)=v;int ok=wait_flash();CR=0;return ok&&H(a)==v;}
static int word(uint32_t a,uint32_t v){return prog(a,(uint16_t)v)&&prog(a+2,(uint16_t)(v>>16));}
static void reset(void){__asm volatile("dsb" ::: "memory");R(0xe000ed0c)=0x05fa0004;__asm volatile("dsb" ::: "memory");for(;;){}}
__attribute__((noreturn)) static void jump(void){uint32_t sp=R(APP),pc=R(APP+4);R(RCC+0x0c)=1u<<3;R(RCC+0x0c)=0;R(RCC+0x18)=0;R(0xe000ed08)=APP;__asm volatile("dsb\n isb\n msr msp,%0\n bx %1"::"r"(sp),"r"(pc):"memory");__builtin_unreachable();}
void boot_main(void){
 /* reset clock HSI, no PLL; GPIOB PB12 input pull-up */
 R(RCC+0x18)=(1u<<3);R(GPIOB+4)=(R(GPIOB+4)&~(15u<<16))|(8u<<16);R(GPIOB+0x10)=1u<<12;
 for(volatile unsigned i=0;i<2000;i++){}
 if((R(GPIOB+8)&(1u<<12))&&valid())jump();
 R(RCC+0x18)|=(1u<<2)|(1u<<14);R(GPIOA+4)=(R(GPIOA+4)&~(0xffu<<4))|(0x4bu<<4);R(USART+8)=69;R(USART+0x0c)=(1u<<13)|(1u<<3)|(1u<<2);
 uint32_t length=0,expected=0,pos=0;int active=0;
 for(;;){uint8_t cmd=rx();
  if(cmd==0x49){tx(ACK);tx('F');tx('S');tx('1');tx('0');tx32(APP);tx32(MAX);continue;}
  if(cmd==0x42){uint32_t n=rx32(),c=rx32();if(active||n<8||n>MAX){tx(NACK);continue;}int ok=unlock()&&erase(META); /* invalidate before touching app */
   for(uint32_t a=APP;ok&&a<META;a+=1024)ok=erase(a);lock();if(ok){length=n;expected=c;pos=0;active=1;}tx(ok?ACK:NACK);continue;}
  if(cmd==0x44){uint32_t n=rx32();if(!n||n>sizeof buf){tx(NACK);active=0;continue;}for(uint32_t i=0;i<n;i++)buf[i]=rx();
   if(!active||n>length-pos||((n&1)&&n!=length-pos)){tx(NACK);continue;}int ok=unlock();for(uint32_t i=0;ok&&i<n;i+=2)ok=prog(APP+pos+i,buf[i]|((uint16_t)(i+1<n?buf[i+1]:0xff)<<8));lock();if(ok)pos+=n;else active=0;tx(ok?ACK:NACK);continue;}
  if(cmd==0x43){int ok=active&&pos==length&&vectors(length)&&crc32((const uint8_t*)APP,length)==expected; if(ok){ok=unlock()&&word(META+4,length)&&word(META+8,expected)&&word(META,MAGIC);lock();}active=0;tx(ok?ACK:NACK);continue;}
  if(cmd==0x52){if(!active&&valid()){tx(ACK);while(!(R(USART)&(1u<<6))){}reset();}else tx(NACK);continue;}
  if(cmd==0x58){active=0;tx(ACK);continue;}tx(NACK);
 }
}
