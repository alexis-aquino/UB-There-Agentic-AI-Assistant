---
name: secure-defaults
description: Use when writing or changing any app code that touches auth, user input, secrets, databases, file uploads, APIs, dependencies or deployment config, so security is built in while coding instead of bolted on at review.
---

# Secure Defaults

Most app vulnerabilities come from a handful of repeated mistakes. This skill makes the safe choice the default one while code is being written. When a rule below conflicts with what the user asked for, say so in one line and propose the safe version instead of silently doing either.

## 1. Secrets

- Never hardcode API keys, passwords, tokens, private keys or connection strings in code, tests, fixtures, docs or commit messages. Read them from environment variables or a secrets manager.
- Create a `.env.example` with placeholder values and make sure `.env`, `*.pem`, `*.key` and credential files are in `.gitignore` before the first commit.
- Never log secrets, full tokens, passwords or full request bodies that may contain them. Redact in loggers and error reporters.
- Anything shipped to a browser or mobile app is public. Only publishable keys (for example a Stripe publishable key or a Firebase web config) may go to the client; secret keys stay server-side.
- If a secret was ever committed, treat it as leaked: tell the user to rotate it. Deleting it from the file is not enough.

## 2. Authentication and sessions

- Use a well-maintained auth library or provider (for example Auth.js, Lucia, Clerk, Supabase Auth, Firebase Auth, Django/Rails built-ins, Devise, Spring Security). Do not invent password hashing, token formats or session schemes.
- If storing passwords yourself: argon2id or bcrypt only, never MD5/SHA-1/SHA-256 alone, never reversible encryption.
- Session cookies: `HttpOnly`, `Secure`, `SameSite=Lax` (or `Strict`), sensible expiry. Prefer server sessions or short-lived access tokens with refresh rotation over long-lived JWTs in `localStorage`.
- Rate-limit login, signup, password reset and OTP endpoints. Return the same message for "no such user" and "wrong password".
- Password reset and email verification tokens: random (crypto-secure), single-use, expiring, stored hashed.

## 3. Authorization (the most commonly missed one)

- Check permissions on the server for every request, not just by hiding buttons in the UI.
- Every query that fetches or changes a record by ID must also scope by the current user or tenant (`WHERE id = ? AND owner_id = ?`). Never trust an ID, role or price coming from the client.
- Deny by default: new routes and endpoints require auth unless explicitly marked public.
- With Supabase/Firebase or any client-direct database, enable Row Level Security or security rules on every table/collection before shipping, and test that one user cannot read another's data.

## 4. Input handling

- Validate all external input at the boundary with a schema (Zod, Pydantic, Joi, class-validator, etc.): type, length, format, allowed values. Reject, don't "fix up".
- SQL: parameterized queries or an ORM only. Never build queries by string concatenation or template literals with user data.
- HTML: rely on the framework's escaping. Avoid `dangerouslySetInnerHTML`, `v-html`, `innerHTML`, `|safe`; if unavoidable, sanitize with DOMPurify or equivalent.
- Shell: never pass user input to `exec`/`system`/`shell=True`. Use argument arrays.
- URLs fetched by the server (webhooks, link previews, image imports): block private/internal IP ranges and metadata endpoints to prevent SSRF.
- Redirects: only to relative paths or an allowlist of domains.
- Deserialization: never `pickle`, `yaml.load` (unsafe), or `eval` on untrusted data.

## 5. File uploads

- Enforce size limits and an allowlist of types, checked by content (magic bytes), not just extension.
- Store with generated names outside the web root or in object storage; serve with `Content-Disposition` and correct `Content-Type`.
- Never let a user-supplied filename build a filesystem path (path traversal).

## 6. Web and API hardening

- HTTPS everywhere; set HSTS in production.
- Security headers: a Content-Security-Policy (start strict, loosen deliberately), `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `frame-ancestors` or `X-Frame-Options`. Use the framework's helper (helmet, django-csp, secure_headers).
- CORS: explicit origin allowlist. Never `*` together with credentials.
- CSRF protection for cookie-authenticated forms and endpoints (framework token or `SameSite` plus origin checks).
- Rate-limit public and expensive endpoints, including anything that calls a paid API (LLMs, SMS, email) so a bot cannot run up the bill.
- Error responses: generic message to the client, details only in server logs. No stack traces in production.

## 7. Data protection

- Collect the minimum personal data needed. Mark which fields are personal or sensitive.
- Encrypt sensitive fields at rest when the database or provider does not already; never store full card numbers (use the payment provider's tokens).
- Backups exist and restore has been tried once.
- Deleting an account actually deletes or anonymizes the user's data.

## 8. Dependencies and supply chain

- Prefer well-maintained, widely used packages. Before adding one, check it exists under that exact name (typosquats and AI-hallucinated package names are a real attack), has recent releases, and is not abandoned.
- Commit the lockfile. Pin versions in CI.
- Run the ecosystem's audit (`npm audit`, `pnpm audit`, `pip-audit`, `cargo audit`, `bundle audit`, `govulncheck`) when adding dependencies and before releases; fix high/critical findings.
- Suggest enabling Dependabot or Renovate plus GitHub secret scanning and push protection on the repo.

## 9. Deployment and config

- Production runs with debug off, default credentials removed, admin panels not on guessable public URLs (or behind auth plus IP/SSO).
- Databases, caches and queues are not exposed to the public internet.
- Least privilege for cloud credentials, service accounts and database users. Separate keys per environment.
- CI secrets are scoped and never echoed in logs.

## 10. AI features (if the app calls an LLM)

- Treat model output as untrusted input: escape it before rendering, never execute it, validate before using it in queries or tool calls.
- Assume users will try prompt injection; don't put secrets in system prompts, and don't give the model tools that can do more than the current user is allowed to do.
- Rate-limit and cap spend per user.

## Workflow

1. While writing code, apply the rules above without being asked.
2. When finishing a feature that touches auth, data access, uploads or payments, add at least one test proving the unhappy path (another user's ID is rejected, oversized file refused, unauthenticated request gets 401/403).
3. Before merging, run `/security-review` on the diff and the dependency audit.
4. At the end of a change, list in 1-3 lines any security trade-off made or anything the user must do themselves (rotate a key, enable RLS, set an env var in production).
