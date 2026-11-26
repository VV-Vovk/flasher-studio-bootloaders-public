"""Collect verbatim license/notice text and focused linker evidence; never release firmware.

The report is an inventory for manual review. Neither a known SPDX label nor a
successful build authorizes redistribution.
"""
import hashlib, json, os, pathlib, re, shutil, subprocess
P=pathlib.Path
ROOT=P('/project')
IDF=P(os.environ['IDF_PATH']).resolve()
OUT=ROOT/'audit'
SDK_COMMIT='f5c3654a1c2d2a01f7f67def7a0dc48e691f63c0'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name,obj):(OUT/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def output(*args):return subprocess.check_output(args,text=True).strip()
def notices(root,label):
    records=[]
    for p in sorted(root.rglob('*')):
        if not p.is_file() or '.git' in p.parts or not p.name.lower().startswith(('license','licence','copying','notice','copyright')):continue
        rel=p.relative_to(root)
        # Do not follow symlinks outside the intended SDK/toolchain.
        if not p.resolve().is_relative_to(root):continue
        if p.stat().st_size>1024*1024:records.append({'path':str(rel),'status':'oversize-manual-review'});continue
        b=p.read_bytes()
        if b'\x00' in b:records.append({'path':str(rel),'status':'non-text-manual-review'});continue
        dest=OUT/'notices'/label/rel.parent/(rel.name+'.txt')
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(b)
        records.append({'path':str(rel),'notice':str(dest.relative_to(OUT)),'size':len(b),'sha256':hashlib.sha256(b).hexdigest()})
    return records
def active_refs(path):
    s=path.read_text(errors='replace')
    if 'Linker script and memory map' not in s:raise ValueError('missing linker memory map')
    active=s.split('Linker script and memory map',1)[1].split('Cross Reference Table',1)[0]
    # Conservative list: objects mentioned in the active portion, not a proof
    # every object was emitted. Exclude the discarded input sections above.
    refs=sorted(set(re.findall(r'[^\s()]+\.a\([^()\n]+\)',active)))
    if not refs:raise ValueError('empty active map '+str(path))
    archives=sorted(set(x.split('(',1)[0] for x in refs))
    result=[]
    for name in archives:
        p=P(name)
        if not p.is_absolute():p=path.parent/p
        result.append({'archive':name,'sha256':sha(p) if p.is_file() else None,'objects':[x.split('(',1)[1][:-1] for x in refs if x.startswith(name+'(')]})
    return result
def main():
    actual=output('git','-c','safe.directory=*','-C',str(IDF),'rev-parse','HEAD')
    if actual!=SDK_COMMIT:raise ValueError('Unexpected SDK revision')
    gcc=shutil.which('riscv32-esp-elf-gcc')
    if not gcc:raise ValueError('Compiler unavailable')
    toolchain=P(gcc).resolve().parent.parent
    sdk_notices=notices(IDF,'sdk')
    runtime_notices=notices(toolchain,'toolchain')
    if not sdk_notices:raise ValueError('No SDK notice inventory')
    required=['components/esp_wifi/lib/LICENSE','components/bt/controller/lib_esp32c3_family/LICENSE','components/esp_phy/lib/LICENSE','components/esp_coex/lib/LICENSE']
    found={x['path'] for x in sdk_notices if 'notice' in x}
    if not all(x in found for x in required):raise ValueError('Missing radio library license')
    save('notice-text-index.json',{'sdkCommit':actual,'sdk':sdk_notices,'toolchain':runtime_notices,'toolchainReviewRequired':True,'compilerVersion':output(gcc,'--version'),'runtimeNoticeCount':sum('notice' in x for x in runtime_notices)})
    maps=[ROOT/'recovery/build/flasher_recovery.map',ROOT/'recovery/build/bootloader/bootloader.map']
    for p in maps:save(p.stem+'-active-archives.json',{'mapSha256':sha(p),'archives':active_refs(p)})
    s=(OUT/'application.spdx').read_text()
    unknown=[];name=''
    for line in s.splitlines():
        if line.startswith('PackageName: '):name=line[13:]
        if line=='PackageLicenseConcluded: NOASSERTION':unknown.append(name)
    save('review-hold.json',{'distributionApproved':False,'unknownSpdxPackages':unknown,'notes':['Resolve all linked components and compiler-runtime conditions.','Notices inventory is not a final distribution bundle.','Manual review and hardware validation required.']})
    print('License evidence only:',len(sdk_notices),'SDK notices;',len(runtime_notices),'toolchain notices;',len(unknown),'unresolved SPDX records. Redistribution remains HOLD.')
if __name__=='__main__':main()
