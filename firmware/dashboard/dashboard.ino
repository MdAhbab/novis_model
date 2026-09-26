/*
  NOVIS live dashboard + dataset capture (ESP32)

  Grew out of the B6 full-module bring-up test
  (firmware/bench_tests/B6_full_module_test/) into a standing tool: this is
  what's actually used now to watch the assembled module live and to collect
  the labelled dataset for the paper, not just a one-time pass/fail check -
  that's why it lives here under firmware/dashboard/ instead of in
  bench_tests/ with the one-component tests. Same sensors, same B6 pin plan;
  see docs/NOVIS_Final_Module_Build.md section 6 for the pass criteria this
  was originally built to verify, and docs/hardware_log.md section 8 for the
  two hardware/firmware faults found while getting this running (a loose
  ground, and a WiFi/I2C startup-ordering bug - the latter matters for
  novis_node.ino's eventual BLE port too: init sensors before the radio).

  What this shows, beyond summary numbers -
    - the full 32x24 thermal frame drawn as a live heatmap
    - both sonar ranges as a rolling time-series
    - the full post-chirp echo waveform, on a round-trip distance axis
  and lets you label and download captured samples as a dataset file,
  so data collection happens from the browser instead of by hand.

  Capture rules the page enforces, so the export needs no cleaning later
  (see docs/data_collection_protocol.md):
    - one sample per new sensor frame; the same frame is never stored twice
    - capture is refused while thermal reads NOT FOUND or the frame is stale
    - "Capture a scene" takes a fixed 25 samples and stops on its own
    - the browser warns before unload while samples are not yet downloaded

  The payload deliberately matches what firmware/novis_node/sensors.cpp is
  specified to produce, so samples captured here are shaped like production
  data: thermal in centi-Celsius (int16, value/100 = degrees C) and
  NOVIS_ECHO_SAMPLES of 16-bit mono audio at 16 kHz.

  ESP32 becomes its own WiFi hotspot (no home router password needed):
    1. Flash this over USB as normal.
    2. Unplug USB, power the board from the battery (see docs/
       NOVIS_Final_Module_Build.md section 7).
    3. On your laptop or phone, connect to WiFi network "NOVIS-B6"
       (password below).
    4. Open a browser to http://192.168.4.1/

  Note: the page has no external images/fonts/scripts - everything is
  inline - because the ESP32 hotspot has no internet passthrough, so any
  external resource would just fail to load.
*/

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_MLX90640.h>
#include <driver/i2s.h>
#include <WiFi.h>
#include <WebServer.h>
#include <stdarg.h>

#define NOVIS_THERMAL_PIXELS (32 * 24)
#define NOVIS_ECHO_SAMPLES   960   // 60 ms at 16 kHz - matches sensors.cpp's planned capture
#define NOVIS_SAMPLE_RATE    16000

// ---- PIN ASSIGNMENTS - the B6 pin plan ----
#define I2C_SDA_PIN   21
#define I2C_SCL_PIN   22

// Second thermal sensor ("BAB"): wide-FOV/short-range MLX90640 modules and
// narrow-FOV/long-range ones are complementary, not interchangeable, so both
// get wired rather than picking one. They cannot share a bus - GY-MCU90640
// modules answer at the fixed address 0x33, so two on one bus would collide
// - hence a second, independent I2C bus on ESP32's I2C1 peripheral (`Wire1`,
// built into the core, distinct from the default `Wire`/I2C0 used above).
// GPIO33/25 are free in the B6 pin plan and are not strapping pins.
#define I2C2_SDA_PIN  33
#define I2C2_SCL_PIN  25

#define TRIG_LEFT     16
#define ECHO_LEFT     17
#define TRIG_RIGHT    18
#define ECHO_RIGHT    19
#define I2S_SCK_PIN   14
#define I2S_WS_PIN    15
#define I2S_SD_PIN    32
#define SPEAKER_PIN   4
#define I2S_PORT      I2S_NUM_0

// ---- WiFi AP settings ----
static const char *AP_SSID = "NOVIS-B6";
static const char *AP_PASS = "novis1234";   // WiFi AP passwords need >= 8 chars

static WebServer server(80);

static Adafruit_MLX90640 mlx;                 // BAA: wide FOV, shorter usable range
static float mlxFrame[NOVIS_THERMAL_PIXELS];
static bool  mlxOk = false;

static Adafruit_MLX90640 mlxFar;              // BAB: narrower FOV, longer usable range
static TwoWire WireFar = TwoWire(1);
static float mlxFarFrame[NOVIS_THERMAL_PIXELS];
static bool  mlxFarOk = false;

#define I2S_CHUNK 256
static int32_t i2sBuf[I2S_CHUNK];

