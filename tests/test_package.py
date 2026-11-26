import hashlib, pathlib, struct, tempfile, unittest, zipfile
from tools.package_stm32 import package, ROOT
class PackageTest(unittest.TestCase):
    def test_exact_package(self):
        with tempfile.TemporaryDirectory() as t:
            d=pathlib.Path(t);b=d/'input.bin';b.write_bytes(struct.pack('<II',0x20005000,0x08000009)+b'hello')
            e=package(b,d/'out','a'*40)['packages'][0];p=d/'out'/e['package']['file']
            self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),e['package']['sha256'])
            self.assertFalse(e['manifest']['autoInstall'])
            self.assertEqual(e['manifest']['update']['maxAppBytes'],47*1024)
            with zipfile.ZipFile(p) as z:
                self.assertEqual(z.read('LICENSE'),(ROOT/'LICENSE').read_bytes())
                self.assertEqual(z.read('bootloader.bin'),b.read_bytes())
            with self.assertRaises(ValueError): package(b,d/'out','main')
            b.write_bytes(struct.pack('<II',0x20005000,0x08004009)+b'hello')
            with self.assertRaises(ValueError): package(b,d/'out','a'*40)
if __name__=='__main__': unittest.main()
