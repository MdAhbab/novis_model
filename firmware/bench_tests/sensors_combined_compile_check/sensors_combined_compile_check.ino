/*
  NOVIS Part C - combined sensor drivers, compile-check draft (ESP32)

  Stands in for firmware/novis_node/sensors.h + sensors.cpp together: all
  four sensor drivers (thermal, sonar x2, mic/I2S, chirp) in one file, using
  the real B6 pin plan, in the exact public-function shape sensors.cpp needs
  to provide (sensors_begin, sensors_read_thermal, sensors_capture_echo,
  sensors_read_sonar).

  Status: compiles clean for esp32:esp32:esp32 (verified). NOT yet run
  against real hardware as a combined unit, and NOT yet the actual
  firmware/novis_node/sensors.cpp - though each driver here matches one that
  has now passed individually (B2-B5) elsewhere in bench_tests/.
  Carries over every B2 fix: PS tied to GND (wiring only, not code-visible
  here), Wire.setClock(400000).

  This only proves the four drivers compile together without symbol/resource
  conflicts on ESP32 - it does not prove sensors_capture_echo's chirp+record
  timing, or that all four sensors can run back-to-back at the frame rate
  NOVIS needs. Part C also still needs the BLE side of novis_node.ino ported
  from Bluefruit (nRF52-only) to an ESP32 BLE stack - see
  docs/hardware_log.md section 9.
*/

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_MLX90640.h>
#include <driver/i2s.h>

#define NOVIS_THERMAL_PIXELS (32 * 24)
#define NOVIS_ECHO_SAMPLES   960   // 60ms at 16kHz

// ---------------------------------------------------------------
// PIN ASSIGNMENTS - from the B6 pin plan
// ---------------------------------------------------------------
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

// ---------------------------------------------------------------
// Thermal
// ---------------------------------------------------------------
static Adafruit_MLX90640 mlx;
static float mlxFrame[NOVIS_THERMAL_PIXELS];
static bool  mlxOk = false;

// ---------------------------------------------------------------
// Microphone (I2S)
// ---------------------------------------------------------------
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

static void i2sReadChunk() {
  size_t bytesRead = 0;
  i2s_read(I2S_PORT, i2sBuf, sizeof(i2sBuf), &bytesRead, portMAX_DELAY);
}

// ---------------------------------------------------------------
// Chirp emitter
// ---------------------------------------------------------------
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

// ---------------------------------------------------------------
// Public functions - the shape firmware/novis_node/sensors.cpp needs
// ---------------------------------------------------------------
bool sensors_begin(void) {
  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
  Wire.setClock(400000);   // required to keep up with 8 Hz thermal frames

  mlxOk = mlx.begin(MLX90640_I2CADDR_DEFAULT, &Wire);
  if (mlxOk) {
    mlx.setMode(MLX90640_CHESS);
    mlx.setResolution(MLX90640_ADC_18BIT);
    mlx.setRefreshRate(MLX90640_8_HZ);
  }

  pinMode(TRIG_LEFT,  OUTPUT);
  pinMode(ECHO_LEFT,  INPUT);
  pinMode(TRIG_RIGHT, OUTPUT);
  pinMode(ECHO_RIGHT, INPUT);
  pinMode(SPEAKER_PIN, OUTPUT);
  digitalWrite(TRIG_LEFT,  LOW);
  digitalWrite(TRIG_RIGHT, LOW);

  i2sBegin();

  return mlxOk;
}

bool sensors_read_thermal(int16_t thermal[NOVIS_THERMAL_PIXELS]) {
  if (!mlxOk) return false;
  if (mlx.getFrame(mlxFrame) != 0) return false;

  for (int i = 0; i < NOVIS_THERMAL_PIXELS; i++) {
    float c = mlxFrame[i];
    if (c < -300.0f) c = -300.0f;
    if (c >  300.0f) c =  300.0f;
    thermal[i] = (int16_t)(c * 100.0f);
  }
  return true;
}

bool sensors_capture_echo(int16_t echo[NOVIS_ECHO_SAMPLES]) {
  emitChirp();

  int written = 0;
  while (written < NOVIS_ECHO_SAMPLES) {
    i2sReadChunk();
    for (int i = 0; i < I2S_CHUNK && written < NOVIS_ECHO_SAMPLES; i++) {
      int32_t s24 = i2sBuf[i] >> 8;
      int32_t s16 = s24 >> 8;
      if (s16 >  32767) s16 =  32767;
      if (s16 < -32768) s16 = -32768;
      echo[written++] = (int16_t)s16;
    }
  }
  return true;
}

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

bool sensors_read_sonar(uint16_t *left, uint16_t *right, uint8_t *status) {
  uint16_t l = readRange(TRIG_LEFT, ECHO_LEFT);
  delayMicroseconds(3000);
  uint16_t r = readRange(TRIG_RIGHT, ECHO_RIGHT);

  *left  = l;
  *right = r;
  *status = (uint8_t)((l > 0 ? 0x01 : 0x00) | (r > 0 ? 0x02 : 0x00));
  return true;
}

void setup() {
  Serial.begin(115200);
  sensors_begin();
}

void loop() {}
