import hashlib
import hmac
import secrets

# PBKDF2 без сторонних зависимостей. Формат:
# pbkdf2_sha256$<iters>$<hex_salt>$<hex_hash>
_ALGO = 'pbkdf2_sha256'
_ITERS = 200_000
_SALT_BYTES = 16
_HASH_BYTES = 32


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac(
        'sha256', password.encode('utf-8'), salt, _ITERS,
        dklen=_HASH_BYTES,
    )
    return (
        f'{_ALGO}${_ITERS}${salt.hex()}${dk.hex()}'
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters_s, salt_hex, hash_hex = stored.split('$', 3)
    except ValueError:
        return False
    if algo != _ALGO:
        return False
    try:
        iters = int(iters_s)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except ValueError:
        return False
    dk = hashlib.pbkdf2_hmac(
        'sha256', password.encode('utf-8'),
        salt, iters, dklen=len(expected),
    )
    return hmac.compare_digest(dk, expected)
