import { useEffect, useRef, useState } from "react";

// Every external figure carries its source and year. Figures are as first published by each source.
const SOURCES = {
  es2025: { label: "KNBS, Economic Survey 2025", url: "https://www.knbs.or.ke/economic-surveys/" },
  es2026: { label: "KNBS, Economic Survey 2026", url: "https://www.knbs.or.ke/economic-surveys/" },
  afidep: { label: "AFIDEP youth employment brief, 2026", url: "https://citizen.digital/article/about-1-million-youth-enter-labour-market-yearly-over-80-find-informal-jobs-report-n384935" },
  cue: { label: "Commission for University Education, 2024 graduates", url: "https://thekenyatimes.com/education/kenya-records-more-graduates-as-women-close-gap-in-private-universities/" },
  ifc: { label: "World Bank & IFC, Demand for Digital Skills in Sub-Saharan Africa, 2021", url: "https://documents1.worldbank.org/curated/en/099614312152318607/pdf/IDU0b36e9e030767f0417e0afb806e2ffdf1e8bf.pdf" },
  ladders: { label: "Ladders eye-tracking study, 2018 (US recruiters)", url: "https://www.hrdive.com/news/eye-tracking-study-shows-recruiters-look-at-resumes-for-7-seconds/541582/" },
} as const;
type SourceKey = keyof typeof SOURCES;

const format = (value: number) => value.toLocaleString("en-KE");

// Fig. 1: one year of supply against formal demand (2024).
const supply = [
  { label: "Young people entering the labour market", value: 800_000, note: "estimate, 800,000 to 1 million a year", source: "afidep" },
  { label: "University graduates", value: 123_928, note: "degrees awarded in 2024", source: "cue" },
  { label: "New modern-sector jobs", value: 78_600, note: "wage and self-employment outside the informal sector", source: "es2025", signal: true },
] satisfies { label: string; value: number; note: string; source: SourceKey; signal?: boolean }[];

// Fig. 2: new jobs by year, thousands. Modern sector = total minus informal.
const newJobs = [
  { year: 2022, total: 816.6, informal: 702.9 },
  { year: 2023, total: 848.2, informal: 720.9 },
  { year: 2024, total: 782.3, informal: 703.7 },
  { year: 2025, total: 822.1, informal: 714.4 }, // 86.9 % informal share applied to the published total
].map((row) => ({ ...row, modern: +(row.total - row.informal).toFixed(1) }));

// Fig. 3 assumptions. Stated on the page, adjustable only through the applications slider.
const READ_MINUTES = 3; // a considered first read; the 7.4 s glance only decides whether to keep reading
const SHORTLIST = 25; // ranked candidates a recruiter reads with JobBridge
const RANKING_MINUTES = 5; // scanning the ranked list and eligibility reasons
const manualHours = (applications: number) => (applications * READ_MINUTES) / 60;
const assistedHours = (applications: number) => (Math.min(applications, SHORTLIST) * READ_MINUTES + RANKING_MINUTES) / 60;

function Source({ keys, children }: { keys: SourceKey[]; children?: React.ReactNode }) {
  return <p className="gap-source">Source: {keys.map((key, index) => <span key={key}>{index > 0 && "; "}<a href={SOURCES[key].url} target="_blank" rel="noopener noreferrer">{SOURCES[key].label}</a></span>)}{children}</p>;
}

function SupplyFigure() {
  const max = supply[0].value;
  return <figure className="gap-figure" aria-labelledby="gap-fig1">
    <figcaption id="gap-fig1"><span>Fig. 1</span>One year in Kenya: people looking for work against new formal jobs</figcaption>
    <ul className="gap-bars">
      {supply.map((item) => <li key={item.label} className={item.signal ? "is-signal" : undefined} tabIndex={0} aria-label={`${item.label}: ${format(item.value)} (${item.note})`}>
        <div className="gap-bar-label"><span>{item.label}</span><strong>{format(item.value)}</strong></div>
        <div className="gap-bar-track"><span style={{ width: `${(item.value / max) * 100}%` }} /></div>
        <small>{item.note} · {SOURCES[item.source].label}</small>
      </li>)}
    </ul>
    <Source keys={["afidep", "cue", "es2025"]} />
  </figure>;
}

