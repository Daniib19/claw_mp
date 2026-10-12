import struct
import tempfile
import unittest
from pathlib import Path
from Scripts.play_lan import validate_archive

class ArchiveValidationTests(unittest.TestCase):
    def test_empty_archive_matches_supplied_attachment(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'CLAW.REZ'
            header=bytearray(168); struct.pack_into('<II',header,131,168,0)
            path.write_bytes(header)
            with self.assertRaisesRegex(ValueError,'empty archive'): validate_archive(path)

    def test_truncated_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'CLAW.REZ'
            header=bytearray(168); struct.pack_into('<II',header,131,168,100)
            path.write_bytes(header)
            with self.assertRaisesRegex(ValueError,'incomplete or invalid'): validate_archive(path)

    def test_complete_directory_size(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'CLAW.REZ'
            header=bytearray(268); struct.pack_into('<II',header,131,168,100)
            path.write_bytes(header)
            validate_archive(path)
