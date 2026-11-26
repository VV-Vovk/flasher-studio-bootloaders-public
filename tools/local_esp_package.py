"""Package a locally built ESP32-C3 candidate. No release or network upload."""
import argparse, hashlib, json, pathlib, re, shutil, tempfile, zipfile, struct
from esp_profiles import profile, rows, csv_text
P=pathlib.Path
ROOT=P(__file__).resolve().parents[1]
VERSION='0.2.3'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x): p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def filemeta(p,**kwargs): return {'file':p.name,'size':p.stat().st_size,'sha256':sha(p),**kwargs}
def base(pid,name,target,source,kind):
    return {'schemaVersion':1,'id':pid,'version':VERSION,'name':name,'target':target,'source':source,'kind':kind,'validation':'local-build-not-hardware-tested','autoInstall':False,'files':[]}
def finalize(d,m,out):
    dump(d/'manifest.json',m); out.mkdir(parents=True,exist_ok=True)
    z=out/f"{m['id']}-{VERSION}.zip"
    with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED) as f:
        for p in sorted(d.iterdir()):
            if p.is_file(): f.write(p,p.name)
    return z

def verify_partition_bin(data,p):
    actual=[]; pos=0; found_md5=False
    while pos+32<=len(data):
        entry=data[pos:pos+32]; magic=int.from_bytes(entry[:2],'little')
        if magic==0xebeb:
            if entry[2:16]!=b'\xff'*14 or entry[16:]!=hashlib.md5(data[:pos]).digest():raise ValueError('partition MD5 mismatch')
            found_md5=True;pos+=32;break
        if magic!=0x50aa:raise ValueError('bad partition entry')
        _,t,st,addr,size,name,flags=struct.unpack('<HBBII16sI',entry)
        if flags:raise ValueError('unexpected partition flags')
        actual.append((name.split(b'\0',1)[0].decode(),t,st,addr,size));pos+=32
    if not found_md5 or any(x!=255 for x in data[pos:]) or actual!=rows(p):raise ValueError('partition table does not match expected layout')

def esp(build,target,radio,flash=4,gpio=None,hold=3,*,out=None,notices=None,source_ref=None):
    if target!='esp32c3':raise ValueError('Local build currently restricted to ESP32-C3')
    if notices is None or not P(notices).is_file():raise ValueError('Missing draft third-party notices')
    if not re.fullmatch('[a-f0-9]{40}',source_ref or ''):raise ValueError('Expected source commit')
    p=profile(target,radio,flash,gpio,hold);build=P(build).resolve();args=json.loads((build/'flasher_args.json').read_text()); files=args['flash_files']; out=P(out or ROOT/'out').resolve()
    sdk=(build/'config'/'sdkconfig.h').read_text()
    def has(key,val='1'):return bool(re.search(r'^#define '+re.escape(key)+r' '+re.escape(str(val))+r'\s*$',sdk,re.M))
    for key,expected in [('CONFIG_FS_WIFI','wifi' in radio),('CONFIG_FS_BLE','ble' in radio)]:
        if has(key)!=expected: raise ValueError(f'wrong radio config: {key}')
    pin=p['gpio']; limit=flash*1024*1024
    if not all((has('CONFIG_IDF_TARGET',f'"{target}"'),has(f'CONFIG_ESPTOOLPY_FLASHSIZE_{flash}MB'),has('CONFIG_BOOTLOADER_FACTORY_RESET'),has('CONFIG_BOOTLOADER_OTA_DATA_ERASE'),has('CONFIG_BOOTLOADER_NUM_PIN_FACTORY_RESET',pin),has('CONFIG_BOOTLOADER_FACTORY_RESET_PIN_LOW'),has('CONFIG_BOOTLOADER_HOLD_TIME_GPIO',hold))):raise ValueError('wrong target, flash or recovery boot config')
    with tempfile.TemporaryDirectory() as tmp:
        d=P(tmp);m=base(p['id'],f'{target.upper()} Recovery {radio} {flash} MiB'+(f' · hold {hold}s' if hold!=3 else ''),{'mcu':target,'flashBytes':limit,'activationGpio':pin,'activationLevel':0,'holdSeconds':hold},{'repo':'espressif/esp-idf','ref':'v5.4.2','localSource':'recovery/','sourceRepo':'https://github.com/VV-Vovk/flasher-studio-bootloaders-public','sourceCommit':source_ref,'localBuild':True,'redistributionReview':'HOLD','sdkImage':'espressif/idf@sha256:4317595a911886e04cbc6d731315d5fc2918e510b6733fc7d03381ab2d270082'},'esp-recovery')
        ranges=[];got=set()
        for addr,path in files.items():
            offset=int(addr,0);src=(build/path).resolve()
            if not src.is_relative_to(build) or not src.is_file():raise ValueError('bad flash path')
            role={'flasher_recovery.bin':'recovery','bootloader.bin':'bootloader','partition-table.bin':'partition-table','ota_data_initial.bin':'ota-data'}.get(src.name)
            if not role:raise ValueError(f'unexpected flash component {src.name}')
            end=offset+src.stat().st_size
            if offset<0 or end>limit or end<=offset or any(offset<b and a<end for a,b in ranges):raise ValueError('overlapping/invalid flash segments')
            bounds={'bootloader':(0x1000 if target in ('esp32','esp32s2') else 0,0x8000),'partition-table':(0x8000,0x9000),'ota-data':(0xf000,0x11000),'recovery':(0x20000,0x1a0000)}[role]
            if offset!=bounds[0] or end>bounds[1] or role in got:raise ValueError('wrong partition layout or duplicate role')
            if role=='partition-table':verify_partition_bin(src.read_bytes(),p)
            got.add(role);ranges.append((offset,end));dst=d/src.name;shutil.copyfile(src,dst);m['files'].append(filemeta(dst,format='bin',offset=offset,role=role))
        if got!={'bootloader','partition-table','ota-data','recovery'}:raise ValueError('missing image component')
        (d/'partitions.csv').write_text(csv_text(p));m.update({'partitionTable':filemeta(d/'partitions.csv'),'install':{'transport':'espressif-serial','requiresFlashBackup':True,'requiresEraseAndConfirmation':True,'secureBootOrEncryptionSupported':False,'gpioBoardValidationRequired':True},'update':{'transports':[x for x in ['wifi','ble'] if x in radio],'protocolVersion':1,'maxAppBytes':p['slot'],'appOnly':True,'requiresMatchingPartitionLayout':True,'slots':p['slots'],'credentials':'per-device-persistent-nvs','initialProvisioning':'physical-serial-console'},'flashSettings':args.get('flash_settings',{})});shutil.copyfile(ROOT/'LICENSE',d/'LICENSE');shutil.copyfile(notices,d/'THIRD_PARTY_NOTICES.txt');m['notices']=filemeta(d/'THIRD_PARTY_NOTICES.txt');z=finalize(d,m,out);dump(out/'catalog.json',{'schemaVersion':1,'version':VERSION,'releaseState':'local-only-review-hold','packages':[{'manifest':m,'package':filemeta(z)}]});return z


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('build');a.add_argument('radio');a.add_argument('flash',type=int);a.add_argument('gpio',type=int);a.add_argument('hold',type=int);a.add_argument('out');a.add_argument('notices');a.add_argument('source_ref');v=a.parse_args();print(esp(v.build,'esp32c3',v.radio,v.flash,v.gpio,v.hold,out=v.out,notices=v.notices,source_ref=v.source_ref))
