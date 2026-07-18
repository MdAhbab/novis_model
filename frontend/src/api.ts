/** Typed client for the NOVIS FastAPI backend. */

export interface ModelInfo {
  name: string;
  params_m: number;
  dim: number;
  depth: number;
  heads: number;
  ffn_ratio: number;
  decoder_chs: number[];
  color_head: boolean;
  out_hw: [number, number];
  grid_hw: [number, number];
  tokens: { thermal: number; echo: number; sonar: number };
  device: string;
  device_name: string;
  checkpoint: string | null;
  trained: boolean;
  config: string;
  config_dump: Record<string, unknown>;
}

export interface SampleSummary {
  id: number;
  thermal_png: string;
  near_m: number;
}

export interface SensorInputs {
  thermal_png: string;
  echo_png: string;
  sonar: {
    left_m: number;
    right_m: number;
    left_valid: boolean;
    right_valid: boolean;
    max_m: number;
  };
  mask: [boolean, boolean, boolean];
}

export interface Outputs {
  gray_png: string;
  depth_png: string;
  depth_min_m: number;
  depth_max_m: number;
  latency_ms: number;
  has_color: boolean;
  color_png?: string;
  conf_png?: string;
  conf_mean?: number;
}

export interface InferResponse {
  inputs: SensorInputs;
  truth: { gray_png: string; depth_png: string } | null;
  outputs: Outputs;
}

export interface RunData {
  name: string;
  epochs: number;
  columns: string[];
  rows: Record<string, number | string>[];
  has_best: boolean;
}

export interface RunsResponse {
  runs: RunData[];
  results: { checkpoint?: string; metrics?: Record<string, number> } | null;
}

export interface LiveFrame extends Outputs {
  t: number;
  thermal_png: string;
  truth_gray_png: string;
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status}: ${body.slice(0, 200)}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  model: () => fetch("/api/model").then((r) => json<ModelInfo>(r)),
  samples: () =>
    fetch("/api/samples").then((r) => json<{ samples: SampleSummary[] }>(r)),
  infer: (body: {
    sample_id?: number;
    seed?: number;
    mask?: [boolean, boolean, boolean];
  }) =>
    fetch("/api/infer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then((r) => json<InferResponse>(r)),
  inferUpload: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return fetch("/api/infer/upload", { method: "POST", body: fd }).then((r) =>
      json<InferResponse>(r),
    );
  },
  runs: () => fetch("/api/runs").then((r) => json<RunsResponse>(r)),
};

export function liveSocket(): WebSocket {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  return new WebSocket(`${proto}://${location.host}/ws/live`);
}
