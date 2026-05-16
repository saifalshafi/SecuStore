"""Cryptographic utilities for secure file storage and transmission.

This is the single, canonical encryption module for the project. It provides:
  - Diffie-Hellman key pair generation and shared-key derivation.
  - AES-256-CFB file encryption for at-rest storage.
  - AES-256-CFB + RSA-OAEP + HMAC-SHA256 file encryption for transmission.
  - Corresponding decryption for transmitted files.
"""

import logging
import os

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.dh import generate_parameters
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.hmac import HMAC
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Diffie-Hellman helpers
# ---------------------------------------------------------------------------

def generate_dh_key_pair():
    """Generate a 2048-bit Diffie-Hellman key pair.

    Returns:
        tuple: ``(private_key, public_key)`` DH key objects.

    Raises:
        Exception: If key generation fails.
    """
    try:
        parameters = generate_parameters(
            generator=2, key_size=2048, backend=default_backend(),
        )
        private_key = parameters.generate_private_key()
        public_key = private_key.public_key()
        return private_key, public_key
    except Exception as e:
        logger.error(f"Error generating DH key pair: {e}")
        raise Exception("Failed to generate Diffie-Hellman key pair.")


def compute_shared_dh_key(private_key, peer_public_key):
    """Derive a 256-bit shared secret from a DH exchange using HKDF-SHA256.

    Args:
        private_key: The local DH private key.
        peer_public_key: The remote party's DH public key.

    Returns:
        bytes: A 32-byte derived key suitable for AES-256.

    Raises:
        Exception: If key derivation fails.
    """
    try:
        shared_key = private_key.exchange(peer_public_key)
        derived_key = HKDF(
            algorithm=SHA256(),
            length=32,
            salt=None,
            info=b'session key',
            backend=default_backend(),
        ).derive(shared_key)
        return derived_key
    except Exception as e:
        logger.error(f"Error computing shared DH key: {e}")
        raise Exception("Failed to compute shared Diffie-Hellman key.")


# ---------------------------------------------------------------------------
# Storage encryption (AES-256-CFB, at-rest)
# ---------------------------------------------------------------------------

