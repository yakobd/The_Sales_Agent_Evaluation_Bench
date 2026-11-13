/* Creative QA Console - single-page app (React 18 + htm, no build step). */
const { useState, useEffect, useMemo, useRef, useCallback, createContext, useContext } = React;
const html = htm.bind(React.createElement);

/* ── helpers ─────────────────────────────────────────────────────────── */
async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail ? (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)) : res.statusText);
  return data;
}
function useApi(path, deps = []) {
  const [state, set] = useState({ data: null, error: null, loading: true });
  useEffect(() => {
    let live = true;
    if (!path) { set({ data: null, error: null, loading: false }); return; }
    set(s => ({ ...s, loading: true }));
    api(path).then(d => live && set({ data: d, error: null, loading: false }))
      .catch(e => live && set({ data: null, error: e.message, loading: false }));
    return () => { live = false; };
  }, [path, ...deps]);
  return state;
}
const pct = (x, d = 1) => (x == null ? "–" : `${(x * 100).toFixed(d)}%`);
const num = (x, d = 3) => (x == null ? "–" : Number(x).toFixed(d));
const signed = (x, d = 3) => (x == null ? "–" : `${x >= 0 ? "+" : "−"}${Math.abs(x).toFixed(d)}`);
const ls = {
  get(k, d) { try { const v = localStorage.getItem(k); return v == null ? d : v; } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} },
};
const PRETTY = {
  week10: "Week 10 template (original)", week10_v2: "Week 10 template v2 (honest)",
  base_short: "Qwen3.5-2B · short prompt", prompt_engineered: "Qwen3.5-2B · full-rules prompt", trained: "Qwen3.5-2B + LoRA",
};
const pretty = c => PRETTY[c] || c;
const DIM_LABEL = { commercial_safety: "commercial safety", brand_safety: "brand safety" };
const dimLabel = d => DIM_LABEL[d] || d;

/* ── tooltip ─────────────────────────────────────────────────────────── */
const TipCtx = createContext(() => {});
function TipLayer({ children }) {
  const [tip, setTip] = useState(null);
  return html`<${TipCtx.Provider} value=${setTip}>
    ${children}
    ${tip && html`<div class="tip" role="tooltip" style=${{ left: Math.min(tip.x + 14, window.innerWidth - 320), top: tip.y + 14 }}>${tip.content}</div>`}
  </${TipCtx.Provider}>`;
}
function useTip() {
  const setTip = useContext(TipCtx);
  return content => ({
    onMouseMove: e => setTip({ x: e.clientX, y: e.clientY, content }),
    onMouseLeave: () => setTip(null),
  });
}

/* ── icons ───────────────────────────────────────────────────────────── */
const I = {
  overview: html`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/></svg>`,
  check: html`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M9 11l3 3 8-8"/><path d="M20 12v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9"/></svg>`,
  exp: html`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></svg>`,
  gate: html`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="M9 12l2 2 4-4"/></svg>`,
  traces: html`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 6h16M4 12h16M4 18h10"/></svg>`,
  review: html`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="9" cy="8" r="4"/><path d="M2 21c0-4 3-6 7-6s7 2 7 6"/><path d="M16 11l2 2 4-4"/></svg>`,
  ab: html`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 20l4-12 4 12M5.5 16h5"/><path d="M15 8h3.5a2.5 2.5 0 0 1 0 5H15zm0 5h4a2.5 2.5 0 0 1 0 5h-4z"/></svg>`,
  cost: html`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="9"/><path d="M15 9.5c-.5-1-1.6-1.5-3-1.5-1.7 0-3 .8-3 2s1.3 1.7 3 2 3 .9 3 2.1-1.3 1.9-3 1.9c-1.4 0-2.6-.6-3-1.6M12 6.5V8M12 16v1.5"/></svg>`,
  sun: html`<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>`,
};
const PassIcon = () => html`<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>`;
const FailIcon = () => html`<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M6 6l12 12M18 6L6 18"/></svg>`;
const Verdict = ({ pass, children }) => html`<span class=${`pill ${pass ? "pass" : "fail"}`}>${pass ? html`<${PassIcon}/>` : html`<${FailIcon}/>`}${children || (pass ? "pass" : "fail")}</span>`;

