/** Switches between light and dark mode. Names the mode it switches *to*. */
export default function ThemeToggle({ theme, onToggle, className }) {
  const toDark = theme === 'light';
  return (
    <button
      type="button"
      className={`theme-toggle ${className ?? ''}`}
      onClick={onToggle}
      aria-label={toDark ? 'Switch to dark mode' : 'Switch to light mode'}
    >
      {toDark ? (
        <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" fill="currentColor" />
        </svg>
      ) : (
        <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="12" r="4.5" fill="currentColor" />
          <path
            d="M12 1.5v3M12 19.5v3M1.5 12h3M19.5 12h3M4.6 4.6l2.1 2.1M17.3 17.3l2.1 2.1M4.6 19.4l2.1-2.1M17.3 6.7l2.1-2.1"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          />
        </svg>
      )}
      <span className="theme-toggle-text">{toDark ? 'Dark mode' : 'Light mode'}</span>
    </button>
  );
}
