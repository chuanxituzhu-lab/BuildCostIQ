from __future__ import annotations

import hashlib


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def verify_bytes(content: bytes, expected_hash: str) -> bool:
    return sha256_bytes(content) == expected_hash