/* ── evidence highlighting ───────────────────────────────────────────── */
function needlesFrom(violations) {
  const out = new Set();
  for (const v of violations || []) {
    const ev = v.evidence || "";
    for (const m of ev.matchAll(/'([^']{2,80})'/g)) out.add(m[1]);
    const head = ev.split(" (")[0].replace(/^'+|'+$/g, "");
    if (head.length >= 3 && head.length <= 60 && !/^\d+ [<>]/.test(head) && !/^(none|no |copy |final url)/i.test(head)) out.add(head);
  }
  return [...out].filter(s => s.trim().length >= 2).sort((a, b) => b.length - a.length);
}
function Highlight({ text, needles }) {
  if (!text) return null;
  if (!needles || !needles.length) return text;
  const esc = needles.map(n => n.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const re = new RegExp(`(${esc.join("|")})`, "gi");
  return text.split(re).map((part, i) => (i % 2 ? html`<mark key=${i}>${part}</mark>` : part));
}

/* ── charts (SVG, single axis, thin marks, hover on every mark) ──────── */
function CIChart({ rows, domain = [0, 1], fmt = v => pct(v, 1) }) {
  const tip = useTip();
  const W = 560, rowH = 32, left = 190, right = 62, top = 16;
  const H = top + rows.length * rowH + 18;
  const x = v => left + ((v - domain[0]) / (domain[1] - domain[0])) * (W - left - right);
  const ticks = [0, 0.25, 0.5, 0.75, 1].map(t => domain[0] + t * (domain[1] - domain[0]));
  return html`<svg class="chart" viewBox=${`0 0 ${W} ${H}`} role="img" aria-label="pass@1 with 95% confidence intervals">
    ${ticks.map(t => html`<g key=${t}><line class="gridline" x1=${x(t)} x2=${x(t)} y1=${top - 6} y2=${H - 16}/>
      <text x=${x(t)} y=${H - 3} text-anchor="middle">${fmt(t)}</text></g>`)}
    ${rows.map((r, i) => {
      const cy = top + i * rowH + rowH / 2;
      const col = r.highlight ? "var(--series-1)" : "var(--baseline)";
      return html`<g key=${r.label} ...${tip(html`<div><b>${r.label}</b><br/>pass@1 ${fmt(r.value)}${r.ci ? html`<br/>95% CI ${fmt(r.ci[0])} – ${fmt(r.ci[1])}` : ""}${r.n ? html`<br/>n = ${r.n}` : ""}${r.note ? html`<br/><span class="muted">${r.note}</span>` : ""}</div>`)}>
        <rect class="hit" x="0" y=${cy - rowH / 2} width=${W} height=${rowH}/>
        <text class="lbl" x=${left - 12} y=${cy + 4} text-anchor="end">${r.label}</text>
        ${r.ci && html`<line x1=${x(r.ci[0])} x2=${x(r.ci[1])} y1=${cy} y2=${cy} stroke=${col} stroke-width="2" stroke-linecap="round"/>`}
        <line x1=${x(domain[0])} x2=${x(r.value)} y1=${cy} y2=${cy} stroke=${col} stroke-width="2" opacity=".18"/>
        <circle cx=${x(r.value)} cy=${cy} r="5.5" fill=${col} stroke="var(--surface-1)" stroke-width="2"/>
        <text x=${Math.max(x(r.ci ? r.ci[1] : r.value), x(r.value)) + 9} y=${cy + 4} class="lbl">${fmt(r.value)}</text>
      </g>`;
    })}
  </svg>`;
}

function DeltaChart({ rows }) {
  const tip = useTip();
  const W = 560, rowH = 34, left = 230, right = 56, top = 14;
  const lo = Math.min(-0.25, ...rows.map(r => r.ci[0])), hi = Math.max(0.25, ...rows.map(r => r.ci[1]));
  const d0 = Math.floor(lo * 4) / 4, d1 = Math.ceil(hi * 4) / 4;
  const H = top + rows.length * rowH + 18;
  const x = v => left + ((v - d0) / (d1 - d0)) * (W - left - right);
  const ticks = []; for (let t = d0; t <= d1 + 1e-9; t += 0.25) ticks.push(Math.round(t * 100) / 100);
  return html`<svg class="chart" viewBox=${`0 0 ${W} ${H}`} role="img" aria-label="paired differences with 95% confidence intervals">
    ${ticks.map(t => html`<g key=${t}><line class=${t === 0 ? "zero" : "gridline"} x1=${x(t)} x2=${x(t)} y1=${top - 6} y2=${H - 16}/>
      <text x=${x(t)} y=${H - 3} text-anchor="middle">${signed(t, 2)}</text></g>`)}
    ${rows.map((r, i) => {
      const cy = top + i * rowH + rowH / 2;
      const col = r.ci[0] > 0 ? "var(--series-1)" : r.ci[1] < 0 ? "var(--series-2)" : "var(--baseline)";
      return html`<g key=${r.label} ...${tip(html`<div><b>${r.label}</b><br/>Δ pass@1 ${signed(r.delta)}<br/>95% CI ${signed(r.ci[0])} to ${signed(r.ci[1])}${r.p != null ? html`<br/>McNemar p ${r.p < 1e-4 ? "< 0.0001" : num(r.p, 4)}` : ""}${r.n ? html`<br/>n = ${r.n}` : ""}</div>`)}>
        <rect class="hit" x="0" y=${cy - rowH / 2} width=${W} height=${rowH}/>
        <text class="lbl" x=${left - 12} y=${cy + 4} text-anchor="end">${r.label}</text>
        <line x1=${x(r.ci[0])} x2=${x(r.ci[1])} y1=${cy} y2=${cy} stroke=${col} stroke-width="2" stroke-linecap="round"/>
        <rect x=${x(r.delta) - 5} y=${cy - 5} width="10" height="10" rx="2" fill=${col} stroke="var(--surface-1)" stroke-width="2"/>
        <text x=${x(Math.max(r.ci[1], r.delta)) + 9} y=${cy + 4} class="lbl">${signed(r.delta, 2)}</text>
      </g>`;
    })}
  </svg>`;
}

function StackedBars({ rows, keys, colors, labels }) {
  const tip = useTip();
  const W = 560, rowH = 30, left = 190, right = 6, top = 6, gap = 2;
  const H = top + rows.length * rowH + 4;
  const span = W - left - right;
  return html`<div>
    <svg class="chart" viewBox=${`0 0 ${W} ${H}`} role="img" aria-label="share of sent emails by writer">
      ${rows.map((r, i) => {
        const tot = keys.reduce((s, k) => s + (r.values[k] || 0), 0) || 1;
        let acc = 0;
        const y = top + i * rowH + 6, h = rowH - 12;
        return html`<g key=${r.label}>
          <text class="lbl" x=${left - 12} y=${y + h / 2 + 4} text-anchor="end">${r.label}</text>
          ${keys.map((k, ki) => {
            const v = r.values[k] || 0; if (!v) return null;
            const x0 = left + (acc / tot) * span, w = (v / tot) * span; acc += v;
            const share = v / tot;
            return html`<g key=${k} ...${tip(html`<div><b>${r.label}</b><br/>${labels[k]}: ${v} of ${tot} (${pct(share, 0)})</div>`)}>
              <rect x=${x0 + (ki ? gap / 2 : 0)} y=${y} width=${Math.max(0, w - gap)} height=${h} rx="4" fill=${colors[k]}/>
              ${w > 46 && html`<text x=${x0 + w / 2} y=${y + h / 2 + 4} text-anchor="middle" style=${{ fill: "#fff", fontWeight: 600 }}>${pct(share, 0)}</text>`}
            </g>`;
          })}
        </g>`;
      })}
    </svg>
    <div class="legend">${keys.map(k => html`<span key=${k}><i style=${{ background: colors[k] }}></i>${labels[k]}</span>`)}</div>
  </div>`;
}

function HBars({ rows, max = 1, fmt = v => pct(v, 0), threshold, thresholdLabel }) {
  const tip = useTip();
  const W = 560, rowH = 28, left = 150, right = 56, top = 8;
  const H = top + rows.length * rowH + 18;
  const x = v => left + (v / max) * (W - left - right);
  return html`<svg class="chart" viewBox=${`0 0 ${W} ${H}`} role="img">
    ${threshold != null && html`<g><line class="zero" x1=${x(threshold)} x2=${x(threshold)} y1=${top - 4} y2=${H - 14}/>
      <text x=${x(threshold)} y=${H - 2} text-anchor="middle">${thresholdLabel}</text></g>`}
    ${rows.map((r, i) => {
      const y = top + i * rowH + 7, h = rowH - 14;
      return html`<g key=${r.label} ...${tip(html`<div><b>${r.label}</b><br/>${r.tip || fmt(r.value)}</div>`)}>
        <rect class="hit" x="0" y=${y - 7} width=${W} height=${rowH}/>
        <text class="lbl" x=${left - 12} y=${y + h / 2 + 4} text-anchor="end">${r.label}</text>
        <rect x=${left} y=${y} width=${Math.max(2, x(r.value) - left)} height=${h} rx="4" fill=${r.color || "var(--series-1)"}/>
        <text x=${x(r.value) + 8} y=${y + h / 2 + 4} class="lbl">${fmt(r.value)}</text>
      </g>`;
    })}
  </svg>`;
}

function niceMax(v) { // axis max whose quarter-steps are 1/2/2.5/5 x 10^k
  if (!(v > 0)) return 1;
  const raw = v / 4, mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(st => st >= raw);
  return step * 4;
}
function seqColor(v) { // one-hue sequential ramp, 7 steps
  const i = Math.max(0, Math.min(6, Math.round(v * 6)));
  return { bg: `var(--seq-${i})`, ink: i >= 4 ? "#fff" : "var(--text-primary)" };
}

/* ── shared bits ─────────────────────────────────────────────────────── */
const Card = ({ title, sub, children, right }) => html`<section class="card">
  ${(title || right) && html`<div class="row" style=${{ alignItems: "flex-start", flexWrap: "nowrap" }}><div style=${{ flex: 1, minWidth: 0 }}>${title && html`<h2>${title}</h2>`}${sub && html`<p class="sub">${sub}</p>`}</div>${right}</div>`}
  ${children}
</section>`;
const Tile = ({ label, value, foot }) => html`<div class="card tile"><div class="label">${label}</div><div class="value">${value}</div>${foot && html`<div class="foot">${foot}</div>`}</div>`;
const Loading = ({ s }) => s.error ? html`<p class="err">${s.error}</p>` : html`<p class="muted">Loading…</p>`;
const Seg = ({ value, options, onChange }) => html`<div class="seg" role="group">${options.map(([v, l]) =>
  html`<button key=${v} aria-pressed=${value === v} onClick=${() => onChange(v)}>${l}</button>`)}</div>`;

function BriefView({ pack, task }) {
  if (!task) return null;
  const inp = task.input || {};
  if (pack === "ad_creative") {
    const b = inp.brand || {}, o = inp.offer || {}, c = inp.channel || {};
    return html`<dl class="kv">
      <dt>Brand</dt><dd>${b.name} · <span class="mono">${b.display_domain}</span></dd>
      <dt>Vertical</dt><dd>${inp.vertical}</dd>
      <dt>Product</dt><dd>${o.product}</dd>
      <dt>Approved claims</dt><dd>${(o.approved_claims || []).join(" · ") || "–"}</dd>
      ${o.substantiated_superlatives && html`<dt>Substantiated</dt><dd>${o.substantiated_superlatives.join(" · ")}</dd>`}
      ${o.promo && html`<dt>Promo</dt><dd>${o.promo.discount}, ends ${o.promo.ends}</dd>`}
      <dt>Competitors</dt><dd>${(b.competitors || []).join(", ") || "–"}</dd>
      <dt>Blocklist</dt><dd>${(b.blocked_terms || []).join(", ") || "–"}</dd>
      <dt>Channel</dt><dd>${c.type}: headline ≤ ${c.headline_max}, description ≤ ${c.description_max}</dd>
      <dt>As of</dt><dd>${inp.as_of}</dd>
    </dl>`;
  }
  const b = inp.hiring_signal_brief || {}, icp = b.icp_classification || {}, ai = b.ai_maturity || {};
  const f = b.firmographics || {}, lay = b.layoff_signal || {}, lead = b.leadership_signal || {};
  const bench = inp.bench_summary || {};
  return html`<dl class="kv">
    <dt>Prospect</dt><dd><b>${b.prospect}</b>${f.num_employees ? ` · ${f.num_employees} employees` : ""}${f.country_code ? ` · ${f.country_code}` : ""}</dd>
    <dt>Email type</dt><dd>${inp.email_type}</dd>
    <dt>ICP segment</dt><dd>${icp.segment ?? "none"} – ${icp.segment_name || ""} <span class="muted">(confidence ${icp.confidence})</span></dd>
    <dt>Signals</dt><dd>${(icp.reasons || []).join("; ") || "–"}</dd>
    <dt>AI maturity</dt><dd>${ai.ai_maturity_score ?? "–"}/3 <span class="muted">(${ai.confidence || "?"})</span></dd>
    <dt>Layoff</dt><dd>${lay.layoff_detected ? `yes${lay.date ? ` (${lay.date})` : ""}${lay.within_window === false ? " – outside 120-day window" : ""}` : "no"}</dd>
    <dt>Leadership</dt><dd>${lead.leadership_change_detected ? `${lead.leader_title || "yes"}${lead.within_window === false ? " – outside 90-day window" : ""}` : "no"}</dd>
    ${f.snapshot_date && html`<dt>Snapshot</dt><dd>${f.snapshot_date}</dd>`}
    <dt>Bench</dt><dd>${bench.available} available · ${Object.entries(bench.stacks || {}).map(([k, v]) => `${k} ${v}`).join(", ")}</dd>
    ${(inp.prior_thread || []).length > 0 && html`<dt>Thread</dt><dd>${inp.prior_thread.map((m, i) => html`<div key=${i} class="small"><b>${m.from || "?"}:</b> ${m.body || m.note || ""}</div>`)}</dd>`}
  </dl>`;
}

function EmailPreview({ pack, output, violations }) {
  const needles = useMemo(() => needlesFrom(violations), [violations]);
  if (!output) return null;
  if (pack === "ad_creative") {
    return html`<div class="email-preview">
      ${(output.headlines || []).map((h, i) => html`<div key=${"h" + i}><span class="muted mono">H${i + 1}</span> <b><${Highlight} text=${h} needles=${needles}/></b> <span class="muted small">(${h.length})</span></div>`)}
      <div style=${{ height: 8 }}></div>
      ${(output.descriptions || []).map((d, i) => html`<div key=${"d" + i}><span class="muted mono">D${i + 1}</span> <${Highlight} text=${d} needles=${needles}/> <span class="muted small">(${d.length})</span></div>`)}
      <div class="mono small muted" style=${{ marginTop: 8 }}>${output.final_url}</div>
    </div>`;
  }
  return html`<div class="email-preview"><div class="subj">Subject: <${Highlight} text=${output.subject || ""} needles=${needles}/></div><${Highlight} text=${output.body || ""} needles=${needles}/></div>`;
}

const ViolationList = ({ violations, policy }) => (violations || []).length === 0
  ? html`<p class="muted small">No violations.</p>`
  : html`<div class="stack" style=${{ gap: 6 }}>${violations.map((v, i) => html`<div key=${i} class=${`violation ${policy && policy[v.code] ? "policy" : ""}`}>
      <span class="code">${v.code}</span> <span class="muted small">· ${dimLabel(v.dimension)}${v.field ? ` · ${v.field}` : ""}</span>
      <div class="ev">${v.evidence}</div></div>`)}</div>`;

/* ── pages ───────────────────────────────────────────────────────────── */
function Overview({ meta, go }) {
  const r = useApi("/api/results");
  const c = useApi("/api/cost");
  if (!r.data) return html`<${Loading} s=${r}/>`;
  const ab = r.data.ablation, gt = r.data.gated, h1 = r.data.human_vs_evaluator.round1, h2 = r.data.human_vs_evaluator.round2;
  const conds = ab.conditions;
  return html`<div class="stack">
    <div class="grid g4">
      <${Tile} label="Trained model pass@1 (held-out)" value=${pct(conds.trained.pass_at_1)} foot=${`95% CI ${pct(conds.trained.ci95[0], 0)}–${pct(conds.trained.ci95[1], 0)} · n = ${conds.trained.n}`}/>
      <${Tile} label="With pre-send policy gate" value=${gt ? pct(gt.pipelines["trained+gate"].pass_at_1) : "–"} foot=${gt ? `gate fires on ${pct(gt.pipelines["trained+gate"].gate_fire_rate, 0)} of drafts` : ""}/>
      <${Tile} label="Evaluator vs human (overall)" value=${pct(h2 ? h2.overall.agreement : h1.overall.agreement, 0)} foot=${`κ ${num(h2 ? h2.overall.cohen_kappa : h1.overall.cohen_kappa, 2)} · honesty only ${pct(h1.per_dimension.honesty.agreement, 0)}`}/>
      <${Tile} label="Total model API spend" value=${c.data ? `$${c.data.total_usd.toFixed(2)}` : "–"} foot=${c.data ? `${c.data.calls} calls · cap $${c.data.budget_usd}` : ""}/>
    </div>
    <div class="grid g2">
      <${Card} title="Held-out pass@1 by system" sub="All five dimensions must pass. Dots are pass@1, lines are 95% bootstrap CIs. Templates are scored on the 54 cold tasks only." right=${html`<button class="btn small" onClick=${() => go("experiments")}>Details</button>`}>
        <${CIChart} rows=${["trained", "prompt_engineered", "base_short", "week10_v2", "week10"].filter(k => conds[k]).map(k => ({ label: pretty(k), value: conds[k].pass_at_1, ci: conds[k].ci95, n: conds[k].n, highlight: k === "trained" }))}/>
      </${Card}>
      <${Card} title="What the numbers do and don't say">
        <div class="stack" style=${{ gap: 8 }}>
          <div class="note"><b>Training works.</b> Same model, same prompt, adapter on vs off: ${signed(ab.comparisons.training_effect_trained_vs_base_short.delta, 2)} pass@1 (exact McNemar p ${"<"} 0.0001).</div>
          <div class="note caveat"><b>Safety, not persuasion.</b> A content-free two-sentence note passes ${ab.diagnostic_null_note_cold.pass}/${ab.diagnostic_null_note_cold.n} cold tasks, and the honest template beats the model on cold emails. Offline pass@1 is a pre-flight check, not a CTR proxy.</div>
          <div class="note caveat"><b>Delta B is partly one habit.</b> Ignoring "[First Name]" placeholders, trained vs full-rules prompt shrinks from ${signed(ab.comparisons.delta_B_trained_vs_prompt_engineered.delta, 2)} to ${signed(ab.sensitivity_ignore_template_placeholder.delta_B_trained_vs_prompt_engineered.delta, 2)}.</div>
          <div class="note"><b>Packs.</b> ${Object.values(meta.packs).map(p => p.label).join(" · ")} — the same evaluator design scores both formats.</div>
        </div>
      </${Card}>
    </div>
  </div>`;
}

function LiveCheck({ meta }) {
  const [pack, setPack] = useState(ls.get("qa-pack", "sales_email"));
  const [q, setQ] = useState("");
  const list = useApi(`/api/tasks?pack=${pack}&q=${encodeURIComponent(q)}&limit=400`);
  const [tid, setTid] = useState(null);
  const task = useApi(tid ? `/api/tasks/${pack}/${tid}` : null);
  const [out, setOut] = useState(null);
  const [res, setRes] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => { ls.set("qa-pack", pack); setTid(null); setOut(null); setRes(null); }, [pack]);
  useEffect(() => { if (!tid && list.data && list.data.rows.length) setTid(list.data.rows[0].task_id); }, [list.data]);
  useEffect(() => {
    if (task.data) {
      const c = task.data.candidate_output || {};
      setOut(pack === "ad_creative"
        ? { headlines: (c.headlines || []).join("\n"), descriptions: (c.descriptions || []).join("\n"), final_url: c.final_url || "" }
        : { subject: c.subject || "", body: c.body || "" });
      setRes(null);
    }
  }, [task.data]);
  const payload = o => pack === "ad_creative"
    ? { headlines: o.headlines.split("\n").map(s => s.trim()).filter(Boolean), descriptions: o.descriptions.split("\n").map(s => s.trim()).filter(Boolean), final_url: o.final_url.trim() }
    : o;
  const run = useCallback(() => {
    if (!tid || !out) return;
    setErr(null);
    api("/api/score", { method: "POST", body: { pack, task_id: tid, output: payload(out) } }).then(setRes).catch(e => setErr(e.message));
  }, [tid, out, pack]);
  useEffect(() => { const t = setTimeout(run, 350); return () => clearTimeout(t); }, [run]);
  const set = k => e => setOut(o => ({ ...o, [k]: e.target.value }));
  const p = meta.packs[pack];
  return html`<div class="grid g-side">
    <div class="stack">
      <${Seg} value=${pack} onChange=${setPack} options=${[["sales_email", "Sales email"], ["ad_creative", "Search ad"]]}/>
      <input class="input" placeholder="Search tasks, prospects, types…" value=${q} onInput=${e => setQ(e.target.value)}/>
      <div class="list" role="listbox" aria-label="tasks">
        ${!list.data ? html`<${Loading} s=${list}/>` : list.data.rows.map(r => html`<div key=${r.task_id} class="list-item" role="option" aria-selected=${r.task_id === tid} onClick=${() => setTid(r.task_id)}>
          <div><div class="t">${r.task_id}</div><div class="m">${r.prospect} · ${r.email_type}</div></div>
          <span class="pill neutral">${r.partition}</span></div>`)}
      </div>
      <p class="muted small">${list.data ? `${list.data.total} tasks` : ""} · held-out tasks are sealed and never listed.</p>
    </div>
    <div class="stack">
      <div class="grid g2">
        <${Card} title="Brief" sub=${task.data ? `${task.data.task_id} · ${task.data.partition}` : ""}>${task.data ? html`<${BriefView} pack=${pack} task=${task.data}/>` : html`<${Loading} s=${task}/>`}</${Card}>
        <${Card} title="Draft" sub="Edit freely – it re-scores as you type.">
          ${out && (pack === "ad_creative" ? html`<div class="stack" style=${{ gap: 10 }}>
            <label class="field">Headlines (one per line)<textarea class="textarea" value=${out.headlines} onInput=${set("headlines")}/></label>
            <label class="field">Descriptions (one per line)<textarea class="textarea" style=${{ minHeight: 80 }} value=${out.descriptions} onInput=${set("descriptions")}/></label>
            <label class="field">Final URL<input class="input mono" value=${out.final_url} onInput=${set("final_url")}/></label></div>`
          : html`<div class="stack" style=${{ gap: 10 }}>
            <label class="field">Subject <span class="muted">${out.subject.length} chars</span><input class="input" value=${out.subject} onInput=${set("subject")}/></label>
            <label class="field">Body<textarea class="textarea" style=${{ minHeight: 220 }} value=${out.body} onInput=${set("body")}/></label></div>`)}
        </${Card}>
      </div>
      ${err && html`<p class="err">${err}</p>`}
      ${res && html`<${Card} title=${html`<span class="verdict"><${Verdict} pass=${res.all_pass}>${res.all_pass ? "Ready to send" : "Blocked by QA"}</${Verdict}></span>`} sub=${p.evaluator}>
        <div class="dimchips" style=${{ marginBottom: 12 }}>${Object.entries(res.checks).map(([d, c]) => html`<${Verdict} key=${d} pass=${c.pass}>${dimLabel(d)}</${Verdict}>`)}</div>
        <div class="grid g2">
          <div><h2 style=${{ fontSize: 13 }}>Violations</h2><${ViolationList} violations=${res.violations} policy=${meta.hard_policies}/></div>
          <div><h2 style=${{ fontSize: 13 }}>Evidence in context</h2><${EmailPreview} pack=${pack} output=${payload(out)} violations=${res.violations}/></div>
        </div>
        ${res.gate && html`<div class="grid g2" style=${{ marginTop: 12 }}>
          <div class="note"><b>Router:</b> ${res.route.writer === "template" ? "honest template" : "model"} – ${res.route.reason}.<br/><span class="muted">In-window signals: ${Object.entries(res.route.valid_signals).filter(([, v]) => v).map(([k]) => k).join(", ") || "none"}</span></div>
          <div class=${`note ${res.gate.action === "block" ? "caveat" : ""}`}><b>Pre-send policy gate:</b> ${res.gate.action === "block" ? `BLOCK – ${res.gate.blocked_by.map(b => b.policy).join("; ")}` : "send – no hard-policy violation"}</div>
        </div>`}
        <p class="muted small" style=${{ marginTop: 10 }}>${p.validation}</p>
      </${Card}>`}
    </div>
  </div>`;
}

