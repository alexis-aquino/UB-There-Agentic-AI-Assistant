import { useEffect, useRef } from 'react';
import AppMenu from './AppMenu.jsx';

/** The nav bar every signed-in screen shares: the seal, the screen's name, and the Menu.
 *  It stays at the top while the page scrolls, and publishes its height as --masthead-height
 *  so other pinned things (the mascot, the topic index) sit below it, not under it. */
export default function Masthead({ subtitle, menu }) {
  const ref = useRef(null);

  useEffect(() => {
    const header = ref.current;
    const root = document.documentElement;
    const publish = () => root.style.setProperty('--masthead-height', `${header.offsetHeight}px`);
    publish();
    const observer = new ResizeObserver(publish);
    observer.observe(header);
    return () => {
      observer.disconnect();
      root.style.removeProperty('--masthead-height');
    };
  }, []);

  return (
    <header className="masthead" ref={ref}>
      <div className="masthead-brand">
        <span className="seal" aria-hidden="true">
          UB
        </span>
        <div>
          <h1>UB There</h1>
          <p className="label">{subtitle}</p>
        </div>
      </div>
      <AppMenu {...menu} />
    </header>
  );
}

/** A page opened from the Menu (Account, My questions, Voice settings), in place of the screen
 *  it was opened from, with the way back at the top. */
export function SubPage({ backLabel, onBack, children }) {
  // Braces matter: an effect may only return a cleanup function, and some browsers' scrollTo
  // returns a value, which React then tries to call on close.
  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, []);

  return (
    <div className="subpage">
      <button type="button" className="link-button subpage-back" onClick={onBack}>
        ← {backLabel}
      </button>
      {children}
    </div>
  );
}
