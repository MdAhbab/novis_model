/*
  NOVIS Part B4 - INMP441 microphone test (ESP32)
  Status as of last session: wired, signal present (peaks ~72k-660k observed),
  but no controlled quiet-vs-clap comparison done yet - see
  docs/hardware_log.md section 7 before trusting this as a pass.

  The nRF52 register-level I2S code in the original build guide does not
  port to ESP32 at all (NRF_I2S is nRF52-only hardware) - this uses the
  ESP32's own I2S driver instead.

  Wiring (vendor page's own recommended pinout for this compatible module):
  ESP32 3V3    -> INMP441 VDD
  ESP32 GND    -> INMP441 GND
  ESP32 GPIO14 -> INMP441 SCK (bit clock)
  ESP32 GPIO15 -> INMP441 WS  (word select)
  ESP32 GPIO32 -> INMP441 SD  (data out)
  ESP32 GND    -> INMP441 L/R  <-- required, or the mic outputs nothing

  PASS = "Peak level" small and steady in a quiet room, spikes clearly above
  baseline on a clap - not yet confirmed with that specific comparison.
*/

#include <driver/i2s.h>

#define I2S_SCK_PIN   14   // bit clock
#define I2S_WS_PIN    15   // word select
#define I2S_SD_PIN    32   // data in from the microphone
#define I2S_PORT      I2S_NUM_0

#define SAMPLES 256
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

void setup() {
  Serial.begin(115200);
  while (!Serial) delay(10);
  Serial.println("INMP441 microphone test...");
  i2sBegin();
}

void loop() {
  size_t bytesRead = 0;
  i2s_read(I2S_PORT, rxBuffer, sizeof(rxBuffer), &bytesRead, portMAX_DELAY);
  int samples = bytesRead / sizeof(int32_t);

  int32_t peak = 0;
  for (int i = 0; i < samples; i++) {
    int32_t s = rxBuffer[i] >> 8;   // 24-bit sample sitting in a 32-bit word
    if (s > peak)  peak = s;
    if (-s > peak) peak = -s;
  }

  Serial.print("Peak level: ");
  Serial.println(peak);
  delay(100);
}