// ---- latest readings, refreshed once a second, served on request ----
static bool     gThermalOk = false;
static int16_t  gThermal[NOVIS_THERMAL_PIXELS];    // centi-Celsius - BAA (wide/near)
static bool     gThermalFarOk = false;
static int16_t  gThermalFar[NOVIS_THERMAL_PIXELS]; // centi-Celsius - BAB (narrow/far)
static int16_t  gEcho[NOVIS_ECHO_SAMPLES];        // 16-bit mono, post-chirp window
static uint16_t gLeft = 0, gRight = 0;
static int32_t  gBefore = 0, gAfter = 0;
static bool     gSpike = false;
static uint32_t gSeq = 0;
static unsigned long gLastUpdateMs = 0;

static void i2sBegin() {
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = NOVIS_SAMPLE_RATE,
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
// 24-bit scale, so it stays comparable with the plain B6 test's numbers.
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

// Ambient peak, then chirp, then keep the whole returning window.
static void captureEcho() {
  gBefore = i2sReadPeak();

  // The RX DMA holds up to 64 ms of already-recorded audio. Without this the
  // "post-chirp" window would start with sound from before the chirp.
  i2s_zero_dma_buffer(I2S_PORT);
  emitChirp();

  int written = 0;
  int32_t peak24 = 0;
  while (written < NOVIS_ECHO_SAMPLES) {
    size_t bytesRead = 0;
    i2s_read(I2S_PORT, i2sBuf, sizeof(i2sBuf), &bytesRead, portMAX_DELAY);
    int n = bytesRead / sizeof(int32_t);
    for (int i = 0; i < n && written < NOVIS_ECHO_SAMPLES; i++) {
      int32_t s24 = i2sBuf[i] >> 8;
      int32_t mag = s24 < 0 ? -s24 : s24;
      if (mag > peak24) peak24 = mag;

      int32_t s16 = s24 >> 8;
      if (s16 >  32767) s16 =  32767;
      if (s16 < -32768) s16 = -32768;
      gEcho[written++] = (int16_t)s16;
    }
  }

  gAfter = peak24;
  gSpike = (gAfter > gBefore * 2);
}

// Shared by both MLX90640 units - same sensor, same conversion, different bus.
static void readThermalInto(Adafruit_MLX90640 &sensor, bool ok, float *frame,
                            int16_t *out, bool *outOk) {
  if (ok && sensor.getFrame(frame) == 0) {
    *outOk = true;
    for (int i = 0; i < NOVIS_THERMAL_PIXELS; i++) {
      float c = frame[i];
      if (c < -300.0f) c = -300.0f;
      if (c >  300.0f) c =  300.0f;
      out[i] = (int16_t)(c * 100.0f);
    }
  } else {
    *outOk = false;
  }
}

static void sampleAllSensors() {
  readThermalInto(mlx,    mlxOk,    mlxFrame,    gThermal,    &gThermalOk);
  readThermalInto(mlxFar, mlxFarOk, mlxFarFrame, gThermalFar, &gThermalFarOk);

  gLeft  = readRange(TRIG_LEFT, ECHO_LEFT);
  delayMicroseconds(3000);
  gRight = readRange(TRIG_RIGHT, ECHO_RIGHT);

  captureEcho();

  gSeq++;
  gLastUpdateMs = millis();
}

// ---------------------------------------------------------------
// JSON frame - one consistent snapshot of every sensor
// ---------------------------------------------------------------
// Sized for two thermal arrays (768 values each) + one echo array (960
// values) + the small fixed fields around them; ~14.8 KB typical, so this
// leaves real headroom rather than sitting right at the edge.
static char   gJson[20480];
static size_t gJsonLen = 0;

static void jsonReset() { gJsonLen = 0; gJson[0] = '\0'; }

static void jsonAdd(const char *fmt, ...) {
  if (gJsonLen >= sizeof(gJson) - 1) return;
  va_list ap;
  va_start(ap, fmt);
  int n = vsnprintf(gJson + gJsonLen, sizeof(gJson) - gJsonLen, fmt, ap);
  va_end(ap);
  if (n > 0) {
    gJsonLen += (size_t)n;
    if (gJsonLen > sizeof(gJson) - 1) gJsonLen = sizeof(gJson) - 1;
  }
}

static void handleFrame() {
  jsonReset();
  jsonAdd("{\"seq\":%lu,\"tMs\":%lu,\"ageMs\":%lu,\"heap\":%lu,",
          (unsigned long)gSeq, (unsigned long)gLastUpdateMs,
          (unsigned long)(millis() - gLastUpdateMs),
          (unsigned long)ESP.getFreeHeap());
  jsonAdd("\"thermalOk\":%s,\"thermalFarOk\":%s,\"sonar\":{\"left\":%u,\"right\":%u},",
          gThermalOk ? "true" : "false", gThermalFarOk ? "true" : "false",
          gLeft, gRight);
  jsonAdd("\"peaks\":{\"before\":%ld,\"after\":%ld,\"spike\":%s},",
          (long)gBefore, (long)gAfter, gSpike ? "true" : "false");

  jsonAdd("\"thermal\":[");
  for (int i = 0; i < NOVIS_THERMAL_PIXELS; i++) {
    jsonAdd(i ? ",%d" : "%d", gThermal[i]);
  }
  jsonAdd("],\"thermalFar\":[");
  for (int i = 0; i < NOVIS_THERMAL_PIXELS; i++) {
    jsonAdd(i ? ",%d" : "%d", gThermalFar[i]);
  }
  jsonAdd("],\"echo\":[");
  for (int i = 0; i < NOVIS_ECHO_SAMPLES; i++) {
    jsonAdd(i ? ",%d" : "%d", gEcho[i]);
  }
  jsonAdd("]}");

  server.sendHeader("Cache-Control", "no-store");
  server.send(200, "application/json", gJson);
}

#include "page_html.h"

static void handleRoot() {
  server.send_P(200, "text/html", PAGE_HTML);
}

void setup() {
  Serial.begin(115200);
  delay(2000);
  Serial.println("=== NOVIS B6 dashboard + dataset capture ===");

  // Sensors first, WiFi last. MLX90640's begin() does one long I2C burst
  // read (its full calibration EEPROM) right at startup - that read was
  // failing intermittently when the WiFi radio was already transmitting
  // beacons during it (confirmed by isolation: the plain B2_thermal test,
  // which has no WiFi at all, always passes; this sketch's earlier version
  // started WiFi.softAP() before Wire.begin()/mlx.begin() and would
  // sometimes report thermal NOT FOUND even on clean USB power). Once
  // MLX90640 is initialised, its per-frame getFrame() reads coexist with
  // WiFi fine, same as the rest of this dashboard's normal operation - only
  // that first heavy read needs the radio quiet.
  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
  Wire.setClock(400000);   // required for 8 Hz thermal frames, see hardware_log.md section 4
  mlxOk = mlx.begin(MLX90640_I2CADDR_DEFAULT, &Wire);
  if (mlxOk) {
    mlx.setMode(MLX90640_CHESS);
    mlx.setResolution(MLX90640_ADC_18BIT);
    mlx.setRefreshRate(MLX90640_8_HZ);
    Serial.println("Thermal (BAA, wide/near): MLX90640 found.");
  } else {
    Serial.println("Thermal (BAA): NOT FOUND - check PS is tied to GND (power-cycle "
                    "after wiring it), check the 4.7k pull-ups on SDA/SCL.");
  }

  // BAB on its own bus (see I2C2_SDA_PIN/I2C2_SCL_PIN above) - same init
  // sequence, same quirks, independent of BAA so one failing doesn't affect
  // the other.
  WireFar.begin(I2C2_SDA_PIN, I2C2_SCL_PIN);
  WireFar.setClock(400000);
  mlxFarOk = mlxFar.begin(MLX90640_I2CADDR_DEFAULT, &WireFar);
  if (mlxFarOk) {
    mlxFar.setMode(MLX90640_CHESS);
    mlxFar.setResolution(MLX90640_ADC_18BIT);
    mlxFar.setRefreshRate(MLX90640_8_HZ);
    Serial.println("Thermal (BAB, narrow/far): MLX90640 found.");
  } else {
    Serial.println("Thermal (BAB): NOT FOUND - check PS tied to GND, pull-ups, and "
                    "that it's wired to GPIO33/25, not the BAA bus.");
  }

  pinMode(TRIG_LEFT,  OUTPUT);
  pinMode(ECHO_LEFT,  INPUT);
  pinMode(TRIG_RIGHT, OUTPUT);
  pinMode(ECHO_RIGHT, INPUT);
  pinMode(SPEAKER_PIN, OUTPUT);
  digitalWrite(TRIG_LEFT,  LOW);
  digitalWrite(TRIG_RIGHT, LOW);

  i2sBegin();

  WiFi.softAP(AP_SSID, AP_PASS);
  // Lower TX power = smaller current spike on every WiFi transmit. On
  // battery this spike, especially if it lands at the same instant as the
  // PAM8302/speaker chirp, is a suspected cause of brownout resets - see
  // docs/hardware_log.md section 9. Fine for the few-metre range this test
  // needs; raise it back towards WIFI_POWER_19_5dBm if the AP won't reach
  // your phone/laptop from where you're standing.
  WiFi.setTxPower(WIFI_POWER_11dBm);
  IPAddress ip = WiFi.softAPIP();
  Serial.printf("WiFi AP \"%s\" started, password \"%s\".\n", AP_SSID, AP_PASS);
  Serial.printf("Open a browser to http://%s/\n", ip.toString().c_str());

  server.on("/", handleRoot);
  server.on("/frame", handleFrame);
  server.begin();

  Serial.println("Setup done. Open the dashboard in a browser to watch readings.");
}

void loop() {
  server.handleClient();

  static unsigned long lastSample = 0;
  if (millis() - lastSample >= 1000) {
    sampleAllSensors();
    lastSample = millis();
  }
}
