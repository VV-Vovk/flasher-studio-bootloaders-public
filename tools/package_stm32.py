#!/usr/bin/env python3
"""Package the independently implemented STM32 FS10 candidate; no third-party binaries."""
import argparse, hashlib, json, pathlib, re, struct, zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
VERSION='0.2.2'
ID='stm32f103c8-uart-recovery'
def digest(b): return hashlib.sha256(b).hexdigest()
def meta(name,b,**kw): return dict(file=name,size=len(b),sha256=digest(b),**kw)
def encode(x): return (json.dumps(x,indent=2,ensure_ascii=False)+'\n').encode()
def package(binary,out,commit):
    if not re.fullmatch('[a-f0-9]{40}',commit): raise ValueError('source commit')
    b=pathlib.Path(binary).read_bytes()
    if not 8<=len(b)<=0x4000: raise ValueError('loader size')
    sp,pc=struct.unpack_from('<II',b)
    if sp!=0x20005000 or not pc&1 or not 0x08000000<=pc-1<0x08000000+len(b): raise ValueError('loader vectors')
    ld=(ROOT/'stm32/application.ld').read_bytes()
    m=dict(schemaVersion=1,id=ID,version=VERSION,name='STM32F103C8 UART Recovery',target=dict(mcu='STM32F103C8T6',flashBytes=65536,ramBytes=20480,activationPin='PB12',activationLevel=0),source=dict(localSource='stm32/',repo='https://github.com/VV-Vovk/flasher-studio-bootloaders-public',ref=commit,license='Apache-2.0'),kind='stm32-uart-recovery',validation='ci-generated-not-hardware-tested',autoInstall=False,files=[meta('bootloader.bin',b,format='bin',offset=0x08000000,role='bootloader')],applicationLinker=meta('application.ld',ld),install=dict(transport='SWD',requiresFullEraseAndBackup=True,manualConfirmationRequired=True,preserveOptionBytes=True),update=dict(transport='uart',protocol='fs-stm32-uart-v1',baud=115200,tx='PA9',rx='PA10',applicationOffset=0x08004000,maxAppBytes=0xbc00,metadataOffset=0x0800fc00,singleSlot=True,physicalAccessOnly=True,requiresRelink=True))
    out=pathlib.Path(out);out.mkdir(parents=True,exist_ok=True)
    name=f'{ID}-{VERSION}.zip'
    entries={'bootloader.bin':b,'application.ld':ld,'LICENSE':(ROOT/'LICENSE').read_bytes(),'STM32-README.md':(ROOT/'stm32/README.md').read_bytes(),'manifest.json':encode(m)}
    with zipfile.ZipFile(out/name,'w',zipfile.ZIP_DEFLATED) as z:
        for n,data in sorted(entries.items()):
            info=zipfile.ZipInfo(n,date_time=(2020,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,data)
    catalog=dict(schemaVersion=1,version=VERSION,releaseState='candidate',packages=[dict(manifest=m,package=meta(name,(out/name).read_bytes()))],factoryReferences=[],upstreamReferences=[])
    (out/'catalog.json').write_bytes(encode(catalog))
    return catalog
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('binary');p.add_argument('out');p.add_argument('commit');a=p.parse_args();package(a.binary,a.out,a.commit)
