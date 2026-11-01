import { useEffect, useRef } from 'react';

/**
 * The masthead stays pinned to the top of the window, so anything else that sticks (the
 * index, the avatar, the dashboard's section tabs) has to stick below it. This keeps the
 * header's live height in --masthead-h on <html> for the CSS to use; it changes when the
 * header wraps onto more lines on a narrow window.
 */
export default function useMastheadHeight() {
  const ref = useRef(null);

  useEffect(() => {
    const header = ref.current;
    if (!header) return undefined;
    const root = document.documentElement;
    const measure = () => root.style.setProperty('--masthead-h', `${header.offsetHeight}px`);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(header);
    return () => {
      observer.disconnect();
      root.style.removeProperty('--masthead-h');
    };
  }, []);

  return ref;
}
