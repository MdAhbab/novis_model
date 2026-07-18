import { useEffect, useState } from "react";
import { api, ModelInfo } from "./api";
import { Icons } from "./components";
import Live from "./pages/Live";
import ModelPage from "./pages/ModelInfo";
import Reconstruct from "./pages/Reconstruct";
import Training from "./pages/Training";

type Page = "reconstruct" | "live" | "training" | "model";

const NAV: { id: Page; label: string; icon: JSX.Element }[] = [
  { id: "reconstruct", label: "Reconstruct", icon: Icons.reconstruct },
  { id: "live", label: "Live stream", icon: Icons.live },
  { id: "training", label: "Training", icon: Icons.training },
  { id: "model", label: "Model", icon: Icons.model },
];

export default function App() {
  const [page, setPage] = useState<Page>("reconstruct");
  const [info, setInfo] = useState<ModelInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .model()
      .then(setInfo)
      .catch((e) => setError(String(e)));
  }, []);

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="8" stroke="#3987e5" strokeWidth="2" />
              <circle cx="12" cy="12" r="2.6" fill="#e66767" />
            </svg>
          </div>
          <div>
            <h1>NOVIS</h1>
            <span>non-optical vision</span>
          </div>
        </div>
        {NAV.map((n) => (
          <button
            key={n.id}
            className={`nav-btn ${page === n.id ? "active" : ""}`}
            onClick={() => setPage(n.id)}
          >
            {n.icon}
            {n.label}
          </button>
        ))}
        <div className="sidebar-foot">
          {info ? (
            <>
              NOVISNet · {info.params_m} M params
              <br />
              {info.device_name}
              <br />
              {info.trained ? "trained checkpoint" : "untrained weights"}
            </>
          ) : (
            "connecting to server…"
          )}
        </div>
      </aside>

      <main className="main">
        {error && (
          <div className="banner">
            <strong>Server unreachable.</strong>&nbsp;Start it with
            &nbsp;<code>python run.py</code>&nbsp;from the NOVIS_Model folder.
            ({error})
          </div>
        )}
        {info && !info.trained && (
          <div className="banner">
            <strong>Untrained weights.</strong>&nbsp;No matching checkpoint was
            found, so reconstructions below are noise. Train with
            &nbsp;<code>python train.py</code>&nbsp;(see README), then restart.
          </div>
        )}
        {page === "reconstruct" && <Reconstruct info={info} />}
        {page === "live" && <Live />}
        {page === "training" && <Training />}
        {page === "model" && <ModelPage info={info} />}
      </main>
    </div>
  );
}
