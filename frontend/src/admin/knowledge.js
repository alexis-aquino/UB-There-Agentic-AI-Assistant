/**
 * SAMPLE knowledge base for the admin's Knowledge base page. The assistant answers from the files
 * in "upload uni info here", indexed by backend/ingest.py; there is no API to change them yet, so
 * this page keeps its list in this browser. Three kinds of content:
 *
 *   documents: { id, name, type, size, addedAt, addedBy, status: 'indexed' | 'waiting' }
 *   entries:   { id, title, topic, office, content, updatedAt, updatedBy, status: 'indexed' | 'waiting' }
 *   pictures:  { id, title, topic, description, src (a shrunk data: URL), updatedAt, updatedBy, status }
 *
 * The backend reads text only, so a picture reaches the assistant through its description.
 *
 * Anything added or changed here is 'waiting' until the backend indexes it.
 */
import { readStore, writeStore } from './store.js';

const STORE = 'ubt-admin-knowledge';
const DAY = 86_400_000;

// What the backend reads (backend/app/brain/readers.py).
export const DOC_TYPES = ['.pdf', '.docx', '.txt', '.md'];
export const IMAGE_TYPES = ['image/png', 'image/jpeg', 'image/webp', 'image/gif'];

function sample(now = new Date()) {
  const at = (days) => new Date(now - days * DAY).toISOString();
  return {
    documents: [
      {
        id: 'doc-handbook',
        name: 'studenthandbook.pdf',
        type: 'PDF',
        size: 2_480_000,
        addedAt: at(60),
        addedBy: 'Office of Student Affairs',
        status: 'indexed',
      },
    ],
    entries: [
      {
        id: 'entry-cashier-hours',
        title: 'Cashier office hours',
        topic: 'Tuition & fees',
        office: 'Accounting / Cashier',
        content:
          'The Cashier is open Monday to Friday, 8:00 AM to 5:00 PM, and Saturday, 8:00 AM to 12:00 NN. ' +
          'It is closed on Sundays and holidays.',
        updatedAt: at(20),
        updatedBy: 'Accounting / Cashier',
        status: 'indexed',
      },
      {
        id: 'entry-library-saturday',
        title: 'Library hours on Saturdays',
        topic: 'Library & facilities',
        office: 'University Library',
        content: 'The main library is open on Saturdays from 8:00 AM to 4:00 PM during regular semesters.',
        updatedAt: at(12),
        updatedBy: 'University Library',
        status: 'indexed',
      },
      {
        id: 'entry-lost-id',
        title: 'Replacing a lost student ID',
        topic: 'Student ID',
        office: 'Office of Student Affairs',
        content:
          'Report the loss to the Office of Student Affairs, submit an affidavit of loss, and pay the ' +
          'replacement fee at the Cashier. The new ID is released after 3 working days.',
        updatedAt: at(5),
        updatedBy: 'Office of Student Affairs',
        status: 'indexed',
      },
    ],
    pictures: [],
  };
}

// Lists saved before pictures existed have none yet.
export const loadKnowledge = () => ({ pictures: [], ...(readStore(STORE, null) ?? sample()) });
export const saveKnowledge = (kb) => writeStore(STORE, kb);

/**
 * A picture shrunk to fit browser storage: at most `max` pixels on its longer side, as a JPEG
 * data: URL on white (transparent areas would otherwise turn black).
 */
export async function shrinkImage(file, max = 1000) {
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, max / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#fff';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close?.();
  return canvas.toDataURL('image/jpeg', 0.82);
}

export const newId = (kind) => `${kind}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;

export function fileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
