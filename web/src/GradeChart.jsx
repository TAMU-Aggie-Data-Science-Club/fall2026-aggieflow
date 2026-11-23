import { useState } from "react";

// Grade distribution by professor for one course, from the API's `grades` field: the same
// professors and numbers get_course_grades gave the agent. Bars are shares of everyone who
// enrolled (letter grades plus Q-drops); "A's" is the share of letter grades, as anex.us
// and the agent's answers state it.

const SEGMENTS = [
  { key: "A", label: "A", color: "#500000" },
  { key: "B", label: "B", color: "#8E3A4C" },
  { key: "C", label: "C", color: "#C08A95" },
  { key: "DF", label: "D / F", color: "#E4CDD2" },
  { key: "Q", label: "Q-drop", color: "#A8A29E" },
];

const SORTS = [
  { id: "gpa", label: "Avg GPA", compare: (x, y) => y.gpa - x.gpa },
  { id: "a", label: "Most A's", compare: (x, y) => y.aPct - x.aPct },
  { id: "q", label: "Fewest Q-drops", compare: (x, y) => x.qPct - y.qPct },
];

const SHOWN = 8;

/** "NGUYEN T" -> "Nguyen T", "O'BRIEN-SMITH K" -> "O'Brien-Smith K" */
function displayName(name) {
  return name.toLowerCase().replace(/(^|[\s'-])([a-z])/g, (_, sep, c) => sep + c.toUpperCase());
}

function rowOf(p) {
  const c = p.counts;
  const graded = c.A + c.B + c.C + c.D + c.F;
  const enrolled = graded + c.Q;
  const share = (n) => (enrolled ? (100 * n) / enrolled : 0);
  return {
    name: displayName(p.name),
    sections: p.sections,
    gpa: p.gpa,
    aPct: graded ? Math.round((100 * c.A) / graded) : 0,
    qPct: enrolled ? Math.round((100 * c.Q) / enrolled) : 0,
    shares: { A: share(c.A), B: share(c.B), C: share(c.C), DF: share(c.D + c.F), Q: share(c.Q) },
  };
}

function barLabel(row) {
  const pct = (k) => `${Math.round(row.shares[k])}%`;
  return `${row.name}: ${pct("A")} A, ${pct("B")} B, ${pct("C")} C, ${pct("DF")} D or F, ${pct("Q")} Q-drop`;
}

export default function GradeChart({ chart }) {
  const [sort, setSort] = useState("gpa");
  const [showAll, setShowAll] = useState(false);
  const compare = SORTS.find((s) => s.id === sort).compare;
  const rows = chart.professors.map(rowOf).sort((x, y) => compare(x, y) || x.name.localeCompare(y.name));
  const visible = showAll ? rows : rows.slice(0, SHOWN);

  return (
    <section className="grade-chart" aria-label={`${chart.course} grades by professor`}>
      <div className="grade-chart-head">
        <div className="grade-chart-titles">
          <div className="grade-chart-title">{chart.course} · grades by professor since {chart.since}</div>
          <div className="grade-chart-sub">
            Professors with at least {chart.min_students} graded students ·{" "}
            <a href={chart.source_url} target="_blank" rel="noopener noreferrer">
              anex.us
            </a>
          </div>
        </div>
        <div className="sort-tabs" role="group" aria-label="Sort professors by">
          {SORTS.map((s) => (
            <button key={s.id} type="button" aria-pressed={sort === s.id} onClick={() => setSort(s.id)}>
              {s.label}
            </button>
          ))}
        </div>
      </div>

      <div className="grade-rows">
        {visible.map((row) => (
          <div key={row.name} className="grade-row">
            <div className="grade-name">
              <span className="grade-prof">{row.name}</span>
              <span className="grade-sections">
                {row.sections} section{row.sections === 1 ? "" : "s"}
              </span>
            </div>
            <div className="grade-bar" role="img" aria-label={barLabel(row)}>
              {SEGMENTS.map((s) =>
                row.shares[s.key] > 0 ? (
                  <span key={s.key} style={{ width: `${row.shares[s.key]}%`, background: s.color }} />
                ) : null,
              )}
            </div>
            <div className="grade-stat grade-gpa">
              <span className="grade-value">{row.gpa.toFixed(2)}</span>
              <span className="grade-unit">avg GPA</span>
            </div>
            <div className="grade-stat grade-a">
              <span className="grade-value">{row.aPct}%</span>
              <span className="grade-unit">A's</span>
            </div>
            <div className="grade-stat grade-q">
              <span className="grade-value">{row.qPct}%</span>
              <span className="grade-unit">Q-drops</span>
            </div>
          </div>
        ))}
      </div>

      <div className="grade-foot">
        <div className="grade-legend" aria-hidden="true">
          {SEGMENTS.map((s) => (
            <span key={s.key}>
              <span className="swatch" style={{ background: s.color }} />
              {s.label}
            </span>
          ))}
        </div>
        {rows.length > SHOWN && (
          <button type="button" className="show-all" onClick={() => setShowAll(!showAll)} aria-expanded={showAll}>
            {showAll ? "Show fewer" : `Show all ${rows.length} professors`}
          </button>
        )}
      </div>
    </section>
  );
}
