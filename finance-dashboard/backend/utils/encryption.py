"""
backend/utils/encryption.py

Thin wrapper around Fernet symmetric encryption.

Why Fernet?
- AES-128-CBC + HMAC-SHA256 in one package — authenticated encryption.
- Tokens are URL-safe base64 strings, trivially storable in SQLite TEXT.
- Key rotation is possible: keep old key(s) for decryption, rotate to new one.

Usage:
    from backend.utils.encryption import encrypt_token, decrypt_token

    stored  = encrypt_token("access-sandbox-abc123")
    plain   = decrypt_token(stored)
"""

from cryptography.fernet import Fernet, InvalidToken

from backend.config import get_settings


def _get_fernet() -> Fernet:
    key = get_settings().encryption_key
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_token(plaintext: str) -> str:
    """
    Encrypt a Plaid access token and return a URL-safe base64 ciphertext string.
    Raises ValueError if encryption fails.
    """
    try:
        fernet = _get_fernet()
        return fernet.encrypt(plaintext.encode()).decode()
    except Exception as exc:
        raise ValueError(f"Encryption failed: {exc}") from exc


def decrypt_token(ciphertext: str) -> str:
    """
    Decrypt a previously encrypted access token.
    Raises ValueError if the ciphertext is invalid or tampered with.
    """
    try:
        fernet = _get_fernet()
        return fernet.decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise ValueError(
            "Failed to decrypt token — the ciphertext may be corrupted or the key is wrong."
        ) from exc
    except Exception as exc:
        raise ValueError(f"Decryption failed: {exc}") from exc
