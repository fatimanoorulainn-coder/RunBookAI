"use client";
import { useState } from "react";

type Evidence = {
  id: string;
  source: "metadata" | "logs" | "runbooks";
  content: string;
  source_location: string;
  timestamp: string;
  relevance_score: number;
};
type Trace = {
  step_number: number;
  tool_name: string;
  tool_input: Record<string, any>;
  tool_output: string;
  latency_ms: number | null;
};
type Investigation = {
  root_cause: string;
  status: "resolved" | "insufficient_evidence";
  confidence_score: number;
  missing_evidence: string[];
  evidence: Evidence[];
};
type Result = { investigation: Investigation; traces: Trace[] };

function band(s: number) {
  return s >= 0.7 ? "High" : s >= 0.4 ? "Moderate" : "Low";
}
function fmtLatency(ms: number | null) {
  if (ms == null) return "—";
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${Math.round(ms)}ms`;
}
function fmtTime(ts: string) {
  try {
    return new Date(ts).toLocaleTimeString([], { hour12: false }) + "." +
      String(new Date(ts).getMilliseconds()).padStart(3, "0");
  } catch {
    return ts;
  }
}

function Gauge({ score }: { score: number }) {
  const filled = Math.round(score * 10);
  return (
    <div className="gauge">
      <div className="row">
        <span className="cap">Confidence</span>
        <span className="val">
          {score.toFixed(2)}
          <span className="band">{band(score)}</span>
        </span>
      </div>
      <div className="ticks">
        {Array.from({ length: 10 }).map((_, i) => (
          <span key={i} className={`tick${i < filled ? " on" : ""}`} />
        ))}
      </div>
    </div>
  );
}

function Verdict({ result }: { result: Result }) {
  const inv = result.investigation;
  const abstain = inv.status === "insufficient_evidence";
  return (
    <div className={`verdict${abstain ? " abstain" : ""}`}>
      <div className="bar" />
      <div className="body">
        <span className={`stamp ${abstain ? "hold" : "ok"}`}>
          <span className="dot" /> {abstain ? "Insufficient evidence" : "Resolved"}
        </span>
        <div className="rc-label">{abstain ? "No confident root cause" : "Root cause"}</div>
        <p className="rc">{inv.root_cause}</p>
        <Gauge score={inv.confidence_score} />
        {abstain && inv.missing_evidence?.length > 0 && (
          <div className="missing">
            <div className="cap">What was missing</div>
            <ul>{inv.missing_evidence.map((m, i) => <li key={i}>{m}</li>)}</ul>
          </div>
        )}
        <div className="meta">
          <span>{result.traces?.length ?? 0} steps</span>
          <span>{inv.evidence?.length ?? 0} evidence</span>
        </div>
      </div>
    </div>
  );
}

function IOValue({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  const long = text.length > 160;
  return (
    <span
      className={`v${long ? " expandable" : ""}${open ? " open" : ""}`}
      onClick={() => long && setOpen(!open)}
    >
      {text}
      {long && !open && <span className="more"> … show more</span>}
    </span>
  );
}

function Timeline({ traces }: { traces: Trace[] }) {
  if (!traces?.length) return null;
  return (
    <>
      <div className="section-label">Execution timeline</div>
      <div className="timeline">
        {traces.map((t, i) => {
          const slow = (t.latency_ms ?? 0) >= 1000;
          const input = Object.entries(t.tool_input)
            .map(([k, v]) => `${k}=${typeof v === "string" ? v : JSON.stringify(v)}`)
            .join("  ");
          return (
            <div className="step done" key={i}>
              <div className="node">{i + 1}</div>
              <div className="head">
                <span className="tool">{t.tool_name}</span>
                <span className={`lat${slow ? " slow" : ""}`}>{fmtLatency(t.latency_ms)}</span>
              </div>
              <div className="io">
                <div className="line">
                  <span className="k">input</span>
                  <IOValue text={input || "—"} />
                </div>
                <div className="line">
                  <span className="k">output</span>
                  <IOValue text={t.tool_output || "(empty)"} />
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </>
  );
}

function EvidenceTree({ result }: { result: Result }) {
  const inv = result.investigation;
  if (!inv.evidence?.length) return null;
  const abstain = inv.status === "insufficient_evidence";
  return (
    <>
      <div className="section-label">Evidence</div>
      <div className={`tree${abstain ? " abstain" : ""}`}>
        <div className="rootline">
          <span className="glyph">└─</span>
          <span>{abstain ? "Inconclusive" : inv.root_cause}</span>
        </div>
        <div className="branch">
          {inv.evidence.map((e) => (
            <div className="exhibit" key={e.id}>
              <div className="top">
                <span className={`src ${e.source}`}>{e.source}</span>
                <span className="rel">
                  <span
                    className={`relbar${e.relevance_score === 0 ? " zero" : e.relevance_score < 0.4 ? " low" : ""}`}
                  >
                    {e.relevance_score > 0 && (
                      <span style={{ width: `${Math.round(e.relevance_score * 100)}%` }} />
                    )}
                  </span>
                  rel {e.relevance_score.toFixed(2)}
                </span>
              </div>
              <div className="loc">{e.source_location}</div>
              <div className="ts">{fmtTime(e.timestamp)}</div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

export default function Home() {
  const [question, setQuestion] = useState("why is payment-service degraded?");
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function investigate() {
    setLoading(true);
    setResult(null);
    setError(null);
    try {
      const res = await fetch("http://localhost:8000/investigate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      if (!res.ok) throw new Error(`Backend returned ${res.status}`);
      setResult(await res.json());
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  const examples = ["payment-service", "checkout-service", "ghost-service"];

  return (
    <main className="wrap">
      <div className="eyebrow">RunBookAI · incident readout</div>
      <h1 className="title">What broke, and why.</h1>
      <p className="tagline">
        Ask about a degraded service. The agent gathers evidence, correlates it,
        and returns a grounded verdict — or tells you it couldn&apos;t.
      </p>

      <div className="console">
        <span className="caret">&gt;</span>
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !loading && investigate()}
          placeholder="why is checkout-service degraded?"
        />
        <button className="run" onClick={investigate} disabled={loading}>
          {loading ? "investigating" : "investigate"}
        </button>
      </div>

      <div className="chips">
        {examples.map((ex) => (
          <button
            key={ex}
            className="chip"
            disabled={loading}
            onClick={() => setQuestion(`why is ${ex} degraded?`)}
          >
            {ex}
          </button>
        ))}
      </div>

      {loading && (
        <div className="scan">
          <div className="label">
            Gathering evidence — metadata, logs, runbooks. First run loads the
            embedding model (~40s).
          </div>
          <div className="track" />
        </div>
      )}

      {error && <div className="err">{error}</div>}

      {result && (
        <>
          <Verdict result={result} />
          <Timeline traces={result.traces} />
          <EvidenceTree result={result} />
        </>
      )}
    </main>
  );
}