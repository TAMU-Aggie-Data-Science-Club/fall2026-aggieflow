import { useEffect, useRef, useState } from "react";
import { askAgent } from "./api.js";
import AnswerText from "./AnswerText.jsx";
import GradeChart from "./GradeChart.jsx";

const TRY_ASKING = [
  "Who should I take for MATH 151?",
  "Compare CSCE 221 grades by professor",
  "Which courses meet the math requirement for my major?",
  "When is the last day to Q-drop this semester?",
];

const FEATURES = [
  {
    icon: "rules",
    title: "Find rules & deadlines",
    body: "Ask about policies, registration dates, Q-drops and campus services in plain words.",
    from: "Student Rules, Registrar",
  },
  {
    icon: "plan",
    title: "Plan your degree",
    body: "See which courses fill a requirement, by major and catalog year.",
    from: "Course Catalog, degree plans",
  },
  {
    icon: "grades",
    title: "Compare courses",
    body: "Look up past grade distributions and student ratings by course and professor.",
    from: "anex.us grade data, RateMyProfessors",
  },
];

let nextId = 1;

/** Earlier turns that got an answer, as the API's history: oldest first. */
function historyBefore(turns, index) {
  return turns.slice(0, index).flatMap((t) =>
    t.status === "done"
      ? [
          { role: "user", content: t.question },
          { role: "assistant", content: t.answer },
        ]
      : [],
  );
}

export default function App() {
  const [turns, setTurns] = useState([]);
  const conversation = useRef(0); // bumped by "New question" so a late answer is dropped
  const threadId = useRef(null); // the server's id for this conversation, from its first answer
  const pending = turns.some((t) => t.status === "pending");

  async function run(id, question, history) {
    const started = conversation.current;
    try {
      const result = await askAgent(question, history, threadId.current);
      if (conversation.current !== started) return;
      threadId.current = result.threadId;
      setTurns((ts) => ts.map((t) => (t.id === id ? { ...t, status: "done", ...result } : t)));
    } catch (err) {
      if (conversation.current !== started) return;
      setTurns((ts) => ts.map((t) => (t.id === id ? { ...t, status: "error", error: err.message } : t)));
    }
  }

  function ask(text) {
    const question = text.trim();
    if (!question || pending) return false;
    const id = nextId++;
    const history = historyBefore(turns, turns.length);
    setTurns((ts) => [...ts, { id, question, status: "pending" }]);
    run(id, question, history);
    return true;
  }

  function retry(id) {
    if (pending) return;
    const index = turns.findIndex((t) => t.id === id);
    const history = historyBefore(turns, index);
    setTurns((ts) => ts.map((t) => (t.id === id ? { ...t, status: "pending", error: undefined } : t)));
    run(id, turns[index].question, history);
  }

  function newQuestion() {
    conversation.current += 1;
    threadId.current = null;
    setTurns([]);
  }

  return (
    <div className="app">
      <Sidebar onNewQuestion={newQuestion} />
      {turns.length === 0 ? (
        <Home onAsk={ask} />
      ) : (
        <Conversation turns={turns} pending={pending} onAsk={ask} onRetry={retry} />
      )}
    </div>
  );
}

function Logo({ size, alt = "" }) {
  return <img className="logo" src="/logo.png" alt={alt} width={size} height={size} />;
}

function Sidebar({ onNewQuestion }) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <Logo size={36} />
        <span className="wordmark">
          <span className="wordmark-aggie">Aggie</span>
          <span className="wordmark-flow">Flow</span>
        </span>
        <span className="beta">Beta</span>
      </div>
      <button type="button" className="new-question" onClick={onNewQuestion}>
        <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <path d="M12 5v14M5 12h14" />
        </svg>
        New question
      </button>
      <div className="sidebar-footer">A Texas A&amp;M Aggie Data Science Club project</div>
    </aside>
  );
}

function Composer({ onAsk, disabled, big, placeholder, label, autoFocus }) {
  const [text, setText] = useState("");
  const box = useRef(null);

  function submit(event) {
    event?.preventDefault();
    if (onAsk(text)) setText("");
    box.current?.focus();
  }

  function onKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) submit(event);
  }

  const id = big ? "question" : "followup";
  return (
    <form className={big ? "composer composer-big" : "composer"} onSubmit={submit}>
      <label htmlFor={id} className="visually-hidden">
        {label}
      </label>
      <textarea
        id={id}
        ref={box}
        rows={big ? 2 : 1}
        value={text}
        placeholder={placeholder}
        autoFocus={autoFocus}
        maxLength={1000}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKeyDown}
      />
      <button type="submit" className="send" aria-label="Ask" disabled={disabled || !text.trim()}>
        <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 19V5M5 12l7-7 7 7" />
        </svg>
      </button>
    </form>
  );
}

const DISCLAIMER = "AggieFlow can be wrong. Check the cited source before you act on an answer.";

