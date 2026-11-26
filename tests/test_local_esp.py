import json, tempfile, unittest, sys, struct, hashlib, zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import local_esp_package as p
from esp_profiles import profile,rows,prepare
class LocalEspTests(unittest.TestCase):
    def test_config(self):
        for hold in range(6):
            with tempfile.TemporaryDirectory() as tmp:
                r=Path(tmp);(r/'sdkconfig.ble').write_text('CONFIG_BT_ENABLED=y\n')
                q=profile('esp32c3','wifi-ble',4,4,hold);prepare(q,r)
                self.assertIn(f'CONFIG_BOOTLOADER_HOLD_TIME_GPIO={hold}\n',(r/'sdkconfig.transport').read_text())
                self.assertEqual(q['id'],'esp32c3-recovery-wifi-ble-4mb'+(f'-hold{hold}s' if hold!=3 else ''))
        for bad in [-1,6,True,0.5]:
            with self.assertRaises(ValueError):profile('esp32c3','wifi',4,4,bad)
    def test_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);b=root/'build';(b/'config').mkdir(parents=True);out=root/'out'
            (root/'notices').write_text('draft')
            (b/'config/sdkconfig.h').write_text('#define CONFIG_FS_WIFI 1\n#define CONFIG_FS_BLE 1\n#define CONFIG_BOOTLOADER_FACTORY_RESET 1\n#define CONFIG_BOOTLOADER_OTA_DATA_ERASE 1\n#define CONFIG_BOOTLOADER_NUM_PIN_FACTORY_RESET 5\n#define CONFIG_IDF_TARGET "esp32c3"\n#define CONFIG_ESPTOOLPY_FLASHSIZE_4MB 1\n#define CONFIG_BOOTLOADER_FACTORY_RESET_PIN_LOW 1\n#define CONFIG_BOOTLOADER_HOLD_TIME_GPIO 0\n')
            q=profile('esp32c3','wifi-ble',4,5,0)
            raw=b''.join(struct.pack('<HBBII16sI',0x50aa,t,st,a,n,name.encode(),0) for name,t,st,a,n in rows(q))
            table=raw+b'\xeb\xeb'+b'\xff'*14+hashlib.md5(raw).digest()+b'\xff'*(0xc00-len(raw)-32)
            files={'0x0':'bootloader.bin','0x8000':'partition-table.bin','0xf000':'ota_data_initial.bin','0x20000':'flasher_recovery.bin'}
            for f in files.values():(b/f).write_bytes(table if f=='partition-table.bin' else b'abc')
            (b/'flasher_args.json').write_text(json.dumps({'flash_files':files}))
            kw=dict(out=out,notices=root/'notices',source_ref='a'*40)
            z=p.esp(b,'esp32c3','wifi-ble',4,5,0,**kw)
            with zipfile.ZipFile(z) as f:
                m=json.loads(f.read('manifest.json'));self.assertEqual(m['target']['holdSeconds'],0);self.assertEqual(m['target']['activationGpio'],5);self.assertEqual(m['source']['redistributionReview'],'HOLD');self.assertEqual(f.read('THIRD_PARTY_NOTICES.txt'),b'draft')
            c=json.loads((out/'catalog.json').read_text());self.assertEqual(c['packages'][0]['package']['sha256'],hashlib.sha256(z.read_bytes()).hexdigest())
            with self.assertRaises(ValueError):p.esp(b,'esp32c3','wifi-ble',4,5,3,**kw)
            del files['0xf000'];(b/'flasher_args.json').write_text(json.dumps({'flash_files':files}))
            with self.assertRaises(ValueError):p.esp(b,'esp32c3','wifi-ble',4,5,0,**kw)
