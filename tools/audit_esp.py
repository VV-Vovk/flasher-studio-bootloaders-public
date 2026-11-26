"""Collect audit metadata only. Never copy firmware, archives or third-party source."""
import hashlib, json, os, pathlib, re, subprocess
P=pathlib.Path
root=P('/project')
idf=P(os.environ['IDF_PATH']).resolve()
out=root/'audit'
out.mkdir(exist_ok=True)
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*args):return subprocess.check_output(['git','-c','safe.directory=*','-C',str(idf),*args],text=True).strip()
def write(name,obj):(out/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
write('sdk.json',{'idfCommit':git('rev-parse','HEAD'),'idfDescription':git('describe','--tags','--always'),'submodules':git('submodule','status','--recursive').splitlines()})
# Both the application and the separate ESP-IDF bootloader must be audited.
maps=[root/'recovery/build/flasher_recovery.map',root/'recovery/build/bootloader/bootloader.map']
for p in maps:
    if not p.is_file():raise ValueError('Missing linker map '+str(p))
    text=p.read_text(errors='replace')
    # Linker archive/object references are evidence, not proof of complete dependency coverage.
    refs=sorted(set(re.findall(r'[^\s()]+\.a\([^()\n]+\)',text)))
    write(p.stem+'-archives.json',{'mapSha256':digest(p),'references':refs})
# Inventory exact notice files; hashes and paths only, no source or binaries.
notices=[]
for p in idf.rglob('*'):
    if p.is_file() and p.name.lower().startswith(('license','licence','copying','notice','copyright')):
        if '.git' not in p.parts:
            notices.append({'path':str(p.relative_to(idf)),'sha256':digest(p)})
write('notice-inventory.json',sorted(notices,key=lambda x:x['path']))
write('build-config.json',{'sdkconfigSha256':digest(root/'recovery/sdkconfig'),'partitionsSha256':digest(root/'recovery/partitions.csv'),'target':os.environ.get('TARGET'),'radio':os.environ.get('RADIO')})
