/*
  The dashboard page, kept out of dashboard.ino on purpose.

  Arduino only runs its ctags-based prototype generator on .ino files, and
  that generator does not understand C++ raw string literals - it reads the
  HTML/JS inside one as if it were code. A single apostrophe in ordinary
  prose ("the module's position") desynchronises its quote tracking, and it
  then emits prototypes for every JavaScript function it sees, which do not
  compile. Keeping the page in a header sidesteps that entirely.
*/

#pragma once

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
  .panel.t2>.bar{background:linear-gradient(90deg,#c76b1f,transparent 70%)}
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
  #cvThermal{height:300px} #cvThermalFar{height:220px} #cvSonar{height:190px} #cvEcho{height:210px} #cvPeaks{height:110px}
  @media(max-width:980px){ #cvThermal{height:260px} #cvThermalFar{height:200px} }
  .formula{
    font-family:var(--mono);font-size:11px;color:var(--dim2);line-height:1.6;
    background:#0c1016;border:1px solid var(--line);border-radius:7px;
    padding:8px 11px;margin-top:2px;
  }
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
  input[type=text],input[type=number],select{
    font:inherit;font-size:13px;color:var(--txt);background:#0c1016;
    border:1px solid var(--line2);border-radius:7px;padding:7px 11px;min-width:190px;
  }
  input[type=text]:focus,input[type=number]:focus,select:focus{outline:none;border-color:#3b82f6}
  input.narrow{min-width:96px}
  input.wide{min-width:260px}
  label.fld{display:flex;flex-direction:column;gap:4px;font-size:11px;color:var(--dim)}
  .toggle{font-size:11px;letter-spacing:.4px}

  .pill{
    font-family:var(--mono);font-size:11px;padding:3px 9px;border-radius:20px;
    border:1px solid var(--line2);color:var(--dim2);white-space:nowrap;
  }
  .pill.good{color:#86efac;border-color:#2c6b41;background:#12251a}
  .pill.bad{color:#fca5a5;border-color:#7f3a3a;background:#241414}

  /* ---- dataset ---- */
  .step{display:flex;gap:12px;margin-bottom:14px}
  .stepno{
    flex:0 0 22px;height:22px;border-radius:50%;margin-top:1px;
    background:#16321f;border:1px solid #2c6b41;color:#86efac;
    font-family:var(--mono);font-size:12px;display:flex;align-items:center;justify-content:center;
  }
  .stepbody{flex:1;min-width:0}
  .steptitle{font-size:13px;font-weight:600;margin-bottom:9px}
  .filebtn{display:inline-block}
  .photorow{display:flex;gap:12px;align-items:flex-start}

  /* Frame check: the phone photo and the live thermal frame at the same size
     and the same 4:3 aspect (32x24 sensor, 512x384 photo), with identical
     guide lines over both, so it is obvious whether they point the same way.
     A photo framed differently from the sensor teaches the model to predict
     something its input never saw, and that cannot be fixed afterwards. */
  .fcpair{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:10px 0}
  .fc{position:relative;margin:0;min-width:0}
  .fc img, .fc canvas, .fc video{
    display:block;width:100%;aspect-ratio:4/3;height:auto;object-fit:cover;
    border-radius:8px;border:1px solid var(--line2);background:#0a0d13;
  }
  .camNote{
    font-family:var(--mono);font-size:11px;padding:8px 11px;border-radius:7px;
    border:1px solid var(--line2);color:var(--dim2);margin-top:8px;line-height:1.6;
  }
  .camNote a{color:#93c5fd}
  .fc figcaption{
    font-size:10px;color:var(--dim);letter-spacing:1.1px;text-transform:uppercase;
    margin-top:6px;
  }
  .guides{
    position:absolute;left:0;right:0;top:0;pointer-events:none;
    aspect-ratio:4/3;border-radius:8px;
    /* transparent border of the same width as the panes', so the guide lines
       land on the image itself rather than a pixel outside it */
    border:1px solid transparent;
    --c:rgba(255,255,255,.5); --t:rgba(255,255,255,.16);
    background:
      linear-gradient(90deg,transparent calc(33.33% - 1px),var(--t) calc(33.33% - 1px),var(--t) 33.33%,transparent 33.33%),
      linear-gradient(90deg,transparent calc(66.66% - 1px),var(--t) calc(66.66% - 1px),var(--t) 66.66%,transparent 66.66%),
      linear-gradient(0deg,transparent calc(33.33% - 1px),var(--t) calc(33.33% - 1px),var(--t) 33.33%,transparent 33.33%),
      linear-gradient(0deg,transparent calc(66.66% - 1px),var(--t) calc(66.66% - 1px),var(--t) 66.66%,transparent 66.66%),
      linear-gradient(90deg,transparent calc(50% - 1px),var(--c) calc(50% - 1px),var(--c) 50%,transparent 50%),
      linear-gradient(0deg,transparent calc(50% - 1px),var(--c) calc(50% - 1px),var(--c) 50%,transparent 50%);
  }
  @media(max-width:620px){ .fcpair{grid-template-columns:1fr} }
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

    <!-- ============ THERMAL (BAA - wide FOV, shorter range) ============ -->
    <div class="col">
      <section class="panel t">
        <div class="bar"></div>
        <div class="head">
          <h2>Thermal BAA &mdash; the capture sensor</h2>
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
          <div class="hint">32&times;24 pixels, 8&nbsp;Hz, wide-FOV MLX90640. Best for near/wide scenes; see docs/data_collection_protocol.md 4.2c for its measured usable range.</div>
        </div>
      </section>

      <!-- ============ THERMAL (BAB - narrow FOV, longer range) ============ -->
      <section class="panel t2">
        <div class="bar"></div>
        <div class="head">
          <h2>Thermal BAB &mdash; recorded only, ignore</h2>
          <div class="sp"><span class="pill" id="tFarStatus">&mdash;</span></div>
        </div>
        <div class="body">
          <div class="reads">
            <div class="read big t"><span>centre</span><b id="tFarCentre">--.-</b></div>
            <div class="read"><span>min</span><b id="tFarMin">--.-</b></div>
            <div class="read"><span>max</span><b id="tFarMax">--.-</b></div>
            <div class="read"><span>hotspot</span><b id="tFarHot">--,--</b></div>
          </div>
          <canvas id="cvThermalFar" height="360"></canvas>
          <div class="hint">Same sensor type, narrower lens, wired on a second I2C bus (GPIO33/25) so it cannot collide with BAA's fixed address. Best for the far end of a room BAA can't resolve. Which one is authoritative for a given scene is decided per-scene by distance, at prepare time (docs/data_collection_protocol.md 4.2c) &mdash; not fused here.</div>
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
            <div class="read big"><span>distance from echo</span><b id="eDist">---- mm</b></div>
            <div class="read"><span>time of flight t</span><b id="eTof">--.- ms</b></div>
            <div class="read"><span>sonar says</span><b id="eSonarRef">---- mm</b></div>
            <div class="read"><span>agreement</span><b id="eAgree">&mdash;</b></div>
          </div>
          <div class="formula">
            d = v&nbsp;&times;&nbsp;t&nbsp;/&nbsp;2 &nbsp;&nbsp;(2d&nbsp;=&nbsp;vt) &nbsp;&nbsp;with
            v&nbsp;=&nbsp;343&nbsp;m/s &mdash; the chirp from the speaker travels to the
            surface and back to the mic, so the surface is at half the path.
          </div>
          <div class="reads" style="margin-top:10px">
            <div class="read"><span>peak before</span><b id="eBefore">------</b></div>
            <div class="read"><span>peak after</span><b id="eAfter">------</b></div>
            <div class="read"><span>ratio</span><b id="eRatio">--.-&times;</b></div>
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

      <div class="step">
        <div class="stepno">1</div>
        <div class="stepbody">
          <div class="steptitle">Name this scene, then photograph it</div>
          <div class="dsrow">
            <input type="text" id="dsScene" placeholder="scene id, e.g. bedroom-01-view2">
            <button class="primary" id="btnLiveCam">Open live camera</button>
            <label class="btn filebtn" for="dsPhoto">Take / choose photo</label>
            <input type="file" id="dsPhoto" accept="image/*" capture="environment" hidden>
            <span class="pill" id="dsPhotoState">no photo yet</span>
          </div>
          <div class="hint" id="camHint">
            <b>Open live camera</b> shows the phone's camera live, right in the frame
            below, at the same box as the thermal view, so you can line them up
            <i>before</i> you shoot instead of checking afterwards. If your browser
            won't allow it here (see the note below), use <b>Take / choose photo</b>,
            which opens the normal camera app instead.
          </div>
          <div class="camNote" id="camNote" hidden></div>
          <div class="hint">
            The photo is the <b>answer</b> the model learns to predict, so it must be
            taken from the module's position, pointing where the module points.
            It is downscaled to 512&times;384 in the browser and stored once per
            scene, not once per sample.
          </div>

          <div id="frameCheck" hidden>
            <div class="fcpair">
              <figure class="fc">
                <img id="dsThumb" alt="the scene photo attached to this scene" hidden>
                <video id="camVideo" autoplay playsinline muted hidden></video>
                <div class="guides"></div>
                <figcaption id="fcCaptionPhoto">phone photo &mdash; the target</figcaption>
              </figure>
              <figure class="fc">
                <canvas id="cvFrame"></canvas>
                <div class="guides"></div>
                <figcaption>thermal BAA, live &mdash; this defines the target frame</figcaption>
              </figure>
            </div>
            <div class="dsrow" id="camControls" hidden>
              <button class="primary" id="btnSnap">Capture this frame</button>
              <button class="danger" id="btnCamCancel">Cancel</button>
              <span class="hint" style="margin:0">Line the warm object up with the same
                grid box on both sides, then capture.</span>
            </div>
            <div class="hint" style="margin-top:0">
              <b>Check the framing before you capture a scene.</b> Both panes are the
              same 4:3 view with the same guide lines. A warm object &mdash; your hand,
              a person, a radiator &mdash; should sit in the same box in both. If it
              drifts left in one and right in the other, the phone was not where the
              module is: re-shoot rather than capturing a scene that cannot be learned.
              The thermal side is deliberately coarse (32&times;24); match the
              <i>position</i> of the warm blobs, not their sharpness. It shows
              <b>BAB</b> (the narrow sensor) because every ground-truth photo is
              framed to BAB's view &mdash; see section 0.5 of the protocol.
            </div>
          </div>
          <div class="dsrow" style="margin-top:12px">
            <label class="fld">room / place
              <input type="text" id="dsRoom" class="narrow" placeholder="bedroom">
            </label>
            <label class="fld">main surface distance (m)
              <input type="number" id="dsDist" class="narrow" step="0.1" min="0" placeholder="2.5">
            </label>
            <label class="fld">people in view
              <input type="number" id="dsPeople" class="narrow" step="1" min="0" value="0">
            </label>
            <label class="fld">lighting
              <select id="dsLight">
                <option value="normal">normal indoor</option>
                <option value="bright">bright</option>
                <option value="dim">dim</option>
                <option value="dark">dark</option>
              </select>
            </label>
            <label class="fld">note
              <input type="text" id="dsNote" class="wide" placeholder="curtains open, sofa on the left">
            </label>
          </div>
          <div class="hint">These describe the scene, not the sample. They ride along in
            the export so the paper's dataset table can be written from the file instead of
            from memory. Fill them in before capturing &mdash; they are stored the moment the
            scene's first sample is taken.</div>
        </div>
      </div>

      <div class="step">
        <div class="stepno">2</div>
        <div class="stepbody">
          <div class="steptitle">Hold the scene still and capture samples into it</div>
          <div class="dsrow">
            <button class="primary" id="btnBurst">Capture a scene (25)</button>
            <button id="btnCapture">Capture 1 sample</button>
            <button id="btnAuto">Auto-capture: off</button>
            <button id="btnScenePng">Save scene .png</button>
            <span class="pill" id="dsSceneCount">0 in this scene</span>
            <span class="pill" id="dsBurst" hidden>&mdash;</span>
          </div>
          <div class="hint" style="margin-top:-4px">&ldquo;Save scene .png&rdquo; writes one
            picture &mdash; your photo beside the averaged thermal frame, with the readings
            printed under it &mdash; straight to this phone, no laptop needed. Optional: the
            <code>.json</code> already holds everything, and
            <code>scripts/export_scene_previews.py</code> makes the same images for every scene
            at once. Use this when you want to keep or send one scene on the spot.</div>
          <div class="hint" style="margin-top:-4px">One button per scene: it takes 25 samples,
            one per sensor cycle (about 25&nbsp;s), then stops on its own &mdash; so stand still
            until the counter says done. A sample is only stored once per new sensor frame, so
            no two rows in the export are the same reading twice. Capture is refused while the
            thermal sensor reads NOT FOUND, because <code>prepare_novis.py</code> would drop
            those samples anyway.</div>
          <div class="dsrow" style="margin-top:8px">
            <span class="pill" id="dsQualEcho">echo returns: &mdash;</span>
            <span class="pill" id="dsQualSonar">sonar valid: &mdash;</span>
          </div>
        </div>
      </div>

      <div class="step">
        <div class="stepno">3</div>
        <div class="stepbody">
          <div class="steptitle">Move to the next scene, and download before you close the tab</div>
          <div class="dsrow">
            <button class="primary" id="btnJson">Download dataset .json</button>
            <button id="btnCsv">Download summary .csv</button>
            <button class="danger" id="btnClear">Clear all</button>
            <span class="pill" id="dsUnsaved">nothing unsaved</span>
          </div>
        </div>
      </div>

      <div class="dsstat">
        <div class="read"><span>samples</span><b id="dsCount">0</b></div>
        <div class="read"><span>scenes</span><b id="dsScenes">0</b></div>
        <div class="read"><span>approx size</span><b id="dsSize">0 KB</b></div>
        <div class="read"><span>last capture</span><b id="dsLast">&mdash;</b></div>
      </div>
      <div class="chips" id="dsChips"></div>
      <div class="hint">Each sample stores the full 768-pixel thermal frame, both sonar ranges, the 960-sample echo window and its peaks, plus its scene id and device timestamp. The download also carries a metadata header (pin plan, units, sample rate, chirp spec) so the file documents itself. Feed it to <code>scripts/prepare_novis.py</code> to build training shards.</div>
      <div class="warn">Samples live in this browser tab only &mdash; download before closing or reloading the page.</div>
    </div>
  </section>
</div>

<script>
const TW = 32, TH = 24, ECHO_N = 960, SR = 16000, SOUND = 343;
const HIST = 90;
const BLANK = 96;   // 6 ms: the 5 ms chirp plus ringdown, heard directly by the mic

const S = {
  last:null, seq:-1, sonar:[], peaks:[], dataset:[], scenes:{}, photo:null,
  smooth:true, lock:false, lockLo:20, lockHi:35, auto:false, live:false,
  // Capture bookkeeping: lastSeq stops one sensor frame being stored twice,
  // burst counts down a whole scene, saved marks how much is already on disk.
  lastSeq:-1, burst:0, saved:0
};
const BURST_N = 25;      // samples per scene - see docs/data_collection_protocol.md
const STALE_MS = 2500;   // a frame older than this is not what the room looks like now

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

// Paints one 768-value frame into a canvas. The main panel and the
// side-by-side frame check show the same frame at different sizes, so the
// painting is shared and only the main panel draws the hotspot marker.
// Returns the frame's min/max/hottest pixel, or null if there was no frame.
// A single dead/broken pixel is a normal MLX90640 trait (manufacturer
// tolerance allows a few per unit) - but one pixel reading far outside the
// rest of the frame can otherwise drag the whole colour scale with it,
// since colour range was literal min/max. Sort once, trim ~1% off each end
// (>=7-8 of 768 pixels - well past a lone dead pixel, tight enough to still
// react to a real warm/cool scene) and use that for both the colour range
// and the hotspot search, so one bad pixel can't wash out or mislabel the
// rest of the frame. The literal min/max is kept too (for the numeric
// readout) precisely because it is what makes a dead pixel visible at all.
// MLX90640 frames arrive mirrored left-right against the scene - confirmed by
// hand on 2026-09-26: a hand moved to the right lit up the LEFT of the panel,
// on both sensors. Flipped here, for DISPLAY only. The .json keeps the
// sensor's raw order, so every capture ever made stays in one orientation and
// scripts/prepare_novis.py flips them all the same way at prepare time.
function mirror(arr){
  if(!arr) return arr;
  const out = new Array(TW*TH);
  for(let y=0;y<TH;y++)
    for(let x=0;x<TW;x++) out[y*TW+x] = arr[y*TW + (TW-1-x)];
  return out;
}

function percentileBounds(arr, frac){
  const sorted = Array.prototype.slice.call(arr).sort((a,b)=>a-b);
  const n = sorted.length;
  const k = Math.max(0, Math.min(Math.floor(n/2)-1, Math.round(n*frac)));
  return [sorted[k], sorted[n-1-k]];
}

function paintThermal(cv, arr, withHotspot, respectLock){
  if(respectLock === undefined) respectLock = true;
  const dpr = window.devicePixelRatio || 1;
  const w = cv.clientWidth, h = cv.clientHeight;
  if(!w || !h) return null;
  if(cv.width!==Math.round(w*dpr)||cv.height!==Math.round(h*dpr)){
    cv.width=Math.round(w*dpr); cv.height=Math.round(h*dpr);
  }
  const ctx = cv.getContext('2d');
  ctx.setTransform(1,0,0,1,0,0);
  ctx.clearRect(0,0,cv.width,cv.height);
  if(!arr) return null;
  arr = mirror(arr);     // hotspot coordinates below are therefore display coordinates

  let lo=1e9, hi=-1e9;
  for(let i=0;i<arr.length;i++){
    if(arr[i]<lo) lo=arr[i];
    if(arr[i]>hi) hi=arr[i];
  }
  const [pLo, pHi] = percentileBounds(arr, 0.01);

  let dLo = pLo/100, dHi = pHi/100;
  if(respectLock && S.lock){ dLo = S.lockLo; dHi = S.lockHi; }
  const span = Math.max(0.1, dHi-dLo);

  for(let i=0;i<TW*TH;i++){
    const c = ramp((arr[i]/100 - dLo)/span);
    img.data[i*4]=c[0]; img.data[i*4+1]=c[1]; img.data[i*4+2]=c[2]; img.data[i*4+3]=255;
  }
  offCtx.putImageData(img,0,0);
  ctx.imageSmoothingEnabled = S.smooth;
  ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(off,0,0,cv.width,cv.height);

  // Hotspot = hottest pixel that is NOT itself an outlier, so a defective
  // pixel spiking hot can't put the marker on a pixel that isn't really a
  // warm object.
  let hotIdx = 0, hotVal = -1e9;
  for(let i=0;i<arr.length;i++){
    if(arr[i] <= pHi && arr[i] > hotVal){ hotVal = arr[i]; hotIdx = i; }
  }

  if(withHotspot){
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
  }
  // A gap of >6C between the literal extreme and the 99th-percentile bound
  // is well past normal room/person variation - flag it as a likely dead
  // pixel rather than silently absorbing it into "auto range".
  const suspectDead = (hi - pHi > 600) || (pLo - lo > 600);
  return {lo, hi, hotIdx, dLo, dHi, suspectDead};
}

// Only ever called with a real frame (paintThermal returns null, and the
// caller returns early, whenever the sensor itself is down) - so "sensor OK"
// is always the right base label here; NOT FOUND is set and left alone by
// poll() before this runs.
function markDeadPixel(el, suspect){
  if(suspect){
    el.textContent = 'sensor OK · check dead pixel';
    el.className = 'pill bad';
  } else {
    el.textContent = 'sensor OK';
    el.className = 'pill good';
  }
}

function drawThermal(arr){
  const r = paintThermal($('cvThermal'), arr, true);
  // The frame check shows BAA: BAA's view is the extent every ground-truth
  // photo is framed to (docs/session1_baa_capture.md step 2), so it is the one
  // the photo has to line up with. respectLock=false so a locked colour scale
  // on BAA's own panel cannot make the frame-check pane hard to read.
  if(!$('frameCheck').hidden) paintThermal($('cvFrame'), arr, false, false);
  if(!r) return;
  $('tCentre').textContent = (arr[12*TW+16]/100).toFixed(1)+'°C';
  $('tMin').textContent = (r.lo/100).toFixed(1)+'°C';
  $('tMax').textContent = (r.hi/100).toFixed(1)+'°C';
  $('tHot').textContent = (r.hotIdx%TW)+','+Math.floor(r.hotIdx/TW);
  $('cbLo').textContent = r.dLo.toFixed(1)+'°C';
  $('cbHi').textContent = r.dHi.toFixed(1)+'°C';
  markDeadPixel($('tStatus'), r.suspectDead);
}

// BAB - always auto-ranges (the lock button belongs to BAA's panel only).
// Recorded on every sample, but nothing is framed to it and no decision is
// made from it: BAA is the capture sensor (docs/session1_baa_capture.md).
function drawThermalFar(arr){
  const r = paintThermal($('cvThermalFar'), arr, true, false);
  if(!r) return;
  $('tFarCentre').textContent = (arr[12*TW+16]/100).toFixed(1)+'°C';
  $('tFarMin').textContent = (r.lo/100).toFixed(1)+'°C';
  $('tFarMax').textContent = (r.hi/100).toFixed(1)+'°C';
  $('tFarHot').textContent = (r.hotIdx%TW)+','+Math.floor(r.hotIdx/TW);
  markDeadPixel($('tFarStatus'), r.suspectDead);
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
/* ---------- echo -> distance ---------- */
// Echolocation proper: the chirp travels to a surface and back, so the sound
// covers twice the distance. 2d = v*t, i.e. d = v*t/2, with v = 343 m/s and
// t measured from the chirp to the first return that clears the noise floor.
//
// Two things make t honest. The first BLANK samples are skipped because the
// speaker sits centimetres from the mic and its chirp reaches it directly
// through the air - that arrival is not a room echo and would report a few
// centimetres in every scene. And the threshold is built from the quiet tail
// of the window, so a noisy room raises the bar instead of triggering on
// itself.
//
// Returns {index, tMs, mm} for the nearest surface, or null if nothing came
// back loudly enough - which is itself a real reading: no surface in range.
// Echo time of flight, measured from the chirp: d = v * t / 2.
// onset = the chirp's index inside the window (firmware echoOnset, normally 8
// because 0.5 ms of pre-roll is kept before it). Measuring from the window
// start instead would add that pre-roll to every flight time: +86 mm on every
// distance. onset -1 means the node never heard its own chirp, so there is no
// time zero and no distance to report. Captures from before echoOnset existed
// pass undefined and keep the old assumption that the window began at the chirp.
function echoDistance(echo, onset){
  if(!echo) return null;
  if(onset === -1) return null;
  const t0 = (onset === undefined || onset === null) ? 0 : onset;
  let acc = 0, n = 0;
  for(let i=Math.floor(ECHO_N*0.75);i<ECHO_N;i++){ acc += echo[i]*echo[i]; n++; }
  const rms = Math.sqrt(acc/Math.max(1,n));
  let peakPost = 0;
  for(let i=t0+BLANK;i<ECHO_N;i++){ const a=Math.abs(echo[i]); if(a>peakPost) peakPost=a; }
  const thr = Math.max(rms*4, peakPost*0.25);
  // An echo counts only where it RISES out of quiet: the W samples before it
  // must all be under the threshold. Without that, a surface nearer than the
  // blind zone (~1 m) - whose echo starts inside the blanked chirp but whose
  // tail runs past BLANK - was reported at exactly the blank edge, 1029 mm,
  // for anything from ~0.6 m to 1 m. That is a wrong number, which is worse
  // than none; sonar covers that range. W (0.5 ms) is longer than half a
  // period of the chirp's lowest tone, so a single echo's own zero-crossings
  // never look like a gap.
  const W = 8;
  let quiet = 0;
  for(let i=t0+BLANK-W;i<ECHO_N;i++){
    if(Math.abs(echo[i])>thr){
      if(quiet>=W && i>=t0+BLANK){
        const t = (i - t0)/SR;                         // seconds since the chirp
        return {index:i, tMs:t*1000, mm:Math.round(SOUND*t/2*1000)};
      }
      quiet = 0;
    } else quiet++;
  }
  return null;
}

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

  // Mark where the nearest surface answered.
  const hit = echoDistance(echo, S.last ? S.last.echoOnset : undefined);
  if(hit){
    const x = (hit.index/ECHO_N)*w;
    ctx.strokeStyle='#4ade80'; ctx.lineWidth=1.5; ctx.setLineDash([4,3]);
    ctx.beginPath(); ctx.moveTo(x,0); ctx.lineTo(x,h-14); ctx.stroke(); ctx.setLineDash([]);
    label(ctx, hit.mm+'mm', x+5, 11, '#4ade80');
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
      if(S.burst > 0){
        if(capture()){
          S.burst--;
          const p = $('dsBurst');
          if(S.burst){
            p.className = 'pill';
            p.textContent = S.burst+' more - hold still';
          } else {
            p.className = 'pill good';
            p.textContent = 'scene done - move the module';
          }
        }
      } else if(S.auto && sceneId() && S.photo) capture();
    }

    $('hSeq').textContent = d.seq;
    $('hUp').textContent = fmtUptime(d.tMs);
    $('hHeap').textContent = (d.heap/1024).toFixed(0)+'K';

    const st = $('tStatus');
    st.textContent = d.thermalOk ? 'sensor OK' : 'NOT FOUND';
    st.className = 'pill '+(d.thermalOk?'good':'bad');

    const stFar = $('tFarStatus');
    stFar.textContent = d.thermalFarOk ? 'sensor OK' : 'NOT FOUND';
    stFar.className = 'pill '+(d.thermalFarOk?'good':'bad');

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

    // Echo distance, and the same surface measured independently by sonar.
    // The two use different physics on different hardware, so when they
    // agree the echolocation path is genuinely working - that agreement is
    // the number worth reporting, not the raw peak heights.
    const hit = echoDistance(d.echo, d.echoOnset);
    const sonarMm = [d.sonar.left, d.sonar.right].filter(v => v > 0);
    const nearest = sonarMm.length ? Math.min(...sonarMm) : null;
    $('eDist').textContent   = hit ? hit.mm+' mm' : 'no return';
    $('eTof').textContent    = hit ? hit.tMs.toFixed(2)+' ms' : '—';
    $('eSonarRef').textContent = nearest !== null ? nearest+' mm' : 'no echo';
    const ag = $('eAgree');
    if(hit && nearest !== null){
      const diff = Math.abs(hit.mm - nearest);
      ag.textContent = '±'+diff+' mm';
      ag.className = diff <= 300 ? 'ok' : diff <= 700 ? '' : 'bad';
    } else {
      ag.textContent = '—';
      ag.className = '';
    }

    drawThermal(d.thermalOk ? d.thermal : null);
    drawThermalFar(d.thermalFarOk ? d.thermalFar : null);
    drawSonar();
    drawEcho(d.echo);
    drawPeaks();
  }catch(e){ setLive(false); }
}

/* ---------- dataset ---------- */

// The scene photo is the training target, so it is stored once per scene
// (not once per sample) and downscaled here - a phone photo is megabytes,
// and the model only ever sees 256x192.
const PHOTO_W = 512, PHOTO_H = 384;

// Cover-crop any image-like source (an <img> or a <video> frame) into the
// model's fixed PHOTO_W x PHOTO_H, same framing rule either way: crop to
// 4:3, never squash.
function coverCropToPhoto(source, srcW, srcH){
  const cv = document.createElement('canvas');
  cv.width = PHOTO_W; cv.height = PHOTO_H;
  const ctx = cv.getContext('2d');
  const sa = srcW / srcH, da = PHOTO_W / PHOTO_H;
  let sw = srcW, sh = srcH, sx = 0, sy = 0;
  if(sa > da){ sw = srcH * da; sx = (srcW - sw) / 2; }
  else       { sh = srcW / da; sy = (srcH - sh) / 2; }
  ctx.drawImage(source, sx, sy, sw, sh, 0, 0, PHOTO_W, PHOTO_H);
  return cv.toDataURL('image/jpeg', 0.85);
}

function loadPhoto(file){
  const img = new Image();
  img.onload = () => {
    S.photo = coverCropToPhoto(img, img.width, img.height);
    showPhoto(S.photo);
    URL.revokeObjectURL(img.src);
  };
  img.src = URL.createObjectURL(file);
}

/* ---------- live camera preview ---------- */
// http://192.168.4.1/ is a plain-HTTP, non-localhost origin, and
// getUserMedia is only granted on a "secure context" (HTTPS, or localhost).
// So on a fresh phone this is normally blocked outright - not a bug in this
// page, a browser policy. It can be lifted once, per browser, per device:
// chrome://flags/#unsafely-treat-insecure-origin-as-secure -> add
// http://192.168.4.1 -> relaunch. Worth doing once since the protocol
// already calls for using the same phone every session.
const CAM_HELP =
  'Live camera needs a "secure origin", and this page is plain http on a '
  + 'private IP, so phones normally block it here. One-time fix on the '
  + 'capture phone’s Chrome: open '
  + '<b>chrome://flags/#unsafely-treat-insecure-origin-as-secure</b>, enable '
  + 'it, add <b>http://192.168.4.1</b> to the box below it, then relaunch '
  + 'Chrome. Until then, use "Take / choose photo" instead - it uses the '
  + 'normal camera app and works everywhere.';

let camStream = null;

function cameraSupported(){
  return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
}

async function startCamera(){
  if(!sceneId()){ alert('Give this scene an id first.'); return; }
  if(!cameraSupported()){
    const n = $('camNote'); n.hidden = false; n.innerHTML = CAM_HELP;
    return;
  }
  try{
    camStream = await navigator.mediaDevices.getUserMedia(
      { video: { facingMode: 'environment' }, audio: false });
  } catch(err){
    const n = $('camNote'); n.hidden = false;
    n.innerHTML = 'Camera blocked or unavailable (' + err.name + '). ' + CAM_HELP;
    return;
  }
  $('camNote').hidden = true;
  const v = $('camVideo');
  v.srcObject = camStream;
  $('frameCheck').hidden = false;
  $('dsThumb').hidden = true;
  v.hidden = false;
  $('camControls').hidden = false;
  $('fcCaptionPhoto').textContent = 'phone camera — line it up, then capture';
  if(S.last) paintThermal($('cvFrame'), S.last.thermalOk ? S.last.thermal : null, false, false);
}

function stopCamera(){
  if(camStream){ camStream.getTracks().forEach(t => t.stop()); camStream = null; }
  $('camVideo').hidden = true;
  $('camControls').hidden = true;
}

function captureFromCamera(){
  const v = $('camVideo');
  if(!v.videoWidth) return;         // stream not ready yet
  S.photo = coverCropToPhoto(v, v.videoWidth, v.videoHeight);
  stopCamera();
  showPhoto(S.photo);
}

// Shows or clears the side-by-side frame check. Passing null is what makes a
// new scene id start with an empty pane instead of the last scene's picture.
function showPhoto(dataUri){
  stopCamera();
  const st = $('dsPhotoState');
  $('frameCheck').hidden = !dataUri;
  $('dsThumb').hidden = !dataUri;
  $('fcCaptionPhoto').textContent = 'phone photo — the target';
  if(dataUri){
    $('dsThumb').src = dataUri;
    st.textContent = 'photo attached'; st.className = 'pill good';
    if(S.last) paintThermal($('cvFrame'), S.last.thermalOk ? S.last.thermal : null, false, false);
  } else {
    $('dsThumb').removeAttribute('src');
    st.textContent = 'new scene - needs a photo'; st.className = 'pill bad';
  }
}

function sceneId(){ return ($('dsScene').value || '').trim(); }

function sceneMeta(){
  const dist = parseFloat($('dsDist').value);
  const ppl  = parseInt($('dsPeople').value, 10);
  return {
    room: ($('dsRoom').value || '').trim(),
    distanceM: isFinite(dist) ? dist : null,
    people: isFinite(ppl) ? ppl : null,
    lighting: $('dsLight').value,
    note: ($('dsNote').value || '').trim()
  };
}

function stopCapture(why){
  S.burst = 0;
  S.auto = false;
  $('btnAuto').textContent = 'Auto-capture: off';
  $('btnAuto').className = '';
  const p = $('dsBurst');
  p.hidden = false; p.textContent = why; p.className = 'pill bad';
}

// Returns true when a sample was actually stored. Everything that would put a
// row in the export that prepare_novis.py has to throw away later is refused
// here instead, while there is still someone standing in front of the module
// who can fix it.
function capture(){
  const d = S.last;
  if(!d) return false;
  const id = sceneId();
  if(!id){ alert('Give this scene an id first (step 1).'); stopCapture('no scene id'); return false; }
  if(!S.photo){ alert('Attach a photo of this scene first - without it the sample has nothing to train against.'); stopCapture('no photo'); return false; }
  if(!d.thermalOk){
    stopCapture('thermal NOT FOUND - fix the sensor');
    return false;
  }
  if(d.ageMs > STALE_MS){       // the node stopped refreshing: stale reading
    stopCapture('sensor frame is stale');
    return false;
  }
  if(d.seq === S.lastSeq) return false;   // same sensor frame, not a new sample

  if(!S.scenes[id]){
    S.scenes[id] = Object.assign(
      { photo:S.photo, capturedAt:new Date().toISOString() }, sceneMeta());
  }
  S.lastSeq = d.seq;
  // echoDistanceMm is derived here rather than left to the analysis scripts so
  // that the number in the file is the same one the operator saw and sanity
  // checked against sonar while standing in the room. The raw echo array is
  // stored too, so it can always be recomputed differently later.
  const hit = echoDistance(d.echo, d.echoOnset);
  S.dataset.push({
    sceneId:id, seq:d.seq, deviceMs:d.tMs, wallClock:new Date().toISOString(),
    thermalOk:d.thermalOk, thermal:d.thermal,
    // BAB (narrow/far) rides along on every sample too, even though the
    // scene's stated distance (sceneMeta().distanceM) decides at prepare
    // time which of the two becomes the model's actual `thermal` input -
    // storing both means that decision is never locked in at capture time.
    thermalFarOk:d.thermalFarOk, thermalFar:d.thermalFar,
    sonarLeftMm:d.sonar.left, sonarRightMm:d.sonar.right,
    echo:d.echo, echoOnset:(d.echoOnset === undefined ? null : d.echoOnset),
    peakBefore:d.peaks.before, peakAfter:d.peaks.after, spike:d.peaks.spike,
    echoDistanceMm: hit ? hit.mm : 0, echoTofMs: hit ? +hit.tMs.toFixed(3) : 0
  });
  $('dsLast').textContent = new Date().toLocaleTimeString();
  refreshDataset();
  return true;
}

function refreshDataset(){
  const n = S.dataset.length;
  const counts = {};
  S.dataset.forEach(s => counts[s.sceneId] = (counts[s.sceneId]||0)+1);
  const nScenes = Object.keys(S.scenes).length;
  $('dsCount').textContent = n;
  $('hSamples').textContent = n;
  $('dsScenes').textContent = nScenes;
  $('dsPill').textContent = n+' sample'+(n===1?'':'s');
  // ~12 KB per sample of sensor JSON (two thermal frames + echo), ~45 KB
  // per stored scene photo.
  $('dsSize').textContent = (n*12 + nScenes*45).toFixed(0)+' KB';

  const here = S.dataset.filter(s => s.sceneId === sceneId());
  $('dsSceneCount').textContent = here.length+' in this scene';
  $('dsChips').innerHTML = Object.entries(counts)
    .map(([k,v])=>`<span class="chip">${k} <b>${v}</b></span>`).join('');

  // Per-scene quality, while you can still re-shoot the scene. A scene where
  // the chirp never came back, or where both sonars always timed out, trains
  // the model on two dead input channels.
  const pill = (el, label, good, total, ok) => {
    const e = $(el);
    e.textContent = label+': '+(total ? good+'/'+total : '—');
    e.className = 'pill'+(total ? (ok ? ' good' : ' bad') : '');
  };
  const spikes = here.filter(s => s.spike).length;
  const sonar  = here.filter(s => s.sonarLeftMm || s.sonarRightMm).length;
  pill('dsQualEcho',  'echo returns', spikes, here.length, spikes >= here.length*0.5);
  pill('dsQualSonar', 'sonar valid',  sonar,  here.length, sonar  >= here.length*0.5);

  const unsaved = n - S.saved;
  const u = $('dsUnsaved');
  u.textContent = unsaved ? unsaved+' sample'+(unsaved===1?'':'s')+' not downloaded yet'
                          : 'nothing unsaved';
  u.className = 'pill'+(unsaved > 200 ? ' bad' : unsaved ? '' : ' good');
}

function meta(){
  return {
    device:'ESP32-WROOM-32', project:'NOVIS', capturedWith:'firmware/dashboard/dashboard.ino',
    thermal:{sensor:'MLX90640 (BAA, wide FOV, shorter usable range)',
             width:TW, height:TH, order:'row-major',
             unit:'centi-Celsius', note:'divide by 100 for degrees C', refreshHz:8,
             orientation:'sensor raw order - MIRRORED left-right against the scene; '
                         + 'the dashboard and prepare_novis.py flip it, the file does not'},
    thermalFar:{sensor:'MLX90640 (BAB, narrower FOV, longer usable range)',
                width:TW, height:TH, order:'row-major', unit:'centi-Celsius',
                note:'same shape and units as thermal; stored on every sample so '
                     + 'the choice of which sensor feeds the model can be made at '
                     + 'prepare time (by scene distance), not locked in here',
                bus:'second, independent I2C bus (Wire1) - BAA and BAB share a '
                    + 'fixed sensor address and cannot coexist on one bus'},
    sonar:{sensor:'HC-SR04 x2', unit:'mm', zeroMeans:'no echo within the 30 ms timeout'},
    echo:{mic:'INMP441', samples:ECHO_N, sampleRateHz:SR, format:'int16 mono',
          window:'starts at the chirp: RX queue drained, chirp, long raw read, window cut '
                 + 'at the detected chirp onset (0.5 ms pre-roll)',
          capture:'aligned-v2',
          captureNote:'files without capture:aligned-v2 were recorded with a window that '
                      + 'began with 384-742 zero samples and never contained the chirp; '
                      + 'their echo carries no echo information',
          onsetField:'echoOnset on each sample: index of the chirp inside the echo '
                     + 'window (normally 8 - 0.5 ms pre-roll is kept), i.e. time zero '
                     + 'for every echo; -1 if the chirp was not heard',
          chirp:'5 ms, 1 kHz to 8 kHz, PAM8302 + speaker on GPIO4'},
    echoDistance:{formula:'d = v*t/2  (2d = vt)', speedOfSoundMs:SOUND,
                  unit:'mm', zeroMeans:'no return cleared the noise floor',
                  tFrom:'first post-chirp sample above max(4*tail RMS, 0.25*post-chirp peak)',
                  blankedSamples:BLANK,
                  blankedWhy:'the speaker sits centimetres from the mic, so the chirp '
                             + 'arrives directly through the air; that arrival is not '
                             + 'a room echo',
                  note:'derived in the browser at capture time from the echo array in '
                       + 'the same sample, so it can be recomputed differently later'},
    scenePhoto:{width:PHOTO_W, height:PHOTO_H, format:'JPEG data URI',
                role:'ground truth - the visible image the model is trained to predict',
                note:'one photo per scene id, shared by every sample in that scene'},
    sceneFields:{room:'free text', distanceM:'metres to the main surface in view',
                 people:'how many people were in view', lighting:'normal|bright|dim|dark',
                 note:'free text'},
    capture:{samplesPerScene:BURST_N, oneSamplePerSensorFrame:true,
             refusedWhen:'thermal NOT FOUND, stale frame, or a repeated sensor frame'},
    pins:{sda:21,scl:22,sdaFar:33,sclFar:25,trigLeft:16,echoLeft:17,
          trigRight:18,echoRight:19,i2sSck:14,i2sWs:15,i2sSd:32,speaker:4},
    exportedAt:new Date().toISOString()
  };
}
function download(name, text, type){
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([text],{type}));
  a.download = name; a.click(); URL.revokeObjectURL(a.href);
}
function stamp(){ return new Date().toISOString().replace(/[:.]/g,'-').slice(0,19); }

/* ---------- one scene as a picture, on the phone ----------
   Same layout scripts/export_scene_previews.py produces on the laptop, so a
   png saved here and one built later from the .json look alike. The .json is
   still the record; this is for checking or sending a scene on the spot. */
function downloadBlob(name, blob){
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = name; a.click();
  setTimeout(()=>URL.revokeObjectURL(a.href), 10000);
}

// Averaging the scene's frames kills most of the per-frame sensor noise, which
// is the same reason the burst takes 25 of them in the first place.
function sceneMeanThermal(id){
  const rows = S.dataset.filter(s => s.sceneId === id && s.thermalOk);
  if(!rows.length) return null;
  const acc = new Float64Array(TW*TH);
  for(const r of rows) for(let i=0;i<TW*TH;i++) acc[i] += r.thermal[i];
  for(let i=0;i<TW*TH;i++) acc[i] /= rows.length;
  return {arr:acc, n:rows.length, rows:rows};
}

function thermalCanvas(arr, w, h){
  const small = document.createElement('canvas');
  small.width = TW; small.height = TH;
  const sc = small.getContext('2d');
  const im = sc.createImageData(TW, TH);
  const [pLo, pHi] = percentileBounds(arr, 0.01);
  const lo = pLo/100, hi = pHi/100, span = Math.max(0.1, hi-lo);
  for(let i=0;i<TW*TH;i++){
    const c = ramp((arr[i]/100 - lo)/span);
    im.data[i*4]=c[0]; im.data[i*4+1]=c[1]; im.data[i*4+2]=c[2]; im.data[i*4+3]=255;
  }
  sc.putImageData(im, 0, 0);
  const out = document.createElement('canvas');   // (arr already mirrored by the caller)
  out.width = w; out.height = h;
  const oc = out.getContext('2d');
  oc.imageSmoothingEnabled = S.smooth;
  oc.imageSmoothingQuality = 'high';
  oc.drawImage(small, 0, 0, w, h);
  return {canvas:out, lo:lo, hi:hi};
}

function saveScenePng(){
  const id = sceneId();
  const sc = S.scenes[id];
  if(!id || !sc){ alert('Capture this scene first - there is nothing to save yet.'); return; }
  const m = sceneMeanThermal(id);
  if(!m){ alert('No thermal samples stored for this scene yet.'); return; }

  const img = new Image();
  img.onload = ()=>{
    const PW = 640;
    const H  = Math.round(img.height * PW / img.width);
    const TWID = Math.round(H * TW / TH);
    const BAR = 78, GAP = 6;
    const cv = document.createElement('canvas');
    cv.width = PW + GAP + TWID; cv.height = H + BAR;
    const ctx = cv.getContext('2d');
    ctx.fillStyle = '#10121a';
    ctx.fillRect(0, 0, cv.width, cv.height);
    ctx.drawImage(img, 0, 0, PW, H);
    const t = thermalCanvas(mirror(m.arr), TWID, H);
    ctx.drawImage(t.canvas, PW + GAP, 0);

    let sl = 0, sr = 0, ne = 0;
    for(const r of m.rows){ sl += r.sonarLeftMm||0; sr += r.sonarRightMm||0;
                            if(r.echoDistanceMm) ne++; }
    sl = Math.round(sl/m.rows.length); sr = Math.round(sr/m.rows.length);

    ctx.fillStyle = '#dee2eb';
    ctx.font = '15px system-ui, sans-serif';
    const L = [
      id+'   '+(sc.room||'?')+'   '+(sc.distanceM==null?'?':sc.distanceM)+' m   '
        +(sc.people==null?0:sc.people)+' people   '+(sc.lighting||'?'),
      'BAA '+t.lo.toFixed(1)+'-'+t.hi.toFixed(1)+' C over '+m.n+' frames'
        +'   sonar L '+sl+' mm / R '+sr+' mm   echo returns '+ne+'/'+m.n,
      'note: '+(sc.note || '-')
    ];
    for(let i=0;i<L.length;i++) ctx.fillText(L[i], 10, H + 24 + i*22);

    cv.toBlob(b => {
      if(!b){ alert('This browser could not build the png.'); return; }
      downloadBlob(id.replace(/[^A-Za-z0-9_.-]/g,'_')+'.png', b);
    }, 'image/png');
  };
  img.onerror = ()=>alert('Could not read this scene’s photo.');
  img.src = sc.photo;
}

/* ---------- wiring ---------- */
$('btnCapture').onclick = ()=>capture();
$('btnBurst').onclick = ()=>{
  if(!sceneId()){ alert('Give this scene an id first (step 1).'); return; }
  if(!S.photo){ alert('Attach a photo of this scene first.'); return; }
  S.auto = false;
  $('btnAuto').textContent = 'Auto-capture: off';
  $('btnAuto').className = '';
  S.burst = BURST_N;
  const p = $('dsBurst');
  p.hidden = false; p.className = 'pill';
  p.textContent = 'capturing '+BURST_N+' - hold still';
};
$('btnAuto').onclick = e => {
  S.auto = !S.auto;
  S.burst = 0;
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
$('btnScenePng').onclick = saveScenePng;
$('btnJson').onclick = ()=>{
  if(!S.dataset.length) return;
  download('novis_dataset_'+stamp()+'.json',
    JSON.stringify({meta:meta(), scenes:S.scenes, samples:S.dataset}),
    'application/json');
  S.saved = S.dataset.length;
  refreshDataset();
};
$('btnCsv').onclick = ()=>{
  if(!S.dataset.length) return;
  const rows = ['sceneId,seq,deviceMs,wallClock,sonarLeftMm,sonarRightMm,echoDistanceMm,echoTofMs,peakBefore,peakAfter,spike,thermalMinC,thermalMaxC,thermalCentreC,thermalFarOk,thermalFarMinC,thermalFarMaxC'];
  S.dataset.forEach(s=>{
    let lo=1e9,hi=-1e9;
    for(const v of s.thermal){ if(v<lo)lo=v; if(v>hi)hi=v; }
    let farLo=1e9,farHi=-1e9;
    for(const v of s.thermalFar){ if(v<farLo)farLo=v; if(v>farHi)farHi=v; }
    rows.push([s.sceneId,s.seq,s.deviceMs,s.wallClock,s.sonarLeftMm,s.sonarRightMm,
      s.echoDistanceMm,s.echoTofMs,
      s.peakBefore,s.peakAfter,s.spike,(lo/100).toFixed(2),(hi/100).toFixed(2),
      (s.thermal[12*TW+16]/100).toFixed(2),s.thermalFarOk,
      (farLo/100).toFixed(2),(farHi/100).toFixed(2)].join(','));
  });
  download('novis_summary_'+stamp()+'.csv', rows.join('\n'), 'text/csv');
};
$('btnClear').onclick = ()=>{
  if(S.dataset.length && confirm('Delete all '+S.dataset.length+' captured samples?')){
    S.dataset = []; S.scenes = {}; S.saved = 0; S.lastSeq = -1; S.burst = 0;
    refreshDataset(); $('dsLast').textContent='—';
  }
};
$('dsPhoto').onchange = e => { if(e.target.files[0]) loadPhoto(e.target.files[0]); };
$('btnLiveCam').onclick = startCamera;
$('btnSnap').onclick = captureFromCamera;
$('btnCamCancel').onclick = () => { stopCamera(); showPhoto(S.photo); };
if(!cameraSupported()){
  $('btnLiveCam').title = 'not available in this browser - use "Take / choose photo"';
}
$('dsScene').oninput = () => {
  // A new scene id needs its own photo - otherwise the previous scene's
  // picture would silently become this scene's training target.
  S.burst = 0;
  $('dsBurst').hidden = true;
  const sc = S.scenes[sceneId()];
  if(sc){
    S.photo = sc.photo;
    showPhoto(S.photo);
    // Show the notes this scene was stored with, so re-entering an id does
    // not make it look like the fields describe it when they do not.
    $('dsRoom').value = sc.room || '';
    $('dsDist').value = (sc.distanceM === null || sc.distanceM === undefined) ? '' : sc.distanceM;
    $('dsPeople').value = (sc.people === null || sc.people === undefined) ? '' : sc.people;
    $('dsLight').value = sc.lighting || 'normal';
    $('dsNote').value = sc.note || '';
  } else if(S.photo){
    S.photo = null;
    showPhoto(null);
  }
  refreshDataset();
};

// Samples live in this tab only. A reload or a stray back-gesture on a phone
// loses every scene captured since the last download, and they cannot be
// re-recorded - the room has already changed.
window.addEventListener('beforeunload', e => {
  if(S.dataset.length > S.saved){ e.preventDefault(); e.returnValue = ''; }
});
$('btnSmooth').className = 'toggle on';
window.addEventListener('resize', ()=>{
  if(!S.last) return;
  drawThermal(S.last.thermalOk ? S.last.thermal : null);
  drawThermalFar(S.last.thermalFarOk ? S.last.thermalFar : null);
  drawSonar(); drawEcho(S.last.echo); drawPeaks();
});

refreshDataset();
poll();
setInterval(poll, 700);
</script>
</body>
</html>
)rawliteral";
