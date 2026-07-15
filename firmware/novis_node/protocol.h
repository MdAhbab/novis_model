// NOVIS wire protocol (shared source of truth with host/protocol.py).
// Keep the two files byte-for-byte compatible: if you change a constant here,
// change it there. See NOVIS/docs/methodology.md Section 3.
//
// Layers, outermost last:
//   frame      = 12-byte header + payload            (plaintext)
//   message    = 8-byte counter + AEAD(frame) + tag  (what gets encrypted)
//   fragment   = 4-byte transport header + chunk      (what BLE notifies)
#ifndef NOVIS_PROTOCOL_H
#define NOVIS_PROTOCOL_H

#include <stdint.h>

// ---- Frame types ----
enum NovisFrameType {
  NOVIS_FRAME_THERMAL = 0x01,  // 768 int16 pixels (32x24), little-endian
  NOVIS_FRAME_ECHO    = 0x02,  // 960 int16 PCM samples (60 ms @ 16 kHz)
  NOVIS_FRAME_SONAR   = 0x03,  // 2 uint16 ranges (mm) + 1 status + 3 pad
};

// ---- Frame header (12 bytes, little-endian) ----
//   [0]    uint8  type
//   [1]    uint8  flags
//   [2..5] uint32 seq   (monotonic, per frame type)
//   [6..11] 48-bit timestamp in milliseconds
#define NOVIS_HEADER_BYTES 12

#define NOVIS_THERMAL_PIXELS 768
#define NOVIS_THERMAL_BYTES  (NOVIS_THERMAL_PIXELS * 2)   // 1536
#define NOVIS_ECHO_SAMPLES   960
#define NOVIS_ECHO_BYTES     (NOVIS_ECHO_SAMPLES * 2)     // 1920
#define NOVIS_SONAR_BYTES    8

// ---- AEAD (ChaCha20-Poly1305) ----
//   nonce (12 bytes) = counter(8, little-endian) || session_salt(4)
//   message on the wire = counter(8) || ciphertext || tag(16)
#define NOVIS_TAG_BYTES     16
#define NOVIS_COUNTER_BYTES 8
#define NOVIS_SALT_BYTES    4
#define NOVIS_KEY_BYTES     32

// ---- Fragmentation over BLE notifications ----
//   transport header (4 bytes):
//     [0..1] uint16 msg_id
//     [2]    uint8  frag_index
//     [3]    uint8  frag_count
// Keep chunk payload under the negotiated ATT MTU minus header. 180 is safe
// for a 247-byte MTU with the 2M PHY.
#define NOVIS_FRAG_HEADER_BYTES 4
#define NOVIS_FRAG_PAYLOAD_MAX  180

// ---- BLE GATT identifiers (128-bit UUIDs) ----
// Regenerate for a real deployment; these are placeholders for the skeleton.
#define NOVIS_SERVICE_UUID  "4e4f5649-5300-4000-8000-000000000001"
#define NOVIS_STREAM_UUID   "4e4f5649-5300-4000-8000-000000000002"  // notify
#define NOVIS_CONTROL_UUID  "4e4f5649-5300-4000-8000-000000000003"  // write

// Build a 12-byte frame header into out. Returns bytes written.
static inline uint8_t novis_write_header(uint8_t *out, uint8_t type,
                                         uint32_t seq, uint64_t ts_ms) {
  out[0] = type;
  out[1] = 0;  // flags
  out[2] = (uint8_t)(seq);
  out[3] = (uint8_t)(seq >> 8);
  out[4] = (uint8_t)(seq >> 16);
  out[5] = (uint8_t)(seq >> 24);
  for (int i = 0; i < 6; i++) out[6 + i] = (uint8_t)(ts_ms >> (8 * i));
  return NOVIS_HEADER_BYTES;
}

#endif  // NOVIS_PROTOCOL_H
