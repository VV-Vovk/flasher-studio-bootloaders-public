#!/usr/bin/env python3
"""Deterministic recovery layouts and build inputs; no inference from board name."""
import argparse, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RADIOS={'esp32':('wifi','ble','wifi-ble'),'esp32c3':('wifi','ble','wifi-ble'),'esp32s3':('wifi','ble','wifi-ble'),'esp32c6':('wifi','ble','wifi-ble'),'esp32s2':('wifi',),'esp32h2':('ble',)}
# Conservative candidates, not guarantees of board-level availability. No straps/flash pins by design.
PINS={'esp32':(4,18,19,21,22,23,25,26,27,32,33),'esp32c3':(4,3,5,6,7,10),'esp32s3':(4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,21),'esp32c6':(2,3,6,7,10,11,18,19,20,21,22,23),'esp32s2':(4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,21),'esp32h2':(4,5,6,7,10,11,12,13,14)}
def profile(target,radio,flash=4,gpio=None,hold=3):
    if type(hold) is not int or not 0<=hold<=5:raise ValueError('hold seconds must be an integer from 0 to 5')
    if target not in RADIOS or radio not in RADIOS[target]:raise ValueError('unsupported radio/MCU combination')
    if flash not in ((4,) if target=='esp32h2' else (4,8,16)):raise ValueError('unsupported flash size')
    default=PINS[target][0]; gpio=default if gpio is None else gpio
    if gpio not in PINS[target]:raise ValueError('GPIO not in conservative candidate list; verify your board')
    size=flash*1024*1024; start=0x1a0000; slot=(size-start)//2
    if slot%0x10000:raise ValueError('invalid slot alignment')
    return dict(target=target,radio=radio,flash=flash,gpio=gpio,hold=hold,slot=slot,slots=[start,start+slot],id=f'{target}-recovery-{radio}-{flash}mb'+(f'-gpio{gpio}' if gpio!=default else '')+(f'-hold{hold}s' if hold!=3 else ''))
def rows(p):
    return [('nvs',1,2,0x9000,0x6000),('otadata',1,0,0xf000,0x2000),('phy_init',1,1,0x11000,0x1000),('fs_meta',1,2,0x12000,0x6000),('recovery',0,0,0x20000,0x180000),('app0',0,16,p['slots'][0],p['slot']),('app1',0,17,p['slots'][1],p['slot'])]
def csv_text(p):
    return '# Name, Type, SubType, Offset, Size, Flags\n'+''.join(f'{n},{"app" if t==0 else "data"},{ {"nvs":"nvs","otadata":"ota","phy_init":"phy","fs_meta":"nvs","recovery":"factory","app0":"ota_0","app1":"ota_1"}[n]},0x{a:x},0x{s:x},\n' for n,t,st,a,s in rows(p))
def prepare(p,root=ROOT/'recovery'):
    (root/'partitions.csv').write_text(csv_text(p))
    (root/'sdkconfig.transport').write_text(f'CONFIG_FS_WIFI={"y" if "wifi" in p["radio"] else "n"}\nCONFIG_FS_BLE={"y" if "ble" in p["radio"] else "n"}\nCONFIG_BOOTLOADER_NUM_PIN_FACTORY_RESET={p["gpio"]}\nCONFIG_BOOTLOADER_HOLD_TIME_GPIO={p["hold"]}\nCONFIG_ESPTOOLPY_FLASHSIZE_{p["flash"]}MB=y\n'+(root/('sdkconfig.ble' if 'ble' in p['radio'] else 'sdkconfig.wifi')).read_text())
def matrix():
    ps=[profile(t,r) for t,rs in RADIOS.items() for r in rs]
    ps += [profile(t, 'wifi-ble' if 'wifi-ble' in rs else 'wifi', f) for t,rs in RADIOS.items() if t!='esp32h2' for f in (8,16)]
    return [{k:p[k] for k in ('target','radio','flash','gpio','id')} for p in ps]
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('command',choices=['matrix','prepare']);a.add_argument('target',nargs='?');a.add_argument('radio',nargs='?');a.add_argument('flash',nargs='?',type=int,default=4);a.add_argument('gpio',nargs='?',type=int);a.add_argument('hold',nargs='?',type=int,default=3);v=a.parse_args()
    if v.command=='matrix': print(json.dumps({'include':matrix()},separators=(',',':')))
    else:prepare(profile(v.target,v.radio,v.flash,v.gpio,v.hold))