function Experiments() {
  const r = useApi("/api/results");
  if (!r.data) return html`<${Loading} s=${r}/>`;
  const ab = r.data.ablation;
  const conds = ab.conditions;
  const order = ["trained", "prompt_engineered", "base_short", "week10_v2", "week10"].filter(k => conds[k]);
  const dims = ["grounding", "honesty", "commercial_safety", "tone", "format"];
  const cmpLabels = {
    delta_A_trained_vs_week10_cold: "Delta A · vs original Week 10 (cold)",
    delta_B_trained_vs_prompt_engineered: "Delta B · vs full-rules prompt",
    training_effect_trained_vs_base_short: "Adapter on vs off (same prompt)",
    replies_trained_vs_prompt_engineered: "Replies · vs full-rules prompt",
    trained_vs_week10_v2_honest_template_cold: "vs honest template v2 (cold)",
  };
  const deltas = Object.entries(ab.comparisons).map(([k, v]) => ({ label: cmpLabels[k] || k, delta: v.delta, ci: v.ci95, p: v.mcnemar_exact_one_sided, n: v.n }));
  const sens = ab.sensitivity_ignore_template_placeholder.delta_B_trained_vs_prompt_engineered;
  deltas.splice(2, 0, { label: "Delta B · placeholders ignored", delta: sens.delta, ci: sens.ci95, p: sens.mcnemar_exact_one_sided, n: sens.n });
  return html`<div class="stack">
    <div class="grid g2">
      <${Card} title="pass@1 on the sealed held-out" sub=${`${ab.held_out.n_tasks} tasks (${ab.held_out.n_cold} cold, ${ab.held_out.n_reply} reply) · ${ab.evaluator} · seed ${ab.seed}, ${ab.n_bootstrap.toLocaleString()} bootstrap resamples`}>
        <${CIChart} rows=${order.map(k => ({ label: pretty(k), value: conds[k].pass_at_1, ci: conds[k].ci95, n: conds[k].n, highlight: k === "trained" }))}/>
      </${Card}>
      <${Card} title="Paired comparisons (trained minus other)" sub="Same tasks, per-task differences. Blue: CI above zero. Orange: CI below zero (the other system is better). Hover for McNemar p.">
        <${DeltaChart} rows=${deltas}/>
      </${Card}>
    </div>
    <${Card} title="Pass rate by dimension" sub="Darker = higher pass rate. The headline needs every dimension to pass, so one weak dimension sinks a system.">
      <div class="scroll-x"><table class="tbl heat"><thead><tr><th>System</th>${dims.map(d => html`<th key=${d} class="num">${dimLabel(d)}</th>`)}<th class="num">all five</th><th class="num">output tokens</th></tr></thead>
        <tbody>${order.map(k => html`<tr key=${k}><td>${pretty(k)}</td>
          ${dims.map(d => { const v = conds[k].per_dimension_pass_rate[d]; const c = seqColor(v); return html`<td key=${d} class="cell" style=${{ background: c.bg, color: c.ink }}>${pct(v, 0)}</td>`; })}
          <td class="num"><b>${pct(conds[k].pass_at_1, 1)}</b></td><td class="num">${conds[k].mean_new_tokens || "–"}</td></tr>`)}</tbody></table></div>
    </${Card}>
    <div class="grid g3">
      <div class="note"><b>Null-note diagnostic.</b> ${ab.diagnostic_null_note_cold.pass}/${ab.diagnostic_null_note_cold.n} cold tasks pass with a content-free note. The metric checks safety; it does not reward persuasion.</div>
      <div class="note"><b>Delta C not computed.</b> ${ab.delta_C}</div>
      <div class="note"><b>Training run.</b> ${ab.training_run.backbone}, ${ab.training_run.train_pairs} pairs, ${ab.training_run.steps} steps, ${ab.training_run.wall_time_minutes} min on a ${ab.training_run.gpu}; final eval loss ${ab.training_run.final_eval_loss}.</div>
    </div>
  </div>`;
}

