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

static Adafruit_MLX90640 mlx;
static float mlxFrame[NOVIS_THERMAL_PIXELS];
static bool  mlxOk = false;

#define I2S_CHUNK 256
static int32_t i2sBuf[I2S_CHUNK];

// ---- latest readings, refreshed once a second, served on request ----
static bool     gThermalOk = false;
static int16_t  gThermal[NOVIS_THERMAL_PIXELS];   // centi-Celsius
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

static void sampleAllSensors() {
  if (mlxOk && mlx.getFrame(mlxFrame) == 0) {
    gThermalOk = true;
    for (int i = 0; i < NOVIS_THERMAL_PIXELS; i++) {
      float c = mlxFrame[i];
      if (c < -300.0f) c = -300.0f;
      if (c >  300.0f) c =  300.0f;
      gThermal[i] = (int16_t)(c * 100.0f);
    }
  } else {
    gThermalOk = false;
  }

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
static char   gJson[16384];
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
  jsonAdd("\"thermalOk\":%s,\"sonar\":{\"left\":%u,\"right\":%u},",
          gThermalOk ? "true" : "false", gLeft, gRight);
  jsonAdd("\"peaks\":{\"before\":%ld,\"after\":%ld,\"spike\":%s},",
          (long)gBefore, (long)gAfter, gSpike ? "true" : "false");

  jsonAdd("\"thermal\":[");
  for (int i = 0; i < NOVIS_THERMAL_PIXELS; i++) {
    jsonAdd(i ? ",%d" : "%d", gThermal[i]);
  }
  jsonAdd("],\"echo\":[");
  for (int i = 0; i < NOVIS_ECHO_SAMPLES; i++) {
    jsonAdd(i ? ",%d" : "%d", gEcho[i]);
  }
  jsonAdd("]}");

  server.sendHeader("Cache-Control", "no-store");
  server.send(200, "application/json", gJson);
}

