# crypto.py - HELA SMART SACCO v3.0
# Enterprise-grade encryption and cryptography manager

import os
import base64
import hashlib
import hmac

from kivy.logger import Logger

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False
    print("WARNING: cryptography not installed. Using fallback encryption.")

from typing import Optional, Tuple


class AdvancedCryptoManager:
    """
    Enterprise-grade encryption with multiple algorithms:
    - AES-256-GCM for field encryption (authenticated encryption)
    - RSA-4096 for key exchange
    - PBKDF2-HMAC-SHA256 for key derivation
    - HMAC-SHA256 for integrity verification
    """

    VERSION = 3
    KEY_ITERATIONS = 600000

    def __init__(self, master_secret: str, device_id: str):
        self.master_secret = master_secret
        self.device_id = device_id
        self._init_keys()

    def _init_keys(self):
        """Initialize all cryptographic keys."""
        salt = hashlib.sha256(self.device_id.encode()).digest()[:32]
        if _CRYPTO_AVAILABLE:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=self.KEY_ITERATIONS,
                backend=default_backend()
            )
            self._master_key = kdf.derive(self.master_secret.encode())
            fernet_key = base64.urlsafe_b64encode(self._master_key)
            self._fernet = Fernet(fernet_key)
            self._aes_key = self._master_key[:32]
            self._private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=4096,
                backend=default_backend()
            )
            self._public_key = self._private_key.public_key()
        else:
            # Fallback key derivation without cryptography library
            self._master_key = hashlib.pbkdf2_hmac(
                'sha256', self.master_secret.encode(), salt, 100000, dklen=32
            )
            self._fernet = None
            self._aes_key = self._master_key[:32]
            self._private_key = None
            self._public_key = None

        Logger.info(f"CryptoManager: Initialized v{self.VERSION} with AES-256-GCM")

    def encrypt_field(self, plaintext: str) -> str:
        """Encrypt a field using AES-256-GCM with authentication."""
        if not plaintext:
            return plaintext

        if not _CRYPTO_AVAILABLE:
            return self._fallback_encrypt(plaintext)

        try:
            nonce = os.urandom(12)
            aesgcm = AESGCM(self._aes_key)
            associated_data = self.device_id.encode()
            ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), associated_data)
            encrypted = bytes([self.VERSION]) + nonce + ciphertext
            return f"A:{base64.urlsafe_b64encode(encrypted).decode()}"
        except Exception as e:
            Logger.error(f"Encryption failed: {e}")
            return self._fallback_encrypt(plaintext)

    def decrypt_field(self, ciphertext: str) -> Optional[str]:
        """Decrypt a field with automatic algorithm detection."""
        if not ciphertext or not isinstance(ciphertext, str):
            return ciphertext

        try:
            if ciphertext.startswith("A:"):
                return self._decrypt_aes(ciphertext[2:])
            elif ciphertext.startswith("F:"):
                return self._decrypt_fernet(ciphertext[2:])
            elif ciphertext.startswith("X:"):
                return self._decrypt_fallback(ciphertext[2:])
            else:
                return self._decrypt_fernet(ciphertext)
        except Exception as e:
            Logger.error(f"Decryption failed: {e}")
            return None

    def _decrypt_aes(self, b64_data: str) -> str:
        if not _CRYPTO_AVAILABLE:
            raise ValueError("cryptography library required for AES decryption")
        data = base64.urlsafe_b64decode(b64_data)
        nonce = data[1:13]
        ciphertext = data[13:]
        aesgcm = AESGCM(self._aes_key)
        return aesgcm.decrypt(nonce, ciphertext, self.device_id.encode()).decode()

    def _decrypt_fernet(self, b64_data: str) -> str:
        if not self._fernet:
            raise ValueError("Fernet not available")
        return self._fernet.decrypt(b64_data.encode()).decode()

    def _fallback_encrypt(self, plaintext: str) -> str:
        """XOR-based fallback with HMAC (NOT for production use)."""
        data = plaintext.encode()
        key = self._master_key
        encrypted = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
        mac = hmac.new(key, encrypted, hashlib.sha256).digest()[:8]
        result = base64.urlsafe_b64encode(mac + encrypted).decode()
        return f"X:{result}"

    def _decrypt_fallback(self, b64_data: str) -> str:
        data = base64.urlsafe_b64decode(b64_data)
        mac = data[:8]
        encrypted = data[8:]
        expected_mac = hmac.new(self._master_key, encrypted, hashlib.sha256).digest()[:8]
        if not hmac.compare_digest(mac, expected_mac):
            raise ValueError("MAC verification failed")
        key = self._master_key
        decrypted = bytes(b ^ key[i % len(key)] for i, b in enumerate(encrypted))
        return decrypted.decode()

    def hash_password(self, password: str) -> Tuple[str, str, int]:
        """Hash a password using PBKDF2. Returns (salt_b64, hash_b64, iterations)."""
        salt = os.urandom(32)
        password_hash = hashlib.pbkdf2_hmac(
            'sha256', password.encode('utf-8'), salt, self.KEY_ITERATIONS, dklen=32
        )
        return (
            base64.b64encode(salt).decode('utf-8'),
            base64.b64encode(password_hash).decode('utf-8'),
            self.KEY_ITERATIONS
        )

    def verify_password(self, password: str, salt_b64: str,
                        hash_b64: str, iterations: int) -> bool:
        """Verify a password with timing-safe comparison."""
        try:
            salt = base64.b64decode(salt_b64)
            stored_hash = base64.b64decode(hash_b64)
            computed_hash = hashlib.pbkdf2_hmac(
                'sha256', password.encode('utf-8'), salt, iterations, dklen=32
            )
            return hmac.compare_digest(computed_hash, stored_hash)
        except Exception:
            return False

    def generate_secure_token(self, length: int = 32) -> str:
        """Generate a cryptographically secure random token."""
        return base64.urlsafe_b64encode(os.urandom(length)).decode()

    def create_digital_signature(self, data: str) -> str:
        """Create an RSA digital signature."""
        if not self._private_key:
            raise ValueError("RSA not available")
        signature = self._private_key.sign(
            data.encode(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return base64.b64encode(signature).decode()

    def verify_signature(self, data: str, signature_b64: str,
                         public_key_pem: str = None) -> bool:
        """Verify an RSA digital signature."""
        try:
            if public_key_pem:
                public_key = serialization.load_pem_public_key(
                    public_key_pem.encode(), backend=default_backend()
                )
            else:
                public_key = self._public_key
            signature = base64.b64decode(signature_b64)
            public_key.verify(
                signature, data.encode(),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except Exception:
            return False

    def derive_key_from_password(self, password: str,
                                  salt: bytes = None) -> Tuple[bytes, bytes]:
        """Derive an encryption key from a user password."""
        if salt is None:
            salt = os.urandom(32)
        if _CRYPTO_AVAILABLE:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
                backend=default_backend()
            )
            key = kdf.derive(password.encode())
        else:
            key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000, dklen=32)
        return key, salt

    def encrypt_file(self, file_path: str, output_path: str = None) -> str:
        """Encrypt a file using AES-256-GCM."""
        if not output_path:
            output_path = file_path + '.enc'
        with open(file_path, 'rb') as f:
            plaintext = f.read()
        nonce = os.urandom(12)
        aesgcm = AESGCM(self._aes_key)
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        with open(output_path, 'wb') as f:
            f.write(bytes([self.VERSION]) + nonce + ciphertext)
        return output_path

    def decrypt_file(self, file_path: str, output_path: str = None) -> str:
        """Decrypt an AES-256-GCM encrypted file."""
        if not output_path:
            output_path = file_path.replace('.enc', '.dec')
        with open(file_path, 'rb') as f:
            data = f.read()
        nonce = data[1:13]
        ciphertext = data[13:]
        aesgcm = AESGCM(self._aes_key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        with open(output_path, 'wb') as f:
            f.write(plaintext)
        return output_path