function Home({ onAsk }) {
  return (
    <main className="home">
      <div className="home-inner">
        <div className="hero">
          <Logo size={88} alt="AggieFlow" />
          <h1>Everything Aggieland</h1>
          <p>Courses, Professors, Policies, and More</p>
        </div>

        <Composer onAsk={onAsk} big autoFocus label="Your question" placeholder="e.g. Who should I take for MATH 151?" />

        <section aria-label="What AggieFlow does" className="features">
          {FEATURES.map((f) => (
            <div key={f.title} className="feature">
              <div className="feature-icon">
                <FeatureIcon name={f.icon} />
              </div>
              <div className="feature-title">{f.title}</div>
              <div className="feature-body">{f.body}</div>
              <div className="feature-from">From: {f.from}</div>
            </div>
          ))}
        </section>

        <section aria-label="Try a question" className="try">
          <div className="try-label">Try asking</div>
          <div className="chips">
            {TRY_ASKING.map((q) => (
              <button key={q} type="button" className="chip" onClick={() => onAsk(q)}>
                {q}
              </button>
            ))}
          </div>
        </section>

        <p className="disclaimer">{DISCLAIMER}</p>
      </div>
    </main>
  );
}

function FeatureIcon({ name }) {
  const common = { "aria-hidden": "true", width: 18, height: 18, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round" };
  if (name === "rules")
    return (
      <svg {...common}>
        <path d="M4 5a2 2 0 0 1 2-2h12v16H6a2 2 0 0 0-2 2z" />
        <path d="M4 21V5M9 8h6M9 12h6" />
      </svg>
    );
  if (name === "plan")
    return (
      <svg {...common}>
        <path d="M3 6l9-3 9 3-9 3z" />
        <path d="M7 8v5c0 1.5 2.5 3 5 3s5-1.5 5-3V8" />
        <path d="M21 6v6" />
      </svg>
    );
  return (
    <svg {...common}>
      <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
    </svg>
  );
}

function Conversation({ turns, pending, onAsk, onRetry }) {
  const latest = useRef(null);
  const last = turns[turns.length - 1];

  // Bring the newest question to the top, so its answer reads from the first line.
  useEffect(() => {
    const smooth = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    latest.current?.scrollIntoView({ behavior: smooth ? "smooth" : "auto", block: "start" });
  }, [turns.length, last.status]);

  return (
    <main className="conversation">
      <header className="conversation-header">
        <h1>{turns[0].question}</h1>
      </header>

      <div className="thread">
        <div className="thread-inner">
          {turns.map((turn, i) => (
            <Turn
              key={turn.id}
              turn={turn}
              bubbleRef={i === turns.length - 1 ? latest : null}
              retryDisabled={pending}
              onRetry={() => onRetry(turn.id)}
              onPick={i === turns.length - 1 && !pending ? onAsk : null}
            />
          ))}
          <div className="thread-end" />
        </div>
      </div>

      <div className="composer-dock">
        <div className="composer-dock-inner">
          <Composer onAsk={onAsk} disabled={pending} autoFocus label="Ask a follow-up" placeholder="Ask a follow-up…" />
          <p className="disclaimer">{DISCLAIMER}</p>
        </div>
      </div>
    </main>
  );
}

function Turn({ turn, bubbleRef, retryDisabled, onRetry, onPick }) {
  return (
    <>
      <div className="user-bubble" ref={bubbleRef}>
        {turn.question}
      </div>
      {turn.status === "pending" && (
        <div className="thinking" role="status" aria-live="polite">
          <span className="dot" />
          <span className="dot" />
          <span className="dot" />
          Thinking…
        </div>
      )}
      {turn.status === "error" && (
        <div className="error-turn" role="alert">
          <p>{turn.error}</p>
          <button type="button" className="retry" onClick={onRetry} disabled={retryDisabled}>
            Try again
          </button>
        </div>
      )}
      {turn.status === "done" && (
        <article className="answer" aria-label="AggieFlow answer">
          <div className="answer-head">
            <Logo size={30} />
            <span className="answer-name">AggieFlow</span>
          </div>
          {turn.asked ? (
            <Choices question={turn.asked} onPick={onPick} />
          ) : (
            <AnswerText text={turn.answer} />
          )}
          {turn.grades.map((chart) => (
            <GradeChart key={chart.course} chart={chart} />
          ))}
          {turn.sources.length > 0 && <Sources sources={turn.sources} />}
        </article>
      )}
    </>
  );
}

/** The agent asked which one the student means. Only the latest question's options can be
 * picked; typing a reply in the composer works too. */
function Choices({ question, onPick }) {
  return (
    <div className="choices">
      <p>{question.prompt}</p>
      <div className="chips" role="group" aria-label={question.prompt}>
        {question.options.map((option) => (
          <button key={option} type="button" className="chip" disabled={!onPick} onClick={() => onPick(option)}>
            {option}
          </button>
        ))}
      </div>
    </div>
  );
}

function siteOf(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

function Sources({ sources }) {
  return (
    <section aria-label="Sources" className="sources">
      <div className="sources-label">
        <svg aria-hidden="true" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M4 5a2 2 0 0 1 2-2h12v16H6a2 2 0 0 0-2 2z" />
          <path d="M4 21V5" />
        </svg>
        Sources
      </div>
      <div className="source-grid">
        {sources.map((s, i) => (
          <a key={s.source_url} className="source" href={s.source_url} target="_blank" rel="noopener noreferrer">
            <span className="source-site">
              <span className="source-n">{i + 1}</span>
              {siteOf(s.source_url)}
            </span>
            <span className="source-title">{s.title}</span>
          </a>
        ))}
      </div>
    </section>
  );
}