static const char PAGE_HTML[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NOVIS B6 - sensor dashboard</title>
<style>
  :root{
    color-scheme: dark;
    --bg:#080a0e; --panel:#10141b; --line:#1d242f; --line2:#2a3340;
    --txt:#e6ecf3; --dim:#6b7a8d; --dim2:#8fa0b4;
    --thermal:#ff9a3c; --sonar:#38bdf8; --sonar2:#f472b6; --echo:#a78bfa;
    --good:#4ade80; --bad:#f87171;
    --mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
  }
  *{box-sizing:border-box}
  body{
    margin:0; padding:18px 20px 40px;
    background:
      radial-gradient(1200px 500px at 20% -10%, #121a26 0%, transparent 60%),
      var(--bg);
    color:var(--txt);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;
    font-size:14px; line-height:1.45;
  }
  .wrap{max-width:1400px;margin:0 auto}

  /* ---- header ---- */
  header{
    display:flex;align-items:center;gap:18px;flex-wrap:wrap;
    padding-bottom:14px;margin-bottom:18px;
    border-bottom:1px solid var(--line);
  }
  .brand{display:flex;flex-direction:column;gap:2px;margin-right:auto}
  .brand h1{margin:0;font-size:17px;font-weight:650;letter-spacing:.2px}
  .brand .tag{font-size:11px;color:var(--dim);letter-spacing:1.4px;text-transform:uppercase}
  .stat{display:flex;flex-direction:column;gap:1px;min-width:74px}
  .stat b{font-family:var(--mono);font-size:15px;font-weight:600;font-variant-numeric:tabular-nums}
  .stat span{font-size:10px;color:var(--dim);letter-spacing:1.1px;text-transform:uppercase}
  .live{display:flex;align-items:center;gap:7px;font-size:12px;color:var(--dim2)}
  .dot{width:8px;height:8px;border-radius:50%;background:var(--good);box-shadow:0 0 0 0 rgba(74,222,128,.6);animation:ping 1.4s infinite}
  .dot.off{background:var(--bad);animation:none}
  @keyframes ping{0%{box-shadow:0 0 0 0 rgba(74,222,128,.5)}70%{box-shadow:0 0 0 7px rgba(74,222,128,0)}100%{box-shadow:0 0 0 0 rgba(74,222,128,0)}}

  /* ---- panels ---- */
  .grid{display:grid;grid-template-columns:minmax(0,420px) minmax(0,1fr);gap:16px;align-items:start}
  .col{display:grid;gap:16px;min-width:0}
  .panel{
    background:linear-gradient(180deg,#141922 0%,var(--panel) 46%);
    border:1px solid var(--line);border-radius:12px;overflow:hidden;min-width:0;
  }
  .panel>.bar{height:2px;background:var(--line2)}
  .panel.t>.bar{background:linear-gradient(90deg,var(--thermal),transparent 70%)}
  .panel.s>.bar{background:linear-gradient(90deg,var(--sonar),transparent 70%)}
  .panel.e>.bar{background:linear-gradient(90deg,var(--echo),transparent 70%)}
  .panel.d>.bar{background:linear-gradient(90deg,var(--good),transparent 70%)}
  .head{display:flex;align-items:center;gap:10px;padding:12px 16px 0}
  .head h2{margin:0;font-size:12px;font-weight:600;letter-spacing:1.5px;text-transform:uppercase;color:var(--dim2)}
  .head .sp{margin-left:auto;display:flex;gap:8px;align-items:center}
  .body{padding:12px 16px 16px}
  .hint{font-size:11px;color:var(--dim);margin-top:8px;line-height:1.5}

  /* ---- readouts ---- */
  .reads{display:flex;gap:18px;flex-wrap:wrap;margin-bottom:10px}
  .read{display:flex;flex-direction:column}
  .read span{font-size:10px;color:var(--dim);letter-spacing:1.1px;text-transform:uppercase}
  .read b{font-family:var(--mono);font-size:19px;font-weight:600;font-variant-numeric:tabular-nums}
  .read.big b{font-size:30px;letter-spacing:-.5px}
  .read.t b{color:var(--thermal)} .read.l b{color:var(--sonar)} .read.r b{color:var(--sonar2)}

  /* heights must be pinned in CSS: the drawing code sets canvas.height for the
     backing store, which would otherwise change the element's layout height */
  canvas{display:block;width:100%;border-radius:8px;background:#0a0d13;border:1px solid #171d27}
  #cvThermal{height:300px} #cvSonar{height:190px} #cvEcho{height:210px} #cvPeaks{height:110px}
  @media(max-width:980px){ #cvThermal{height:260px} }
  .cbar{height:9px;border-radius:5px;margin-top:9px;border:1px solid #1b222d}
  .cscale{display:flex;justify-content:space-between;font-family:var(--mono);font-size:11px;color:var(--dim);margin-top:4px}

  /* ---- controls ---- */
  button,.btn{
    font:inherit;font-size:12px;color:var(--txt);background:#1a212c;
    border:1px solid var(--line2);border-radius:7px;padding:6px 12px;cursor:pointer;
    transition:.13s;
  }
  button:hover{background:#222b38;border-color:#39465a}
  button.on{background:#16321f;border-color:#2c6b41;color:#86efac}
  button.primary{background:#1d3a5c;border-color:#2f5f92;color:#bfdcff;font-weight:600}
  button.primary:hover{background:#24487094}
  button.danger:hover{background:#3a1c1c;border-color:#7f3a3a;color:#fca5a5}
  input[type=text]{
    font:inherit;font-size:13px;color:var(--txt);background:#0c1016;
    border:1px solid var(--line2);border-radius:7px;padding:7px 11px;min-width:190px;
  }
  input[type=text]:focus{outline:none;border-color:#3b82f6}
  .toggle{font-size:11px;letter-spacing:.4px}

  .pill{
    font-family:var(--mono);font-size:11px;padding:3px 9px;border-radius:20px;
    border:1px solid var(--line2);color:var(--dim2);white-space:nowrap;
  }
  .pill.good{color:#86efac;border-color:#2c6b41;background:#12251a}
  .pill.bad{color:#fca5a5;border-color:#7f3a3a;background:#241414}

  /* ---- dataset ---- */
  .dsrow{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:12px}
  .chips{display:flex;gap:7px;flex-wrap:wrap;margin-top:4px}
  .chip{
    font-family:var(--mono);font-size:11px;padding:4px 10px;border-radius:6px;
    background:#141a23;border:1px solid var(--line2);color:var(--dim2);
  }
  .chip b{color:var(--txt)}
  .dsstat{display:flex;gap:22px;flex-wrap:wrap;padding:11px 14px;background:#0c1016;border:1px solid var(--line);border-radius:9px}
  .warn{font-size:11px;color:#fbbf24;margin-top:10px}

  @media(max-width:980px){ .grid{grid-template-columns:minmax(0,1fr)} }
</style>
</head>
<body>
<div class="wrap">

  <header>
    <div class="brand">
      <h1>NOVIS &mdash; B6 sensor dashboard</h1>
      <div class="tag">thermal &middot; sonar &middot; echolocation &middot; dataset capture</div>
    </div>
    <div class="stat"><b id="hSeq">&mdash;</b><span>frame</span></div>
    <div class="stat"><b id="hUp">&mdash;</b><span>uptime</span></div>
    <div class="stat"><b id="hHeap">&mdash;</b><span>free heap</span></div>
    <div class="stat"><b id="hSamples">0</b><span>captured</span></div>
    <div class="live"><span class="dot" id="hDot"></span><span id="hLive">connecting</span></div>
  </header>

  <div class="grid">

    <!-- ============ THERMAL ============ -->
    <div class="col">
      <section class="panel t">
        <div class="bar"></div>
        <div class="head">
          <h2>Thermal &mdash; MLX90640</h2>
          <div class="sp">
            <span class="pill" id="tStatus">&mdash;</span>
            <button class="toggle" id="btnSmooth">smooth</button>
            <button class="toggle" id="btnLock">auto range</button>
          </div>
        </div>
        <div class="body">
          <div class="reads">
            <div class="read big t"><span>centre</span><b id="tCentre">--.-</b></div>
            <div class="read"><span>min</span><b id="tMin">--.-</b></div>
            <div class="read"><span>max</span><b id="tMax">--.-</b></div>
            <div class="read"><span>hotspot</span><b id="tHot">--,--</b></div>
          </div>
          <canvas id="cvThermal" height="360"></canvas>
          <div class="cbar" id="cbar"></div>
          <div class="cscale"><span id="cbLo">--</span><span id="cbHi">--</span></div>
          <div class="hint">32&times;24 pixels, 8&nbsp;Hz sensor, drawn from the raw centi-Celsius frame &mdash; the same array a captured sample stores.</div>
        </div>
      </section>
    </div>

    <div class="col">
      <!-- ============ SONAR ============ -->
      <section class="panel s">
        <div class="bar"></div>
        <div class="head">
          <h2>Sonar &mdash; HC-SR04 &times;2</h2>
          <div class="sp"><span class="pill" id="sInfo">rolling 90 frames</span></div>
        </div>
        <div class="body">
          <div class="reads">
            <div class="read big l"><span>left</span><b id="sLeft">---- mm</b></div>
            <div class="read big r"><span>right</span><b id="sRight">---- mm</b></div>
            <div class="read"><span>&Delta; left&minus;right</span><b id="sDelta">---- mm</b></div>
          </div>
          <canvas id="cvSonar" height="190"></canvas>
          <div class="hint">A reading of <b>0&nbsp;mm</b> means no echo returned inside the 30&nbsp;ms timeout &mdash; plotted as a gap, not as zero distance.</div>
        </div>
      </section>

      <!-- ============ ECHO ============ -->
      <section class="panel e">
        <div class="bar"></div>
        <div class="head">
          <h2>Echolocation &mdash; chirp return</h2>
          <div class="sp"><span class="pill" id="eBadge">&mdash;</span></div>
        </div>
        <div class="body">
          <div class="reads">
            <div class="read"><span>peak before</span><b id="eBefore">------</b></div>
            <div class="read"><span>peak after</span><b id="eAfter">------</b></div>
            <div class="read"><span>ratio</span><b id="eRatio">--.-&times;</b></div>
            <div class="read"><span>first return</span><b id="eFirst">--- mm</b></div>
          </div>
          <canvas id="cvEcho" height="200"></canvas>
          <div class="hint">960 samples @ 16&nbsp;kHz (60&nbsp;ms) captured straight after the 5&nbsp;ms chirp. The lower axis is round-trip distance &mdash; a bump at 2&nbsp;m means a surface about 2&nbsp;m away reflected the chirp. The shaded strip on the left is the chirp reaching the mic directly through the air; <b>first return</b> is measured after it, so it reports a real surface rather than the speaker.</div>
          <canvas id="cvPeaks" height="110" style="margin-top:12px"></canvas>
          <div class="hint">Peak history: faint bar = ambient before the chirp, solid bar = loudest sample after. Green when the return is more than double the ambient.</div>
        </div>
      </section>
    </div>
  </div>

  <!-- ============ DATASET ============ -->
  <section class="panel d" style="margin-top:16px">
    <div class="bar"></div>
    <div class="head">
      <h2>Dataset capture</h2>
      <div class="sp"><span class="pill" id="dsPill">0 samples</span></div>
    </div>
    <div class="body">
      <div class="dsrow">
        <input type="text" id="dsLabel" placeholder="label, e.g. empty-room / person-1m / wall-2m">
        <button class="primary" id="btnCapture">Capture sample</button>
        <button id="btnAuto">Auto-capture: off</button>
        <button id="btnJson">Download .json</button>
        <button id="btnCsv">Download summary .csv</button>
        <button class="danger" id="btnClear">Clear</button>
      </div>
      <div class="dsstat">
        <div class="read"><span>samples</span><b id="dsCount">0</b></div>
        <div class="read"><span>labels</span><b id="dsLabels">0</b></div>
        <div class="read"><span>approx size</span><b id="dsSize">0 KB</b></div>
        <div class="read"><span>last capture</span><b id="dsLast">&mdash;</b></div>
      </div>
      <div class="chips" id="dsChips"></div>
      <div class="hint">Each sample stores the full 768-pixel thermal frame, both sonar ranges, the 960-sample echo window and its peaks, plus the label and device timestamp. The download also carries a metadata header (pin plan, units, sample rate, chirp spec) so the file documents itself.</div>
      <div class="warn">Samples live in this browser tab only &mdash; download before closing or reloading the page.</div>
    </div>
  </section>
</div>

<script>
const TW = 32, TH = 24, ECHO_N = 960, SR = 16000, SOUND = 343;
const HIST = 90;
const BLANK = 96;   // 6 ms: the 5 ms chirp plus ringdown, heard directly by the mic

const S = {
  last:null, seq:-1, sonar:[], peaks:[], dataset:[],
  smooth:true, lock:false, lockLo:20, lockHi:35, auto:false, live:false
};

const $ = id => document.getElementById(id);

/* ---------- inferno-style ramp, shared by heatmap and colourbar ---------- */
const STOPS = [[0,8,5,30],[0.15,44,17,96],[0.3,87,21,126],[0.45,138,34,106],
               [0.6,186,54,85],[0.75,224,92,47],[0.88,248,149,64],[1,252,255,164]];
function ramp(t){
  t = t<0?0:t>1?1:t;
  for(let i=1;i<STOPS.length;i++){
    if(t<=STOPS[i][0]){
      const a=STOPS[i-1], b=STOPS[i];
      const k=(t-a[0])/(b[0]-a[0]);
      return [a[1]+(b[1]-a[1])*k, a[2]+(b[2]-a[2])*k, a[3]+(b[3]-a[3])*k];
    }
  }
  return [252,255,164];
}
$('cbar').style.background = 'linear-gradient(90deg,' +
  STOPS.map(s=>`rgb(${s[1]},${s[2]},${s[3]}) ${(s[0]*100).toFixed(0)}%`).join(',') + ')';

/* ---------- canvas helpers ---------- */
function fit(cv){
  const dpr = window.devicePixelRatio || 1;
  const w = cv.clientWidth, h = cv.clientHeight;
  if(cv.width !== Math.round(w*dpr) || cv.height !== Math.round(h*dpr)){
    cv.width = Math.round(w*dpr); cv.height = Math.round(h*dpr);
  }
  const ctx = cv.getContext('2d');
  ctx.setTransform(dpr,0,0,dpr,0,0);
  ctx.clearRect(0,0,w,h);
  return {ctx,w,h};
}
function gridlines(ctx,w,h,rows){
  ctx.strokeStyle='#161d27'; ctx.lineWidth=1;
  for(let i=0;i<=rows;i++){
    const y = Math.round(h*i/rows)+0.5;
    ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(w,y); ctx.stroke();
  }
}
function label(ctx,text,x,y,color,align){
  ctx.fillStyle=color; ctx.font='11px ui-monospace,Menlo,Consolas,monospace';
  ctx.textAlign=align||'left'; ctx.textBaseline='middle'; ctx.fillText(text,x,y);
}

/* ---------- thermal heatmap ---------- */
const off = document.createElement('canvas'); off.width=TW; off.height=TH;
const offCtx = off.getContext('2d');
const img = offCtx.createImageData(TW,TH);

function drawThermal(arr){
  const cv = $('cvThermal');
  const dpr = window.devicePixelRatio || 1;
  const w = cv.clientWidth, h = cv.clientHeight;
  if(cv.width!==Math.round(w*dpr)||cv.height!==Math.round(h*dpr)){
    cv.width=Math.round(w*dpr); cv.height=Math.round(h*dpr);
  }
  const ctx = cv.getContext('2d');
  ctx.setTransform(1,0,0,1,0,0);
  ctx.clearRect(0,0,cv.width,cv.height);
  if(!arr){ return; }

  let lo=1e9, hi=-1e9, hotIdx=0;
  for(let i=0;i<arr.length;i++){
    if(arr[i]<lo) lo=arr[i];
    if(arr[i]>hi){ hi=arr[i]; hotIdx=i; }
  }
  let dLo = lo/100, dHi = hi/100;
  if(S.lock){ dLo = S.lockLo; dHi = S.lockHi; }
  const span = Math.max(0.1, dHi-dLo);

  for(let i=0;i<TW*TH;i++){
    const c = ramp((arr[i]/100 - dLo)/span);
    img.data[i*4]=c[0]; img.data[i*4+1]=c[1]; img.data[i*4+2]=c[2]; img.data[i*4+3]=255;
  }
  offCtx.putImageData(img,0,0);
  ctx.imageSmoothingEnabled = S.smooth;
  ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(off,0,0,cv.width,cv.height);

  // hotspot crosshair, in device pixels
  const hx = ((hotIdx%TW)+0.5)/TW*cv.width, hy = (Math.floor(hotIdx/TW)+0.5)/TH*cv.height;
  const r = 9*dpr;
  ctx.strokeStyle='rgba(255,255,255,.85)'; ctx.lineWidth=1.5*dpr;
  ctx.beginPath(); ctx.arc(hx,hy,r,0,Math.PI*2); ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(hx-r*1.9,hy); ctx.lineTo(hx-r*0.6,hy);
  ctx.moveTo(hx+r*0.6,hy); ctx.lineTo(hx+r*1.9,hy);
  ctx.moveTo(hx,hy-r*1.9); ctx.lineTo(hx,hy-r*0.6);
  ctx.moveTo(hx,hy+r*0.6); ctx.lineTo(hx,hy+r*1.9);
  ctx.stroke();

  $('tCentre').textContent = (arr[12*TW+16]/100).toFixed(1)+'°C';
  $('tMin').textContent = (lo/100).toFixed(1)+'°C';
  $('tMax').textContent = (hi/100).toFixed(1)+'°C';
  $('tHot').textContent = (hotIdx%TW)+','+Math.floor(hotIdx/TW);
  $('cbLo').textContent = dLo.toFixed(1)+'°C';
  $('cbHi').textContent = dHi.toFixed(1)+'°C';
}

/* ---------- sonar rolling chart ---------- */
function drawSonar(){
  const {ctx,w,h} = fit($('cvSonar'));
  const pad = 12;
  const d = S.sonar;

  let max = 100;
  for(const p of d){ if(p.l>max) max=p.l; if(p.r>max) max=p.r; }
  max = Math.ceil(max/500)*500;

  const px = i => (i/(HIST-1))*w;
  const py = v => (h-pad) - (v/max)*(h-pad*2);

  ctx.strokeStyle='#161d27'; ctx.lineWidth=1;
  for(let i=0;i<=4;i++){
    const v = max*(4-i)/4, y = Math.round(py(v))+0.5;
    ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(w,y); ctx.stroke();
    label(ctx, (v/1000).toFixed(1)+'m', 6, y-7, '#4a5666');
  }
  if(!d.length) return;

  const trace = (key,color) => {
    ctx.strokeStyle=color; ctx.lineWidth=1.8; ctx.lineJoin='round';
    ctx.beginPath();
    let pen = false;
    d.forEach((p,i)=>{
      const v = p[key];
      const x = px(i + (HIST - d.length));
      if(v<=0){ pen=false; return; }        // 0 = timeout, leave a gap
      if(!pen){ ctx.moveTo(x,py(v)); pen=true; } else ctx.lineTo(x,py(v));
    });
    ctx.stroke();
    const lastV = d[d.length-1][key];
    if(lastV>0){
      const x = px(HIST-1), y = py(lastV);
      ctx.fillStyle=color; ctx.beginPath(); ctx.arc(x,y,3,0,Math.PI*2); ctx.fill();
    }
  };
  trace('l','#38bdf8');
  trace('r','#f472b6');
}

/* ---------- echo waveform, on a distance axis ---------- */
function drawEcho(echo){
  const {ctx,w,h} = fit($('cvEcho'));
  const mid = h*0.52, amp = h*0.42;

  // distance gridlines every 2 m of round trip
  const maxMs = ECHO_N/SR*1000, maxM = SOUND*(maxMs/1000)/2;
  ctx.strokeStyle='#161d27'; ctx.lineWidth=1;
  for(let m=0;m<=maxM;m+=2){
    const x = Math.round((m/maxM)*w)+0.5;
    ctx.beginPath(); ctx.moveTo(x,0); ctx.lineTo(x,h-14); ctx.stroke();
    if(m>0 && x < w-26) label(ctx, m+'m', x+4, h-7, '#4a5666');
  }

  // The speaker sits centimetres from the mic, so the chirp reaches it directly.
  // Anything inside this window is that direct path, never a room echo.
  const bx = (BLANK/ECHO_N)*w;
  ctx.fillStyle='rgba(120,132,155,.09)';
  ctx.fillRect(0,0,bx,h-14);
  label(ctx,'chirp',3,h-7,'#4a5666');

  ctx.strokeStyle='#232c39';
  ctx.beginPath(); ctx.moveTo(0,mid+0.5); ctx.lineTo(w,mid+0.5); ctx.stroke();
  if(!echo) return;

  // min/max envelope per pixel column - proper way to show 960 samples in ~700px
  const per = ECHO_N/w;
  const grad = ctx.createLinearGradient(0,mid-amp,0,mid+amp);
  grad.addColorStop(0,'#c4b5fd'); grad.addColorStop(0.5,'#a78bfa'); grad.addColorStop(1,'#c4b5fd');
  ctx.strokeStyle = grad; ctx.lineWidth = 1;
  for(let x=0;x<w;x++){
    let lo=0, hi=0;
    const s = Math.floor(x*per), e = Math.min(ECHO_N, Math.floor((x+1)*per)+1);
    for(let i=s;i<e;i++){ const v=echo[i]; if(v<lo)lo=v; if(v>hi)hi=v; }
    const y1 = mid - (hi/32768)*amp, y2 = mid - (lo/32768)*amp;
    ctx.beginPath(); ctx.moveTo(x+0.5,y1); ctx.lineTo(x+0.5,Math.max(y2,y1+0.7)); ctx.stroke();
  }

  // First sample after the chirp window that clears the noise floor: the
  // nearest surface that reflected the chirp back. Noise floor comes from the
  // quiet tail, so a loud room raises the bar instead of triggering on itself.
  let acc = 0, n = 0;
  for(let i=Math.floor(ECHO_N*0.75);i<ECHO_N;i++){ acc += echo[i]*echo[i]; n++; }
  const rms = Math.sqrt(acc/Math.max(1,n));
  let peakPost = 0;
  for(let i=BLANK;i<ECHO_N;i++){ const a=Math.abs(echo[i]); if(a>peakPost) peakPost=a; }
  const thr = Math.max(rms*4, peakPost*0.25);
  let first = -1;
  for(let i=BLANK;i<ECHO_N;i++){ if(Math.abs(echo[i])>thr){ first=i; break; } }
  if(first>=0){
    const x = (first/ECHO_N)*w;
    ctx.strokeStyle='#4ade80'; ctx.lineWidth=1.5; ctx.setLineDash([4,3]);
    ctx.beginPath(); ctx.moveTo(x,0); ctx.lineTo(x,h-14); ctx.stroke(); ctx.setLineDash([]);
    const mm = Math.round(SOUND*(first/SR)/2*1000);
    label(ctx, mm+'mm', x+5, 11, '#4ade80');
    $('eFirst').textContent = mm+' mm';
  } else {
    $('eFirst').textContent = '—';
  }
}

/* ---------- peak history bars ---------- */
function drawPeaks(){
  const {ctx,w,h} = fit($('cvPeaks'));
  const d = S.peaks; if(!d.length) return;
  let max = 1;
  for(const p of d){ max = Math.max(max, p.after, p.before); }
  const n = 40, start = Math.max(0, d.length-n);
  const slot = w/n;
  d.slice(start).forEach((p,i)=>{
    const x = i*slot, bw = Math.max(3, slot*0.62);
    const hb = (p.before/max)*(h-16), ha = (p.after/max)*(h-16);
    ctx.fillStyle = 'rgba(148,163,184,.28)';
    ctx.fillRect(x, h-16-hb, bw, hb);
    ctx.fillStyle = p.spike ? '#4ade80' : '#64748b';
    ctx.fillRect(x, h-16-ha, bw*0.55, ha);
  });
  ctx.strokeStyle='#232c39';
  ctx.beginPath(); ctx.moveTo(0,h-15.5); ctx.lineTo(w,h-15.5); ctx.stroke();
  label(ctx, 'peak before (faint) vs after (solid)', 4, h-6, '#4a5666');
}

/* ---------- polling ---------- */
function fmtUptime(ms){
  const s = Math.floor(ms/1000);
  return String(Math.floor(s/60)).padStart(2,'0')+':'+String(s%60).padStart(2,'0');
}
function setLive(on){
  S.live = on;
  $('hDot').className = 'dot'+(on?'':' off');
  $('hLive').textContent = on ? 'live' : 'connection lost';
}

async function poll(){
  try{
    const r = await fetch('/frame',{cache:'no-store'});
    const d = await r.json();
    setLive(true);
    const isNew = d.seq !== S.seq;
    S.seq = d.seq; S.last = d;

    if(isNew){
      S.sonar.push({l:d.sonar.left, r:d.sonar.right});
      if(S.sonar.length>HIST) S.sonar.shift();
      S.peaks.push({before:d.peaks.before, after:d.peaks.after, spike:d.peaks.spike});
      if(S.peaks.length>HIST) S.peaks.shift();
      if(S.auto) capture(true);
    }

    $('hSeq').textContent = d.seq;
    $('hUp').textContent = fmtUptime(d.tMs);
    $('hHeap').textContent = (d.heap/1024).toFixed(0)+'K';

    const st = $('tStatus');
    st.textContent = d.thermalOk ? 'sensor OK' : 'NOT FOUND';
    st.className = 'pill '+(d.thermalOk?'good':'bad');

    $('sLeft').textContent  = (d.sonar.left ?d.sonar.left +' mm':'no echo');
    $('sRight').textContent = (d.sonar.right?d.sonar.right+' mm':'no echo');
    $('sDelta').textContent = (d.sonar.left&&d.sonar.right)
      ? (d.sonar.left-d.sonar.right)+' mm' : '—';

    $('eBefore').textContent = d.peaks.before.toLocaleString();
    $('eAfter').textContent  = d.peaks.after.toLocaleString();
    const ratio = d.peaks.before>0 ? d.peaks.after/d.peaks.before : 0;
    $('eRatio').textContent = ratio.toFixed(2)+'×';
    const badge = $('eBadge');
    badge.textContent = d.peaks.spike ? 'echo return detected' : 'no clear return';
    badge.className = 'pill '+(d.peaks.spike?'good':'bad');

    drawThermal(d.thermalOk ? d.thermal : null);
    drawSonar();
    drawEcho(d.echo);
    drawPeaks();
  }catch(e){ setLive(false); }
}

/* ---------- dataset ---------- */
function capture(silent){
  const d = S.last;
  if(!d){ return; }
  const label = ($('dsLabel').value || 'unlabelled').trim();
  S.dataset.push({
    label, seq:d.seq, deviceMs:d.tMs, wallClock:new Date().toISOString(),
    thermalOk:d.thermalOk, thermal:d.thermal,
    sonarLeftMm:d.sonar.left, sonarRightMm:d.sonar.right,
    echo:d.echo, peakBefore:d.peaks.before, peakAfter:d.peaks.after, spike:d.peaks.spike
  });
  $('dsLast').textContent = new Date().toLocaleTimeString();
  refreshDataset();
}
function refreshDataset(){
  const n = S.dataset.length;
  const counts = {};
  S.dataset.forEach(s => counts[s.label] = (counts[s.label]||0)+1);
  $('dsCount').textContent = n;
  $('hSamples').textContent = n;
  $('dsLabels').textContent = Object.keys(counts).length;
  $('dsPill').textContent = n+' sample'+(n===1?'':'s');
  $('dsSize').textContent = ((n*8.4)).toFixed(0)+' KB';
  $('dsChips').innerHTML = Object.entries(counts)
    .map(([k,v])=>`<span class="chip">${k} <b>${v}</b></span>`).join('');
}
function meta(){
  return {
    device:'ESP32-WROOM-32', project:'NOVIS', capturedWith:'firmware/dashboard/dashboard.ino',
    thermal:{sensor:'MLX90640', width:TW, height:TH, order:'row-major',
             unit:'centi-Celsius', note:'divide by 100 for degrees C', refreshHz:8},
    sonar:{sensor:'HC-SR04 x2', unit:'mm', zeroMeans:'no echo within the 30 ms timeout'},
    echo:{mic:'INMP441', samples:ECHO_N, sampleRateHz:SR, format:'int16 mono',
          window:'captured immediately after the chirp, DMA flushed first',
          chirp:'5 ms, 1 kHz to 8 kHz, PAM8302 + speaker on GPIO4'},
    pins:{sda:21,scl:22,trigLeft:16,echoLeft:17,trigRight:18,echoRight:19,
          i2sSck:14,i2sWs:15,i2sSd:32,speaker:4},
    exportedAt:new Date().toISOString()
  };
}
function download(name, text, type){
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([text],{type}));
  a.download = name; a.click(); URL.revokeObjectURL(a.href);
}
function stamp(){ return new Date().toISOString().replace(/[:.]/g,'-').slice(0,19); }

/* ---------- wiring ---------- */
$('btnCapture').onclick = ()=>capture(false);
$('btnAuto').onclick = e => {
  S.auto = !S.auto;
  e.target.textContent = 'Auto-capture: '+(S.auto?'on':'off');
  e.target.className = S.auto?'on':'';
};
$('btnSmooth').onclick = e => { S.smooth=!S.smooth; e.target.className=S.smooth?'toggle on':'toggle';
  if(S.last) drawThermal(S.last.thermal); };
$('btnLock').onclick = e => {
  S.lock = !S.lock;
  if(S.lock && S.last && S.last.thermal){
    let lo=1e9,hi=-1e9;
    for(const v of S.last.thermal){ if(v<lo)lo=v; if(v>hi)hi=v; }
    S.lockLo = lo/100; S.lockHi = hi/100;
  }
  e.target.textContent = S.lock ? 'range locked' : 'auto range';
  e.target.className = S.lock?'toggle on':'toggle';
  if(S.last) drawThermal(S.last.thermal);
};
$('btnJson').onclick = ()=>{
  if(!S.dataset.length) return;
  download('novis_dataset_'+stamp()+'.json',
    JSON.stringify({meta:meta(), samples:S.dataset}), 'application/json');
};
$('btnCsv').onclick = ()=>{
  if(!S.dataset.length) return;
  const rows = ['label,seq,deviceMs,wallClock,sonarLeftMm,sonarRightMm,peakBefore,peakAfter,spike,thermalMinC,thermalMaxC,thermalCentreC'];
  S.dataset.forEach(s=>{
    let lo=1e9,hi=-1e9;
    for(const v of s.thermal){ if(v<lo)lo=v; if(v>hi)hi=v; }
    rows.push([s.label,s.seq,s.deviceMs,s.wallClock,s.sonarLeftMm,s.sonarRightMm,
      s.peakBefore,s.peakAfter,s.spike,(lo/100).toFixed(2),(hi/100).toFixed(2),
      (s.thermal[12*TW+16]/100).toFixed(2)].join(','));
  });
  download('novis_summary_'+stamp()+'.csv', rows.join('\n'), 'text/csv');
};
$('btnClear').onclick = ()=>{
  if(S.dataset.length && confirm('Delete all '+S.dataset.length+' captured samples?')){
    S.dataset = []; refreshDataset(); $('dsLast').textContent='—';
  }
};
$('btnSmooth').className = 'toggle on';
window.addEventListener('resize', ()=>{
  if(!S.last) return;
  drawThermal(S.last.thermal); drawSonar(); drawEcho(S.last.echo); drawPeaks();
});

refreshDataset();
poll();
setInterval(poll, 700);
</script>
</body>
</html>
)rawliteral";

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
