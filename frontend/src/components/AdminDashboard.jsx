import { Fragment, useEffect, useMemo, useState } from 'react';
import { STATES, buildReport, filterRecords, monthOf, stateOf } from '../admin/report.js';
import { TOPICS, loadQueryLog } from '../admin/sampleData.js';
import { monthName, periodName, readYears, yearMonths } from '../admin/months.js';
import MonthPicker from './MonthPicker.jsx';
import ThemeToggle from './ThemeToggle.jsx';

const FILTER_ORDER = ['answered', 'rerouted', 'pending', 'resolved', 'flagged'];
const PAGE = 25;

// The three views under the report's figures, each its own tab (and its own #admin/<tab>, so a reload keeps it).
const VIEWS = [
  ['questions', 'Asked questions'],
  ['trends', 'Inquiry trends'],
  ['tracker', 'Inquiry tracker'],
];
const viewFromHash = () => {
  const hash = window.location.hash.split('/')[1];
  return VIEWS.some(([key]) => key === hash) ? hash : 'questions';
};
const FLAG_STORE = 'ubt-admin-flags';

// Staff flags live in this browser until the backend stores them.
function loadFlags() {
  try {
    return JSON.parse(localStorage.getItem(FLAG_STORE)) ?? {};
  } catch {
    return {};
  }
}

function saveFlags(flags) {
  try {
    localStorage.setItem(FLAG_STORE, JSON.stringify(flags));
  } catch {
    // Private windows can refuse storage; the flag still holds for this visit.
  }
}