function Gate({ meta }) {
  const r = useApi("/api/results");
  if (!r.data) return html`<${Loading} s=${r}/>`;
  const g = r.data.gated;
  if (!g) return html`<p class="muted">Run <code>ablations/score_gated.py</code> to produce the gated results.</p>`;
  const names = Object.keys(g.pipelines).filter(k => g.pipelines[k].pass_at_1 != null);
  const keys = ["model", "template", "fallback"];
  const colors = { model: "var(--series-1)", template: "var(--series-2)", fallback: "var(--series-3)" };
  const labels = { model: "written by the model", template: "routed to the template", fallback: "blocked → safe fallback" };
  const rows = names.map(n => {
    const s = g.pipelines[n].sent_by;
    const fb = Object.entries(s).filter(([k]) => k.startsWith("fallback")).reduce((a, [, v]) => a + v, 0);
    return { label: n.replaceAll("_", " "), values: { model: s.model || 0, template: s.template || 0, fallback: fb } };
  });
  return html`<div class="stack">
    <div class="note"><b>The model proposes, policy disposes.</b> Hard policies run in code before anything is sent; a blocked draft is replaced by a safe fallback.
      The gate reuses the frozen evaluator's rules for those codes, so its effect there is by construction. Read the <b>fire rate</b> and <b>what the model actually wrote</b>, not just pass@1.</div>
    <div class="grid g2">
      <${Card} title="pass@1 by pipeline" sub=${`held-out n = ${g.held_out_n} · router sends ${g.router.to_template} cold tasks without an in-window signal to the template`}>
        <${CIChart} rows=${names.map(n => ({ label: n.replaceAll("_", " "), value: g.pipelines[n].pass_at_1, highlight: n.startsWith("trained") && n !== "trained" }))}/>
      </${Card}>
      <${Card} title="Who actually wrote what was sent" sub="A high pass rate with a low model share means the safety net is doing the work.">
        <${StackedBars} rows=${rows} keys=${keys} colors=${colors} labels=${labels}/>
      </${Card}>
    </div>
    <${Card} title="Pipelines">
      <div class="scroll-x"><table class="tbl"><thead><tr><th>Pipeline</th><th class="num">pass@1</th><th class="num">cold</th><th class="num">reply</th><th class="num">model share</th><th class="num">gate fires</th><th>gate fired on</th><th>still failing</th></tr></thead>
      <tbody>${names.map(n => { const p = g.pipelines[n]; return html`<tr key=${n} class=${n === "trained+gate" ? "hl" : ""}><td>${n}</td><td class="num">${pct(p.pass_at_1)}</td><td class="num">${pct(p.pass_at_1_cold)}</td><td class="num">${pct(p.pass_at_1_reply)}</td><td class="num">${pct(p.model_share_of_sent, 0)}</td><td class="num">${p.gate_fire_rate == null ? "–" : pct(p.gate_fire_rate, 0)}</td>
        <td class="small mono">${Object.entries(p.gate_fired_on).map(([k, v]) => `${k} ${v}`).join(", ") || "–"}</td><td class="small mono">${Object.entries(p.residual_violations).map(([k, v]) => `${k} ${v}`).join(", ") || "–"}</td></tr>`; })}</tbody></table></div>
    </${Card}>
    <${Card} title="Hard policies enforced before send">
      <div class="grid g2">${Object.entries(meta.hard_policies).map(([k, v]) => html`<div key=${k} class="violation policy"><span class="code">${k}</span><div class="ev">${v}</div></div>`)}</div>
    </${Card}>
  </div>`;
}

