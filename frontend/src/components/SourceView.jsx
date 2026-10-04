import { useState } from 'react';
import { API_URL } from '../api.js';

// "studenthandbook.pdf" -> "student handbook"
function documentName(file) {
  return file
    .replace(/\.(pdf|docx?|txt|md)$/i, '')
    .replace(/[_-]+/g, ' ')
    .replace(/([a-z])(handbook|manual|guide|policy|policies|catalog)\b/gi, '$1 $2')
    .trim();
}

function where(c) {
  const name = documentName(c.file);
  return c.page ? `page ${c.page} of the ${name}` : `the ${name}`;
}

function pictureUrl(c, crop) {
  const params = new URLSearchParams({ file: c.file, page: String(c.page), quote: c.quote, crop: String(crop) });
  return `${API_URL}/api/sources/image?${params}`;
}

/** "Where I got this": the page, the passage, and a picture of it highlighted on the page. */
export default function SourceView({ citations }) {
  const [shown, setShown] = useState(0);
  const c = citations[shown];
  if (!c) return null;

  return (
    <div className="source-view">
      <p className="source-where">
        I got this from <strong>{where(c)}</strong>.
      </p>
      <blockquote className="source-quote">“{c.quote}”</blockquote>

      {c.image && (
        <a className="source-picture" href={pictureUrl(c, false)} target="_blank" rel="noreferrer">
          <img
            src={pictureUrl(c, true)}
            alt={`${where(c)}, with the passage highlighted`}
            loading="lazy"
          />
          <span className="source-open">Open the full page ↗</span>
        </a>
      )}

      {citations.length > 1 && (
        <p className="source-others">
          Also checked:{' '}
          {citations.map((other, i) =>
            i === shown ? null : (
              <button key={other.label} type="button" className="link-button" onClick={() => setShown(i)}>
                {other.page ? `page ${other.page}` : documentName(other.file)}
              </button>
            ),
          )}
        </p>
      )}
    </div>
  );
}
