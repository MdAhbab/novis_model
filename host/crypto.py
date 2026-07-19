"""Application-layer AEAD for NOVIS frames (host side).

ChaCha20-Poly1305, matching firmware/novis_node/crypto.h. The nonce is
counter(8, little-endian) || session_salt(4). The message on the wire is
counter(8) || ciphertext || tag(16).

Requires the `cryptography` package (pip install cryptography).
"""

from __future__ import annotations

import struct
import logging

from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

from . import protocol as P


class Session:
    """Holds the 32-byte key and 4-byte salt derived at handshake."""

    def __init__(self, key: bytes, salt: bytes):
        if len(key) != P.KEY_BYTES:
            raise ValueError("key must be 32 bytes")
        if len(salt) != P.SALT_BYTES:
            raise ValueError("salt must be 4 bytes")
        if key == b"\x00" * P.KEY_BYTES and salt == b"\x00" * P.SALT_BYTES:
            logging.warning("SECURITY: Using placeholder all-zero AEAD key and salt. "
                            "Do not use in production!")
        self._aead = ChaCha20Poly1305(key)
        self._salt = salt

    def _nonce(self, counter: int) -> bytes:
        return struct.pack("<Q", counter & 0xFFFFFFFFFFFFFFFF) + self._salt

    def seal(self, counter: int, frame: bytes) -> bytes:
        """frame -> counter(8) || ciphertext || tag(16)."""
        ct = self._aead.encrypt(self._nonce(counter), frame, None)
        return struct.pack("<Q", counter & 0xFFFFFFFFFFFFFFFF) + ct

    def open(self, message: bytes) -> bytes:
        """counter(8) || ciphertext || tag(16) -> frame. Raises on bad tag."""
        if len(message) < P.COUNTER_BYTES + P.TAG_BYTES:
            raise ValueError("message too short")
        counter = struct.unpack_from("<Q", message, 0)[0]
        ct = message[P.COUNTER_BYTES:]
        return self._aead.decrypt(self._nonce(counter), ct, None)
