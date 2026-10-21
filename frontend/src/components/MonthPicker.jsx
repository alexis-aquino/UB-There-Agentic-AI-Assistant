import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { MAX_YEARS, periodName, readYears, yearMonths } from '../admin/months.js';

const MONTHS = Array.from({ length: 12 }, (_, i) => ({
  num: String(i + 1).padStart(2, '0'),
  name: new Date(2000, i, 1).toLocaleString(undefined, { month: 'short' }),
}));

/**
 * The report period as one dropdown: all months, or any months picked by typing a year (or a
 * span of years, "2024-2026") and ticking months. Picks are kept when the year changes, so one
 * report can cover several years.
 * `value` is 'all' or a list of "YYYY-MM"; `available` is the months with questions.
 * `yearText`/`onYearText` is what's typed in the year box. The dashboard keeps it, so the typed
 * years stay put when the dropdown closes or the report switches tabs.
 */
export default function MonthPicker({ available, value, onChange, yearText, onYearText }) {
  const all = value === 'all';
  const chosen = all ? [] : value;

  const [open, setOpen] = useState(false);
  const box = useRef(null);
  const yearInput = useRef(null);
  const panelId = useId();

  const years = readYears(yearText);
  const hasData = useMemo(() => new Set(available), [available]);

  useEffect(() => {
    if (!open) return undefined;
    yearInput.current?.select();
    const away = (e) => {
      if (!box.current?.contains(e.target)) setOpen(false);
    };
    document.addEventListener('pointerdown', away);
    return () => document.removeEventListener('pointerdown', away);
  }, [open]);

  const keyOf = (y, m) => `${y}-${m.num}`;

  // With All months on, every box shows ticked. Unticking one keeps all the others: every
  // month of the typed years (or, with no years typed, every month with questions).
  const isOn = (m) => all || chosen.includes(m);
  const current = all ? (years ? yearMonths(years) : available) : chosen;

  let label = chosen.length ? periodName(chosen) : 'No months selected';
  if (all) label = years ? `All months · ${periodName(yearMonths(years))}` : 'All months';

  function toggle(m) {
    if (!isOn(m)) return onChange([...chosen, m]);
    onChange(current.filter((c) => c !== m));
  }

  // Tick or clear one year's months together (the year boxes in a span of years).
  function toggleAll(list) {
    if (!list.every(isOn)) return onChange([...new Set([...chosen, ...list])]);
    onChange(current.filter((m) => !list.includes(m)));
  }

  const yearKeys = (y) => MONTHS.map((m) => keyOf(y, m));

  return (
    <div
      className="adm-picker"
      ref={box}
      onKeyDown={(e) => {
        if (e.key === 'Escape') setOpen(false);
      }}
    >
      <button
        type="button"
        className="adm-picker-button"
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen(!open)}
      >
        <span className="label">Months</span>
        <span className="adm-picker-value">
          {label}
        </span>
        <span aria-hidden="true" className="adm-picker-caret">
          ▾
        </span>
      </button>

      {open && (
        <div className="adm-picker-panel" id={panelId} role="dialog" aria-label="Choose months">
          <div className="adm-picker-yearrow">
            <label>
              <span className="label">Year or years</span>
              <input
                ref={yearInput}
                type="text"
                inputMode="numeric"
                maxLength={14}
                value={yearText}
                placeholder="2025 or 2024-2026"
                onChange={(e) => onYearText(e.target.value.replace(/[^\d\s\-–—to]/gi, ''))}
              />
            </label>
            {(all || chosen.length > 0) && (
              <button type="button" className="link-button" onClick={() => onChange([])}>
                Clear
              </button>
            )}
          </div>

          <label className="adm-picker-option is-all">
            <input type="checkbox" checked={all} onChange={() => onChange(all ? [] : 'all')} />
            All months
          </label>

          {years ? (
            <div className="adm-picker-years">
              {years.map((y) => (
                <div key={y} className="adm-picker-months" role="group" aria-label={`Months of ${y}`}>
                  {years.length > 1 && (
                    <label className="adm-picker-yearname">
                      <input
                        type="checkbox"
                        checked={yearKeys(y).every(isOn)}
                        ref={(el) => {
                          // Part of the year ticked: show the box half-filled.
                          if (el) el.indeterminate = yearKeys(y).some(isOn) && !yearKeys(y).every(isOn);
                        }}
                        onChange={() => toggleAll(yearKeys(y))}
                      />
                      {y}
                    </label>
                  )}
                  {MONTHS.map((m) => {
                    const key = keyOf(y, m);
                    return (
                      <label
                        key={key}
                        className={`adm-picker-option ${hasData.has(key) ? '' : 'is-empty'}`}
                        title={hasData.has(key) ? undefined : 'No questions this month'}
                      >
                        <input type="checkbox" checked={isOn(key)} onChange={() => toggle(key)} />
                        {m.name}
                      </label>
                    );
                  })}
                </div>
              ))}
            </div>
          ) : (
            <p className="adm-picker-hint">
              Type a year like 2025, or a span like 2024-2026 (up to {MAX_YEARS} years).
            </p>
          )}

          {!all && (
            <p className="adm-picker-hint">
              {chosen.length ? (
                <>
                  Chosen: <strong>{periodName(chosen)}</strong>
                  {chosen.length > 1 && ` · ${chosen.length} months`}
                </>
              ) : (
                'Nothing chosen — tick a month, or All months.'
              )}
            </p>
          )}

          <div className="adm-picker-foot">
            <button type="button" className="chip-button" onClick={() => setOpen(false)}>
              Done
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