function when(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

function percent(part, whole) {
  return whole ? Math.round((part / whole) * 100) : 0;
}

function Delta({ now, before }) {
  if (!before && !now) return null;
  if (!before) return <span className="adm-delta">new this month</span>;
  const change = now - before;
  if (change === 0) return <span className="adm-delta">same as last month</span>;
  return (
    <span className="adm-delta">
      <span aria-hidden="true">{change > 0 ? '▲' : '▼'}</span> {Math.abs(change)} vs last month
    </span>
  );
}

function StatePill({ status }) {
  const state = STATES[status] ?? { label: status, tone: 'muted' };
  return <span className={`adm-pill is-${state.tone}`}>{state.label}</span>;
}

/** Mark an inquiry as offensive or off-topic, or clear the mark. */
function FlagControls({ q, onFlag }) {
  return (
    <div className="adm-flag">
      <p className="adm-flag-status">
        {q.flag ? (
          <>
            <StatePill status="flagged" /> Flagged by {q.flag.by}
            {q.flag.at && <span className="adm-timeline-at">{when(q.flag.at)}</span>}
          </>
        ) : (
          'Not flagged'
        )}
      </p>
      <div className="adm-chips" role="group" aria-label="Flag this inquiry">
        {q.flag ? (
          <button type="button" onClick={() => onFlag(q.id, false)}>
            Clear flag
          </button>
        ) : (
          <button type="button" onClick={() => onFlag(q.id, true)}>
            Flag as offensive or off-topic
          </button>
        )}
      </div>
    </div>
  );
}

/** The inquiry's life as a vertical track: asked -> handbook -> office -> office's answer. */
function Timeline({ q }) {
  const steps = [
    {
      title: 'Asked',
      at: q.askedAt,
      detail: q.student ? `by ${q.student.name}` : 'Not signed in',
      state: 'done',
    },
  ];

  if (q.status === 'answered') {
    steps.push({
      title: 'Answered by the chatbot',
      at: q.repliedAt,
      detail: `${q.source}${q.confidence ? ` · ${Math.round(q.confidence * 100)}% match` : ''}`,
      state: 'done',
    });
  } else {
    steps.push({
      title: 'Rerouted',
      at: q.repliedAt,
      detail: 'The chatbot couldn’t answer it from the handbook and offered “Ask an office”.',
      state: 'warn',
    });
    if (q.ticket) {
      steps.push({
        title: `Sent to the ${q.ticket.officeName}`,
        at: q.escalatedAt,
        detail: q.ticket.ref,
        state: 'done',
      });
      steps.push(
        q.status === 'resolved'
          ? {
              title: 'Resolved',
              at: q.resolvedAt,
              detail: `Answered by ${q.ticket.answeredBy}`,
              quote: q.ticket.answer,
              state: 'done',
            }
          : {
              title: 'Pending',
              detail: 'Waiting for the office. The student will see the answer under “My questions”.',
              state: 'current',
            },
      );
    } else {
      steps.push({
        title: 'Not sent to an office yet',
        detail: 'The student hasn’t asked an office.',
        state: 'idle',
      });
    }
  }
  if (q.flag) {
    steps.push({
      title: 'Flagged as offensive or off-topic',
      at: q.flag.at,
      detail: `by ${q.flag.by}`,
      state: 'stopped',
    });
  }

  return (
    <ol className="adm-timeline">
      {steps.map((s) => (
        <li key={s.title} className={`is-${s.state}`}>
          <span className="adm-timeline-dot" aria-hidden="true" />
          <div>
            <p className="adm-timeline-title">
              {s.title}
              {s.at && <span className="adm-timeline-at">{when(s.at)}</span>}
            </p>
            {s.detail && <p className="adm-timeline-detail">{s.detail}</p>}
            {s.quote && <blockquote className="adm-timeline-quote">{s.quote}</blockquote>}
          </div>
        </li>
      ))}
    </ol>
  );
}

/** Topics × months, shaded by how often each was asked. A table, so it reads without color too. */
function TrendGrid({ report }) {
  const rows = report.topics.filter((t) => t.total > 0);
  const max = Math.max(1, ...rows.flatMap((t) => t.counts));
  const shade = (n) => (n ? Math.round(10 + (n / max) * 78) : 0);
  // Months from more than one year carry their year, so "Mar" isn't ambiguous.
  const manyYears = new Set(report.months.map((m) => m.slice(0, 4))).size > 1;
  // Many months still fit the page: one letter per month, and each year named once, where it starts.
  const compact = report.months.length > 18;
  return (
    <div className="adm-scroll">
      <table className={`adm-heat ${compact ? 'is-compact' : ''}`}>
        <caption className="sr-only">Questions per topic per month</caption>
        <thead>
          <tr>
            <th scope="col">Topic</th>
            {report.months.map((m, i) => (
              <th key={m} scope="col" title={monthName(m)}>
                {monthName(m, compact ? 'narrow' : 'short')}
                {manyYears && (
                  <span className="adm-heat-year">
                    {!compact || i === 0 || m.endsWith('-01') ? m.slice(0, 4) : ' '}
                  </span>
                )}
              </th>
            ))}
            <th scope="col">Total</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((t) => (
            <tr key={t.topic}>
              <th scope="row">{t.topic}</th>
              {t.counts.map((n, i) => {
                const p = shade(n);
                const m = report.months[i];
                return (
                  <td
                    key={m}
                    className={p > 50 ? 'is-strong' : ''}
                    style={{ '--heat': `${p}%` }}
                    title={`${t.topic}, ${monthName(m)}: ${n} question${n === 1 ? '' : 's'}`}
                  >
                    {n || ''}
                  </td>
                );
              })}
              <td className="adm-heat-total">{t.total}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <th scope="row">All questions</th>
            {report.volume.map((v) => (
              <td key={v.month}>{v.questions}</td>
            ))}
            <td className="adm-heat-total">{report.volume.reduce((sum, v) => sum + v.questions, 0)}</td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

/** The administrator's view of the query log: monthly trends and where every inquiry stands. */
export default function AdminDashboard({ user, theme, onBack }) {
  const [log, setLog] = useState(null);
  const [flags, setFlags] = useState(loadFlags); // id -> flag, or null where staff cleared one
  const [months, setMonths] = useState(() => [monthOf(new Date())]); // 'all' or a list of "YYYY-MM"
  // What's typed in the Months dropdown's year box ("2026" or "2024-2026"), kept across tabs.
  const [yearText, setYearText] = useState(() => monthOf(new Date()).slice(0, 4));

  const [status, setStatus] = useState('');
  const [topic, setTopic] = useState('');
  const [search, setSearch] = useState('');
  const [shown, setShown] = useState(PAGE);
  const [open, setOpen] = useState(null);

  useEffect(() => {
    loadQueryLog().then(setLog);
  }, []);

  // The log with staff's flags laid over the assistant's.
  const records = useMemo(
    () => log?.map((r) => (r.id in flags ? { ...r, flag: flags[r.id] } : r)) ?? null,
    [log, flags],
  );

  const [view, setView] = useState(viewFromHash);
  useEffect(() => {
    const onHash = () => setView(viewFromHash());
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  function openView(key) {
    setView(key);
    window.history.replaceState(null, '', `#admin/${key}`);
  }

  // Arrow keys move between tabs, as in any tab strip.
  function onTabKey(e) {
    const i = VIEWS.findIndex(([key]) => key === view);
    const step = { ArrowRight: 1, ArrowLeft: -1 }[e.key];
    if (!step) return;
    e.preventDefault();
    const [next] = VIEWS[(i + step + VIEWS.length) % VIEWS.length];
    openView(next);
    document.getElementById(`adm-tab-${next}`)?.focus();
  }

  function flagInquiry(id, flagged) {
    const next = {
      ...flags,
      [id]: flagged ? { by: user.name, at: new Date().toISOString() } : null,
    };
    setFlags(next);
    saveFlags(next);
  }

  // Months that have questions, newest first, for the picker.
  const available = useMemo(
    () => (records ? [...new Set(records.map((r) => monthOf(r.askedAt)))].sort().reverse() : []),
    [records],
  );

  // The months the report covers, oldest first. All months means every month of the years typed
  // in the Months dropdown; with no valid years typed, every month that has questions.
  const period = useMemo(() => {
    if (months !== 'all') return [...months].sort();
    const years = readYears(yearText);
    if (years) return yearMonths(years);
    return available.length ? [...available].reverse() : [monthOf(new Date())];
  }, [months, available, yearText]);
  const single = period.length === 1;

  // Nothing ticked in the dropdown means no report until months are picked again.
  const report = useMemo(() => (records && period.length ? buildReport(records, period) : null), [records, period]);
  const matches = useMemo(
    () =>
      records && report
        ? filterRecords(records, {
            months: report.inPeriod,
            status,
            topic,
            search,
          })
        : [],
    [records, report, status, topic, search],
  );

  // A new filter starts the list from the top.
  useEffect(() => setShown(PAGE), [period, status, topic, search]);

  const s = report?.status ?? {};
  const asked = report?.totals;
  const before = report?.before;
  const scope = single ? 'this month' : 'this period';
  const sent = s.pending + s.resolved;
  const ranked = report?.topics.filter((t) => t.inPeriod > 0).slice(0, 7) ?? []; // the top seven only
  const topMax = Math.max(1, ...ranked.map((t) => t.inPeriod));

  return (
    <div className="app-shell adm-shell">
      <header className="masthead">
        <div className="masthead-brand">
          <span className="seal" aria-hidden="true">
            UB
          </span>
          <div>
            <h1>UB There</h1>
            <p className="label">Administrator · {user.name}</p>
          </div>
        </div>
        <div className="adm-head-actions">
          <ThemeToggle theme={theme.theme} onToggle={theme.toggle} />
          <button type="button" className="chip-button" onClick={onBack}>
            Back to chat
          </button>
        </div>
      </header>

      <div className="notice" role="status">
        <span className="label">Sample data</span>
        <span>These figures are made up to show the dashboard. Real ones appear once the backend logs them.</span>
      </div>

      {!records && <p className="voice-hint">Loading the query log…</p>}

      {records && (
        <>
          <section className="adm-cover">
            <div>
              <p className="label">Inquiry report{period.length > 1 ? ` · ${period.length} months` : ''}</p>
              <h2 className="adm-title">
                {months === 'all' ? 'All months' : period.length ? periodName(period) : 'No months selected'}
              </h2>
              {months === 'all' && <p className="adm-sub">{periodName(period)}</p>}
            </div>
            <MonthPicker
              available={available}
              value={months}
              onChange={setMonths}
              yearText={yearText}
              onYearText={setYearText}
            />
          </section>

          {!report && (
            <p className="voice-hint">Pick one or more months, or All months, from the dropdown to see the report.</p>
          )}

          {report && (
            <>
              <dl className="adm-ledger">
                <div>
                  <dt>Questions asked</dt>
                  <dd>{asked.questions}</dd>
                  <span className="adm-delta">
                    from {asked.askers} {asked.askers === 1 ? 'student' : 'students'}
                  </span>
                  {single && <Delta now={asked.questions} before={before?.questions ?? 0} />}
                </div>
                <div>
                  <dt>{STATES.answered.label}</dt>
                  <dd>{s.answered}</dd>
                  <span className="adm-delta">{percent(s.answered, asked.questions)}% of questions</span>
                </div>
                <div>
                  <dt>{STATES.rerouted.label}</dt>
                  <dd>{s.rerouted}</dd>
                  <span className="adm-delta">not sent to an office yet</span>
                </div>
                <div>
                  <dt>{STATES.pending.label}</dt>
                  <dd>{s.pending}</dd>
                  <span className="adm-delta">waiting on an office</span>
                </div>
                <div>
                  <dt>{STATES.resolved.label}</dt>
                  <dd>{s.resolved}</dd>
                  <span className="adm-delta">{percent(s.resolved, sent)}% of those sent to offices</span>
                </div>
                <div>
                  <dt>{STATES.flagged.label}</dt>
                  <dd>{s.flagged}</dd>
                  <span className="adm-delta">flagged</span>
                </div>
              </dl>

              <div className="adm-tabs" role="tablist" aria-label="Report views" onKeyDown={onTabKey}>
                {VIEWS.map(([key, label]) => (
                  <button
                    key={key}
                    id={`adm-tab-${key}`}
                    type="button"
                    role="tab"
                    aria-selected={view === key}
                    aria-controls={`adm-view-${key}`}
                    tabIndex={view === key ? 0 : -1}
                    onClick={() => openView(key)}
                  >
                    {label}
                    {key === 'tracker' && <span className="adm-chip-n">{matches.length}</span>}
                  </button>
                ))}
              </div>

              {view === 'questions' && (
                <div
                  className="adm-columns adm-view"
                  role="tabpanel"
                  id="adm-view-questions"
                  aria-labelledby="adm-tab-questions"
                >
                  <section className="adm-section">
                    <h3>Top inquiry topics</h3>
                    <p className="adm-sub">What students asked about most in {periodName(period)}.</p>
                    {ranked.length === 0 ? (
                      <p className="voice-hint">No questions {scope} yet.</p>
                    ) : (
                      <ol className="adm-bars">
                        {ranked.map((t, i) => (
                          <li key={t.topic}>
                            <button
                              type="button"
                              className={topic === t.topic ? 'is-active' : ''}
                              onClick={() => {
                                setTopic(t.topic);
                                openView('tracker');
                              }}
                              title="Show these in the tracker"
                            >
                              <span className="adm-bar-rank">{i + 1}</span>
                              <span className="adm-bar-name">{t.topic}</span>
                              <span className="adm-bar-count">
                                {t.inPeriod} <small>({percent(t.inPeriod, asked.questions)}%)</small>
                              </span>
                              <span className="adm-bar-track" aria-hidden="true">
                                <span
                                  style={{
                                    width: `${(t.inPeriod / topMax) * 100}%`,
                                  }}
                                />
                              </span>
                              {single && <Delta now={t.inPeriod} before={t.lastMonth} />}
                            </button>
                          </li>
                        ))}
                      </ol>
                    )}
                  </section>

                  <section className="adm-section">
                    <h3>Most asked questions</h3>
                    <p className="adm-sub">Repeats are counted together, ignoring case and punctuation.</p>
                    {report.topQuestions.length === 0 ? (
                      <p className="voice-hint">Nothing asked yet.</p>
                    ) : (
                      <ol className="adm-top">
                        {report.topQuestions.map((q) => (
                          <li key={q.question}>
                            <span className="adm-top-count">{q.count}×</span>
                            <div>
                              <p className="adm-top-question">{q.question}</p>
                              <p className="adm-top-meta">
                                Last asked {when(q.last.askedAt)} · <StatePill status={stateOf(q.last)} />
                              </p>
                            </div>
                          </li>
                        ))}
                      </ol>
                    )}
                  </section>
                </div>
              )}

              {view === 'trends' && (
                <section
                  className="adm-section adm-view"
                  role="tabpanel"
                  id="adm-view-trends"
                  aria-labelledby="adm-tab-trends"
                >
                  <h3>Inquiry trends by month</h3>
                  <p className="adm-sub">
                    Questions per topic in each month picked at the top
                    {report.months.length > 1 ? ` (${report.months.length} months)` : ''}. Darker means asked more
                    often.
                  </p>
                  <TrendGrid report={report} />
                </section>
              )}

              {view === 'tracker' && (
                <section
                  className="adm-section adm-view"
                  role="tabpanel"
                  id="adm-view-tracker"
                  aria-labelledby="adm-tab-tracker"
                >
                  <div className="adm-tracker-head">
                    <div>
                      <h3>Inquiry tracker</h3>
                      <p className="adm-sub">
                        Every question from {periodName(period)} and where it stands. Open one to follow it, or flag it
                        if it’s offensive or off-topic.
                      </p>
                    </div>
                    <span className="adm-count">
                      {matches.length} {matches.length === 1 ? 'inquiry' : 'inquiries'}
                    </span>
                  </div>

                  <div className="adm-filters">
                    {/* One state at a time: picking one replaces the last. */}
                    <div className="adm-chips" role="group" aria-label="Filter by state">
                      <button type="button" aria-pressed={!status} onClick={() => setStatus('')}>
                        All
                      </button>
                      {FILTER_ORDER.map((key) => (
                        <button
                          key={key}
                          type="button"
                          aria-pressed={status === key}
                          className={key === 'flagged' ? 'adm-chip-flag' : undefined}
                          onClick={() => setStatus(status === key ? '' : key)}
                        >
                          {STATES[key].label}
                          <span className="adm-chip-n">{s[key]}</span>
                        </button>
                      ))}
                    </div>
                    <div className="adm-filter-row">
                      <input
                        type="search"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        placeholder="Search questions or students…"
                        aria-label="Search questions or students"
                      />
                      <select value={topic} onChange={(e) => setTopic(e.target.value)} aria-label="Topic">
                        <option value="">All topics</option>
                        {TOPICS.map((name) => (
                          <option key={name} value={name}>
                            {name}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  {matches.length === 0 ? (
                    <p className="voice-hint">No inquiries match.</p>
                  ) : (
                    <div className="adm-scroll">
                      <table className="adm-log">
                        <thead>
                          <tr>
                            <th scope="col">Question</th>
                            <th scope="col">Student</th>
                            <th scope="col">Topic</th>
                            <th scope="col">Asked</th>
                            <th scope="col">State</th>
                          </tr>
                        </thead>
                        <tbody>
                          {matches.slice(0, shown).map((q) => (
                            <Fragment key={q.id}>
                              <tr className={`${open === q.id ? 'is-open' : ''} ${q.flag ? 'is-flagged' : ''}`}>
                                <td>
                                  <button
                                    type="button"
                                    className="adm-log-question"
                                    aria-expanded={open === q.id}
                                    onClick={() => setOpen(open === q.id ? null : q.id)}
                                  >
                                    {q.question}
                                  </button>
                                </td>
                                <td className="adm-log-muted">{q.student?.name ?? 'Not signed in'}</td>
                                <td className="adm-log-muted">{q.topic}</td>
                                <td className="adm-log-muted">{when(q.askedAt)}</td>
                                <td>
                                  <StatePill status={stateOf(q)} />
                                  {q.ticket && <span className="adm-log-ref">{q.ticket.ref}</span>}
                                </td>
                              </tr>
                              {open === q.id && (
                                <tr className="adm-log-detail">
                                  <td colSpan={5}>
                                    <Timeline q={q} />
                                    <FlagControls q={q} onFlag={flagInquiry} />
                                  </td>
                                </tr>
                              )}
                            </Fragment>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                  {shown < matches.length && (
                    <button type="button" className="link-button adm-more" onClick={() => setShown(shown + PAGE)}>
                      Show more ({matches.length - shown} left)
                    </button>
                  )}
                </section>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
