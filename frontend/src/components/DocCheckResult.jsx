const VERDICTS = {
  passed: 'Looks complete',
  needs_fixing: 'Needs fixing',
  denied: 'Can’t be checked',
  unreadable: 'Retake the photo',
};

const MARKS = { met: '✓', missing: '✗', unclear: '?' };
const STATUS_NAMES = { met: 'Met', missing: 'Missing', unclear: 'Can’t tell from the photo' };

/** The verdict on a document photo: each handbook requirement, met or not. */
export default function DocCheckResult({ result }) {
  return (
    <div className={`doc-check is-${result.status}`}>
      <p className="doc-check-verdict">
        <span className="doc-check-badge">{VERDICTS[result.status] ?? result.status}</span>
        <span className="ticket-meta">{result.document_type}</span>
      </p>
      {result.checks.length > 0 && (
        <ul className="doc-check-list">
          {result.checks.map((c, i) => (
            <li key={i} className={`doc-check-item is-${c.status}`}>
              <span className="doc-check-mark" aria-label={STATUS_NAMES[c.status]} title={STATUS_NAMES[c.status]}>
                {MARKS[c.status]}
              </span>
              <span>
                <span className="doc-check-requirement">{c.requirement}</span>
                {c.detail && <span className="doc-check-detail">{c.detail}</span>}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
