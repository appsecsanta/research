import os
import base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidPadding


class DataEncryptor:
    """
    A class to encrypt and decrypt data using AES-256-CBC symmetric encryption.

    The key must be a 32-byte (256-bit) key, provided as a URL-safe
    base64 encoded string. Use the `generate_key` static method to create
    a suitable key.

    The encrypted output is a URL-safe base64 encoded string containing the
    initialization vector (IV) and the ciphertext, suitable for storage or
    transmission.
    """

    _BLOCK_SIZE_BITS = 128
    _KEY_SIZE_BYTES = 32  # 256 bits

    def __init__(self, key: str):
        """
        Initializes the encryptor with a URL-safe base64 encoded key.

        The key should be securely stored and managed, for example, in an
        environment variable or a secrets management system.

        Args:
            key: A URL-safe base64 encoded string representing the 32-byte key.

        Raises:
            ValueError: If the decoded key is not 32 bytes long or is invalid.
        """
        if not isinstance(key, str) or not key:
            raise ValueError("Key must be a non-empty string.")

        try:
            self._key = base64.urlsafe_b64decode(key)
            if len(self._key) != self._KEY_SIZE_BYTES:
                raise ValueError(
                    f"Invalid key size. Key must be {self._KEY_SIZE_BYTES} bytes long."
                )
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid base64-encoded key: {e}") from e

        self._backend = default_backend()

    @staticmethod
    def generate_key() -> str:
        """
        Generates a cryptographically secure 32-byte key and returns it
        as a URL-safe base64 encoded string.

        This method should be used once to generate a key, which is then
        stored securely.

        Returns:
            A URL-safe base64 encoded key string.
        """
        key = os.urandom(DataEncryptor._KEY_SIZE_BYTES)
        return base64.urlsafe_b64encode(key).decode("utf-8")

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypts a plaintext string.

        Args:
            plaintext: The string data to encrypt.

        Returns:
            A URL-safe base64 encoded string containing the IV and ciphertext.
        
        Raises:
            TypeError: If plaintext is not a string.
        """
        if not isinstance(plaintext, str):
            raise TypeError("Plaintext must be a string.")

        plaintext_bytes = plaintext.encode("utf-8")
        iv = os.urandom(self._BLOCK_SIZE_BITS // 8)

        padder = padding.PKCS7(self._BLOCK_SIZE_BITS).padder()
        padded_data = padder.update(plaintext_bytes) + padder.finalize()

        cipher = Cipher(
            algorithms.AES(self._key), modes.CBC(iv), backend=self._backend
        )
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(padded_data) + encryptor.finalize()

        token = iv + ciphertext
        return base64.urlsafe_b64encode(token).decode("utf-8")

    def decrypt(self, token: str) -> str:
        """
        Decrypts a token back to the original plaintext string.

        Args:
            token: The URL-safe base64 encoded string from the encrypt method.

        Returns:
            The original decrypted string.

        Raises:
            ValueError: If the token is malformed or decryption fails due to an
                        incorrect key, corrupted data, or invalid padding.
            TypeError: If the token is not a string.
        """
        if not isinstance(token, str):
            raise TypeError("Token must be a string.")

        try:
            encrypted_data = base64.urlsafe_b64decode(token)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid base64-encoded token: {e}") from e

        iv_size = self._BLOCK_SIZE_BITS // 8
        if len(encrypted_data) < iv_size:
            raise ValueError("Invalid token: too short to contain IV.")

        iv = encrypted_data[:iv_size]
        ciphertext = encrypted_data[iv_size:]

        cipher = Cipher(
            algorithms.AES(self._key), modes.CBC(iv), backend=self._backend
        )
        decryptor = cipher.decryptor()

        try:
            padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()
            unpadder = padding.PKCS7(self._BLOCK_SIZE_BITS).unpadder()
            plaintext_bytes = unpadder.update(padded_plaintext) + unpadder.finalize()
        except (ValueError, InvalidPadding) as e:
            raise ValueError(
                "Decryption failed. The token may be invalid or the key incorrect."
            ) from e

        return plaintext_bytes.decode("utf-8")


if __name__ == "__main__":
    # Example Usage:
    # In a real application, the key would be loaded from a secure source,
    # such as an environment variable or a secret manager.
    #
    # 1. Generate a key ONCE and store it securely.
    #    DO NOT generate a new key for each encryption.
    # encryption_key = DataEncryptor.generate_key()
    # print(f"Generated Encryption Key: {encryption_key}")
    # print("Store this key securely!")

    # 2. Use the stored key to initialize the encryptor.
    #    (Using a pre-generated key for this example)
    ENCRYPTION_KEY = "R6xVpBqH_Ld2jC8fE4kZgA7sW3uN0xI5yVb9pQ2rE1o="
    encryptor = DataEncryptor(ENCRYPTION_KEY)

    # 3. Encrypt and decrypt data.
    sensitive_data = "123-45-6789"
    print(f"Original data: {sensitive_data}")

    encrypted_token = encryptor.encrypt(sensitive_data)
    print(f"Encrypted token: {encrypted_token}")

    decrypted_data = encryptor.decrypt(encrypted_token)
    print(f"Decrypted data: {decrypted_data}")

    assert sensitive_data == decrypted_data
    print("\nEncryption and decryption successful.")

    # Example of a decryption failure
    try:
        invalid_token = "invalid" + encrypted_token[7:]
        encryptor.decrypt(invalid_token)
    except ValueError as e:
        print(f"\nCaught expected error for invalid token: {e}")

    try:
        wrong_key = DataEncryptor.generate_key()
        wrong_encryptor = DataEncryptor(wrong_key)
        wrong_encryptor.decrypt(encrypted_token)
    except ValueError as e:
        print(f"Caught expected error for wrong key: {e}")
