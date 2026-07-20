from __future__ import annotations

import bcrypt

from shared.config import get_config


def hash_password(plaintext: str) -> str:
    rounds = get_config().backend.bcrypt_rounds
    return bcrypt.hashpw(plaintext.encode("utf-8"), bcrypt.gensalt(rounds=rounds)).decode("utf-8")


def verify_password(plaintext: str, hashed: str) -> bool:
    return bcrypt.checkpw(plaintext.encode("utf-8"), hashed.encode("utf-8"))
