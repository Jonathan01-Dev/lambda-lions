from Crypto.Cipher import AES
import os


class Session:
    def __init__(self, key: bytes):
        """Initialize session with a 32-byte key."""
        self.key = key

    def encrypt(self, plaintext: bytes) -> bytes:
        """Encrypt plaintext using AES-256-GCM. Returns nonce + tag + ciphertext."""
        cipher = AES.new(self.key, AES.MODE_GCM)
        ciphertext, tag = cipher.encrypt_and_digest(plaintext)
        # AES GCM default nonce is 16 bytes in some libs, but 12 is recommended
        # pycryptodome uses 16 by default if not specified, let's keep it consistent
        return cipher.nonce + tag + ciphertext

    def decrypt(self, data: bytes) -> bytes:
        """Decrypt data. Expects nonce(16) + tag(16) + ciphertext."""
        if len(data) < 32:
            raise ValueError("Data too short to decrypt")
            
        nonce = data[:16]
        tag = data[16:32]
        ciphertext = data[32:]
        cipher = AES.new(self.key, AES.MODE_GCM, nonce=nonce)
        return cipher.decrypt_and_verify(ciphertext, tag)
