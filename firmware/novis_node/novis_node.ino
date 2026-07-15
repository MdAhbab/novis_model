// NOVIS sensor node firmware (skeleton) for the nRF52840.
//
// Board:  any nRF52840 board with the Adafruit nRF52 Arduino core (Feather
//         nRF52840, ProMicro nRF52840, etc.). Select it in Tools > Board.
// Libraries: Adafruit Bluefruit nRF52 (bundled with the core). Add the sensor
//         and crypto libraries listed in sensors.h and crypto.h.
//
// What this skeleton does:
//   setup(): init sensors, derive a session key (placeholder), start BLE.
//   loop():  sample thermal (8 Hz), echo (4 Hz), sonar (10 Hz); for each frame
//            build header + payload, AEAD-seal it, fragment it, notify it.
//
// What you must finish before real use:
//   - Real sensor driver bodies (sensors.cpp).
//   - Real LE Secure Connections pairing and an HKDF key handshake over the
//     control characteristic (crypto_set_session is called with a placeholder).
//   - Real ChaCha20-Poly1305 (crypto.cpp), ideally on CryptoCell.
#include <bluefruit.h>

#include "protocol.h"
#include "sensors.h"
#include "crypto.h"

static BLEService        novisService(NOVIS_SERVICE_UUID);
static BLECharacteristic streamChar(NOVIS_STREAM_UUID);

static uint32_t seqThermal = 0, seqEcho = 0, seqSonar = 0;
static uint64_t msgCounter = 0;
static uint16_t msgId = 0;

// Scratch buffers sized for the largest frame.
static uint8_t frameBuf[NOVIS_HEADER_BYTES + NOVIS_THERMAL_BYTES];
static uint8_t sealBuf[NOVIS_COUNTER_BYTES + sizeof(frameBuf) + NOVIS_TAG_BYTES];

static uint32_t lastThermalMs = 0, lastEchoMs = 0, lastSonarMs = 0;

static void startAdv(void) {
  Bluefruit.Advertising.addFlags(BLE_GAP_ADV_FLAGS_LE_ONLY_GENERAL_DISC_MODE);
  Bluefruit.Advertising.addService(novisService);
  Bluefruit.Advertising.addName();
  Bluefruit.Advertising.restartOnDisconnect(true);
  Bluefruit.Advertising.setInterval(32, 244);
  Bluefruit.Advertising.start(0);
}

// Fragment sealed bytes into BLE notifications with the 4-byte transport header.
static void notifyFragmented(const uint8_t *msg, size_t n) {
  uint8_t fragCount = (uint8_t)((n + NOVIS_FRAG_PAYLOAD_MAX - 1) /
                                NOVIS_FRAG_PAYLOAD_MAX);
  uint8_t chunk[NOVIS_FRAG_HEADER_BYTES + NOVIS_FRAG_PAYLOAD_MAX];
  for (uint8_t i = 0; i < fragCount; i++) {
    size_t off = (size_t)i * NOVIS_FRAG_PAYLOAD_MAX;
    size_t len = min((size_t)NOVIS_FRAG_PAYLOAD_MAX, n - off);
    chunk[0] = (uint8_t)(msgId);
    chunk[1] = (uint8_t)(msgId >> 8);
    chunk[2] = i;
    chunk[3] = fragCount;
    memcpy(chunk + NOVIS_FRAG_HEADER_BYTES, msg + off, len);
    while (!streamChar.notify(chunk, NOVIS_FRAG_HEADER_BYTES + len)) {
      delay(2);  // wait for the BLE stack buffer to drain
    }
  }
  msgId++;
}

static void sendFrame(uint8_t type, uint32_t seq, const uint8_t *payload,
                      size_t payloadLen) {
  size_t hlen = novis_write_header(frameBuf, type, seq, millis());
  memcpy(frameBuf + hlen, payload, payloadLen);
  size_t sealed = crypto_seal(msgCounter++, frameBuf, hlen + payloadLen,
                              sealBuf);
  notifyFragmented(sealBuf, sealed);
}

void setup(void) {
  Serial.begin(115200);
  sensors_begin();

  // Placeholder session material. Replace with an HKDF result computed after
  // LE Secure Connections pairing and a nonce exchange over the control char.
  uint8_t key[NOVIS_KEY_BYTES] = {0};
  uint8_t salt[NOVIS_SALT_BYTES] = {0};
  crypto_set_session(key, salt);

  Bluefruit.begin();
  Bluefruit.setName("NOVIS-Node");
  Bluefruit.Security.setIOCaps(true, true, false);  // numeric comparison
  novisService.begin();
  streamChar.setProperties(CHR_PROPS_NOTIFY);
  streamChar.setPermission(SECMODE_ENC_WITH_MITM, SECMODE_NO_ACCESS);
  streamChar.setMaxLen(NOVIS_FRAG_HEADER_BYTES + NOVIS_FRAG_PAYLOAD_MAX);
  streamChar.begin();
  startAdv();
}

void loop(void) {
  uint32_t now = millis();

  if (now - lastThermalMs >= 125) {  // 8 Hz
    lastThermalMs = now;
    static int16_t thermal[NOVIS_THERMAL_PIXELS];
    if (sensors_read_thermal(thermal))
      sendFrame(NOVIS_FRAME_THERMAL, seqThermal++, (uint8_t *)thermal,
                NOVIS_THERMAL_BYTES);
  }
  if (now - lastEchoMs >= 250) {     // 4 Hz
    lastEchoMs = now;
    static int16_t echo[NOVIS_ECHO_SAMPLES];
    if (sensors_capture_echo(echo))
      sendFrame(NOVIS_FRAME_ECHO, seqEcho++, (uint8_t *)echo, NOVIS_ECHO_BYTES);
  }
  if (now - lastSonarMs >= 100) {    // 10 Hz
    lastSonarMs = now;
    uint16_t l, r; uint8_t st;
    if (sensors_read_sonar(&l, &r, &st)) {
      uint8_t p[NOVIS_SONAR_BYTES] = {0};
      p[0] = (uint8_t)l; p[1] = (uint8_t)(l >> 8);
      p[2] = (uint8_t)r; p[3] = (uint8_t)(r >> 8);
      p[4] = st;
      sendFrame(NOVIS_FRAME_SONAR, seqSonar++, p, NOVIS_SONAR_BYTES);
    }
  }
}
