import struct
import tempfile
import unittest
from pathlib import Path
from Scripts.import_assets import pack_assets
from Scripts.play_lan import validate_archive

class AssetImportTests(unittest.TestCase):
    def test_round_trip_payloads_and_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);assets=root/'Assets'
            expected={'CLAW/IMAGES/FRAME001.PID':b'sprite-data','LEVEL1/WORLDS/WORLD.WWD':b'world-data','STATES/MENU/SCREENS/MENU.PCX':b'menu-data'}
            for name,data in expected.items():
                p=assets/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
            output=root/'CLAW.REZ'
            self.assertEqual(pack_assets(assets,output),3)
            validate_archive(output)
            raw=output.read_bytes();offset,size=struct.unpack_from('<II',raw,131)
            restored={}
            def read_directory(offset,size,prefix=''):
                end=offset+size
                while offset<end:
                    flag,data_offset,data_size=struct.unpack_from('<III',raw,offset)
                    if flag:
                        finish=raw.index(0,offset+16)
                        name=raw[offset+16:finish].decode()
                        read_directory(data_offset,data_size,prefix+name+'/')
                        offset=finish+1
                    else:
                        finish=raw.index(0,offset+28)
                        name=raw[offset+28:finish].decode()
                        extension=raw[offset+20:offset+24].split(b'\0')[0][::-1].decode()
                        restored[(prefix+name+'.'+extension).upper()]=raw[data_offset:data_offset+data_size]
                        offset=finish+2
            read_directory(offset,size)
            self.assertEqual(restored,expected)

    def test_missing_files_does_not_replace_existing_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);assets=root/'Assets';assets.mkdir()
            output=root/'CLAW.REZ';output.write_bytes(b'existing')
            with self.assertRaisesRegex(ValueError,'Missing original game assets'):
                pack_assets(assets,output)
            self.assertEqual(output.read_bytes(),b'existing')