function Traces({ meta }) {
  const [f, setF] = useState({ condition: "trained", outcome: "fail", code: "", email_type: "" });
  const qs = new URLSearchParams(Object.entries(f).filter(([, v]) => v)).toString();
  const t = useApi(`/api/traces?${qs}&limit=400`);
  const [sel, setSel] = useState(null);
  const cmp = useApi(sel ? `/api/traces?task_id=${sel.task_id}` : null);
  if (t.data && !t.data.available) return html`<div class="note caveat">${t.data.reason}</div>`;
  const facets = (t.data && t.data.facets) || {};
  const opt = (name, k) => html`<label class="field">${name}<select class="select" value=${f[k]} onChange=${e => setF({ ...f, [k]: e.target.value })}>
    <option value="">all</option>${Object.entries(facets[k] || {}).sort((a, b) => b[1] - a[1]).map(([v, n]) => html`<option key=${v} value=${v}>${k === "condition" ? pretty(v) : v} (${n})</option>`)}</select></label>`;
  return html`<div class="stack">
    <div class="note">Held-out outputs, scored by the frozen evaluator. Local only: task inputs stay sealed; set <code>TB_DASHBOARD_HIDE_HELDOUT=1</code> to hide these when presenting remotely.</div>
    <div class="grid g4">${opt("System", "condition")}
      <label class="field">Outcome<select class="select" value=${f.outcome} onChange=${e => setF({ ...f, outcome: e.target.value })}><option value="">all</option><option value="pass">pass</option><option value="fail">fail</option></select></label>
      ${opt("Violation code", "code")}${opt("Email type", "email_type")}</div>
    <div class="grid g-side">
      <div class="list">${!t.data ? html`<${Loading} s=${t}/>` : t.data.rows.length === 0 ? html`<div class="empty">No traces match.</div>` :
        t.data.rows.map((r, i) => html`<div key=${i} class="list-item" aria-selected=${sel && sel.task_id === r.task_id && sel.condition === r.condition} onClick=${() => setSel(r)}>
          <div><div class="t">${r.task_id}</div><div class="m">${pretty(r.condition)} · ${r.email_type}</div></div>
          <${Verdict} pass=${r.violations.length === 0}>${r.violations.length ? `${r.violations.length}` : "pass"}</${Verdict}></div>`)}</div>
      <div class="stack">
        ${!sel ? html`<div class="card empty">Select a trace to see the email, its violations, and every system's output for the same task.</div>` : html`
          <${Card} title=${`${sel.task_id} · ${pretty(sel.condition)}`} sub=${sel.email_type}>
            <div class="grid g2"><${EmailPreview} pack="sales_email" output=${sel.email} violations=${sel.violations}/><${ViolationList} violations=${sel.violations} policy=${meta.hard_policies}/></div>
          </${Card}>
          <${Card} title="Same task, every system">
            ${!cmp.data ? html`<${Loading} s=${cmp}/>` : html`<div class="grid g2">${cmp.data.rows.map(r => html`<div key=${r.condition} class="stack" style=${{ gap: 6 }}>
              <div class="row"><b class="small">${pretty(r.condition)}</b><span class="spacer"></span><${Verdict} pass=${!r.violations.length}/></div>
              <${EmailPreview} pack="sales_email" output=${r.email} violations=${r.violations}/>
              ${r.violations.length > 0 && html`<div class="small mono muted">${r.violations.map(v => v.code).join(", ")}</div>`}</div>`)}</div>`}
          </${Card}>`}
      </div>
    </div>
  </div>`;
}

