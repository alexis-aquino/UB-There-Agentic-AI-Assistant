import { useCallback, useEffect, useState } from 'react';

const KEY = 'ub-there-theme';

function savedTheme() {
  try {
    const value = localStorage.getItem(KEY);
    return value === 'light' || value === 'dark' ? value : null;
  } catch {
    return null;
  }
}

function systemTheme() {
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

/**
 * Light or dark, as <html data-theme="...">. Follows the device setting until the user picks
 * one; after that their choice sticks. index.html applies the same rule before first paint,
 * so the page never flashes in the wrong theme.
 */
export default function useTheme() {
  const [chosen, setChosen] = useState(savedTheme);
  const [system, setSystem] = useState(systemTheme);
  const theme = chosen ?? system;

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    const query = window.matchMedia?.('(prefers-color-scheme: dark)');
    if (!query) return undefined;
    const follow = () => setSystem(query.matches ? 'dark' : 'light');
    query.addEventListener('change', follow);
    return () => query.removeEventListener('change', follow);
  }, []);

  const toggle = useCallback(() => {
    const next = theme === 'dark' ? 'light' : 'dark';
    setChosen(next);
    try {
      localStorage.setItem(KEY, next);
    } catch {
      // Private mode: the choice lasts until reload.
    }
  }, [theme]);

  return { theme, toggle };
}