function JobsFigure() {
  const max = 900;
  return <figure className="gap-figure" aria-labelledby="gap-fig2">
    <figcaption id="gap-fig2"><span>Fig. 2</span>New jobs created each year, thousands</figcaption>
    <ul className="gap-legend" aria-label="Legend"><li className="is-informal">Informal sector</li><li className="is-modern">Modern sector</li></ul>
    <div className="gap-columns" role="img" aria-label={newJobs.map((row) => `${row.year}: ${row.total} thousand new jobs, ${row.informal} thousand informal, ${row.modern} thousand modern sector`).join("; ")}>
      {newJobs.map((row) => <div key={row.year} className="gap-column" tabIndex={0} title={`${row.year}: ${row.informal}k informal, ${row.modern}k modern sector`}>
        <b>{row.total}</b>
        <div className="gap-stack" style={{ height: `${(row.total / max) * 100}%` }}>
          <span className="is-modern" style={{ flexGrow: row.modern }}><i>{row.modern}</i></span>
          <span className="is-informal" style={{ flexGrow: row.informal }} />
        </div>
        <span className="gap-year">{row.year}</span>
        <div className="gap-tip" role="tooltip"><strong>{row.year}</strong>Informal {row.informal}k · {Math.round((row.informal / row.total) * 100)}%<br />Modern sector {row.modern}k</div>
      </div>)}
    </div>
    <details className="gap-table"><summary>View the data</summary><table><thead><tr><th>Year</th><th>Total</th><th>Informal</th><th>Modern sector</th></tr></thead><tbody>{newJobs.map((row) => <tr key={row.year}><td>{row.year}</td><td>{row.total}</td><td>{row.informal}</td><td>{row.modern}</td></tr>)}</tbody></table></details>
    <Source keys={["es2025", "es2026"]}>. Economic Surveys 2023 to 2026, as first published. Modern sector is the total minus the informal sector; 2025 informal applies the published 86.9% share.</Source>
  </figure>;
}

