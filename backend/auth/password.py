from __future__ import annotations

import bcrypt

from shared.config import get_config

# bcrypt hard-limits the input to 72 bytes and (>=5.0) RAISES on longer input
# instead of truncating. Passwords up to 128 chars pass schema validation, and
# multi-byte (e.g. Chinese) passwords exceed 72 bytes well under 72 chars, so we
# truncate to 72 bytes here — symmetrically in hash and verify — to avoid a 500.
_BCRYPT_MAX_BYTES = 72


def _prepare(plaintext: str) -> bytes:
    return plaintext.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(plaintext: str) -> str:
    rounds = get_config().backend.bcrypt_rounds
    return bcrypt.hashpw(_prepare(plaintext), bcrypt.gensalt(rounds=rounds)).decode("utf-8")


def verify_password(plaintext: str, hashed: str) -> bool:
    return bcrypt.checkpw(_prepare(plaintext), hashed.encode("utf-8"))
