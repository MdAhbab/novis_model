import { useEffect, useRef, useState } from "react";
import { LiveFrame, liveSocket } from "../api";
import { Chip, Frame, Panel, Stat } from "../components";

export default function Live() {
  const [running, setRunning] = useState(false);
  const [frame, setFrame] = useState<LiveFrame | null>(null);
  const [fps, setFps] = useState(0);
  const wsRef = useRef<WebSocket | null>(null);
  const timesRef = useRef<number[]>([]);

  const stop = () => {
    wsRef.current?.close();
    wsRef.current = null;
    setRunning(false);
  };

  const start = () => {
    const ws = liveSocket();
    wsRef.current = ws;
    ws.onmessage = (ev) => {
      const f = JSON.parse(ev.data) as LiveFrame;
      setFrame(f);
      const now = performance.now();
      const times = timesRef.current;
      times.push(now);
      while (times.length > 12) times.shift();
      if (times.length > 1) {
        setFps(
          ((times.length - 1) / (times[times.length - 1] - times[0])) * 1000,
        );
      }
    };
    ws.onclose = () => setRunning(false);
    ws.onerror = () => setRunning(false);
    setRunning(true);
  };

  useEffect(() => {
    return () => {
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, []);

  return (
    <>
      <div className="page-head">
        <h2>Live stream</h2>
        <p>
          A continuously animated scene is sensed, streamed, and reconstructed
          in real time - the same path a BLE-connected sensor node takes
          through host/receiver.py, minus the radio.
        </p>
      </div>

      <div className="grid live-grid">
        <Panel
          title="Reconstruction"
          right={
            running ? (
              <Chip tone="ok">
                <span className="pulse">streaming</span>
              </Chip>
            ) : (
              <Chip>stopped</Chip>
            )
          }
        >
          {frame ? (
            <Frame
              label="Grayscale view"
              src={frame.gray_png}
              smooth
              corner={`t = ${frame.t.toFixed(1)} s`}
            />
          ) : (
            <div className="empty-state">
              Press <code>Start stream</code> to begin.
            </div>
          )}
          <div className="btn-row" style={{ marginTop: 12 }}>
            {!running ? (
              <button className="btn primary" onClick={start}>
                Start stream
              </button>
            ) : (
              <button className="btn" onClick={stop}>
                Stop
              </button>
            )}
          </div>
        </Panel>

        <div className="stack">
          <div className="stat-row">
            <Stat k="Frame rate" v={fps ? fps.toFixed(1) : "—"} u="fps" />
            <Stat
              k="Model latency"
              v={frame ? frame.latency_ms.toFixed(0) : "—"}
              u="ms"
            />
          </div>
          {frame && (
            <>
              <Panel title="Sensor input">
                <Frame label="Thermal 32x24" src={frame.thermal_png} />
              </Panel>
              <Panel title="Depth">
                <Frame label="Depth" src={frame.depth_png} smooth />
              </Panel>
              <Panel title="Scene (simulator truth)">
                <Frame label="True luminance" src={frame.truth_gray_png} smooth />
              </Panel>
            </>
          )}
        </div>
      </div>
    </>
  );
}
