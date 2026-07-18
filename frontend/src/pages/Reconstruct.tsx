import { useEffect, useRef, useState } from "react";
import {
  api,
  InferResponse,
  ModelInfo,
  SampleSummary,
} from "../api";
import { Chip, Frame, Panel } from "../components";
import { useGatedColor } from "../gatedColor";

export default function Reconstruct(props: { info: ModelInfo | null }) {
  const [samples, setSamples] = useState<SampleSummary[]>([]);
  const [selected, setSelected] = useState<number>(0);
  const [seed, setSeed] = useState<number | null>(null);
  const [mask, setMask] = useState<[boolean, boolean, boolean]>([
    true,
    true,
    true,
  ]);
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<InferResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [showColor, setShowColor] = useState(false);
  const [gate, setGate] = useState(0.45);
  const fileRef = useRef<HTMLInputElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useGatedColor(
    canvasRef,
    res?.outputs.gray_png,
    res?.outputs.color_png,
    res?.outputs.conf_png,
    showColor,
    gate,
  );

  useEffect(() => {
    api
      .samples()
      .then((r) => setSamples(r.samples))
      .catch(() => undefined);
  }, []);

  const run = async (opts?: { seed?: number }) => {
    setBusy(true);
    setErr(null);
    try {
      const body =
        opts?.seed !== undefined
          ? { seed: opts.seed, mask }
          : { sample_id: selected, mask };
      setRes(await api.infer(body));
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  const runUpload = async (f: File) => {
    setBusy(true);
    setErr(null);
    try {
      setRes(await api.inferUpload(f));
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  const download = () => {
    const canvas = canvasRef.current;
    if (!canvas || !res) return;
    const a = document.createElement("a");
    a.download = "novis_reconstruction.png";
    a.href = canvas.toDataURL("image/png");
    a.click();
  };

  const modality = (i: number, label: string) => (
    <label className="check-row" key={label}>
      <input
        type="checkbox"
        checked={mask[i]}
        onChange={(e) => {
          const m = [...mask] as [boolean, boolean, boolean];
          m[i] = e.target.checked;
          if (m.some(Boolean)) setMask(m);
        }}
      />
      {label}
    </label>
  );

  return (
    <>
      <div className="page-head">
        <h2>Reconstruct</h2>
        <p>
          Feed a sensor observation (thermal array, chirp echoes, ultrasonic
          ranges) through NOVISNet and inspect the reconstructed view of the
          scene. No camera is involved at any point.
        </p>
      </div>

      <div className="grid reconstruct-grid">
        {/* ---------------------------------------------- input column */}
        <div className="stack">
          <Panel title="Demo scenes">
            <div className="sample-grid">
              {samples.map((s) => (
                <button
                  key={s.id}
                  className={`sample-tile ${
                    seed === null && selected === s.id ? "selected" : ""
                  }`}
                  onClick={() => {
                    setSelected(s.id);
                    setSeed(null);
                  }}
                >
                  <img src={s.thermal_png} alt={`scene ${s.id}`} />
                  <figcaption>#{s.id}</figcaption>
                </button>
              ))}
            </div>
            <p className="field-note">
              Synthetic scenes rendered from the same sensor simulators used in
              training. Thumbnails show the 32x24 thermal frame.
            </p>
          </Panel>

          <Panel title="Sensors in play">
            {modality(0, "Thermal array (MLX90640, 32x24)")}
            {modality(1, "Acoustic echoes (chirp + microphone)")}
            {modality(2, "Ultrasonic ranges (2x HC-SR04)")}
            <p className="field-note">
              Disable a sensor to see the model fall back on its learned mask
              tokens - the reconstruction degrades gracefully instead of
              breaking.
            </p>
          </Panel>

          <Panel title="Run">
            <div className="btn-row">
              <button
                className="btn primary"
                disabled={busy}
                onClick={() => run(seed !== null ? { seed } : undefined)}
              >
                {busy ? "Reconstructing…" : "Run reconstruction"}
              </button>
              <button
                className="btn"
                disabled={busy}
                onClick={() => {
                  const s = Math.floor(Math.random() * 100000);
                  setSeed(s);
                  run({ seed: s });
                }}
              >
                Random scene
              </button>
              <button
                className="btn"
                disabled={busy}
                onClick={() => fileRef.current?.click()}
              >
                Upload .npz
              </button>
              <input
                ref={fileRef}
                type="file"
                accept=".npz"
                hidden
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) runUpload(f);
                  e.target.value = "";
                }}
              />
            </div>
            <p className="field-note">
              .npz keys: thermal (1,24,32) · echo (2,64,64) · sonar (10,) - any
              subset, values in [0,1]. Recordings from the prototype node
              (host/receiver.py) drop straight in.
            </p>
            {err && (
              <p className="field-note" style={{ color: "var(--critical)" }}>
                {err}
              </p>
            )}
          </Panel>
        </div>

        {/* --------------------------------------------- output column */}
        <div className="stack">
          {res && (
            <>
              <Panel
                title="Sensor observation"
                right={
                  <span className="chip mono">
                    mask&nbsp;
                    {res.inputs.mask.map((m) => (m ? "1" : "0")).join("")}
                  </span>
                }
              >
                <div className="output-grid">
                  <Frame
                    label="Thermal 32x24"
                    src={res.inputs.thermal_png}
                    corner={res.inputs.mask[0] ? "active" : "masked"}
                  />
                  <Frame
                    label="Echo spectrogram"
                    src={res.inputs.echo_png}
                    corner={res.inputs.mask[1] ? "active" : "masked"}
                  />
                  <div>
                    <div className="stat" style={{ marginBottom: 8 }}>
                      <div className="k">Sonar left</div>
                      <div className="v">
                        {res.inputs.sonar.left_valid
                          ? res.inputs.sonar.left_m.toFixed(2)
                          : "—"}
                        <span className="u">m</span>
                      </div>
                    </div>
                    <div className="stat">
                      <div className="k">Sonar right</div>
                      <div className="v">
                        {res.inputs.sonar.right_valid
                          ? res.inputs.sonar.right_m.toFixed(2)
                          : "—"}
                        <span className="u">m</span>
                      </div>
                    </div>
                  </div>
                </div>
              </Panel>

              <Panel
                title="Reconstruction"
                right={
                  <span style={{ display: "flex", gap: 8 }}>
                    <Chip tone="accent" mono>
                      {res.outputs.latency_ms.toFixed(0)} ms
                    </Chip>
                    <button className="btn small" onClick={download}>
                      Download PNG
                    </button>
                  </span>
                }
              >
                <div className="output-grid">
                  <div>
                    <Frame
                      label={showColor ? "View · inferred color" : "View · grayscale"}
                      smooth
                    >
                      <canvas ref={canvasRef} />
                    </Frame>
                    {res.outputs.has_color && (
                      <div style={{ marginTop: 10 }}>
                        <label className="check-row">
                          <input
                            type="checkbox"
                            checked={showColor}
                            onChange={(e) => setShowColor(e.target.checked)}
                          />
                          Colorize (inferred, not measured)
                        </label>
                        {showColor && (
                          <>
                            <input
                              type="range"
                              min={0}
                              max={1}
                              step={0.01}
                              value={gate}
                              onChange={(e) =>
                                setGate(parseFloat(e.target.value))
                              }
                            />
                            <p className="field-note">
                              Confidence gate {gate.toFixed(2)} - color is
                              painted only where the model trusts its own
                              estimate; elsewhere the view stays grayscale.
                            </p>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                  <div>
                    <Frame
                      label="Depth"
                      src={res.outputs.depth_png}
                      smooth
                    />
                    <div className="depth-legend">
                      <span>{res.outputs.depth_max_m.toFixed(1)} m</span>
                      <div className="ramp" style={{ transform: "scaleX(-1)" }} />
                      <span>{res.outputs.depth_min_m.toFixed(1)} m</span>
                    </div>
                  </div>
                  {res.outputs.conf_png && (
                    <Frame
                      label="Color confidence"
                      src={res.outputs.conf_png}
                      smooth
                      corner={`mean ${res.outputs.conf_mean?.toFixed(2)}`}
                    />
                  )}
                </div>
              </Panel>

              {res.truth && (
                <Panel title="Reference (synthetic ground truth)">
                  <div className="output-grid">
                    <Frame label="True luminance" src={res.truth.gray_png} smooth />
                    <Frame label="True depth" src={res.truth.depth_png} smooth />
                  </div>
                  <p className="field-note">
                    Available for demo scenes only - a real capture has no
                    optical ground truth at inference time.
                  </p>
                </Panel>
              )}
            </>
          )}

          {!res && (
            <Panel>
              <div className="empty-state">
                Pick a demo scene (or upload a recording) and hit{" "}
                <code>Run reconstruction</code>.
                <br />
                {props.info && !props.info.trained && (
                  <>Outputs will be noise until a checkpoint is trained.</>
                )}
              </div>
            </Panel>
          )}
        </div>
      </div>
    </>
  );
}
