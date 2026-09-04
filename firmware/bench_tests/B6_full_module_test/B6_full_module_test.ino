/*
  NOVIS B6 - full module combined test (ESP32)

  Runs all four sensors together, about once per second, and prints one
  clear block of readings so you can confirm the WHOLE assembled module
  works as a unit - not just each sensor alone on its own breadboard.

  This is a slow, human-readable diagnostic loop (~1 Hz). It is NOT the
  final 8 Hz production timing the real firmware needs - that is separate,
  still-open work (see docs/hardware_log.md section 9 and Part C of
  docs/NOVIS_Build_Guide.md).

  Status: compiles clean for esp32:esp32:esp32 (verified). NOT yet run on
  the assembled module - that is what it is for.

  Pin plan = the B6 pin plan used everywhere else in this repo. If you
  wired different pins, change the #defines below to match - nothing
  else needs to change.

  Pass criteria for each line: see docs/NOVIS_Final_Module_Build.md,
  section 6, "Now run the whole module together".
*/

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_MLX90640.h>
#include <driver/i2s.h>

#define NOVIS_THERMAL_PIXELS (32 * 24)

// ---- PIN ASSIGNMENTS - the B6 pin plan ----
#define I2C_SDA_PIN   21
#define I2C_SCL_PIN   22
#define TRIG_LEFT     16
#define ECHO_LEFT     17
#define TRIG_RIGHT    18
#define ECHO_RIGHT    19
#define I2S_SCK_PIN   14
#define I2S_WS_PIN    15
#define I2S_SD_PIN    32
#define SPEAKER_PIN   4
#define I2S_PORT      I2S_NUM_0

static Adafruit_MLX90640 mlx;
static float mlxFrame[NOVIS_THERMAL_PIXELS];
static bool  mlxOk = false;

#define I2S_CHUNK 256
static int32_t i2sBuf[I2S_CHUNK];

static void i2sBegin() {
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = 16000,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 4,
    .dma_buf_len = I2S_CHUNK,
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

// One buffer's worth of mic samples, reduced to a single peak number.
static int32_t i2sReadPeak() {
  size_t bytesRead = 0;
  i2s_read(I2S_PORT, i2sBuf, sizeof(i2sBuf), &bytesRead, portMAX_DELAY);
  int samples = bytesRead / sizeof(int32_t);
  int32_t peak = 0;
  for (int i = 0; i < samples; i++) {
    int32_t s = i2sBuf[i] >> 8;   // 24-bit sample sitting in a 32-bit word
    if (s > peak)  peak = s;
    if (-s > peak) peak = -s;
  }
  return peak;
}

// 5 ms chirp, 1 kHz -> 8 kHz.
static void emitChirp() {
  const int steps = 20;
  for (int i = 0; i < steps; i++) {
    float t = (float)i / (float)(steps - 1);
    int freq = (int)(1000.0f * powf(8.0f, t));
    tone(SPEAKER_PIN, freq);
    delayMicroseconds(250);
  }
  noTone(SPEAKER_PIN);
}

// Returns distance in millimetres, or 0 if nothing was detected.
static uint16_t readRange(int trigPin, int echoPin) {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);
  unsigned long duration = pulseIn(echoPin, HIGH, 30000UL);
  if (duration == 0) return 0;
  return (uint16_t)((duration * 343UL) / 2000UL);
}

void setup() {
  Serial.begin(115200);
  delay(2000);
  Serial.println("=== NOVIS B6 full module test ===");

  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
  Wire.setClock(400000);   // required for 8 Hz thermal frames, see hardware_log.md section 4
  mlxOk = mlx.begin(MLX90640_I2CADDR_DEFAULT, &Wire);
  if (mlxOk) {
    mlx.setMode(MLX90640_CHESS);
    mlx.setResolution(MLX90640_ADC_18BIT);
    mlx.setRefreshRate(MLX90640_8_HZ);
    Serial.println("Thermal : MLX90640 found.");
  } else {
    Serial.println("Thermal : NOT FOUND - check PS is tied to GND (power-cycle after "
                    "wiring it), check the 4.7k pull-ups on SDA/SCL.");
  }

  pinMode(TRIG_LEFT,  OUTPUT);
  pinMode(ECHO_LEFT,  INPUT);
  pinMode(TRIG_RIGHT, OUTPUT);
  pinMode(ECHO_RIGHT, INPUT);
  pinMode(SPEAKER_PIN, OUTPUT);
  digitalWrite(TRIG_LEFT,  LOW);
  digitalWrite(TRIG_RIGHT, LOW);

  i2sBegin();
  Serial.println("Setup done. Starting the test loop (about once per second).");
  Serial.println();
}

void loop() {
  Serial.println("---------------------------------------------");

  // 1) Thermal
  if (mlxOk && mlx.getFrame(mlxFrame) == 0) {
    float centre = mlxFrame[(12 * 32) + 16];   // middle of the 32x24 grid
    float lo = 1000, hi = -1000;
    for (int i = 0; i < NOVIS_THERMAL_PIXELS; i++) {
      if (mlxFrame[i] < lo) lo = mlxFrame[i];
      if (mlxFrame[i] > hi) hi = mlxFrame[i];
    }
    Serial.printf("Thermal   : centre=%.1fC  min=%.1fC  max=%.1fC\n", centre, lo, hi);
  } else {
    Serial.println("Thermal   : read failed (sensor not found, or getFrame() error)");
  }

  // 2) Sonar - left, then right, with a gap so they don't hear each other
  uint16_t left  = readRange(TRIG_LEFT, ECHO_LEFT);
  delayMicroseconds(3000);
  uint16_t right = readRange(TRIG_RIGHT, ECHO_RIGHT);
  Serial.printf("Sonar     : left=%u mm   right=%u mm\n", left, right);

  // 3) Mic + speaker echo test - an objective before/after comparison,
  //    not just "did I hear a click".
  int32_t before = i2sReadPeak();
  emitChirp();
  int32_t after = i2sReadPeak();
  Serial.printf("Echo test : mic peak before=%ld  after=%ld  %s\n",
                (long)before, (long)after,
                (after > before * 2) ? "<- spike seen, echo path is working" : "");

  delay(700);
}
