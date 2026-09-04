/*
  NOVIS Part B5 - PAM8302 + speaker, chirp-only test (ESP32)
  Status: PASS on hardware. If a rebuilt module goes silent again, see
  docs/hardware_log.md section 8 for the two findings that caused it before,
  and check them before assuming this code is at fault:
    1. This PAM8302A board's SD (shutdown) pin must be tied to VIN or the
       amp stays muted no matter what signal reaches A+.
    2. A speaker wire looped-through-the-hole but not soldered onto
       OUT+/OUT- is a real suspect for "wiring looks right, still silent".

  Wiring:
  ESP32 GPIO4 -> PAM8302 A+     PAM8302 A- -> GND
  PAM8302 VIN -> 3.3V or 5V (measured 4.8V in our build)
  PAM8302 SD  -> VIN (same rail, tapped twice - not a real second connection)
  PAM8302 OUT+/OUT- -> speaker red/black (reversed polarity is harmless)

  Never wire the speaker directly to an ESP32 pin - always through the amp.

  PASS = a short, quiet "tick"/chirp every two seconds. It is only 5 ms long,
  so listen carefully in a quiet room.

  The chirp below is the real 5 ms design value (20 steps x 250 us), which is
  what the paper's chirp-duration number assumes. If you need an obviously
  audible sweep while debugging silent hardware, temporarily swap
  delayMicroseconds(250) for delay(50) - then put it back, or the paper's
  number no longer matches the code.
*/

#define SPEAKER_PIN 4

void setup() {
  Serial.begin(115200);
  pinMode(SPEAKER_PIN, OUTPUT);
  Serial.println("Chirp test. Listen for a short rising tone every 2 seconds.");
}

// Emit a chirp that sweeps from 1 kHz up to 8 kHz.
void emitChirp() {
  const int steps = 20;
  for (int i = 0; i < steps; i++) {
    float t = (float)i / (float)(steps - 1);
    int freq = (int)(1000.0f * powf(8.0f, t));
    tone(SPEAKER_PIN, freq);
    delayMicroseconds(250);   // 20 steps x 250 us = the real 5 ms chirp.
                              // Swap for delay(50) only as a temporary
                              // debugging aid - see the header comment.
  }
  noTone(SPEAKER_PIN);
}

void loop() {
  emitChirp();
  delay(2000);
}
