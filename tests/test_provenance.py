import tempfile
import unittest
from pathlib import Path

from adapters import ImmutableSourceStore
from core import Evidence, sha256_bytes


class ProvenanceTests(unittest.TestCase):
    def test_ingest_is_content_addressed_and_verifiable(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ImmutableSourceStore(Path(directory))
            source = store.ingest("contract.txt", b"sanitized contract", "text/plain")
            self.assertEqual(source.content_hash, sha256_bytes(b"sanitized contract"))
            self.assertEqual(store.read(source), b"sanitized contract")

    def test_evidence_payload_is_immutable(self):
        evidence = Evidence("project", "source", "change", {"amount": 100})
        with self.assertRaises(TypeError):
            evidence.payload["amount"] = 200


if __name__ == "__main__":
    unittest.main()

