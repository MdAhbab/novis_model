/*
  NOVIS Part B5 - objective mic+speaker echo test (ESP32)

  Combines B4 and B5 so the microphone reports a number instead of asking a
  human ear to judge a 5-50 ms chirp. This is also the guide's actual B5
  echo test brought forward: point the node at a wall ~1 m away and confirm
  the "AFTER" peak spikes clearly above "BEFORE" right after each chirp -
  that spike is the echo coming back, i.e. echolocation working, whether or
  not you can hear the chirp yourself.

  Wiring: same as B2 (I2C 21/22, unused here), B4 (I2S 14/15/32), and B5
  (speaker on GPIO4) combined. See docs/hardware_log.md section 8.

  If B5's amp+speaker still seems silent before reaching for this: try the
  "pop test" first - briefly touch the PAM8302's A+ wire to VIN. A working
  amp+speaker makes an audible pop with no code involved. Pop = the problem
  is upstream (GPIO4 wiring or the chirp code, this sketch helps). No pop =
  downstream (OUT+/OUT- connection or the speaker itself) - check solder
  joints before debugging code further.
*/

#include <driver/i2s.h>

#define SPEAKER_PIN   4
#define I2S_SCK_PIN   14
#define I2S_WS_PIN    15
#define I2S_SD_PIN    32
#define I2S_PORT      I2S_NUM_0
#define SAMPLES       256

static int32_t rxBuffer[SAMPLES];

void i2sBegin() {
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = 16000,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 4,
    .dma_buf_len = SAMPLES,
    .use_apll = false
  };
  i2s_pin_config_t pin_config = {
    .bck_io_num = I2S_SCK_PIN,
    .ws_io_num = I2S_WS_PIN,
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num = I2S_SD_PIN
  };
  i2s_driver_install(I2S_PORT, &i2s_config, 0, NULL);
  i2s_set_pin(I2S_PORT, &pin_config);
}

int32_t readMicPeak() {
  size_t bytesRead = 0;
  i2s_read(I2S_PORT, rxBuffer, sizeof(rxBuffer), &bytesRead, portMAX_DELAY);
  int samples = bytesRead / sizeof(int32_t);
  int32_t peak = 0;
  for (int i = 0; i < samples; i++) {
    int32_t s = rxBuffer[i] >> 8;
    if (s > peak) peak = s;
    if (-s > peak) peak = -s;
  }
  return peak;
}

void emitChirp() {
  const int steps = 20;
  for (int i = 0; i < steps; i++) {
    float t = (float)i / (float)(steps - 1);
    int freq = (int)(1000.0f * powf(8.0f, t));
    tone(SPEAKER_PIN, freq);
    delayMicroseconds(250);   // 20 steps x 250 us = the real 5 ms chirp.
                              // This test has to use the real duration - a
                              // longer chirp would measure an echo NOVIS
                              // never actually emits.
  }
  noTone(SPEAKER_PIN);
}

void setup() {
  Serial.begin(115200);
  pinMode(SPEAKER_PIN, OUTPUT);
  i2sBegin();
  Serial.println("Chirp + mic combined test starting...");
}

void loop() {
  int32_t before = readMicPeak();
  Serial.print("Mic peak BEFORE chirp: ");
  Serial.println(before);

  emitChirp();

  int32_t after = readMicPeak();
  Serial.print("Mic peak DURING/AFTER chirp: ");
  Serial.println(after);
  Serial.println("-----");

  delay(1500);
}
