import { ModelInfo } from "../api";
import { Chip, Panel, Stat } from "../components";

function Arrow() {
  return (
    <span className="arch-arrow">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M5 12h14M13 6l6 6-6 6" />
      </svg>
    </span>
  );
}

export default function ModelPage(props: { info: ModelInfo | null }) {
  const info = props.info;
  if (!info) {
    return (
      <Panel>
        <div className="empty-state">Waiting for the server…</div>
      </Panel>
    );
  }
  const [oh, ow] = info.out_hw;
  const stages = info.decoder_chs.length;

  return (
    <>
      <div className="page-head">
        <h2>Model</h2>
        <p>
          NOVISNet fuses three non-optical sensor streams into aligned
          grayscale, depth, and optional color reconstructions. Numbers below
          are read live from the served model.
        </p>
      </div>

      <div className="stack">
        <div className="stat-row">
          <Stat k="Parameters" v={info.params_m} u="M" />
          <Stat k="Fusion blocks" v={info.depth} />
          <Stat k="Token dim" v={info.dim} />
          <Stat k="Output" v={`${ow}x${oh}`} u="px" />
          <Stat k="Latency device" v={info.device.toUpperCase()} />
        </div>

        <Panel
          title="Architecture"
          right={
            <span style={{ display: "flex", gap: 8 }}>
              <Chip tone={info.trained ? "ok" : "warn"}>
                {info.trained ? "checkpoint loaded" : "untrained"}
              </Chip>
              <Chip tone="accent">{info.device_name}</Chip>
            </span>
          }
        >
          <div className="arch-flow">
            <div className="arch-node">
              <div className="t">Thermal stem</div>
              <div className="d">
                1x24x32 → {info.tokens.thermal} tokens
                <br />+ 24x32 skip map
              </div>
            </div>
            <div className="arch-node">
              <div className="t">Echo stem</div>
              <div className="d">2x64x64 → {info.tokens.echo} tokens</div>
            </div>
            <div className="arch-node">
              <div className="t">Sonar stem</div>
              <div className="d">10-vector → {info.tokens.sonar} tokens</div>
            </div>
            <Arrow />
            <div className="arch-node hot">
              <div className="t">Fusion backbone</div>
              <div className="d">
                {info.depth}x sandwich blocks
                <br />
                dim {info.dim} · {info.heads} heads · FFN x{info.ffn_ratio}
                <br />
                mask tokens for absent sensors
              </div>
            </div>
            <Arrow />
            <div className="arch-node hot">
              <div className="t">Decoder</div>
              <div className="d">
                {stages}x PixelShuffle stages
                <br />
                [{info.decoder_chs.join(", ")}]
                <br />
                thermal skip @ 24x32
              </div>
            </div>
            <Arrow />
            <div className="arch-node">
              <div className="t">Heads</div>
              <div className="d">
                grayscale · inverse depth
                {info.color_head && (
                  <>
                    <br />
                    ab color · confidence (optional)
                  </>
                )}
              </div>
            </div>
          </div>
        </Panel>

        <div className="grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
          <Panel title="Serving">
            <table className="kv">
              <tbody>
                <tr>
                  <td>Config</td>
                  <td>{info.config}</td>
                </tr>
                <tr>
                  <td>Checkpoint</td>
                  <td>{info.checkpoint ?? "none (random init)"}</td>
                </tr>
                <tr>
                  <td>Device</td>
                  <td>
                    {info.device} ({info.device_name})
                  </td>
                </tr>
                <tr>
                  <td>Color head</td>
                  <td>
                    {info.color_head
                      ? "enabled (rendered only on request)"
                      : "disabled"}
                  </td>
                </tr>
                <tr>
                  <td>Token grid</td>
                  <td>
                    {info.grid_hw[1]}x{info.grid_hw[0]} → {ow}x{oh}
                  </td>
                </tr>
              </tbody>
            </table>
          </Panel>

          <Panel title="Config (resolved)">
            <pre className="code" style={{ maxHeight: 320, overflowY: "auto" }}>
              {JSON.stringify(info.config_dump, null, 2)}
            </pre>
          </Panel>
        </div>
      </div>
    </>
  );
}
