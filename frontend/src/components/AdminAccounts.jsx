import { useEffect, useState } from 'react';
import {
  accountState,
  daysUntilDeletable,
  loadAccounts,
  loadDeleted,
  loadDisabled,
  saveDeleted,
  saveDisabled,
} from '../admin/accounts.js';
import { ago, day } from '../admin/store.js';

const UNUSED_DAYS = 60; // "Not used": no use in the last 2 months, or never
const STATE_LABELS = { active: 'Active', inactive: 'Not used', disabled: 'Disabled' };
const STATE_TONES = { active: 'ok', inactive: 'warn', disabled: 'danger' };

/** Every account, how recently it was used, disabling the ones nobody uses, and deleting those
 * that have stayed disabled for a month. */
export default function AdminAccounts({ user, records }) {
  const [accounts, setAccounts] = useState(null);
  const [disabled, setDisabled] = useState(loadDisabled);
  const [deleted, setDeleted] = useState(loadDeleted);
  const [filter, setFilter] = useState('');
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState(() => new Set());
  const [confirm, setConfirm] = useState(null); // { action: 'disable' | 'delete', emails, label } waiting for a yes
  const [note, setNote] = useState('');

  useEffect(() => {
    // Deleted accounts are gone from the list for good.
    loadAccounts(records, user).then((list) => setAccounts(list.filter((a) => !deleted[a.email])));
  }, [records, user, deleted]);

  const isMe = (a) => a.email.toLowerCase() === user.email.toLowerCase();
  const stateOf = (a) => accountState(a, disabled, UNUSED_DAYS);

  const counts = { active: 0, inactive: 0, disabled: 0 };
  for (const a of accounts ?? []) counts[stateOf(a)] += 1;

  const text = search.trim().toLowerCase();
  const shown = (accounts ?? []).filter(
    (a) =>
      (!filter || stateOf(a) === filter) &&
      (!text || a.name.toLowerCase().includes(text) || a.email.toLowerCase().includes(text)),
  );
  const unused = (accounts ?? []).filter((a) => stateOf(a) === 'inactive' && !isMe(a));
  const deletable = (accounts ?? []).filter((a) => disabled[a.email] && daysUntilDeletable(disabled[a.email]) === 0);
  const picked = shown.filter((a) => selected.has(a.email));

  function update(next) {
    setDisabled(next);
    saveDisabled(next);
    setSelected(new Set());
    setConfirm(null);
    setNote('');
  }

  // Only accounts disabled for a month or more; the account and its disabled mark both go.
  function remove(emails) {
    const ok = emails.filter((email) => disabled[email] && daysUntilDeletable(disabled[email]) === 0);
    const stamp = { by: user.name, at: new Date().toISOString() };
    const nextDeleted = { ...deleted };
    const nextDisabled = { ...disabled };
    for (const email of ok) {
      nextDeleted[email] = stamp;
      delete nextDisabled[email];
    }
    setDeleted(nextDeleted);
    saveDeleted(nextDeleted);
    update(nextDisabled);
    setNote(`Deleted ${ok.length} account${ok.length === 1 ? '' : 's'}.`);
  }

  function disable(emails) {
    const stamp = { by: user.name, at: new Date().toISOString() };
    const next = { ...disabled };
    for (const email of emails) if (!next[email]) next[email] = stamp;
    update(next);
  }

  function enable(emails) {
    const next = { ...disabled };
    for (const email of emails) delete next[email];
    update(next);
  }

  function toggle(email) {
    const next = new Set(selected);
    if (next.has(email)) next.delete(email);
    else next.add(email);
    setSelected(next);
  }

  const selectable = shown.filter((a) => !isMe(a));
  const allPicked = selectable.length > 0 && selectable.every((a) => selected.has(a.email));

  if (!accounts) return <p className="voice-hint">Loading accounts…</p>;

  return (
    <section className="adm-section adm-page" aria-labelledby="adm-accounts-title">
      <div className="adm-tracker-head">
        <div>
          <h3 id="adm-accounts-title">Accounts</h3>
          <p className="adm-sub">
            Everyone with a UB There account and when they last used it. An account is “Not used” after 2 months without
            use. Disabling keeps the account and its history, and it can be enabled again. An account that has been
            disabled for a month can be deleted for good.
          </p>
        </div>
      </div>

      <dl className="adm-ledger adm-ledger-short">
        <div>
          <dt>Accounts</dt>
          <dd>{accounts.length}</dd>
        </div>
        <div>
          <dt>Active</dt>
          <dd>{counts.active}</dd>
          <span className="adm-delta">used in the last 2 months</span>
        </div>
        <div>
          <dt>Not used</dt>
          <dd>{counts.inactive}</dd>
          <span className="adm-delta">no use in 2 months, or never</span>
        </div>
        <div>
          <dt>Disabled</dt>
          <dd>{counts.disabled}</dd>
          <span className="adm-delta">can’t sign in</span>
        </div>
      </dl>

      {note && (
        <p className="adm-kb-note" role="status">
          {note}
        </p>
      )}

      {deletable.length > 0 && !confirm && (
        <div className="adm-callout is-danger">
          <p>
            <strong>{deletable.length}</strong> {deletable.length === 1 ? 'account has' : 'accounts have'} been disabled
            for over a month and can be deleted.
          </p>
          <button
            type="button"
            className="adm-danger-button"
            onClick={() =>
              setConfirm({
                action: 'delete',
                emails: deletable.map((a) => a.email),
                label: `${deletable.length} account${deletable.length === 1 ? '' : 's'} disabled for over a month`,
              })
            }
          >
            Delete all {deletable.length}
          </button>
        </div>
      )}

      {unused.length > 0 && !confirm && (
        <div className="adm-callout">
          <p>
            <strong>{unused.length}</strong> {unused.length === 1 ? 'account hasn’t' : 'accounts haven’t'} been used in
            2 months.
          </p>
          <button
            type="button"
            className="chip-button"
            onClick={() =>
              setConfirm({
                action: 'disable',
                emails: unused.map((a) => a.email),
                label: `${unused.length} account${unused.length === 1 ? '' : 's'} not used in 2 months`,
              })
            }
          >
            Disable all {unused.length}
          </button>
        </div>
      )}

      {confirm && (
        <div
          className="adm-callout is-confirm"
          role="alertdialog"
          aria-label={confirm.action === 'delete' ? 'Confirm deleting' : 'Confirm disabling'}
        >
          <p>
            {confirm.action === 'delete'
              ? `Delete ${confirm.label}? The account and its history are removed for good. This can’t be undone.`
              : `Disable ${confirm.label}? They won’t be able to sign in until an administrator enables them again.`}
          </p>
          <div className="adm-callout-actions">
            <button
              type="button"
              className="adm-danger-button"
              onClick={() => (confirm.action === 'delete' ? remove(confirm.emails) : disable(confirm.emails))}
            >
              {confirm.action === 'delete' ? 'Delete for good' : 'Disable'}
            </button>
            <button type="button" className="link-button" onClick={() => setConfirm(null)}>
              Cancel
            </button>
          </div>
        </div>
      )}

      <div className="adm-filters">
        <div className="adm-chips" role="group" aria-label="Filter by status">
          <button type="button" aria-pressed={!filter} onClick={() => setFilter('')}>
            All <span className="adm-chip-n">{accounts.length}</span>
          </button>
          {Object.entries(STATE_LABELS).map(([key, label]) => (
            <button
              key={key}
              type="button"
              aria-pressed={filter === key}
              onClick={() => setFilter(filter === key ? '' : key)}
            >
              {label} <span className="adm-chip-n">{counts[key]}</span>
            </button>
          ))}
        </div>
        <div className="adm-filter-row">
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search names or emails…"
            aria-label="Search names or emails"
          />
          {picked.length > 0 && (
            <>
              <button
                type="button"
                className="chip-button"
                onClick={() =>
                  setConfirm({
                    action: 'disable',
                    emails: picked.filter((a) => !disabled[a.email]).map((a) => a.email),
                    label: `the ${picked.filter((a) => !disabled[a.email]).length} selected account${picked.filter((a) => !disabled[a.email]).length === 1 ? '' : 's'}`,
                  })
                }
                disabled={picked.every((a) => disabled[a.email])}
              >
                Disable selected ({picked.filter((a) => !disabled[a.email]).length})
              </button>
              {picked.some((a) => disabled[a.email]) && (
                <button type="button" className="link-button" onClick={() => enable(picked.map((a) => a.email))}>
                  Enable selected ({picked.filter((a) => disabled[a.email]).length})
                </button>
              )}
              {picked.some((a) => deletable.includes(a)) && (
                <button
                  type="button"
                  className="link-button adm-danger-link"
                  onClick={() => {
                    const list = picked.filter((a) => deletable.includes(a));
                    setConfirm({
                      action: 'delete',
                      emails: list.map((a) => a.email),
                      label: `the ${list.length} selected account${list.length === 1 ? '' : 's'}`,
                    });
                  }}
                >
                  Delete selected ({picked.filter((a) => deletable.includes(a)).length})
                </button>
              )}
            </>
          )}
        </div>
      </div>

      {shown.length === 0 ? (
        <p className="voice-hint">No accounts match.</p>
      ) : (
        <div className="adm-scroll">
          <table className="adm-log adm-accounts">
            <thead>
              <tr>
                <th scope="col" className="adm-check-col">
                  <input
                    type="checkbox"
                    checked={allPicked}
                    onChange={() => setSelected(allPicked ? new Set() : new Set(selectable.map((a) => a.email)))}
                    aria-label="Select all shown"
                  />
                </th>
                <th scope="col">Account</th>
                <th scope="col">Sign-in</th>
                <th scope="col">Joined</th>
                <th scope="col">Last used</th>
                <th scope="col">Questions</th>
                <th scope="col">Status</th>
                <th scope="col">
                  <span className="sr-only">Action</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {shown.map((a) => {
                const state = stateOf(a);
                const off = disabled[a.email];
                return (
                  <tr key={a.email} className={state === 'disabled' ? 'is-disabled' : ''}>
                    <td className="adm-check-col">
                      {!isMe(a) && (
                        <input
                          type="checkbox"
                          checked={selected.has(a.email)}
                          onChange={() => toggle(a.email)}
                          aria-label={`Select ${a.name}`}
                        />
                      )}
                    </td>
                    <td>
                      <span className="adm-account-name">
                        {a.name}
                        {a.role === 'admin' && <span className="adm-tag">Admin</span>}
                        {isMe(a) && <span className="adm-tag">You</span>}
                      </span>
                      <span className="adm-log-ref">{a.email}</span>
                    </td>
                    <td className="adm-log-muted">{a.signIn}</td>
                    <td className="adm-log-muted">{day(a.createdAt)}</td>
                    <td className="adm-log-muted" title={day(a.lastActiveAt)}>
                      {ago(a.lastActiveAt)}
                    </td>
                    <td className="adm-log-muted">{a.questions}</td>
                    <td>
                      <span className={`adm-pill is-${STATE_TONES[state]}`}>{STATE_LABELS[state]}</span>
                      {off && (
                        <span className="adm-log-ref">
                          by {off.by}, {day(off.at)}
                          {daysUntilDeletable(off) > 0 &&
                            ` · can be deleted in ${daysUntilDeletable(off)} day${daysUntilDeletable(off) === 1 ? '' : 's'}`}
                        </span>
                      )}
                    </td>
                    <td className="adm-row-action">
                      {isMe(a) ? null : off ? (
                        <span className="adm-callout-actions adm-row-buttons">
                          <button type="button" className="link-button" onClick={() => enable([a.email])}>
                            Enable
                          </button>
                          {daysUntilDeletable(off) === 0 && (
                            <button
                              type="button"
                              className="link-button adm-danger-link"
                              onClick={() => setConfirm({ action: 'delete', emails: [a.email], label: a.name })}
                            >
                              Delete
                            </button>
                          )}
                        </span>
                      ) : (
                        <button
                          type="button"
                          className="link-button adm-danger-link"
                          onClick={() => setConfirm({ action: 'disable', emails: [a.email], label: a.name })}
                        >
                          Disable
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