function ProjectionFigure() {
  const [applications, setApplications] = useState(200);
  const frame = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(560);
  useEffect(() => {
    const target = frame.current;
    if (!target) return;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(260, Math.round(entry.contentRect.width))));
    observer.observe(target);
    return () => observer.disconnect();
  }, []);
  const height = 240, left = 34, right = 16, top = 14, bottom = 30;
  const maxApplications = 500, maxHours = 25;
  const x = (value: number) => left + (value / maxApplications) * (width - left - right);
  const y = (value: number) => top + (1 - value / maxHours) * (height - top - bottom);
  const steps = Array.from({ length: 51 }, (_, index) => index * 10);
  const path = (hours: (applications: number) => number) => steps.map((value, index) => `${index ? "L" : "M"}${x(value).toFixed(1)},${y(hours(value)).toFixed(1)}`).join("");
  const manual = manualHours(applications), assisted = assistedHours(applications);
  const saved = Math.round((1 - assisted / manual) * 100);
  const pick = (clientX: number, element: SVGSVGElement) => {
    const box = element.getBoundingClientRect();
    const value = Math.round((((clientX - box.left) - left) / (width - left - right)) * maxApplications / 10) * 10;
    setApplications(Math.min(maxApplications, Math.max(10, value)));
  };
  return <figure className="gap-figure gap-projection" aria-labelledby="gap-fig3">
    <figcaption id="gap-fig3"><span>Fig. 3</span>Projection: recruiter reading time per role<em>Scenario estimate</em></figcaption>
    <label className="gap-slider">Applications received for one role<strong>{applications}</strong><input type="range" min={10} max={maxApplications} step={10} value={applications} onChange={(event) => setApplications(Number(event.target.value))} /></label>
    <ul className="gap-legend" aria-label="Legend"><li className="is-informal">Reading every application</li><li className="is-modern">Reading a JobBridge shortlist</li></ul>
    <div ref={frame} className="gap-chart">
      <svg width={width} height={height} role="img" aria-label={`At ${applications} applications: ${manual.toFixed(1)} hours reading every application, ${assisted.toFixed(1)} hours with a shortlist`} onPointerMove={(event) => pick(event.clientX, event.currentTarget)} onPointerDown={(event) => pick(event.clientX, event.currentTarget)}>
        {[0, 5, 10, 15, 20, 25].map((tick) => <g key={tick}><line className="gap-grid" x1={left} x2={width - right} y1={y(tick)} y2={y(tick)} /><text className="gap-axis" x={left - 8} y={y(tick) + 4} textAnchor="end">{tick}</text></g>)}
        {[0, 100, 200, 300, 400, 500].map((tick) => <text key={tick} className="gap-axis" x={x(tick)} y={height - 8} textAnchor={tick === 0 ? "start" : tick === maxApplications ? "end" : "middle"}>{tick}</text>)}
        <text className="gap-axis" x={left} y={top - 2}>hours</text>
        <line className="gap-crosshair" x1={x(applications)} x2={x(applications)} y1={top} y2={height - bottom} />
        <path className="gap-line is-informal" d={path(manualHours)} />
        <path className="gap-line is-modern" d={path(assistedHours)} />
        <circle className="gap-dot is-informal" cx={x(applications)} cy={y(manual)} r={5} />
        <circle className="gap-dot is-modern" cx={x(applications)} cy={y(assisted)} r={5} />
      </svg>
    </div>
    <p className="gap-readout" aria-live="polite"><span><b>{manual.toFixed(1)} h</b> reading every application</span><span><b>{assisted.toFixed(1)} h</b> with a ranked shortlist</span><span><b>{saved}%</b> less first-pass reading</span></p>
    <ul className="gap-assumptions">
      <li>Assumes {READ_MINUTES} minutes for a considered first read of one application. The often-quoted 7.4-second glance (Ladders, 2018) only decides whether to keep reading.</li>
      <li>With JobBridge, eligibility rules run automatically and the recruiter reads the top {SHORTLIST} ranked candidates, plus {RANKING_MINUTES} minutes to scan the ranking and its reasons.</li>
      <li>Measured on this deployment: ranking 228 candidates took a median of 1.15 seconds.</li>
      <li>This is an estimate, not a measured outcome. The matching model is trained on synthetic labels and its rankings have not yet been validated against real hiring decisions.</li>
    </ul>
    <Source keys={["ladders"]}>. Projection by JobBridge.</Source>
  </figure>;
}

/** Landing-page bulletin: sourced figures on Kenya's job-matching gap and a labelled projection of the platform's effect. */
export function LabourGap() {
  return <section className="public-gap" id="kenya" aria-labelledby="kenya-title"><div className="public-container public-section">
    <div className="public-section-heading"><p className="public-kicker">Kenya's labour market / In numbers</p><h2 id="kenya-title">Many people looking.<br />Few formal openings.</h2><p>Every year far more young Kenyans start looking for work than the formal economy can absorb, and recruiters still read applications one by one. Figures below are sourced; the projection is marked as an estimate.</p></div>
    <dl className="gap-stats">
      <div><dt>Young people joining the labour market each year</dt><dd>800k–1M</dd><Source keys={["afidep"]} /></div>
      <div><dt>New jobs in 2025 that were informal</dt><dd>86.9%</dd><Source keys={["es2026"]} /></div>
      <div><dt>Kenyan jobs needing digital skills by 2030</dt><dd>50–55%</dd><Source keys={["ifc"]} /></div>
    </dl>
    <div className="gap-grid-layout"><SupplyFigure /><JobsFigure /></div>
    <ProjectionFigure />
  </div></section>;
}