function Review({ meta }) {
  const [pack, setPack] = useState("sales_email");
  const [reviewer, setReviewer] = useState(ls.get("qa-reviewer", "reviewer"));
  const [nonce, setNonce] = useState(0);
  const [skip, setSkip] = useState([]);
  const next = useApi(`/api/review/next?pack=${pack}&reviewer=${encodeURIComponent(reviewer)}&skip=${skip.join(",")}`, [nonce]);
  const [labels, setLabels] = useState({});
  const [note, setNote] = useState("");
  const [reveal, setReveal] = useState(null);
  const [err, setErr] = useState(null);
  const [src, setSrc] = useState("round1");
  const agr = useApi(`/api/review/agreement?source=${src}&pack=${pack}${src === "ui" ? `&reviewer=${encodeURIComponent(reviewer)}` : ""}`, [nonce]);
  useEffect(() => { ls.set("qa-reviewer", reviewer); }, [reviewer]);
  useEffect(() => { setLabels({}); setNote(""); setReveal(null); }, [next.data]);
  useEffect(() => { if (pack !== "sales_email") setSrc("ui"); setSkip([]); }, [pack]);
  const dims = meta.packs[pack].dimensions;
  const task = next.data && !next.data.done ? next.data.task : null;
  const submit = () => {
    setErr(null);
    api("/api/review", { method: "POST", body: { pack, task_id: task.task_id, reviewer, labels, note } })
      .then(setReveal).catch(e => setErr(e.message));
  };
  const out = task && task.candidate_output;
  return html`<div class="stack">
    <div class="row"><${Seg} value=${pack} onChange=${setPack} options=${[["sales_email", "Sales email"], ["ad_creative", "Search ad"]]}/>
      <label class="field" style=${{ width: 200 }}>Reviewer<input class="input" value=${reviewer} onChange=${e => setReviewer(e.target.value || "reviewer")}/></label>
      <span class="spacer"></span><span class="muted small">${next.data ? `${next.data.labelled} labelled${next.data.remaining != null ? ` · ${next.data.remaining} remaining` : ""}` : ""}</span></div>
    <div class="grid g2">
      <${Card} title="Blind review" sub="The evaluator's verdict, the stored label and the metadata stay hidden until you submit, to avoid anchoring.">
        ${!next.data ? html`<${Loading} s=${next}/>` : next.data.done ? html`<div class="empty">Queue complete for ${reviewer}.</div>` : html`<div class="stack">
          <div class="row"><b>${task.task_id}</b><span class="spacer"></span><button class="btn small" onClick=${() => setSkip(s => [...s, task.task_id])}>Skip</button></div>
          <${BriefView} pack=${pack} task=${task}/>
          <${EmailPreview} pack=${pack} output=${out} violations=${reveal ? reveal.evaluator.violations : []}/>
          <div class="stack" style=${{ gap: 6 }}>${dims.map(d => html`<div key=${d} class="row"><span style=${{ width: 140 }}>${dimLabel(d)}</span>
            <${Seg} value=${labels[d]} onChange=${v => !reveal && setLabels(l => ({ ...l, [d]: v }))} options=${[["P", "Pass"], ["F", "Fail"]]}/>
            ${reveal && html`<span>${reveal.agreement[d] ? html`<span class="pill pass"><${PassIcon}/>agrees</span>` : html`<span class="pill warn">evaluator: ${reveal.evaluator.checks[d].pass ? "pass" : "fail"}</span>`}</span>`}</div>`)}</div>
          <input class="input" placeholder="Note (optional): why?" value=${note} onInput=${e => setNote(e.target.value)} disabled=${!!reveal}/>
          ${err && html`<p class="err">${err}</p>`}
          <div class="row">${!reveal
            ? html`<button class="btn primary" disabled=${Object.keys(labels).length !== dims.length} onClick=${submit}>Submit & reveal</button>`
            : html`<button class="btn primary" onClick=${() => setNonce(n => n + 1)}>Next task</button>`}</div>
          ${reveal && html`<${ViolationList} violations=${reveal.evaluator.violations} policy=${meta.hard_policies}/>`}
        </div>`}
      </${Card}>
      <${Card} title="Human vs evaluator agreement" sub="Per dimension; the dashed line is the 80% bar the protocol uses for rubric revision." right=${html`<${Seg} value=${src} onChange=${setSrc} options=${(pack === "sales_email" ? [["round1", "Round 1"], ["round2", "Round 2"]] : []).concat([["ui", "This console"]])}/>`}>
        ${!agr.data ? html`<${Loading} s=${agr}/>` : agr.data.n === 0 ? html`<div class="empty">No labels yet from this source.</div>` : html`<div class="stack">
          <${HBars} rows=${Object.entries(agr.data.per_dimension).map(([d, v]) => ({ label: dimLabel(d), value: v.agreement, tip: `${v.agree}/${agr.data.n} agree · κ ${num(v.cohen_kappa, 2)}`, color: v.agreement < 0.8 ? "var(--series-2)" : "var(--series-1)" })).concat([{ label: "overall verdict", value: agr.data.overall.agreement, color: agr.data.overall.agreement < 0.8 ? "var(--series-2)" : "var(--series-1)", tip: `${agr.data.overall.agree}/${agr.data.n} · κ ${num(agr.data.overall.cohen_kappa, 2)}` }])} threshold=${0.8} thresholdLabel="80%"/>
          <p class="small muted">n = ${agr.data.n} · orange bars are below the 80% bar.</p>
          <div class="list" style=${{ maxHeight: 260 }}>${agr.data.disagreements.map((d, i) => html`<div key=${i} class="list-item"><div><div class="t">${d.task_id} · ${dimLabel(d.dimension)}</div><div class="m">human ${d.human} · evaluator ${d.evaluator}${d.codes.length ? ` (${d.codes.join(", ")})` : ""}</div></div></div>`)}</div>
        </div>`}
      </${Card}>
    </div>
  </div>`;
}

