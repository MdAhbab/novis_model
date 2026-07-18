import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, RunData, RunsResponse } from "../api";
import { Panel, Stat } from "../components";

const SERIES = {
  train_loss: "var(--series-1)",
  val_loss: "var(--series-5)",
  psnr: "var(--series-1)",
  ssim: "var(--series-2)",
  lpips: "var(--series-4)",
  rmse_m: "var(--series-3)",
  d_loss: "var(--series-3)",
};

function Curve(props: {
  title: string;
  rows: Record<string, number | string>[];
  keys: (keyof typeof SERIES)[];
}) {
  const keys = props.keys.filter((k) =>
    props.rows.some((r) => typeof r[k] === "number"),
  );
  if (keys.length === 0) return null;
  return (
    <Panel className="chart-box">
      <h4>{props.title}</h4>
      {keys.length > 1 && (
        <div className="legend-row">
          {keys.map((k) => (
            <span key={k}>
              <span className="sw" style={{ background: SERIES[k] }} />
              {k}
            </span>
          ))}
        </div>
      )}
      <ResponsiveContainer width="100%" height={210}>
        <LineChart data={props.rows} margin={{ top: 6, right: 8, bottom: 0, left: -14 }}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="0" vertical={false} />
          <XAxis
            dataKey="epoch"
            stroke="var(--text-3)"
            tick={{ fontSize: 11, fill: "var(--text-3)" }}
            tickLine={false}
            axisLine={{ stroke: "var(--border-strong)" }}
          />
          <YAxis
            stroke="var(--text-3)"
            tick={{ fontSize: 11, fill: "var(--text-3)" }}
            tickLine={false}
            axisLine={false}
            width={58}
            domain={["auto", "auto"]}
            tickFormatter={(v: number) => v.toPrecision(3)}
          />
          <Tooltip
            contentStyle={{
              background: "var(--surface-2)",
              border: "1px solid var(--border-strong)",
              borderRadius: 8,
              fontSize: 12,
            }}
            labelStyle={{ color: "var(--text-3)" }}
            labelFormatter={(l) => `epoch ${l}`}
          />
          {keys.map((k) => (
            <Line
              key={k}
              type="monotone"
              dataKey={k}
              stroke={SERIES[k]}
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </Panel>
  );
}

export default function Training() {
  const [data, setData] = useState<RunsResponse | null>(null);
  const [active, setActive] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api
      .runs()
      .then((d) => {
        setData(d);
        if (d.runs.length) setActive(d.runs[d.runs.length - 1].name);
      })
      .catch((e) => setErr(String(e)));
  }, []);

  const run: RunData | undefined = useMemo(
    () => data?.runs.find((r) => r.name === active),
    [data, active],
  );

  const last = run?.rows[run.rows.length - 1];

  return (
    <>
      <div className="page-head">
        <h2>Training</h2>
        <p>
          Curves are read from checkpoints/&lt;run&gt;/log.csv, written by
          train.py. Metrics on held-out data land here after eval.py runs.
        </p>
      </div>

      {err && <div className="banner">{err}</div>}

      {data && data.runs.length === 0 && (
        <Panel>
          <div className="empty-state">
            No training runs found. Start one with
            <br />
            <br />
            <code>
              python train.py --config configs/debug_tiny.yaml --data synthetic
            </code>
          </div>
        </Panel>
      )}

      {data && data.runs.length > 0 && (
        <>
          <div className="run-tabs">
            {data.runs.map((r) => (
              <button
                key={r.name}
                className={`btn small ${r.name === active ? "primary" : ""}`}
                onClick={() => setActive(r.name)}
              >
                {r.name} · {r.epochs} ep
              </button>
            ))}
          </div>

          {run && last && (
            <div className="stack">
              <div className="stat-row">
                <Stat
                  k="Val loss"
                  v={Number(last.val_loss ?? NaN).toFixed(4)}
                />
                <Stat k="PSNR" v={Number(last.psnr ?? NaN).toFixed(2)} u="dB" />
                <Stat k="SSIM" v={Number(last.ssim ?? NaN).toFixed(3)} />
                {typeof last.lpips === "number" && (
                  <Stat k="LPIPS" v={last.lpips.toFixed(3)} />
                )}
                {typeof last.rmse_m === "number" && (
                  <Stat k="Depth RMSE" v={last.rmse_m.toFixed(2)} u="m" />
                )}
              </div>

              <div className="chart-grid">
                <Curve
                  title="Loss"
                  rows={run.rows}
                  keys={["train_loss", "val_loss"]}
                />
                <Curve title="PSNR (dB)" rows={run.rows} keys={["psnr"]} />
                <Curve title="SSIM" rows={run.rows} keys={["ssim"]} />
                <Curve title="LPIPS (lower is better)" rows={run.rows} keys={["lpips"]} />
                <Curve title="Depth RMSE (m)" rows={run.rows} keys={["rmse_m"]} />
                <Curve title="Discriminator loss" rows={run.rows} keys={["d_loss"]} />
              </div>
            </div>
          )}
        </>
      )}

      {data?.results?.metrics && (
        <Panel title="Held-out evaluation (results/metrics.json)">
          <table className="kv">
            <tbody>
              {Object.entries(data.results.metrics).map(([k, v]) => (
                <tr key={k}>
                  <td>{k}</td>
                  <td>{typeof v === "number" ? v.toFixed(4) : String(v)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      )}
    </>
  );
}
