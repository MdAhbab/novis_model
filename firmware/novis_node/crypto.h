// AEAD interface: ChaCha20-Poly1305 over one frame.
//
// On the nRF52840, prefer the CryptoCell-310 accelerator through the Nordic
// nrf_cc310 / CryptoCell API, or the mbedTLS ChaCha20-Poly1305 that ships with
// the nRF Connect SDK. For an Arduino-only build, a portable implementation
// such as rweather/Crypto (ChaChaPoly) works and is what the stub assumes.
//
// nonce = counter (8 bytes, little-endian) || session_salt (4 bytes).
#ifndef NOVIS_CRYPTO_H
#define NOVIS_CRYPTO_H

#include <stdint.h>
#include <stddef.h>
#include "protocol.h"

// Set the 32-byte session key and 4-byte salt derived at handshake (HKDF).
void crypto_set_session(const uint8_t key[NOVIS_KEY_BYTES],
                        const uint8_t salt[NOVIS_SALT_BYTES]);

// Encrypt `frame` (len bytes) under the current session with `counter`.
// Writes counter(8) || ciphertext(len) || tag(16) into out.
// out must hold NOVIS_COUNTER_BYTES + len + NOVIS_TAG_BYTES bytes.
// Returns total bytes written.
size_t crypto_seal(uint64_t counter, const uint8_t *frame, size_t len,
                   uint8_t *out);

#endif  // NOVIS_CRYPTO_H
