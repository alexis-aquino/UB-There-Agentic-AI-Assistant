/**
 * The query log from the backend (GET /api/admin/inquiries, administrators only): every question
 * students asked the assistant, newest first, and the topics the backend sorts them into.
 * The record shape is described in sampleData.js; report.js turns it into the report.
 */
import { apiFetch } from '../api.js';

export function loadQueryLog(token) {
  return apiFetch('/api/admin/inquiries', { token });
}

/** Mark an inquiry offensive or off-topic, or clear the mark. Returns the updated record. */
export function flagInquiry(token, id, flagged) {
  return apiFetch(`/api/admin/inquiries/${id}/flag`, { token, method: 'PUT', body: { flagged } });
}
