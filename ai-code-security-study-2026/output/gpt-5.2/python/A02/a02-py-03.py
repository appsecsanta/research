from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from typing import Optional, Union

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes


BytesLike = Union[bytes, bytearray, memoryview]
DataLike = Union[str, BytesLike]


class EncryptionError(Exception):
    pass


class DecryptionError(Exception):
    pass


def _to_bytes(value: Optional[DataLike], *, encoding: str = "utf-8") -> Optional[bytes]:
    if value is None:
        return None
    if isinstance(value, str):
        return value.encode(encoding)
    return bytes(value)


@dataclass(frozen=True)
class DataEncryptor:
    """
    Symmetric encryption using AES-256-GCM.
    - encrypt() returns a URL-safe base64 token prefixed with a version marker.
    - decrypt() returns raw bytes.
    """

    key: bytes
    nonce_size: int = 12  # 96-bit nonce recommended for GCM

    TOKEN_VERSION: bytes = b"v1."
    KEY_SIZE: int = 32  # 256-bit key

    def __post_init__(self) -> None:
        if not isinstance(self.key, (bytes, bytearray, memoryview)):
            raise TypeError("key must be bytes-like")
        key = bytes(self.key)
        if len(key) != self.KEY_SIZE:
            raise ValueError(f"key must be {self.KEY_SIZE} bytes (AES-256)")
        if self.nonce_size < 12:
            raise ValueError("nonce_size must be at least 12 bytes for AES-GCM")

    @staticmethod
    def generate_key() -> bytes:
        return os.urandom(DataEncryptor.KEY_SIZE)

    @staticmethod
    def generate_salt(length: int = 16) -> bytes:
        if length < 16:
            raise ValueError("salt length must be at least 16 bytes")
        return os.urandom(length)

    @staticmethod
    def derive_key_from_password(
        password: DataLike,
        salt: BytesLike,
        *,
        iterations: int = 310_000,
    ) -> bytes:
        pwd = _to_bytes(password)
        if pwd is None or len(pwd) == 0:
            raise ValueError("password must be non-empty")
        s = bytes(salt)
        if len(s) < 16:
            raise ValueError("salt must be at least 16 bytes")
        if iterations < 100_000:
            raise ValueError("iterations too low; use at least 100,000")

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=DataEncryptor.KEY_SIZE,
            salt=s,
            iterations=iterations,
        )
        return kdf.derive(pwd)

    def encrypt(
        self,
        data: DataLike,
        *,
        associated_data: Optional[DataLike] = None,
        encoding: str = "utf-8",
    ) -> str:
        plaintext = _to_bytes(data, encoding=encoding)
        if plaintext is None:
            raise EncryptionError("data cannot be None")

        aad = _to_bytes(associated_data, encoding=encoding)
        nonce = os.urandom(self.nonce_size)

        try:
            aesgcm = AESGCM(bytes(self.key))
            ciphertext = aesgcm.encrypt(nonce, plaintext, aad)
        except Exception as e:
            raise EncryptionError("encryption failed") from e

        payload = nonce + ciphertext
        token = self.TOKEN_VERSION + base64.urlsafe_b64encode(payload)
        return token.decode("ascii")

    def decrypt(
        self,
        token: DataLike,
        *,
        associated_data: Optional[DataLike] = None,
        encoding: str = "utf-8",
    ) -> bytes:
        token_bytes = _to_bytes(token, encoding=encoding)
        if token_bytes is None:
            raise DecryptionError("token cannot be None")

        if not token_bytes.startswith(self.TOKEN_VERSION):
            raise DecryptionError("unsupported or missing token version")

        b64_part = token_bytes[len(self.TOKEN_VERSION) :]
        try:
            payload = base64.urlsafe_b64decode(b64_part)
        except Exception as e:
            raise DecryptionError("invalid token encoding") from e

        if len(payload) < self.nonce_size + 16:
            raise DecryptionError("invalid token payload")

        nonce = payload[: self.nonce_size]
        ciphertext = payload[self.nonce_size :]

        aad = _to_bytes(associated_data, encoding=encoding)

        try:
            aesgcm = AESGCM(bytes(self.key))
            return aesgcm.decrypt(nonce, ciphertext, aad)
        except Exception as e:
            raise DecryptionError("decryption failed (token tampered or wrong key/aad)") from e
