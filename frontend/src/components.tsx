import { ReactNode } from "react";

export function Panel(props: {
  title?: string;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${props.className ?? ""}`}>
      {props.title && (
        <h3 className="panel-title">
          <span>{props.title}</span>
          {props.right}
        </h3>
      )}
      {props.children}
    </section>
  );
}

export function Chip(props: {
  tone?: "ok" | "warn" | "accent" | "plain";
  mono?: boolean;
  children: ReactNode;
}) {
  const tone = props.tone === "plain" || !props.tone ? "" : props.tone;
  return (
    <span className={`chip ${tone} ${props.mono ? "mono" : ""}`}>
      <span className="dot" />
      {props.children}
    </span>
  );
}

export function Frame(props: {
  label?: string;
  corner?: string;
  src?: string;
  smooth?: boolean;
  children?: ReactNode;
}) {
  return (
    <figure
      className={`frame ${props.smooth ? "smooth" : ""}`}
      style={{ margin: 0 }}
    >
      {props.src && <img src={props.src} alt={props.label ?? "frame"} />}
      {props.children}
      {props.label && <span className="frame-label">{props.label}</span>}
      {props.corner && <span className="frame-corner">{props.corner}</span>}
    </figure>
  );
}

export function Stat(props: { k: string; v: string | number; u?: string }) {
  return (
    <div className="stat">
      <div className="k">{props.k}</div>
      <div className="v">
        {props.v}
        {props.u && <span className="u">{props.u}</span>}
      </div>
    </div>
  );
}

export const Icons = {
  reconstruct: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="M3 14l5-4 4 3 4-5 5 6" />
    </svg>
  ),
  live: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <circle cx="12" cy="12" r="2.4" fill="currentColor" stroke="none" />
      <path d="M7.5 7.5a6.4 6.4 0 000 9M16.5 7.5a6.4 6.4 0 010 9" />
      <path d="M4.8 4.8a10.2 10.2 0 000 14.4M19.2 4.8a10.2 10.2 0 010 14.4" />
    </svg>
  ),
  training: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M4 19V5M4 19h16" />
      <path d="M7 15l4-6 3 3 5-7" />
    </svg>
  ),
  model: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <rect x="4" y="4" width="7" height="7" rx="1.5" />
      <rect x="13" y="4" width="7" height="7" rx="1.5" />
      <rect x="4" y="13" width="7" height="7" rx="1.5" />
      <rect x="13" y="13" width="7" height="7" rx="1.5" />
    </svg>
  ),
};
