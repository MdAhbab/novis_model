/*
  NOVIS Part C - crypto.cpp, compile-check (ESP32)

  Stands in for firmware/novis_node/crypto.cpp: ChaCha20-Poly1305 AEAD via
  the "Crypto" library (Rhys Weatherley). Nonce = 8-byte counter + 4-byte
  session salt, so it never repeats as long as the counter only increases.

  Status: compiles and runs on ESP32 (verified - prints the sealed frame
  length on boot). The "Crypto" library is written to be portable across
  AVR/SAMD/ESP32/nRF52, and this confirms it holds for ESP32 specifically.
  Uses an all-zero placeholder key, same as the rest of this project's bench
  work - fine for node<->host testing, not for any real deployment. See
  docs/hardware_log.md section 9.
*/

#include <Arduino.h>
#include <ChaChaPoly.h>
#include <string.h>

#define NOVIS_KEY_BYTES 32
#define NOVIS_SALT_BYTES 4
#define NOVIS_COUNTER_BYTES 8
#define NOVIS_TAG_BYTES 16

static uint8_t sessionKey[NOVIS_KEY_BYTES];
static uint8_t sessionSalt[NOVIS_SALT_BYTES];

void crypto_set_session(const uint8_t key[NOVIS_KEY_BYTES],
                        const uint8_t salt[NOVIS_SALT_BYTES]) {
  memcpy(sessionKey,  key,  NOVIS_KEY_BYTES);
  memcpy(sessionSalt, salt, NOVIS_SALT_BYTES);
}

size_t crypto_seal(uint64_t counter, const uint8_t *frame, size_t len,
                   uint8_t *out) {
  uint8_t nonce[12];
  for (int i = 0; i < 8; i++) nonce[i] = (uint8_t)(counter >> (8 * i));
  memcpy(nonce + 8, sessionSalt, NOVIS_SALT_BYTES);

  ChaChaPoly cipher;
  cipher.clear();
  cipher.setKey(sessionKey, NOVIS_KEY_BYTES);
  cipher.setIV(nonce, 12);

  memcpy(out, nonce, NOVIS_COUNTER_BYTES);
  cipher.encrypt(out + NOVIS_COUNTER_BYTES, frame, len);
  cipher.computeTag(out + NOVIS_COUNTER_BYTES + len, NOVIS_TAG_BYTES);

  return NOVIS_COUNTER_BYTES + len + NOVIS_TAG_BYTES;
}

void setup() {
  Serial.begin(115200);
  uint8_t key[NOVIS_KEY_BYTES] = {0};
  uint8_t salt[NOVIS_SALT_BYTES] = {0};
  crypto_set_session(key, salt);
  uint8_t frame[16] = {0};
  uint8_t out[64];
  size_t n = crypto_seal(1, frame, sizeof(frame), out);
  Serial.println(n);
}

void loop() {}