def encrypt_file_storage(file_path):
    """Encrypt a file for at-rest storage using AES-256-CFB.

    The encrypted output is written to ``<file_path>.enc`` and consists of
    the 16-byte IV followed by the ciphertext.

    Args:
        file_path: Absolute path to the plaintext file.

    Returns:
        tuple: ``(encrypted_file_path, aes_key)`` where *aes_key* is the
        raw 32-byte AES key that must be stored securely.

    Raises:
        Exception: On file-not-found or encryption failure.
    """
    try:
        aes_key = os.urandom(32)  # 256-bit key
        iv = os.urandom(16)       # 128-bit IV

        with open(file_path, 'rb') as f:
            file_data = f.read()

        cipher = Cipher(algorithms.AES(aes_key), modes.CFB(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        encrypted_data = encryptor.update(file_data) + encryptor.finalize()

        encrypted_file_path = f"{file_path}.enc"
        with open(encrypted_file_path, 'wb') as ef:
            ef.write(iv + encrypted_data)

        return encrypted_file_path, aes_key

    except FileNotFoundError:
        logger.error(f"File not found during storage encryption: {file_path}")
        raise Exception("File not found for storage encryption.")
    except Exception as e:
        logger.error(f"Storage encryption error: {e}")
        raise Exception("File encryption for storage failed.")


# ---------------------------------------------------------------------------
# Transmission encryption (AES-256-CFB + RSA-OAEP + HMAC-SHA256)
# ---------------------------------------------------------------------------

def encrypt_file_transmission(file_path, recipient_public_key, session_key):
    """Encrypt a file for secure transmission.

    The output file (``<file_path>.trans.secure``) contains, in order:
      1. RSA-OAEP wrapped session key (256 bytes for 2048-bit RSA).
      2. 16-byte AES IV.
      3. AES-256-CFB ciphertext.
      4. 32-byte HMAC-SHA256 tag over ``(IV || ciphertext)`` keyed with
         the wrapped session key.

    Args:
        file_path: Path to the plaintext file.
        recipient_public_key: PEM-encoded RSA public key of the recipient.
        session_key: Raw 32-byte AES session key.

    Returns:
        str: Path to the encrypted output file.

    Raises:
        Exception: On file-not-found, RSA, or encryption failure.
    """
    try:
        iv = os.urandom(16)
        with open(file_path, 'rb') as f:
            file_data = f.read()

        # AES-256-CFB encryption
        cipher = Cipher(algorithms.AES(session_key), modes.CFB(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        encrypted_data = encryptor.update(file_data) + encryptor.finalize()

        # RSA-OAEP wrap the session key
        recipient_rsa_key = serialization.load_pem_public_key(
            recipient_public_key, backend=default_backend(),
        )
        encrypted_session_key = recipient_rsa_key.encrypt(
            session_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=SHA256()),
                algorithm=SHA256(),
                label=None,
            ),
        )

        # HMAC-SHA256 integrity tag
        h = HMAC(encrypted_session_key, hashes.SHA256(), backend=default_backend())
        h.update(iv + encrypted_data)
        tag = h.finalize()

        # Write: wrapped_key || iv || ciphertext || tag
        encrypted_file_path = f"{file_path}.trans.secure"
        with open(encrypted_file_path, 'wb') as ef:
            ef.write(encrypted_session_key + iv + encrypted_data + tag)

        return encrypted_file_path

    except FileNotFoundError:
        logger.error(f"File not found for transmission encryption: {file_path}")
        raise Exception("File not found for transmission encryption.")
    except ValueError as e:
        logger.error(f"RSA key error during transmission encryption: {e}")
        raise Exception("RSA encryption failed during transmission.")
    except Exception as e:
        logger.error(f"Transmission encryption error: {e}")
        raise Exception("File encryption for transmission failed.")


def decrypt_file_transmission(encrypted_file_path, recipient_private_key):
    """Decrypt a file that was encrypted for transmission.

    Verifies the HMAC-SHA256 tag *before* performing any decryption
    (encrypt-then-MAC pattern).

    Args:
        encrypted_file_path: Path to the ``.trans.secure`` file.
        recipient_private_key: PEM-encoded RSA private key bytes.

    Returns:
        str: Path to the decrypted plaintext file.

    Raises:
        Exception: On integrity failure, key errors, or I/O errors.
    """
    try:
        data = open(encrypted_file_path, 'rb').read()

        # Split components (256-byte wrapped key for 2048-bit RSA)
        wrapped = data[:256]
        iv = data[256:272]
        ciphertext = data[272:-32]
        tag = data[-32:]

        # Verify HMAC before decryption
        h = HMAC(wrapped, hashes.SHA256(), backend=default_backend())
        h.update(iv + ciphertext)
        h.verify(tag)  # raises InvalidSignature on mismatch

        # Unwrap session key with RSA-OAEP
        private_key = serialization.load_pem_private_key(
            recipient_private_key, password=None, backend=default_backend(),
        )
        session_key = private_key.decrypt(
            wrapped,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=SHA256()),
                algorithm=SHA256(),
                label=None,
            ),
        )

        # AES-256-CFB decryption
        cipher = Cipher(algorithms.AES(session_key), modes.CFB(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        decrypted_data = decryptor.update(ciphertext) + decryptor.finalize()

        decrypted_file_path = encrypted_file_path.replace('.trans.secure', '')
        with open(decrypted_file_path, 'wb') as df:
            df.write(decrypted_data)

        return decrypted_file_path

    except FileNotFoundError:
        logger.error(f"Encrypted file not found for decryption: {encrypted_file_path}")
        raise Exception("File not found for decryption.")
    except ValueError as e:
        logger.error(f"Decryption key error: {e}")
        raise Exception("Decryption failed due to invalid keys.")
    except Exception as e:
        logger.error(f"Decryption error: {e}")
        raise Exception("Decryption failed during transmission.")