function ABTest() {
  const [f, setF] = useState({ successes_a: 120, trials_a: 10000, successes_b: 150, trials_b: 10000 });
  const [res, setRes] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => {
    const t = setTimeout(() => api("/api/abtest/proportions", { method: "POST", body: Object.fromEntries(Object.entries(f).map(([k, v]) => [k, Number(v)])) })
      .then(r => { setRes(r); setErr(null); }).catch(e => { setRes(null); setErr(e.message); }), 250);
    return () => clearTimeout(t);
  }, [f]);
  const [pa, setPa] = useState("trained"), [pb, setPb] = useState("prompt_engineered"), [et, setEt] = useState("");
  const [pr, setPr] = useState(null), [perr, setPerr] = useState(null);
  useEffect(() => { api("/api/abtest/paired", { method: "POST", body: { condition_a: pa, condition_b: pb, email_type: et } }).then(r => { setPr(r); setPerr(null); }).catch(e => { setPr(null); setPerr(e.message); }); }, [pa, pb, et]);
  const conds = ["trained", "prompt_engineered", "base_short", "week10", "week10_v2"];
  const inp = k => html`<input class="input" type="number" min="0" value=${f[k]} onInput=${e => setF({ ...f, [k]: e.target.value })}/>`;
  const maxRate = res ? niceMax(Math.max(res.ci95_a[1], res.ci95_b[1]) * 1.1) : 1;
  return html`<div class="grid g2">
    <${Card} title="Online A/B: two creatives, independent traffic" sub="Clicks / impressions (or conversions / clicks). Two-sided pooled z-test, Wilson CI per arm.">
      <div class="grid g2" style=${{ marginBottom: 12 }}>
        <label class="field">Variant A successes${inp("successes_a")}</label><label class="field">Variant A trials${inp("trials_a")}</label>
        <label class="field">Variant B successes${inp("successes_b")}</label><label class="field">Variant B trials${inp("trials_b")}</label>
      </div>
      ${err && html`<p class="err">${err}</p>`}
      ${res && html`<div class="stack">
        <${CIChart} rows=${[{ label: "Variant A", value: res.rate_a, ci: res.ci95_a, n: f.trials_a }, { label: "Variant B", value: res.rate_b, ci: res.ci95_b, n: f.trials_b, highlight: true }]} domain=${[0, maxRate]} fmt=${v => pct(v, 2)}/>
        <div class="grid g3">
          <${Tile} label="Relative lift (B vs A)" value=${res.relative_lift == null ? "–" : `${res.relative_lift >= 0 ? "+" : ""}${(res.relative_lift * 100).toFixed(1)}%`} foot=${`Δ ${signed(res.diff_b_minus_a * 100, 2)} pts`}/>
          <${Tile} label="p (two-sided)" value=${num(res.p_two_sided, 4)} foot=${html`<${Verdict} pass=${res["significant_at_0.05"]}>${res["significant_at_0.05"] ? "significant at 5%" : "not significant"}</${Verdict}>`}/>
          <${Tile} label="Detectable at this traffic" value=${res.mde_at_this_traffic == null ? "–" : `${(res.mde_at_this_traffic * 100).toFixed(2)} pts`} foot="80% power, α = 0.05"/>
        </div>
        <p class="small muted">95% CI for B − A: ${signed(res.diff_ci95[0] * 100, 2)} to ${signed(res.diff_ci95[1] * 100, 2)} pts. If the observed lift is smaller than the detectable effect, more traffic is needed before calling it.</p>
      </div>`}
    </${Card}>
    <${Card} title="Offline paired comparison: two systems, same tasks" sub="Paired bootstrap CI and exact McNemar on the held-out traces – the right test when both variants see identical inputs.">
      <div class="grid g3" style=${{ marginBottom: 12 }}>
        <label class="field">System A<select class="select" value=${pa} onChange=${e => setPa(e.target.value)}>${conds.map(c => html`<option key=${c} value=${c}>${pretty(c)}</option>`)}</select></label>
        <label class="field">System B<select class="select" value=${pb} onChange=${e => setPb(e.target.value)}>${conds.map(c => html`<option key=${c} value=${c}>${pretty(c)}</option>`)}</select></label>
        <label class="field">Subset<select class="select" value=${et} onChange=${e => setEt(e.target.value)}><option value="">all tasks</option><option value="cold">cold</option><option value="reply">reply</option></select></label>
      </div>
      ${perr && html`<p class="err">${perr}</p>`}
      ${pr && html`<div class="stack">
        <p class="small muted" style=${{ margin: 0 }}>A = ${pretty(pa)} · B = ${pretty(pb)}</p>
        <${DeltaChart} rows=${[{ label: "A − B (pass@1)", delta: pr.delta, ci: pr.ci95, p: pr.mcnemar_exact_one_sided, n: pr.n }]}/>
        <div class="grid g3">
          <${Tile} label="pass@1, A vs B" value=${html`<span style=${{ fontSize: 22 }}>${pct(pr.a_pass_at_1, 0)} vs ${pct(pr.b_pass_at_1, 0)}</span>`} foot=${`${pr.n_shared_tasks} shared tasks`}/>
          <${Tile} label="Discordant pairs" value=${`${pr.discordant.a_only_pass} : ${pr.discordant.b_only_pass}`} foot="A-only pass : B-only pass"/>
          <${Tile} label="McNemar (one-sided)" value=${pr.mcnemar_exact_one_sided < 1e-4 ? "< 0.0001" : num(pr.mcnemar_exact_one_sided, 4)} foot=${html`<${Verdict} pass=${pr["significant_at_0.05"]}>${pr["significant_at_0.05"] ? "A better" : "not shown better"}</${Verdict}>`}/>
        </div></div>`}
    </${Card}>
  </div>`;
}

