import tempfile
import unittest
from pathlib import Path
from delivery_check import ROOT_FILES, REQUIRED_CHECKS, inventory, record, verify

class DeliveryGuards(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.payload=self.root/'payload'
        self.evidence=self.root/'evidence'
        for name in ROOT_FILES|{'runtime/python.exe','app/pyproject.toml'}:
            p=self.payload/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_text('synthetic')
        self.smoke={'status':'passed','checks':sorted(REQUIRED_CHECKS)}

    def test_matching_receipt(self):
        record(self.payload,self.evidence,self.smoke)
        self.assertTrue(verify(self.payload,self.evidence))

    def test_modified_payload_rejected(self):
        record(self.payload,self.evidence,self.smoke)
        (self.payload/'launch.py').write_text('changed')
        with self.assertRaises(ValueError): verify(self.payload,self.evidence)

    def test_unexpected_data_rejected(self):
        p=self.payload/'runtime/auth/users.json'; p.parent.mkdir(); p.write_text('{}')
        with self.assertRaises(ValueError): record(self.payload,self.evidence,self.smoke)

    def test_incomplete_smoke_rejected(self):
        with self.assertRaises(ValueError): record(self.payload,self.evidence,{'status':'passed','checks':[]})

    def test_missing_required_file_rejected(self):
        (self.payload/'runtime/python.exe').unlink()
        with self.assertRaises(ValueError): record(self.payload,self.evidence,self.smoke)

    def test_only_product_logo_is_allowlisted_as_image_asset(self):
        for name in ('app/gui/static/sayelf-logo.png','app/gui/static/sayelf-logo.ico'):
            p=self.payload/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(b'brand')
        self.assertTrue(inventory(self.payload))
        bad=self.payload/'app/gui/static/unreviewed.svg'; bad.write_text('<svg/>')
        with self.assertRaises(ValueError): inventory(self.payload)
        bad.unlink()
        out_of_scope=self.payload/'app/core/unreviewed.png'; out_of_scope.parent.mkdir(parents=True,exist_ok=True)
        out_of_scope.write_bytes(b'unknown image')
        with self.assertRaises(ValueError): inventory(self.payload)

if __name__=='__main__': unittest.main()
