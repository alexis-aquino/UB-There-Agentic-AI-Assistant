import { Fragment, useEffect, useMemo, useState } from 'react';
import { STATES, buildReport, filterRecords, monthOf, stateOf } from '../admin/report.js';
import { flagInquiry as saveFlag, loadQueryLog } from '../admin/queryLog.js';
import { monthName, periodName, readYears, yearMonths } from '../admin/months.js';
import AdminAccounts from './AdminAccounts.jsx';
import AdminKnowledge from './AdminKnowledge.jsx';
import MonthPicker from './MonthPicker.jsx';
import ThemeToggle from './ThemeToggle.jsx';

const FILTER_ORDER = ['answered', 'rerouted', 'pending', 'resolved', 'closed', 'flagged'];
const PAGE = 25;

// The three views under the report's figures, each its own tab (and its own #admin/<tab>, so a reload keeps it).
const VIEWS = [
  ['questions', 'Asked questions'],
  ['trends', 'Inquiry trends'],
  ['tracker', 'Inquiry tracker'],
];
// The dashboard's parts. The report keeps its own tabs (#admin/questions …); the others are
// #admin/accounts and #admin/knowledge.
const SECTIONS = [
  ['report', 'Inquiry report'],
  ['accounts', 'Accounts'],
  ['knowledge', 'Knowledge base'],
];
const sectionFromHash = () => {
  const hash = window.location.hash.split('/')[1];
  return hash === 'accounts' || hash === 'knowledge' ? hash : 'report';
};
const viewFromHash = () => {
  const hash = window.location.hash.split('/')[1];
  return VIEWS.some(([key]) => key === hash) ? hash : 'questions';
};
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
      detail: q.student ? `by ${q.student.name}${q.student.deleted ? ' (account deleted)' : ''}` : 'Not signed in',
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
      if (q.status === 'resolved') {
        steps.push({
          title: 'Resolved',
          at: q.resolvedAt,
          detail: `Answered by ${q.ticket.answeredBy}`,
          quote: q.ticket.answer,
          state: 'done',
        });
      } else if (q.status !== 'closed') {
        steps.push({
          title: 'Pending',
          detail: 'Waiting for the office. The student will see the answer under “My questions”.',
          state: 'current',
        });
      }
    } else if (q.status !== 'closed') {
      steps.push({
        title: 'Not sent to an office yet',
        detail: 'The student hasn’t asked an office.',
        state: 'idle',
      });
    }
  }
  if (q.status === 'closed') {
    steps.push({
      title: 'Closed',
      at: q.closedAt,
      detail: q.ticket
        ? 'The student’s account was deleted before the office answered, so it can no longer be answered.'
        : 'The student’s account was deleted before it was sent to an office.',
      state: 'stopped',
    });
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

const MONTH_NUMS = Array.from({ length: 12 }, (_, i) => String(i + 1).padStart(2, '0'));

/**
 * One topics × months table, shaded by how often each was asked. A table, so it reads without
 * color too. `columns` are the months to show; any not in `picked` are greyed out. `countOf`
 * gives a topic's count for a month, and `max` is the darkest cell, shared across tables.
 */
function HeatTable({ caption, rows, columns, picked, countOf, max, label }) {
  const shade = (n) => (n ? Math.round(10 + (n / max) * 78) : 0);
  const sum = (list) => list.reduce((a, b) => a + b, 0);
  return (
    <table className="adm-heat">
      <caption className="sr-only">{caption}</caption>
      <thead>
        <tr>
          <th scope="col">Topic</th>
          {columns.map((m) => (
            <th key={m} scope="col" title={monthName(m)} className={picked.has(m) ? '' : 'is-off'}>
              {label(m)}
            </th>
          ))}
          <th scope="col">Total</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((t) => (
          <tr key={t.topic}>
            <th scope="row">{t.topic}</th>
            {columns.map((m) => {
              if (!picked.has(m)) {
                return (
                  <td key={m} className="is-off" title={`${monthName(m)} isn't in the report`}>
                    ·
                  </td>
                );
              }
              const n = countOf(t, m);
              const p = shade(n);
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
            <td className="adm-heat-total">{sum(columns.filter((m) => picked.has(m)).map((m) => countOf(t, m)))}</td>
          </tr>
        ))}
      </tbody>
      <tfoot>
        <tr>
          <th scope="row">All questions</th>
          {columns.map((m) => (
            <td key={m} className={picked.has(m) ? '' : 'is-off'}>
              {picked.has(m) ? sum(rows.map((t) => countOf(t, m))) : '·'}
            </td>
          ))}
          <td className="adm-heat-total">
            {sum(columns.filter((m) => picked.has(m)).flatMap((m) => rows.map((t) => countOf(t, m))))}
          </td>
        </tr>
      </tfoot>
    </table>
  );
}

/** Each year's total per topic, with totals at the side and along the bottom. */
function YearTable({ rows, years, yearTotal }) {
  const max = Math.max(1, ...rows.flatMap((t) => years.map(([y]) => yearTotal(t, y))));
  const shade = (n) => (n ? Math.round(10 + (n / max) * 78) : 0);
  const yearAll = (y) => rows.reduce((sum, t) => sum + yearTotal(t, y), 0);
  return (
    <table className="adm-heat adm-heat-summary">
      <caption className="sr-only">Questions per topic per year</caption>
      <thead>
        <tr>
          <th scope="col">Topic</th>
          {years.map(([y]) => (
            <th key={y} scope="col">
              {y}
            </th>
          ))}
          <th scope="col">Total</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((t) => (
          <tr key={t.topic}>
            <th scope="row">{t.topic}</th>
            {years.map(([y]) => {
              const n = yearTotal(t, y);
              const p = shade(n);
              return (
                <td
                  key={y}
                  className={p > 50 ? 'is-strong' : ''}
                  style={{ '--heat': `${p}%` }}
                  title={`${t.topic}, ${y}: ${n} question${n === 1 ? '' : 's'}`}
                >
                  {n}
                </td>
              );
            })}
            <td className="adm-heat-total">{years.reduce((sum, [y]) => sum + yearTotal(t, y), 0)}</td>
          </tr>
        ))}
      </tbody>
      <tfoot>
        <tr>
          <th scope="row">All questions</th>
          {years.map(([y]) => (
            <td key={y}>{yearAll(y)}</td>
          ))}
          <td className="adm-heat-total">{years.reduce((sum, [y]) => sum + yearAll(y), 0)}</td>
        </tr>
      </tfoot>
    </table>
  );
}

/**
 * Topics over the months picked at the top. Within one year: a single table, a column per month.
 * Across years: "All" shows a column per year; each year button shows that year's Jan–Dec, one
 * table at a time, so the page stays short however many years are in the report.
 */
function TrendGrid({ report }) {
  const rows = report.topics.filter((t) => t.total > 0);
  const column = new Map(report.months.map((m, i) => [m, i]));
  const countOf = (t, m) => (column.has(m) ? t.counts[column.get(m)] : 0);
  const max = Math.max(1, ...rows.flatMap((t) => t.counts));

  const byYear = new Map();
  for (const m of report.months) {
    const y = m.slice(0, 4);
    if (!byYear.has(y)) byYear.set(y, []);
    byYear.get(y).push(m);
  }
  const years = [...byYear];

  // 'all' for the yearly table, or the year whose months are shown.
  const [picked, setPicked] = useState('all');
  const shown = byYear.has(picked) ? picked : 'all';

  if (years.length === 1) {
    return (
      <div className="adm-scroll">
        <HeatTable
          caption="Questions per topic per month"
          rows={rows}
          columns={report.months}
          picked={report.inPeriod}
          countOf={countOf}
          max={max}
          label={(m) => monthName(m, 'short')}
        />
      </div>
    );
  }

  const yearTotal = (t, y) => byYear.get(y).reduce((sum, m) => sum + countOf(t, m), 0);
  const questionsIn = (y) => rows.reduce((sum, t) => sum + yearTotal(t, y), 0);
  const months = shown === 'all' ? null : byYear.get(shown);
  return (
    <div>
      <div className="adm-year-switch">
        <h4 className="adm-heat-heading">Month by month</h4>
        <div className="adm-chips" role="group" aria-label="Year to show">
          <button type="button" aria-pressed={shown === 'all'} onClick={() => setPicked('all')}>
            All
          </button>
          {[...years].reverse().map(([y]) => (
            <button key={y} type="button" aria-pressed={y === shown} onClick={() => setPicked(y)}>
              {y}
            </button>
          ))}
        </div>
      </div>

      {shown === 'all' ? (
        <>
          <p className="adm-sub">
            Each year’s total per topic, for the months picked at the top. Pick a year to see its months.
          </p>
          <div className="adm-scroll">
            <YearTable rows={rows} years={years} yearTotal={yearTotal} />
          </div>
        </>
      ) : (
        <>
          <p className="adm-sub">
            {shown}: {months.length === 12 ? 'all 12 months' : `${months.length} of 12 months picked`} ·{' '}
            {questionsIn(shown)} questions. Months not picked show as “·”.
          </p>
          <div className="adm-scroll">
            <HeatTable
              caption={`Questions per topic per month, ${shown}`}
              rows={rows}
              columns={MONTH_NUMS.map((n) => `${shown}-${n}`)}
              picked={report.inPeriod}
              countOf={countOf}
              max={max}
              label={(m) => monthName(m, 'short')}
            />
          </div>
        </>
      )}
    </div>
  );
}

/** The administrator's view of the query log: monthly trends and where every inquiry stands. */
export default function AdminDashboard({ user, token, theme, onBack }) {
  const [records, setRecords] = useState(null); // the query log, newest first
  const [topics, setTopics] = useState([]);
  const [loadError, setLoadError] = useState(null);
  const [flagError, setFlagError] = useState(null);
  const [months, setMonths] = useState(() => [monthOf(new Date())]); // 'all' or a list of "YYYY-MM"
  // What's typed in the Months dropdown's year box ("2026" or "2024-2026"), kept across tabs.
  const [yearText, setYearText] = useState(() => monthOf(new Date()).slice(0, 4));

  const [status, setStatus] = useState('');
  const [topic, setTopic] = useState('');
  const [search, setSearch] = useState('');
  const [shown, setShown] = useState(PAGE);
  const [open, setOpen] = useState(null);

  useEffect(() => {
    loadQueryLog(token)
      .then((data) => {
        setRecords(data.inquiries);
        setTopics(data.topics);
      })
      .catch((err) => setLoadError(err.message));
  }, [token]);

  const [view, setView] = useState(viewFromHash);
  const [section, setSection] = useState(sectionFromHash);
  useEffect(() => {
    const onHash = () => {
      setView(viewFromHash());
      setSection(sectionFromHash());
    };
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  function openView(key) {
    setView(key);
    window.history.replaceState(null, '', `#admin/${key}`);
  }

  function openSection(key) {
    setSection(key);
    // The report comes back on the tab it was left on.
    window.history.replaceState(null, '', `#admin/${key === 'report' ? view : key}`);
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
    setFlagError(null);
    saveFlag(token, id, flagged)
      .then((updated) => setRecords((prev) => prev.map((r) => (r.id === id ? updated : r))))
      .catch((err) => setFlagError(err.message));
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
  const sent = report?.sent ?? 0;
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

      <nav className="adm-sections" aria-label="Dashboard">
        {SECTIONS.map(([key, label]) => (
          <button
            key={key}
            type="button"
            aria-current={section === key ? 'page' : undefined}
            onClick={() => openSection(key)}
          >
            {label}
          </button>
        ))}
      </nav>

      {section === 'knowledge' && (
        <div className="notice" role="status">
          <span className="label">Sample data</span>
          <span>Changes here are saved only in this browser. The assistant uses them once the backend can index them.</span>
        </div>
      )}

      {section === 'accounts' && <AdminAccounts user={user} token={token} />}

      {section === 'knowledge' && <AdminKnowledge user={user} />}

      {section === 'report' && !records && (
        <p className="voice-hint">{loadError ? `Couldn't load the query log: ${loadError}` : 'Loading the query log…'}</p>
      )}
      {section === 'report' && flagError && <p className="voice-hint">Couldn't save the flag: {flagError}</p>}

      {section === 'report' && records && (
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
                  <dt>{STATES.closed.label}</dt>
                  <dd>{s.closed}</dd>
                  <span className="adm-delta">student’s account deleted</span>
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
                  <h3>Inquiry trends</h3>
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
                        {topics.map((name) => (
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
                                <td className="adm-log-muted">
                                  {q.student?.name ?? 'Not signed in'}
                                  {q.student?.deleted && <span className="adm-log-ref">Account deleted</span>}
                                </td>
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