function Cost() {
  const c = useApi("/api/cost");
  const [gpuHr, setGpuHr] = useState(ls.get("qa-gpu-hr", "0.50"));
  useEffect(() => ls.set("qa-gpu-hr", gpuHr), [gpuHr]);
  if (!c.data) return html`<${Loading} s=${c}/>`;
  const d = c.data;
  const lat = d.single_request_latency_s || {};
  const mean = a => (a && a.length ? a.reduce((s, x) => s + x, 0) / a.length : null);
  const perK = s => (s == null ? null : (s * 1000 / 3600) * Number(gpuHr || 0));
  const inf = d.inference || {};
  return html`<div class="stack">
    <div class="grid g4">
      <${Tile} label="API spend, all phases" value=${`$${d.total_usd.toFixed(2)}`} foot=${`${pct(d.total_usd / d.budget_usd, 0)} of the $${d.budget_usd} cap · ${d.calls} calls`}/>
      <${Tile} label="Trained model, per email" value=${mean(lat.trained) ? `${mean(lat.trained).toFixed(2)} s` : "–"} foot=${`${inf.trained ? inf.trained.mean_new_tokens : "–"} output tokens · ${d.gpu || "GPU"}, one request`}/>
      <${Tile} label="Full-rules prompt, per email" value=${mean(lat.prompt_engineered) ? `${mean(lat.prompt_engineered).toFixed(2)} s` : "–"} foot=${`${inf.prompt_engineered ? inf.prompt_engineered.mean_new_tokens : "–"} output tokens`}/>
      <${Tile} label="Trained, per 1,000 creatives" value=${perK(mean(lat.trained)) == null ? "–" : `$${perK(mean(lat.trained)).toFixed(2)}`} foot=${html`at $<input class="input" style=${{ width: 70, padding: "1px 6px", display: "inline-block" }} value=${gpuHr} onInput=${e => setGpuHr(e.target.value)}/>/GPU-hour, sequential`}/>
    </div>
    <div class="grid g2">
      <${Card} title="Spend by model" sub="Every call logged by llm_client.py to cost_log.jsonl. Training and inference ran on a free Colab T4.">
        <${HBars} rows=${Object.entries(d.by_model).map(([m, v]) => ({ label: m.split("/").pop(), value: v.usd, tip: `$${v.usd.toFixed(4)} · ${v.calls} calls · ${v.tokens.toLocaleString()} tokens` }))} max=${Math.max(...Object.values(d.by_model).map(v => v.usd)) * 1.1} fmt=${v => `$${v.toFixed(3)}`}/>
      </${Card}>
      <${Card} title="Quality vs cost per system" sub="Output tokens drive generation cost; the trained model also drops the rule block from every prompt.">
        <table class="tbl"><thead><tr><th>System</th><th class="num">pass@1</th><th class="num">output tokens</th><th class="num">prompt chars</th></tr></thead>
          <tbody>${Object.entries(inf).map(([k, v]) => html`<tr key=${k} class=${k === "trained" ? "hl" : ""}><td>${pretty(k)}</td><td class="num">${pct(v.pass_at_1)}</td><td class="num">${v.mean_new_tokens ? v.mean_new_tokens : "–"}</td><td class="num">${v.mean_prompt_chars ? v.mean_prompt_chars.toLocaleString() : "–"}</td></tr>`)}</tbody></table>
        <p class="small muted">Per-1,000 cost assumes one request at a time on one GPU at the hourly price you enter; batching lowers it.</p>
      </${Card}>
    </div>
  </div>`;
}

/* ── shell ───────────────────────────────────────────────────────────── */
const PAGES = [
  ["overview", "Overview", I.overview, "Headline results, validity and spend at a glance."],
  ["check", "Live check", I.check, "Score any draft against a rule pack. Violations come with the evidence that triggered them."],
  ["experiments", "Experiments", I.exp, "Offline evaluation on the sealed held-out: pass@1, paired deltas, per-dimension rates."],
  ["gate", "Policy gate", I.gate, "Pre-send hard policies and routing: what they catch, how often they fire, who actually wrote what was sent."],
  ["traces", "Traces", I.traces, "Every scored held-out output, filterable by system, outcome and violation."],
  ["review", "Review queue", I.review, "Blind human labelling and human-vs-evaluator agreement."],
  ["ab", "A/B test", I.ab, "Significance, lift and detectable effect for creative tests."],
  ["cost", "Cost & latency", I.cost, "API spend, per-email latency and cost per 1,000 creatives."],
];

function App() {
  const [page, setPage] = useState((location.hash || "#overview").slice(1));
  const [theme, setTheme] = useState(document.documentElement.dataset.theme || "");
  const meta = useApi("/api/meta");
  useEffect(() => { const f = () => setPage((location.hash || "#overview").slice(1)); addEventListener("hashchange", f); return () => removeEventListener("hashchange", f); }, []);
  const go = p => { location.hash = p; };
  const toggleTheme = () => {
    const dark = theme ? theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    const next = dark ? "light" : "dark";
    document.documentElement.dataset.theme = next; ls.set("qa-theme", next); setTheme(next);
  };
  const cur = PAGES.find(p => p[0] === page) || PAGES[0];
  const body = !meta.data ? html`<${Loading} s=${meta}/>` : ({
    overview: html`<${Overview} meta=${meta.data} go=${go}/>`, check: html`<${LiveCheck} meta=${meta.data}/>`,
    experiments: html`<${Experiments}/>`, gate: html`<${Gate} meta=${meta.data}/>`, traces: html`<${Traces} meta=${meta.data}/>`,
    review: html`<${Review} meta=${meta.data}/>`, ab: html`<${ABTest}/>`, cost: html`<${Cost}/>`,
  })[cur[0]];
  return html`<${TipLayer}><div class="shell">
    <nav class="side" aria-label="sections">
      <div class="brand"><span class="brand-mark">✓</span><div>Creative QA<small>Tenacious-Bench v0.2</small></div></div>
      ${PAGES.map(([k, label, icon]) => html`<button key=${k} class="nav-btn" aria-current=${k === cur[0] ? "page" : undefined} onClick=${() => go(k)}>${icon}${label}</button>`)}
      <div class="side-foot">
        <button class="btn small" onClick=${toggleTheme}>${I.sun} Theme</button>
        <a href="/docs" target="_blank" rel="noopener">API docs ↗</a>
        <span>${meta.data ? (meta.data.held_out_outputs_visible ? "Held-out outputs: local view" : "Held-out outputs: hidden") : ""}</span>
      </div>
    </nav>
    <main class="main">
      <div class="page-head"><div><h1>${cur[1]}</h1><p>${cur[3]}</p></div></div>
      ${body}
    </main>
  </div></${TipLayer}>`;
}

ReactDOM.createRoot(document.getElementById("root")).render(html`<${App}/>`);
